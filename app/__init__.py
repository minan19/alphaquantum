from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
import logging
from pathlib import Path
import time
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api import router
from app.routers.admin import router as admin_router
from app.routers.auth import router as auth_router
from app.routers.collections import router as collections_router
from app.routers.connectors import router as connectors_router
from app.routers.crm import router as crm_router
from app.routers.dashboard import router as dashboard_router
from app.routers.finance import router as finance_router
from app.routers.financial_instruments import router as financial_instruments_router
from app.routers.holdings import router as holdings_router
from app.routers.intercompany import router as intercompany_router
from app.routers.kvkk import router as kvkk_router
from app.routers.market import router as market_router
from app.routers.realtime import router as realtime_router
from app.routers.dashboard_layout import router as dashboard_layout_router
from app.routers.anomalies import router as anomalies_router
from app.routers.cashflow_forecast import router as cashflow_forecast_router
from app.routers.connectors_import import router as connectors_import_router
from app.routers.staging_promotion import router as staging_promotion_router
from app.routers.community import router as community_router
from app.routers.sample_data import router as sample_data_router
from app.routers.audit_admin import router as audit_admin_router
from app.routers.ocr import router as ocr_router
from app.routers.efatura import router as efatura_router
from app.routers.treasury import router as treasury_router
from app.routers.notifications import router as notifications_router
from app.routers.onboarding import router as onboarding_router
from app.routers.procurement import router as procurement_router
from app.routers.reports import router as reports_router
from app.routers.system import router as system_router
from app.routers.schedule import router as schedule_router
from app.routers.tasks import router as tasks_router
from app.audit_repository import AuditRepository
from app.auth_limiter import build_auth_attempt_limiter
from app.balance_service import BalanceService
from app.auth_service import AuthService
from app.connector_adapters import ConnectorAdapterRegistry
from app.connector_repository import ConnectorRepository
from app.connector_sync_worker import ConnectorSyncWorker
from app.config import get_settings
from app.crm_repository import CRMRepository
from app.task_repository import TaskRepository
from app.invoice_repository import InvoiceRepository
from app.financial_instrument_repository import FinancialInstrumentRepository
from app.notification_repository import NotificationRepository
from app.delivery_log_repository import DeliveryLogRepository
from app.kvkk_repository import KVKKRepository
from app.engines import (
    CollectionsEngine,
    CompanyEngine,
    ComparisonEngine,
    ConnectorEngine,
    ConsolidationEngine,
    CRMEngine,
    ExecSummaryEngine,
    OnboardingEngine,
    DashboardEngine,
    DeliveryEngine,
    TaskEngine,
    FeasibilityEngine,
    FinanceEngine,
    FinancialInstrumentEngine,
    GlobalAnalysisEngine,
    GroupFXEngine,
    HoldingEngine,
    IntercompanyTransferEngine,
    InternationalOperationsEngine,
    InventoryEngine,
    InstitutionWebEngine,
    KVKKEngine,
    MarketDataEngine,
    MarketIntelligenceEngine,
    NotificationEngine,
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
from app.intercompany_transfer_repository import IntercompanyTransferRepository
from app.llm_service import create_llm_service
from app.websocket_manager import WebSocketConnectionManager
from app.market_repository import MarketDataRepository
from app.migration_manager import MigrationManager
from app.observability import (
    StructuredFormatter,
    get_performance_counter,
    is_json_logging_enabled,
)
from app.procurement_repository import ProcurementRepository
from app.repository import CompanyRepository, default_companies
from app.security import validate_security_settings
from app.services import AnalysisService, DashboardService


def _configure_logging(log_level: str) -> None:
    level = getattr(logging, log_level.upper(), logging.INFO)
    # G+5: Production'da AQ_LOG_JSON=1 → JSON structured output (Loki/Datadog
    # uyumlu). Dev'de fallback text format (insan-okunabilir).
    if is_json_logging_enabled():
        handler = logging.StreamHandler()
        handler.setFormatter(StructuredFormatter())
        logging.basicConfig(level=level, handlers=[handler], force=True)
        return
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
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
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
    # G1.5: Ledger-derived authoritative balance (Critical Finding #2 fix)
    app.state.balance_service = BalanceService(
        company_repo=app.state.company_repository,
        finance_repo=app.state.finance_repository,
    )
    app.state.holding_repository = HoldingRepository(settings.database_path)
    app.state.holding_engine = HoldingEngine(
        app.state.holding_repository,
        app.state.company_repository,
    )
    # G1.2: Konsolide P&L motor (intercompany eliminasyonlu)
    app.state.consolidation_engine = ConsolidationEngine(
        finance_repo=app.state.finance_repository,
        holding_repo=app.state.holding_repository,
    )
    # G1.3: Intercompany transfer + 4-eyes onay
    app.state.intercompany_transfer_repository = IntercompanyTransferRepository(
        settings.database_path
    )
    app.state.intercompany_transfer_engine = IntercompanyTransferEngine(
        transfer_repo=app.state.intercompany_transfer_repository,
        holding_repo=app.state.holding_repository,
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
    app.state.crm_repository = CRMRepository(settings.database_path)
    app.state.task_repository = TaskRepository(settings.database_path)
    app.state.invoice_repository = InvoiceRepository(settings.database_path)
    # G1.4: Holding-wide multi-currency net pozisyon + sensitivity analysis
    # Bağımlılıklar: invoice (AR), intercompany_transfer (cross-currency flow), holding
    app.state.group_fx_engine = GroupFXEngine(
        holding_repo=app.state.holding_repository,
        invoice_repo=app.state.invoice_repository,
        transfer_repo=app.state.intercompany_transfer_repository,
    )
    # G+1: AI Layer — Claude LLM exec summary (Sahne 5)
    # Factory: AQ_LLM_OFFLINE=true → offline, AQ_ANTHROPIC_API_KEY → Claude
    app.state.llm_service = create_llm_service()
    app.state.exec_summary_engine = ExecSummaryEngine(
        consolidation_engine=app.state.consolidation_engine,
        group_fx_engine=app.state.group_fx_engine,
        intercompany_engine=app.state.intercompany_transfer_engine,
        llm_service=app.state.llm_service,
    )
    # G+2: WebSocket Connection Manager (holding-scoped real-time broadcast)
    app.state.ws_connection_manager = WebSocketConnectionManager()
    # BZ1: Onboarding wizard — self-service 10dk aktivasyon
    app.state.onboarding_engine = OnboardingEngine(
        company_repo=app.state.company_repository,
        invoice_repo=app.state.invoice_repository,
    )
    # F4: Dashboard widget customization
    from app.dashboard_layout_repository import DashboardLayoutRepository
    from app.engines.dashboard_layout_engine import DashboardLayoutEngine
    app.state.dashboard_layout_repository = DashboardLayoutRepository(
        settings.database_path
    )
    app.state.dashboard_layout_engine = DashboardLayoutEngine(
        repo=app.state.dashboard_layout_repository,
    )
    # A2: Cross-company anomaly detection + A2.1 adaptive calibration
    from app.anomaly_signals_repository import AnomalySignalsRepository
    from app.engines.adaptive_calibration_engine import AdaptiveCalibrationEngine
    from app.engines.anomaly_detection_engine import AnomalyDetectionEngine
    app.state.anomaly_signals_repository = AnomalySignalsRepository(
        settings.database_path
    )
    app.state.anomaly_calibration_engine = AdaptiveCalibrationEngine(
        settings.database_path
    )
    app.state.anomaly_detection_engine = AnomalyDetectionEngine(
        repo=app.state.anomaly_signals_repository,
        ledger_db_path=settings.database_path,
        calibration=app.state.anomaly_calibration_engine,
    )
    # A3: Adaptive cashflow forecasting (Holt-Winters)
    from app.cashflow_forecast_repository import CashflowForecastRepository
    from app.engines.cashflow_forecast_engine import CashflowForecastEngine
    app.state.cashflow_forecast_repository = CashflowForecastRepository(
        settings.database_path
    )
    app.state.cashflow_forecast_engine = CashflowForecastEngine(
        repo=app.state.cashflow_forecast_repository,
        ledger_db_path=settings.database_path,
    )
    # I1: Logo Tiger ERP connector import framework
    from app.connector_import_repository import ConnectorImportRepository
    from app.engines.connector_import_engine import ConnectorImportEngine
    app.state.connector_import_repository = ConnectorImportRepository(
        settings.database_path
    )
    app.state.connector_import_engine = ConnectorImportEngine(
        repo=app.state.connector_import_repository,
        ledger_db_path=settings.database_path,
    )
    # I2: Staging → CRM/Invoice/Ledger promotion
    from app.engines.staging_promotion_engine import StagingPromotionEngine
    app.state.staging_promotion_engine = StagingPromotionEngine(
        database_path=settings.database_path,
    )
    # BZ3: Public changelog + roadmap voting
    from app.engines.community_engine import CommunityEngine
    app.state.community_engine = CommunityEngine(
        database_path=settings.database_path,
    )
    # OBS1: Sample data seeder
    from app.engines.sample_data_engine import SampleDataEngine
    app.state.sample_data_engine = SampleDataEngine(
        database_path=settings.database_path,
    )
    # A4: AI Invoice OCR (Claude Vision)
    from app.engines.ocr_engine import OcrEngine
    from app.ocr_service import create_ocr_service
    app.state.ocr_service = create_ocr_service()
    app.state.ocr_engine = OcrEngine(
        database_path=settings.database_path,
        ocr_service=app.state.ocr_service,
    )
    # T1: Multi-bank Treasury
    from app.engines.treasury_engine import TreasuryEngine
    app.state.treasury_engine = TreasuryEngine(
        database_path=settings.database_path,
        # Default FX (production'da group_fx_engine'den canlı çekilebilir)
        fx_rates={"TRY": 1.0, "USD": 32.0, "EUR": 35.0, "GBP": 40.0},
    )
    app.state.notification_repository = NotificationRepository(settings.database_path)
    app.state.financial_instrument_repository = FinancialInstrumentRepository(
        settings.database_path
    )
    app.state.delivery_log_repository = DeliveryLogRepository(settings.database_path)
    app.state.kvkk_repository = KVKKRepository(settings.database_path)
    app.state.crm_engine = CRMEngine(app.state.crm_repository)
    app.state.task_engine = TaskEngine(app.state.task_repository)
    app.state.collections_engine = CollectionsEngine(app.state.invoice_repository)
    app.state.notification_engine = NotificationEngine(
        notif_repo=app.state.notification_repository,
        invoice_repo=app.state.invoice_repository,
    )
    app.state.financial_instrument_engine = FinancialInstrumentEngine(
        app.state.financial_instrument_repository
    )
    app.state.delivery_engine = DeliveryEngine(
        delivery_log_repo=app.state.delivery_log_repository,
        notification_repo=app.state.notification_repository,
        crm_repo=app.state.crm_repository,
        invoice_repo=app.state.invoice_repository,
    )
    app.state.kvkk_engine = KVKKEngine(
        kvkk_repo=app.state.kvkk_repository,
        identity_repo=app.state.identity_repository,
    )
    app.state.scheduled_report_repository = ScheduledReportRepository(settings.database_path)
    app.state.schedule_engine = ScheduleEngine(app.state.scheduled_report_repository)
    app.state.auth_service = AuthService(app.state.identity_repository, settings)
    app.state.audit_repository = AuditRepository(settings.database_path)

    @app.middleware("http")
    async def request_logging_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
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
        # G+5: Performance counter — in-memory metrics. /system/metrics ile export.
        get_performance_counter().record(
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        # Structured log (extra fields → StructuredFormatter JSON'a yansır)
        logger.info(
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
            },
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
    app.include_router(admin_router)
    app.include_router(auth_router)
    app.include_router(collections_router)
    app.include_router(connectors_router)
    app.include_router(crm_router)
    app.include_router(dashboard_router)
    app.include_router(finance_router)
    app.include_router(financial_instruments_router)
    app.include_router(holdings_router)
    app.include_router(intercompany_router)
    app.include_router(kvkk_router)
    app.include_router(market_router)
    app.include_router(dashboard_layout_router)
    app.include_router(anomalies_router)
    app.include_router(cashflow_forecast_router)
    app.include_router(connectors_import_router)
    app.include_router(staging_promotion_router)
    app.include_router(community_router)
    app.include_router(sample_data_router)
    app.include_router(audit_admin_router)
    app.include_router(ocr_router)
    app.include_router(efatura_router)
    app.include_router(treasury_router)
    app.include_router(notifications_router)
    app.include_router(realtime_router)
    app.include_router(onboarding_router)
    app.include_router(procurement_router)
    app.include_router(reports_router)
    app.include_router(schedule_router)
    app.include_router(system_router)
    app.include_router(tasks_router)

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
        "crm_repository",
        "task_repository",
        "invoice_repository",
        "notification_repository",
        "financial_instrument_repository",
        "delivery_log_repository",
        "kvkk_repository",
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
