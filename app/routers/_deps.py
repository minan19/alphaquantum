"""Shared dependencies for Alpha Quantum router modules.

This module centralizes:
- Engine accessors (e.g. `_crm_engine(request)` → app.state.crm_engine)
- Repository accessors (e.g. `_repo(request)` → company repository)
- Auth/scope checks (`_is_holding_scope`, `_ensure_company_scope`)
- Audit log emission (`_emit_audit_event`)

All accessors take a `Request` and return the appropriate singleton from
`request.app.state`, which `app.create_app()` populates.

Importing pattern in router files:
    from app.routers._deps import (
        _ensure_company_scope, _is_holding_scope, _crm_engine, ...
    )

Naming convention: leading underscore is preserved from the original
`app/api.py` location so existing import sites stay compatible during the
incremental migration.
"""
from __future__ import annotations

from typing import Any, cast

from fastapi import HTTPException, Request, status
from fastapi.responses import Response

from app.audit_repository import AuditRepository
from app.config import Settings
from app.auth_service import AuthService
from app.engines import (
    CollectionsEngine,
    CompanyEngine,
    ComparisonEngine,
    ConsolidationEngine,
    ConnectorEngine,
    IntercompanyTransferEngine,
    CRMEngine,
    DashboardEngine,
    DeliveryEngine,
    FeasibilityEngine,
    FinanceEngine,
    FinancialInstrumentEngine,
    GlobalAnalysisEngine,
    HoldingEngine,
    InstitutionWebEngine,
    InternationalOperationsEngine,
    InventoryEngine,
    MarketDataEngine,
    MarketIntelligenceEngine,
    NotificationEngine,
    ProcurementEngine,
    ReportingEngine,
    ScheduleEngine,
    StrategicEcosystemEngine,
    TaskEngine,
    TenderEngine,
)
from app.migration_manager import MigrationManager
from app.models import Company, UserProfile
from app.repository import CompanyRepository
from app.services import AnalysisService, DashboardService


# ── Common HTTP helpers ──────────────────────────────────────────────────────


def _value_error_to_http(exc: ValueError) -> HTTPException:
    """Translate engine-layer ValueError into FastAPI HTTPException.

    Convention: "not found" → 404, everything else → 400. Engines should raise
    ValueError with descriptive text; this helper preserves the message in
    `detail` so the API client can surface it.
    """
    text = str(exc)
    if "not found" in text.lower():
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=text)
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=text)


def _build_export_response(
    content: bytes,
    media_type: str,
    filename: str,
    secret: str,
    reporting: ReportingEngine,
) -> Response:
    """Build signed export Response (PDF / XLSX / CSV).

    Adds `X-Export-Signature` header (HMAC-SHA256 over content) so clients
    can verify the artifact wasn't tampered with after download. Used by
    invoice PDF, ledger XLSX, and other report exports.
    """
    signature = reporting.sign(content, secret)
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Export-Signature": signature,
        },
    )


# ── Repository / Service accessors ───────────────────────────────────────────

def _repo(request: Request) -> CompanyRepository:
    return cast(CompanyRepository, request.app.state.company_repository)


def _analysis_service(request: Request) -> AnalysisService:
    return cast(AnalysisService, request.app.state.analysis_service)


def _dashboard_service(request: Request) -> DashboardService:
    return cast(DashboardService, request.app.state.dashboard_service)


def _auth_service(request: Request) -> AuthService:
    return cast(AuthService, request.app.state.auth_service)


def _audit_repo(request: Request) -> AuditRepository:
    return cast(AuditRepository, request.app.state.audit_repository)


def _settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def _migration_manager(request: Request) -> MigrationManager:
    return cast(MigrationManager, request.app.state.migration_manager)


# ── Engine accessors ─────────────────────────────────────────────────────────

def _company_engine(request: Request) -> CompanyEngine:
    return cast(CompanyEngine, request.app.state.company_engine)


def _connector_engine(request: Request) -> ConnectorEngine:
    return cast(ConnectorEngine, request.app.state.connector_engine)


def _inventory_engine(request: Request) -> InventoryEngine:
    return cast(InventoryEngine, request.app.state.inventory_engine)


def _finance_engine(request: Request) -> FinanceEngine:
    return cast(FinanceEngine, request.app.state.finance_engine)


def _reporting_engine(request: Request) -> ReportingEngine:
    return cast(ReportingEngine, request.app.state.reporting_engine)


def _dashboard_engine(request: Request) -> DashboardEngine:
    return cast(DashboardEngine, request.app.state.dashboard_engine)


def _comparison_engine(request: Request) -> ComparisonEngine:
    return cast(ComparisonEngine, request.app.state.comparison_engine)


def _consolidation_engine(request: Request) -> ConsolidationEngine:
    return cast(ConsolidationEngine, request.app.state.consolidation_engine)


def _intercompany_transfer_engine(request: Request) -> IntercompanyTransferEngine:
    return cast(
        IntercompanyTransferEngine,
        request.app.state.intercompany_transfer_engine,
    )


def _crm_engine(request: Request) -> CRMEngine:
    return cast(CRMEngine, request.app.state.crm_engine)


def _task_engine(request: Request) -> TaskEngine:
    return cast(TaskEngine, request.app.state.task_engine)


def _collections_engine(request: Request) -> CollectionsEngine:
    return cast(CollectionsEngine, request.app.state.collections_engine)


def _notification_engine(request: Request) -> NotificationEngine:
    return cast(NotificationEngine, request.app.state.notification_engine)


def _financial_instrument_engine(request: Request) -> FinancialInstrumentEngine:
    return cast(FinancialInstrumentEngine, request.app.state.financial_instrument_engine)


def _delivery_engine(request: Request) -> DeliveryEngine:
    return cast(DeliveryEngine, request.app.state.delivery_engine)


def _market_engine(request: Request) -> MarketDataEngine:
    return cast(MarketDataEngine, request.app.state.market_data_engine)


def _market_intelligence_engine(request: Request) -> MarketIntelligenceEngine:
    return cast(MarketIntelligenceEngine, request.app.state.market_intelligence_engine)


def _global_engine(request: Request) -> GlobalAnalysisEngine:
    return cast(GlobalAnalysisEngine, request.app.state.global_analysis_engine)


def _institution_engine(request: Request) -> InstitutionWebEngine:
    return cast(InstitutionWebEngine, request.app.state.institution_web_engine)


def _tender_engine(request: Request) -> TenderEngine:
    return cast(TenderEngine, request.app.state.tender_engine)


def _procurement_engine(request: Request) -> ProcurementEngine:
    return cast(ProcurementEngine, request.app.state.procurement_engine)


def _feasibility_engine(request: Request) -> FeasibilityEngine:
    return cast(FeasibilityEngine, request.app.state.feasibility_engine)


def _international_engine(request: Request) -> InternationalOperationsEngine:
    return cast(InternationalOperationsEngine, request.app.state.international_operations_engine)


def _ecosystem_engine(request: Request) -> StrategicEcosystemEngine:
    return cast(StrategicEcosystemEngine, request.app.state.strategic_ecosystem_engine)


def _holding_engine(request: Request) -> HoldingEngine:
    return cast(HoldingEngine, request.app.state.holding_engine)


def _schedule_engine(request: Request) -> ScheduleEngine:
    return cast(ScheduleEngine, request.app.state.schedule_engine)


# ── Audit ────────────────────────────────────────────────────────────────────

def _emit_audit_event(
    request: Request,
    user: UserProfile,
    event_type: str,
    event_detail: dict[str, Any] | None = None,
) -> None:
    """Write an audit log entry for a security-relevant action."""
    request_id = getattr(request.state, "request_id", "")
    _audit_repo(request).write_event(
        username=user.username,
        role=user.role,
        event_type=event_type,
        event_detail=event_detail,
        request_id=str(request_id),
        ip_address=request.client.host if request.client else None,
    )


# ── Scope helpers ────────────────────────────────────────────────────────────

def _scope_mode_from_scopes(scopes: list[str]) -> str:
    """Classify a user's scope list into 'holding', 'single', or 'multi'."""
    if "*" in scopes:
        return "holding"
    if len(scopes) <= 1:
        return "single"
    return "multi"


def _is_holding_scope(request: Request, user: UserProfile) -> bool:
    """True if user can see all companies (e.g. `*` scope)."""
    return _auth_service(request).is_holding_scope(user.id)


def _user_has_company_scope(
    request: Request, user: UserProfile, company_name: str
) -> bool:
    """True if user is permitted to act on `company_name`."""
    return _auth_service(request).user_has_company_scope(user.id, company_name)


def _ensure_company_scope(
    request: Request, user: UserProfile, company_name: str
) -> None:
    """Raise 403 if user is not authorized for the given company."""
    if _user_has_company_scope(request, user, company_name):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"User scope does not allow company: {company_name}",
    )


def _filter_companies_by_user_scope(
    request: Request,
    user: UserProfile,
    companies: list[Company],
) -> list[Company]:
    """Holding-scope users see all; others see only their scoped companies."""
    if _is_holding_scope(request, user):
        return companies
    return [
        company
        for company in companies
        if _user_has_company_scope(request, user, company.name)
    ]
