from __future__ import annotations

from contextlib import asynccontextmanager
import logging
from pathlib import Path
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import router
from app.audit_repository import AuditRepository
from app.auth_limiter import build_auth_attempt_limiter
from app.auth_service import AuthService
from app.connector_adapters import ConnectorAdapterRegistry
from app.connector_repository import ConnectorRepository
from app.connector_sync_worker import ConnectorSyncWorker
from app.config import get_settings
from app.engines import (
    CompanyEngine,
    ComparisonEngine,
    ConnectorEngine,
    DashboardEngine,
    FeasibilityEngine,
    FinanceEngine,
    GlobalAnalysisEngine,
    HoldingEngine,
    InternationalOperationsEngine,
    InventoryEngine,
    InstitutionWebEngine,
    MarketDataEngine,
    MarketIntelligenceEngine,
    ProcurementEngine,
    ReportingEngine,
    ScheduleEngine,
    StrategicEcosystemEngine,
    TenderEngine,
)
from app.feasibility_repository import FeasibilityRepository
from app.finance_repository import FinanceRepository
from app.scheduled_report_repository import ScheduledReportRepository
from app.identity_repository import IdentityRepository
from app.international_repository import InternationalProjectRepository
from app.holding_repository import HoldingRepository
from app.market_repository import MarketDataRepository
from app.migration_manager import MigrationManager
from app.procurement_repository import ProcurementRepository
from app.repository import CompanyRepository, default_companies
from app.security import validate_security_settings
from app.services import AnalysisService, DashboardService


def _configure_logging(log_level: str) -> None:
    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def create_app() -> FastAPI:
    settings = get_settings()
    validate_security_settings(settings)
    _configure_logging(settings.log_level)
    logger = logging.getLogger("alpha_quantum")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        _start_background_workers(app)
        try:
            yield
        finally:
            _stop_background_workers(app)
            _close_app_resources(app)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Enterprise management API for Alpha Quantum",
        lifespan=lifespan,
    )

    cors_origins = ["*"] if settings.allow_all_cors else settings.cors_origins
    if cors_origins:
        allow_credentials = settings.cors_allow_credentials and not settings.allow_all_cors
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=allow_credentials,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.state.settings = settings
    app.state.company_repository = CompanyRepository(
        settings.database_path,
        default_companies(),
    )
    app.state.analysis_service = AnalysisService()
    app.state.dashboard_service = DashboardService()
    app.state.auth_limiter = build_auth_attempt_limiter(
        window_seconds=settings.auth_rate_limit_window_seconds,
        max_attempts=settings.auth_rate_limit_max_attempts,
        backend_mode=settings.auth_rate_limit_backend,
        redis_url=settings.auth_rate_limit_redis_url,
        fail_open=settings.auth_rate_limit_fail_open,
    )
    app.state.identity_repository = IdentityRepository(settings.database_path)
    migrations_dir = Path(__file__).resolve().parent.parent / "migrations"
    app.state.migration_manager = MigrationManager(
        settings.database_path,
        str(migrations_dir),
    )
    app.state.migration_manager.apply_all()
    app.state.finance_repository = FinanceRepository(settings.database_path)
    app.state.company_engine = CompanyEngine()
    app.state.inventory_engine = InventoryEngine()
    app.state.finance_engine = FinanceEngine(app.state.finance_repository)
    app.state.holding_repository = HoldingRepository(settings.database_path)
    app.state.holding_engine = HoldingEngine(
        app.state.holding_repository,
        app.state.company_repository,
    )
    app.state.connector_repository = ConnectorRepository(settings.database_path)
    app.state.connector_engine = ConnectorEngine(app.state.connector_repository)
    app.state.connector_adapter_registry = ConnectorAdapterRegistry()
    app.state.connector_sync_worker = ConnectorSyncWorker(
        engine=app.state.connector_engine,
        adapters=app.state.connector_adapter_registry,
        poll_interval_seconds=settings.connector_worker_poll_interval_seconds,
        retry_backoff_seconds=settings.connector_worker_retry_backoff_seconds,
        max_retries=settings.connector_worker_max_retries,
        leader_lock_enabled=settings.connector_worker_leader_lock_enabled,
        lease_seconds=settings.connector_worker_lease_seconds,
        heartbeat_seconds=settings.connector_worker_heartbeat_seconds,
    )
    app.state.market_repository = MarketDataRepository(settings.database_path)
    app.state.market_data_engine = MarketDataEngine(app.state.market_repository)
    app.state.global_analysis_engine = GlobalAnalysisEngine(app.state.market_data_engine)
    app.state.institution_web_engine = InstitutionWebEngine()
    app.state.market_intelligence_engine = MarketIntelligenceEngine(
        app.state.market_data_engine,
        app.state.institution_web_engine,
    )
    app.state.tender_engine = TenderEngine()
    app.state.procurement_repository = ProcurementRepository(settings.database_path)
    app.state.procurement_engine = ProcurementEngine(
        app.state.procurement_repository,
        app.state.tender_engine,
    )
    app.state.feasibility_repository = FeasibilityRepository(settings.database_path)
    app.state.feasibility_engine = FeasibilityEngine(
        app.state.feasibility_repository,
        app.state.market_data_engine,
    )
    app.state.international_repository = InternationalProjectRepository(settings.database_path)
    app.state.international_operations_engine = InternationalOperationsEngine(
        app.state.international_repository
    )
    app.state.strategic_ecosystem_engine = StrategicEcosystemEngine(
        app.state.feasibility_engine,
        app.state.international_operations_engine,
        app.state.procurement_engine,
    )
    app.state.reporting_engine = ReportingEngine()
    app.state.dashboard_engine = DashboardEngine()
    app.state.comparison_engine = ComparisonEngine()
    app.state.scheduled_report_repository = ScheduledReportRepository(settings.database_path)
    app.state.schedule_engine = ScheduleEngine(app.state.scheduled_report_repository)
    app.state.auth_service = AuthService(app.state.identity_repository, settings)
    app.state.audit_repository = AuditRepository(settings.database_path)

    @app.middleware("http")
    async def request_logging_middleware(request: Request, call_next):
        request_id = uuid4().hex[:10]
        start = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            _write_audit_log(
                app=app,
                request=request,
                request_id=request_id,
                status_code=500,
                duration_ms=duration_ms,
            )
            logger.exception(
                "request_id=%s method=%s path=%s unhandled_error",
                request_id,
                request.method,
                request.url.path,
            )
            raise

        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cache-Control"] = "no-store"
        logger.info(
            "request_id=%s method=%s path=%s status=%s duration_ms=%.2f",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        _write_audit_log(
            app=app,
            request=request,
            request_id=request_id,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        return response

    app.include_router(router)

    return app


def _start_background_workers(app: FastAPI) -> None:
    settings = app.state.settings
    if not settings.connector_worker_enabled:
        return
    worker = getattr(app.state, "connector_sync_worker", None)
    if worker is None:
        return
    worker.start()


def _stop_background_workers(app: FastAPI) -> None:
    worker = getattr(app.state, "connector_sync_worker", None)
    if worker is None:
        return
    worker.stop()


def _close_app_resources(app: FastAPI) -> None:
    logger = logging.getLogger("alpha_quantum")
    close_order = (
        "company_repository",
        "holding_repository",
        "connector_repository",
        "finance_repository",
        "market_repository",
        "procurement_repository",
        "feasibility_repository",
        "international_repository",
        "scheduled_report_repository",
        "identity_repository",
        "audit_repository",
        "auth_limiter",
        "migration_manager",
    )

    for state_key in close_order:
        resource = getattr(app.state, state_key, None)
        if resource is None:
            continue
        try:
            resource.close()
        except Exception:
            logger.exception("resource_close_failed resource=%s", state_key)


def _write_audit_log(
    *,
    app: FastAPI,
    request: Request,
    request_id: str,
    status_code: int,
    duration_ms: float,
) -> None:
    auth_user = getattr(request.state, "auth_user", None)
    username = getattr(auth_user, "username", None)
    role = getattr(auth_user, "role", None)
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    try:
        app.state.audit_repository.write_log(
            request_id=request_id,
            username=username,
            role=role,
            method=request.method,
            path=request.url.path,
            status_code=status_code,
            ip_address=ip_address,
            user_agent=user_agent,
            duration_ms=duration_ms,
        )
    except Exception:
        logging.getLogger("alpha_quantum").exception(
            "request_id=%s method=%s path=%s audit_log_write_failed",
            request_id,
            request.method,
            request.url.path,
        )
