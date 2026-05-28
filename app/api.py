from __future__ import annotations

from datetime import datetime, timezone
from html import escape
import logging
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, Response

# Engine + service + audit accessors `app/routers/_deps.py`'den import ediliyor (A5.1).
# Sadece doğrudan class metodu olarak kullanılan engine burada kalır:
#   - FinanceEngine.build_overview() — sync class method
# (ReportingEngine kullanımı A5.6'da `_build_export_response` üzerinden _deps.py'a taşındı.)
from app.engines import FinanceEngine
from app.models import (
    AnalysisResult,
    AuditLogRead,
    CentralBankPanelResponse,
    Company,
    CompanyEngineResponse,
    MigrationDryRunResponse,
    MigrationPreflightResponse,
    ConnectorCanonicalPreviewRequest,
    ConnectorCanonicalPreviewResponse,
    ConnectorCreateRequest,
    ConnectorListResponse,
    ConnectorQueueHealthResponse,
    ConnectorRead,
    ConnectorSyncDispatchRequest,
    ConnectorSyncDispatchResponse,
    ConnectorSyncJobCreateRequest,
    ConnectorSyncJobListResponse,
    ConnectorSyncJobRead,
    DashboardDataResponse,
    DashboardSummary,
    EcosystemActivationRequest,
    EcosystemActivationResponse,
    EcosystemPortfolioActivationRequest,
    EcosystemPortfolioActivationResponse,
    FeasibilityReportListResponse,
    FeasibilityReportRequest,
    FeasibilityReportStoredResponse,
    HealthResponse,
    HoldingBulkOnboardRequest,
    HoldingBulkOnboardResponse,
    HoldingCreateRequest,
    HoldingDetailResponse,
    HoldingListResponse,
    HoldingOnboardRequest,
    HoldingOnboardResponse,
    HoldingRead,
    InstitutionReportRequest,
    InstitutionReportResponse,
    InsightItem,
    InternationalProjectListResponse,
    InternationalProjectRequest,
    InternationalProjectStoredResponse,
    InventoryEngineResponse,
    LegacyAnalysisResult,
    LegacyUpdateResult,
    MigrationActionResponse,
    MigrationRollbackRequest,
    MigrationStatusItem,
    MarketAnalysisResponse,
    MarketBacktestResponse,
    MarketIntelligenceRequest,
    MarketIntelligenceResponse,
    MarketOHLCVResponse,
    MarketRefreshRequest,
    MarketRefreshResponse,
    MarketSourceCatalogResponse,
    MarketSignalsResponse,
    ProfessionalReportResponse,
    ProcurementAutoOrderRequest,
    ProcurementEvaluationResponse,
    ProcurementPurchaseOrderBatchResponse,
    ProcurementRequestCreateRequest,
    ProcurementRequestListResponse,
    ProcurementRequestRead,
    ProcurementTenderPlanRequest,
    ProcurementTenderPlanResponse,
    ProcurementVendorQuoteCreateRequest,
    ProcurementVendorQuoteListResponse,
    ProcurementVendorQuoteRead,
    TenderDossierResponse,
    TenderGenerationRequest,
    CompanyComparisonResponse,
    DeliveryLogListResponse,
    DispatchResponse,
    FinancialInstrumentCreateRequest,
    FinancialInstrumentListResponse,
    FinancialInstrumentRead,
    FinancialInstrumentStatusUpdateRequest,
    FinancialInstrumentSummaryResponse,
    NotificationGenerateResponse,
    NotificationListResponse,
    NotificationRead,
    NotificationSummaryResponse,
    DashboardLiveSignalsResponse,
    UpdateResult,
    UserProfile,
    WorldBankPanelResponse,
)
# MigrationManager, CompanyRepository, AnalysisService, DashboardService
# `app/routers/_deps.py`'den helper'lar üzerinden erişiliyor (A5.1).
from app.security import require_permissions

router = APIRouter()
logger = logging.getLogger("alpha_quantum.auth")

# A5.1 — Helper accessors `app/routers/_deps.py`'ye taşındı (Mayıs 26, 2026).
# Bu sayede yeni router modülleri (app/routers/<domain>.py) aynı helper'ları
# tek bir yerden import edebilir. Geçiş döneminde api.py burada hâlâ duruyor;
# `app/routers/__init__.py` migration sırasını dokümante ediyor.
from app.routers._deps import (  # noqa: E402  (configured imports after router init)
    _analysis_service,
    _audit_repo,
    _collections_engine,
    _company_engine,
    _comparison_engine,
    _connector_engine,
    _dashboard_engine,
    _dashboard_service,
    _delivery_engine,
    _ecosystem_engine,
    _emit_audit_event,
    _feasibility_engine,
    _finance_engine,
    _financial_instrument_engine,
    _global_engine,
    _holding_engine,
    _institution_engine,
    _international_engine,
    _inventory_engine,
    _market_engine,
    _build_export_response,
    _market_intelligence_engine,
    _migration_manager,
    _notification_engine,
    _procurement_engine,
    _reporting_engine,
    _repo,
    _task_engine,
    _tender_engine,
    _value_error_to_http,
)


# ── S-312: Scheduled Reports ── MOVED to app/routers/schedule.py (A5.2) ────────


# ── S-311: Live Dashboard Signals ─────────────────────────────────────────────

@router.get(
    "/api/v1/dashboard/live-signals",
    response_model=DashboardLiveSignalsResponse,
    tags=["dashboard"],
)
def live_dashboard_signals(
    request: Request,
    company: str | None = Query(default=None),
    lookback_days: int = Query(default=30, ge=1, le=365),
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> DashboardLiveSignalsResponse:
    if company is not None:
        _ensure_company_scope(request, user, company)
    elif not _is_holding_scope(request, user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scoped users must provide company parameter",
        )

    companies = request.app.state.company_repository.list_companies()
    finance_overview = FinanceEngine.build_overview(companies)

    try:
        cashflow = _finance_engine(request).build_cashflow(
            company=company, lookback_days=lookback_days
        )
    except Exception:
        cashflow = None

    low_stock_count = sum(
        1
        for c in companies
        if (company is None or c.name == company)
        for item in c.inventory
        if item.quantity < item.min_level
    )

    try:
        proc_rows = request.app.state.procurement_repository.list_requests(
            status=None, limit=10_000
        )
        procurement_active_count = len(proc_rows)
    except Exception:
        procurement_active_count = 0

    try:
        feasibility_rows = request.app.state.feasibility_repository.list_reports(
            limit=10_000
        )
        feasibility_pending_count = len(feasibility_rows)
    except Exception:
        feasibility_pending_count = 0

    try:
        market_signal_count = len(request.app.state.market_repository.list_symbols())
    except Exception:
        market_signal_count = 0

    # S-335 — operational signals (best-effort; failures degrade to zero)
    try:
        overdue_task_count = _task_engine(request).status_summary(
            company=company
        ).overdue
    except Exception:
        overdue_task_count = 0

    try:
        unread_critical_notification_count = len(
            _notification_engine(request).list_notifications(
                company=company, severity="critical", unread_only=True
            ).notifications
        )
    except Exception:
        unread_critical_notification_count = 0

    return _dashboard_engine(request).build_signals(
        company_scope=company,
        finance_overview=finance_overview,
        cashflow=cashflow,
        low_stock_count=low_stock_count,
        procurement_active_count=procurement_active_count,
        feasibility_pending_count=feasibility_pending_count,
        market_signal_count=market_signal_count,
        overdue_task_count=overdue_task_count,
        unread_critical_notification_count=unread_critical_notification_count,
    )


# ── S-313: Multi-Company Comparison Panel ─────────────────────────────────────

@router.get(
    "/api/v1/analytics/company-comparison",
    response_model=CompanyComparisonResponse,
    tags=["analytics"],
)
def company_comparison(
    request: Request,
    lookback_days: int = Query(default=30, ge=1, le=365),
    year: int | None = Query(default=None, ge=2000, le=2100),
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> CompanyComparisonResponse:
    if not _is_holding_scope(request, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Multi-company comparison requires holding scope",
        )

    companies = request.app.state.company_repository.list_companies()

    cashflows: dict[str, object] = {}
    for company in companies:
        try:
            cashflows[company.name] = _finance_engine(request).build_cashflow(
                company=company.name, lookback_days=lookback_days
            )
        except Exception:
            cashflows[company.name] = None

    budget_reports: dict[str, object] = {}
    if year is not None:
        for company in companies:
            try:
                budget_reports[company.name] = _finance_engine(request).budget_vs_actual(
                    company=company.name, year=year, month=None
                )
            except Exception:
                budget_reports[company.name] = None

    return _comparison_engine(request).build_comparison(
        companies=companies,
        cashflows=cashflows,
        budget_reports=budget_reports,
        year=year,
        lookback_days=lookback_days,
    )


# ── S-321/S-333 CRM endpoints ── MOVED to app/routers/crm.py (A5.4) ───────────


# ── S-322 Task Tracking endpoints ── MOVED to app/routers/tasks.py (A5.5) ─────


# ── S-323/S-331/S-341 Collections endpoints ── MOVED to app/routers/collections.py (A5.6) ──


# ── S-342: Financial Instruments (senet / çek / bono) ────────────────────────

@router.post(
    "/api/v1/financial-instruments",
    response_model=FinancialInstrumentRead,
    status_code=201,
    tags=["financial-instruments"],
)
def create_financial_instrument(
    payload: FinancialInstrumentCreateRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("write_finance")),
) -> FinancialInstrumentRead:
    _ensure_company_scope(request, user, payload.company)
    return _financial_instrument_engine(request).create(payload=payload)


@router.get(
    "/api/v1/financial-instruments",
    response_model=FinancialInstrumentListResponse,
    tags=["financial-instruments"],
)
def list_financial_instruments(
    request: Request,
    company: str | None = Query(default=None),
    kind: str | None = Query(default=None, pattern="^(senet|cek|bono)$"),
    instr_status: str | None = Query(default=None, alias="status",
                                      pattern="^(pending|cleared|bounced|cancelled)$"),
    customer_id: int | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> FinancialInstrumentListResponse:
    if company:
        _ensure_company_scope(request, user, company)
    elif not _is_holding_scope(request, user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scoped users must provide company parameter",
        )
    return _financial_instrument_engine(request).list_instruments(
        company=company, kind=kind, status=instr_status,
        customer_id=customer_id, limit=limit,
    )


@router.get(
    "/api/v1/financial-instruments/summary",
    response_model=FinancialInstrumentSummaryResponse,
    tags=["financial-instruments"],
)
def financial_instruments_summary(
    request: Request,
    company: str | None = Query(default=None),
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> FinancialInstrumentSummaryResponse:
    if company:
        _ensure_company_scope(request, user, company)
    elif not _is_holding_scope(request, user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scoped users must provide company parameter",
        )
    return _financial_instrument_engine(request).summary(company=company)


@router.get(
    "/api/v1/financial-instruments/{instrument_id}",
    response_model=FinancialInstrumentRead,
    tags=["financial-instruments"],
)
def get_financial_instrument(
    instrument_id: int,
    request: Request,
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> FinancialInstrumentRead:
    result = _financial_instrument_engine(request).get(instrument_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Instrument not found")
    _ensure_company_scope(request, user, result.company)
    return result


@router.patch(
    "/api/v1/financial-instruments/{instrument_id}",
    response_model=FinancialInstrumentRead,
    tags=["financial-instruments"],
)
def update_financial_instrument_status(
    instrument_id: int,
    payload: FinancialInstrumentStatusUpdateRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("write_finance")),
) -> FinancialInstrumentRead:
    existing = _financial_instrument_engine(request).get(instrument_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Instrument not found")
    _ensure_company_scope(request, user, existing.company)
    try:
        result = _financial_instrument_engine(request).update_status(
            instrument_id, payload=payload
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail="Instrument not found")
    return result


# ── S-334: Notifications (vade uyarı / bildirim motoru) ───────────────────────

@router.post(
    "/api/v1/notifications/generate",
    response_model=NotificationGenerateResponse,
    tags=["notifications"],
)
def generate_notifications(
    request: Request,
    company: str | None = Query(default=None),
    user: UserProfile = Depends(require_permissions("write_finance")),
) -> NotificationGenerateResponse:
    """Scan unpaid invoices and create any missing window notifications.

    Idempotent — duplicates are dropped by a UNIQUE constraint at the DB layer.
    """
    if company:
        _ensure_company_scope(request, user, company)
    elif not _is_holding_scope(request, user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scoped users must provide company parameter",
        )
    return _notification_engine(request).scan_invoices(company=company)


@router.get(
    "/api/v1/notifications",
    response_model=NotificationListResponse,
    tags=["notifications"],
)
def list_notifications(
    request: Request,
    company: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    unread_only: bool = Query(default=False),
    kind: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> NotificationListResponse:
    if company:
        _ensure_company_scope(request, user, company)
    elif not _is_holding_scope(request, user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scoped users must provide company parameter",
        )
    return _notification_engine(request).list_notifications(
        company=company, severity=severity, unread_only=unread_only,
        kind=kind, limit=limit,
    )


@router.get(
    "/api/v1/notifications/summary",
    response_model=NotificationSummaryResponse,
    tags=["notifications"],
)
def notification_summary(
    request: Request,
    company: str | None = Query(default=None),
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> NotificationSummaryResponse:
    if company:
        _ensure_company_scope(request, user, company)
    elif not _is_holding_scope(request, user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scoped users must provide company parameter",
        )
    return _notification_engine(request).summary(company=company)


@router.patch(
    "/api/v1/notifications/{notification_id}/read",
    response_model=NotificationRead,
    tags=["notifications"],
)
def mark_notification_read(
    notification_id: int,
    request: Request,
    user: UserProfile = Depends(require_permissions("write_finance")),
) -> NotificationRead:
    existing = _notification_engine(request).get(notification_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    _ensure_company_scope(request, user, existing.company)
    result = _notification_engine(request).mark_read(notification_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    return result


# ── S-343: Tahsilat Kanalı (Dispatch + Delivery Log) ──────────────────────────

@router.post(
    "/api/v1/notifications/{notification_id}/dispatch",
    response_model=DispatchResponse,
    tags=["notifications"],
)
def dispatch_notification(
    notification_id: int,
    request: Request,
    channels: str | None = Query(default=None,
        description="Comma-separated channel list. Defaults to env config."),
    user: UserProfile = Depends(require_permissions("write_finance")),
) -> DispatchResponse:
    """S-343 — Send a notification across configured channels.

    Honors per-customer KVKK consent flags. Channels without consent are
    skipped (status='skipped_no_consent' in delivery_log). Missing contact
    info → status='skipped_no_contact'.
    """
    existing = _notification_engine(request).get(notification_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    _ensure_company_scope(request, user, existing.company)
    channel_list = (
        [c.strip() for c in channels.split(",") if c.strip()]
        if channels else None
    )
    result = _delivery_engine(request).dispatch(
        notification_id=notification_id, channels=channel_list
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    return result


@router.get(
    "/api/v1/delivery-log",
    response_model=DeliveryLogListResponse,
    tags=["notifications"],
)
def list_delivery_log(
    request: Request,
    company: str | None = Query(default=None),
    notification_id: int | None = Query(default=None),
    channel: str | None = Query(default=None),
    delivery_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=200, ge=1, le=1000),
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> DeliveryLogListResponse:
    if company:
        _ensure_company_scope(request, user, company)
    elif not _is_holding_scope(request, user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scoped users must provide company parameter",
        )
    return _delivery_engine(request).list_log(
        company=company,
        notification_id=notification_id,
        channel=channel,
        status=delivery_status,
        limit=limit,
    )


# ── S-343 KVKK consent endpoint ── MOVED to app/routers/crm.py (A5.4) ─────────


# ── S-332 Cashflow projection ── MOVED to app/routers/finance.py (A5.7) ───────


# ── Auth core + roles/permissions endpoints ── MOVED to app/routers/auth.py (A5.3) ──


@router.get(
    "/api/v1/admin/migrations/status",
    response_model=list[MigrationStatusItem],
    tags=["admin"],
)
def migration_status(
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_migrations")),
) -> list[MigrationStatusItem]:
    del user
    rows = _migration_manager(request).status()
    return [MigrationStatusItem(**row) for row in rows]


@router.post(
    "/api/v1/admin/migrations/apply",
    response_model=MigrationActionResponse,
    tags=["admin"],
)
def migration_apply(
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_migrations")),
) -> MigrationActionResponse:
    versions = _migration_manager(request).apply_all()
    _emit_audit_event(request, user, "migration.apply", {"versions_applied": versions})
    return MigrationActionResponse(
        message="Migrations applied",
        versions=versions,
    )


@router.post(
    "/api/v1/admin/migrations/rollback",
    response_model=MigrationActionResponse,
    tags=["admin"],
)
def migration_rollback(
    payload: MigrationRollbackRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_migrations")),
) -> MigrationActionResponse:
    try:
        versions = _migration_manager(request).rollback(steps=payload.steps, force=payload.force)
    except ValueError as exc:
        raise _value_error_to_http(exc)
    _emit_audit_event(
        request, user, "migration.rollback",
        {"versions_rolled_back": versions, "steps": payload.steps, "force": payload.force},
    )
    return MigrationActionResponse(
        message="Migrations rolled back",
        versions=versions,
    )


@router.get(
    "/api/v1/admin/migrations/dry-run",
    response_model=MigrationDryRunResponse,
    tags=["admin"],
)
def migration_dry_run(
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_migrations")),
) -> MigrationDryRunResponse:
    del user
    result = _migration_manager(request).dry_run()
    return MigrationDryRunResponse(**result)


@router.post(
    "/api/v1/admin/migrations/preflight",
    response_model=MigrationPreflightResponse,
    tags=["admin"],
)
def migration_preflight(
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_migrations")),
) -> MigrationPreflightResponse:
    del user
    result = _migration_manager(request).preflight()
    return MigrationPreflightResponse(**result)


# ── Users CRUD + password rotate ── MOVED to app/routers/auth.py (A5.3) ────────


@router.get("/api/v1/audit-logs", response_model=list[AuditLogRead], tags=["audit"])
def list_audit_logs(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    user: UserProfile = Depends(require_permissions("view_audit_logs")),
) -> list[AuditLogRead]:
    del user
    rows = _audit_repo(request).list_logs(limit=limit)
    return [AuditLogRead(**row) for row in rows]


@router.get("/", tags=["legacy"])
def root(request: Request) -> dict:
    companies = _repo(request).list_companies()
    return {
        "message": "Alpha Quantum aktif",
        "companies": [company.model_dump() for company in companies],
    }


@router.get("/api/v1/companies", response_model=list[Company], tags=["companies"])
def list_companies(request: Request) -> list[Company]:
    return _repo(request).list_companies()


@router.get(
    "/api/v1/company-engine/overview",
    response_model=CompanyEngineResponse,
    tags=["company_engine"],
)
def company_engine_overview(request: Request) -> CompanyEngineResponse:
    companies = _repo(request).list_companies()
    return _company_engine(request).build_overview(companies)


@router.get(
    "/api/v1/inventory-engine/critical",
    response_model=InventoryEngineResponse,
    tags=["inventory_engine"],
)
def inventory_engine_critical(request: Request) -> InventoryEngineResponse:
    companies = _repo(request).list_companies()
    return _inventory_engine(request).list_critical(companies)


# ── Finance engine endpoints (overview, ledger, cashflow, forecast, recurring,
#    budgets) ── MOVED to app/routers/finance.py (A5.7) ──────────────────────


# ── Reporting exports ──────────────────────────────────────────────────────────
# _build_export_response helper'ı app/routers/_deps.py'a taşındı (A5.6).


@router.get(
    "/api/v1/reports/finance/ledger.xlsx",
    tags=["reports"],
    response_class=Response,
)
def export_ledger_xlsx(
    request: Request,
    company: str | None = Query(default=None),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    limit: int = Query(default=1000, ge=1, le=1000),
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> Response:
    if company:
        _ensure_company_scope(request, user, company)
    elif not _is_holding_scope(request, user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scoped users must provide company parameter",
        )
    ledger = _finance_engine(request).list_ledger_entries(
        company=company, start_date=start_date, end_date=end_date, limit=limit
    )
    entries = [e.model_dump() for e in ledger.entries]
    reporting = _reporting_engine(request)
    content = reporting.ledger_to_xlsx(entries)
    return _build_export_response(
        content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "finance_ledger.xlsx", request.app.state.settings.jwt_secret, reporting,
    )


@router.get(
    "/api/v1/reports/finance/ledger.pdf",
    tags=["reports"],
    response_class=Response,
)
def export_ledger_pdf(
    request: Request,
    company: str | None = Query(default=None),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    limit: int = Query(default=1000, ge=1, le=1000),
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> Response:
    if company:
        _ensure_company_scope(request, user, company)
    elif not _is_holding_scope(request, user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scoped users must provide company parameter",
        )
    ledger = _finance_engine(request).list_ledger_entries(
        company=company, start_date=start_date, end_date=end_date, limit=limit
    )
    entries = [e.model_dump() for e in ledger.entries]
    reporting = _reporting_engine(request)
    content = reporting.ledger_to_pdf(entries)
    return _build_export_response(
        content, "application/pdf",
        "finance_ledger.pdf", request.app.state.settings.jwt_secret, reporting,
    )


@router.get(
    "/api/v1/reports/finance/budget-vs-actual.xlsx",
    tags=["reports"],
    response_class=Response,
)
def export_budget_vs_actual_xlsx(
    request: Request,
    year: int = Query(..., ge=2000, le=2100),
    company: str | None = Query(default=None),
    month: int | None = Query(default=None, ge=1, le=12),
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> Response:
    if company:
        _ensure_company_scope(request, user, company)
    elif not _is_holding_scope(request, user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scoped users must provide company parameter",
        )
    report = _finance_engine(request).budget_vs_actual(
        company=company, year=year, month=month
    )
    items = [i.model_dump() for i in report.items]
    totals = {
        "total_budget_income": report.total_budget_income,
        "total_budget_expense": report.total_budget_expense,
        "total_actual_income": report.total_actual_income,
        "total_actual_expense": report.total_actual_expense,
        "net_budget": report.net_budget,
        "net_actual": report.net_actual,
        "net_variance": report.net_variance,
    }
    reporting = _reporting_engine(request)
    content = reporting.budget_vs_actual_to_xlsx(
        company=company, year=year, month=month, items=items, totals=totals
    )
    return _build_export_response(
        content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "budget_vs_actual.xlsx", request.app.state.settings.jwt_secret, reporting,
    )


@router.get(
    "/api/v1/reports/finance/budget-vs-actual.pdf",
    tags=["reports"],
    response_class=Response,
)
def export_budget_vs_actual_pdf(
    request: Request,
    year: int = Query(..., ge=2000, le=2100),
    company: str | None = Query(default=None),
    month: int | None = Query(default=None, ge=1, le=12),
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> Response:
    if company:
        _ensure_company_scope(request, user, company)
    elif not _is_holding_scope(request, user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scoped users must provide company parameter",
        )
    report = _finance_engine(request).budget_vs_actual(
        company=company, year=year, month=month
    )
    items = [i.model_dump() for i in report.items]
    totals = {
        "total_budget_income": report.total_budget_income,
        "total_budget_expense": report.total_budget_expense,
        "total_actual_income": report.total_actual_income,
        "total_actual_expense": report.total_actual_expense,
        "net_budget": report.net_budget,
        "net_actual": report.net_actual,
        "net_variance": report.net_variance,
    }
    reporting = _reporting_engine(request)
    content = reporting.budget_vs_actual_to_pdf(
        company=company, year=year, month=month, items=items, totals=totals
    )
    return _build_export_response(
        content, "application/pdf",
        "budget_vs_actual.pdf", request.app.state.settings.jwt_secret, reporting,
    )


@router.get(
    "/api/v1/market/ohlcv",
    response_model=MarketOHLCVResponse,
    tags=["market"],
)
def market_ohlcv(
    request: Request,
    symbol: str = Query(default="AAPL", min_length=1),
    timeframe: str = Query(default="1d"),
    days: int = Query(default=180, ge=20, le=3650),
    refresh: bool = Query(default=False),
    user: UserProfile = Depends(require_permissions("read_market")),
) -> MarketOHLCVResponse:
    del user
    try:
        return _market_engine(request).get_ohlcv(
            symbol=symbol,
            timeframe=timeframe,
            days=days,
            refresh=refresh,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc)


@router.get(
    "/api/v1/market/analysis",
    response_model=MarketAnalysisResponse,
    tags=["market"],
)
def market_analysis(
    request: Request,
    symbol: str = Query(default="AAPL", min_length=1),
    timeframe: str = Query(default="1d"),
    days: int = Query(default=180, ge=20, le=3650),
    refresh: bool = Query(default=False),
    user: UserProfile = Depends(require_permissions("read_market")),
) -> MarketAnalysisResponse:
    del user
    try:
        return _market_engine(request).analyze_symbol(
            symbol=symbol,
            timeframe=timeframe,
            days=days,
            refresh=refresh,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc)


@router.get(
    "/api/v1/market/signals",
    response_model=MarketSignalsResponse,
    tags=["market"],
)
def market_signals(
    request: Request,
    symbols: str = Query(default="AAPL,MSFT,NVDA,TSLA"),
    timeframe: str = Query(default="1d"),
    days: int = Query(default=180, ge=20, le=3650),
    refresh: bool = Query(default=False),
    user: UserProfile = Depends(require_permissions("read_market")),
) -> MarketSignalsResponse:
    del user
    parsed_symbols = _parse_symbols_csv(symbols)
    if not parsed_symbols:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="symbols parameter is empty")

    try:
        return _market_engine(request).analyze_symbols(
            symbols=parsed_symbols,
            timeframe=timeframe,
            days=days,
            refresh=refresh,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc)


@router.post(
    "/api/v1/market/refresh",
    response_model=MarketRefreshResponse,
    tags=["market"],
)
def market_refresh(
    payload: MarketRefreshRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("refresh_market")),
) -> MarketRefreshResponse:
    del user
    symbols = payload.symbols or ["AAPL", "MSFT", "NVDA", "TSLA"]

    try:
        refreshed = _market_engine(request).refresh_symbols(
            symbols=symbols,
            timeframe=payload.timeframe,
            days=payload.days,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc)

    return MarketRefreshResponse(
        refreshed_count=len(refreshed),
        symbols=refreshed,
    )


@router.get(
    "/api/v1/global/central-banks",
    response_model=CentralBankPanelResponse,
    tags=["global_intel"],
)
def global_central_banks(
    request: Request,
    days: int = Query(default=720, ge=90, le=3650),
    user: UserProfile = Depends(require_permissions("read_global_intel")),
) -> CentralBankPanelResponse:
    del user
    return _global_engine(request).central_bank_panel(days=days)


@router.get(
    "/api/v1/global/world-bank",
    response_model=WorldBankPanelResponse,
    tags=["global_intel"],
)
def global_world_bank(
    request: Request,
    countries: str = Query(default="USA,TUR,DEU"),
    indicators: str = Query(default="FP.CPI.TOTL.ZG,NY.GDP.MKTP.KD.ZG,SL.UEM.TOTL.ZS"),
    years: int = Query(default=20, ge=5, le=60),
    user: UserProfile = Depends(require_permissions("read_global_intel")),
) -> WorldBankPanelResponse:
    del user
    return _global_engine(request).world_bank_panel(
        countries=_parse_symbols_csv(countries),
        indicators=_parse_symbols_csv(indicators),
        years=years,
    )


@router.get(
    "/api/v1/global/report",
    response_model=ProfessionalReportResponse,
    tags=["global_intel"],
)
def global_professional_report(
    request: Request,
    countries: str = Query(default="USA,TUR,DEU"),
    indicators: str = Query(default="FP.CPI.TOTL.ZG,NY.GDP.MKTP.KD.ZG,SL.UEM.TOTL.ZS"),
    bank_symbols: str = Query(default="JPM,BAC,HSBC,BNP.PA"),
    index_symbols: str = Query(default="SPX,NDX,DAX,XU100"),
    market_days: int = Query(default=260, ge=60, le=3650),
    macro_days: int = Query(default=720, ge=90, le=3650),
    macro_years: int = Query(default=20, ge=5, le=60),
    refresh_market: bool = Query(default=False),
    user: UserProfile = Depends(require_permissions("read_global_intel")),
) -> ProfessionalReportResponse:
    del user
    return _global_engine(request).build_professional_report(
        countries=_parse_symbols_csv(countries),
        indicators=_parse_symbols_csv(indicators),
        bank_symbols=_parse_symbols_csv(bank_symbols),
        index_symbols=_parse_symbols_csv(index_symbols),
        market_days=market_days,
        macro_days=macro_days,
        macro_years=macro_years,
        refresh_market=refresh_market,
    )


@router.post(
    "/api/v1/public-institutions/report",
    response_model=InstitutionReportResponse,
    tags=["public_intel"],
)
def public_institutions_report(
    payload: InstitutionReportRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("read_public_sources")),
) -> InstitutionReportResponse:
    del user
    return _institution_engine(request).build_report(payload)


@router.post(
    "/api/v1/market/intelligence",
    response_model=MarketIntelligenceResponse,
    tags=["market"],
)
def market_intelligence_report(
    payload: MarketIntelligenceRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("read_market", "read_public_sources")),
) -> MarketIntelligenceResponse:
    del user
    try:
        return _market_intelligence_engine(request).build_report(payload)
    except ValueError as exc:
        raise _value_error_to_http(exc)


@router.post(
    "/api/v1/procurement/requests",
    response_model=ProcurementRequestRead,
    status_code=201,
    tags=["procurement"],
)
def create_procurement_request(
    payload: ProcurementRequestCreateRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("write_procurement")),
) -> ProcurementRequestRead:
    _ensure_company_scope(request, user, payload.company)
    try:
        return _procurement_engine(request).create_request(payload)
    except ValueError as exc:
        raise _value_error_to_http(exc)


@router.get(
    "/api/v1/procurement/requests",
    response_model=ProcurementRequestListResponse,
    tags=["procurement"],
)
def list_procurement_requests(
    request: Request,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    user: UserProfile = Depends(require_permissions("read_procurement")),
) -> ProcurementRequestListResponse:
    response = _procurement_engine(request).list_requests(
        status=status_filter,
        limit=limit,
    )
    filtered_items = [
        item
        for item in response.items
        if _user_has_company_scope(request, user, item.company)
    ]
    return ProcurementRequestListResponse(
        total=len(filtered_items),
        items=filtered_items,
    )


@router.get(
    "/api/v1/procurement/requests/{request_id}",
    response_model=ProcurementRequestRead,
    tags=["procurement"],
)
def get_procurement_request(
    request_id: int,
    request: Request,
    user: UserProfile = Depends(require_permissions("read_procurement")),
) -> ProcurementRequestRead:
    try:
        result = _procurement_engine(request).get_request(request_id)
    except ValueError as exc:
        raise _value_error_to_http(exc)
    _ensure_company_scope(request, user, result.company)
    return result


@router.post(
    "/api/v1/procurement/requests/from-tender",
    response_model=ProcurementTenderPlanResponse,
    status_code=201,
    tags=["procurement"],
)
def create_procurement_from_tender(
    payload: ProcurementTenderPlanRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("write_procurement", "prepare_tender_docs")),
) -> ProcurementTenderPlanResponse:
    _ensure_company_scope(request, user, payload.tender.company_name)
    try:
        return _procurement_engine(request).create_request_from_tender(payload)
    except ValueError as exc:
        raise _value_error_to_http(exc)


@router.post(
    "/api/v1/procurement/quotes",
    response_model=ProcurementVendorQuoteRead,
    status_code=201,
    tags=["procurement"],
)
def create_procurement_quote(
    payload: ProcurementVendorQuoteCreateRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("write_procurement")),
) -> ProcurementVendorQuoteRead:
    try:
        target_request = _procurement_engine(request).get_request(payload.request_id)
    except ValueError as exc:
        raise _value_error_to_http(exc)
    _ensure_company_scope(request, user, target_request.company)

    try:
        return _procurement_engine(request).submit_quote(payload)
    except ValueError as exc:
        raise _value_error_to_http(exc)


@router.get(
    "/api/v1/procurement/requests/{request_id}/quotes",
    response_model=ProcurementVendorQuoteListResponse,
    tags=["procurement"],
)
def list_procurement_quotes(
    request_id: int,
    request: Request,
    user: UserProfile = Depends(require_permissions("read_procurement")),
) -> ProcurementVendorQuoteListResponse:
    try:
        target_request = _procurement_engine(request).get_request(request_id)
        _ensure_company_scope(request, user, target_request.company)
        return _procurement_engine(request).list_quotes(request_id)
    except ValueError as exc:
        raise _value_error_to_http(exc)


@router.get(
    "/api/v1/procurement/requests/{request_id}/evaluation",
    response_model=ProcurementEvaluationResponse,
    tags=["procurement"],
)
def evaluate_procurement_request(
    request_id: int,
    request: Request,
    strategy_override: str | None = Query(default=None),
    user: UserProfile = Depends(require_permissions("read_procurement")),
) -> ProcurementEvaluationResponse:
    try:
        target_request = _procurement_engine(request).get_request(request_id)
        _ensure_company_scope(request, user, target_request.company)
        return _procurement_engine(request).evaluate_request(
            request_id=request_id,
            strategy_override=strategy_override,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc)


@router.post(
    "/api/v1/procurement/requests/{request_id}/purchase-orders/auto",
    response_model=ProcurementPurchaseOrderBatchResponse,
    tags=["procurement"],
)
def auto_create_purchase_orders(
    request_id: int,
    payload: ProcurementAutoOrderRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("approve_procurement")),
) -> ProcurementPurchaseOrderBatchResponse:
    try:
        target_request = _procurement_engine(request).get_request(request_id)
        _ensure_company_scope(request, user, target_request.company)
        return _procurement_engine(request).create_auto_purchase_orders(request_id, payload)
    except ValueError as exc:
        raise _value_error_to_http(exc)


@router.get(
    "/api/v1/procurement/requests/{request_id}/purchase-orders",
    response_model=ProcurementPurchaseOrderBatchResponse,
    tags=["procurement"],
)
def list_procurement_purchase_orders(
    request_id: int,
    request: Request,
    user: UserProfile = Depends(require_permissions("read_procurement")),
) -> ProcurementPurchaseOrderBatchResponse:
    try:
        target_request = _procurement_engine(request).get_request(request_id)
        _ensure_company_scope(request, user, target_request.company)
        return _procurement_engine(request).list_purchase_orders(request_id)
    except ValueError as exc:
        raise _value_error_to_http(exc)


@router.post(
    "/api/v1/feasibility/report",
    response_model=FeasibilityReportStoredResponse,
    status_code=201,
    tags=["feasibility"],
)
def generate_feasibility_report(
    payload: FeasibilityReportRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("write_feasibility")),
) -> FeasibilityReportStoredResponse:
    if payload.company_name:
        _ensure_company_scope(request, user, payload.company_name)
    elif not _is_holding_scope(request, user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scoped users must provide company_name in feasibility report request",
        )
    try:
        return _feasibility_engine(request).generate(payload)
    except ValueError as exc:
        raise _value_error_to_http(exc)


@router.get(
    "/api/v1/feasibility/reports",
    response_model=FeasibilityReportListResponse,
    tags=["feasibility"],
)
def list_feasibility_reports(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    sector: str | None = Query(default=None),
    company: str | None = Query(default=None),
    user: UserProfile = Depends(require_permissions("read_feasibility")),
) -> FeasibilityReportListResponse:
    if company:
        _ensure_company_scope(request, user, company)
        return _feasibility_engine(request).list_reports(limit=limit, sector=sector, company_name=company)
    if not _is_holding_scope(request, user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scoped users must provide company parameter",
        )
    return _feasibility_engine(request).list_reports(limit=limit, sector=sector)


@router.get(
    "/api/v1/feasibility/reports/{report_id}",
    response_model=FeasibilityReportStoredResponse,
    tags=["feasibility"],
)
def get_feasibility_report(
    report_id: int,
    request: Request,
    user: UserProfile = Depends(require_permissions("read_feasibility")),
) -> FeasibilityReportStoredResponse:
    try:
        result = _feasibility_engine(request).get_report(report_id)
    except ValueError as exc:
        raise _value_error_to_http(exc)
    if result.company_name:
        _ensure_company_scope(request, user, result.company_name)
    elif not _is_holding_scope(request, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Scoped users cannot access unscoped feasibility reports",
        )
    return result


@router.post(
    "/api/v1/international/projects",
    response_model=InternationalProjectStoredResponse,
    status_code=201,
    tags=["international"],
)
def create_international_project(
    payload: InternationalProjectRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("write_international")),
) -> InternationalProjectStoredResponse:
    _ensure_company_scope(request, user, payload.company_name)
    try:
        return _international_engine(request).create_project(payload)
    except ValueError as exc:
        raise _value_error_to_http(exc)


@router.get(
    "/api/v1/international/projects",
    response_model=InternationalProjectListResponse,
    tags=["international"],
)
def list_international_projects(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    status_filter: str | None = Query(default=None, alias="status"),
    country: str | None = Query(default=None),
    user: UserProfile = Depends(require_permissions("read_international")),
) -> InternationalProjectListResponse:
    try:
        result = _international_engine(request).list_projects(
            limit=limit,
            status=status_filter,
            country=country,
        )
        filtered_items = [
            item
            for item in result.items
            if _user_has_company_scope(request, user, item.company_name)
        ]
        return InternationalProjectListResponse(
            total=len(filtered_items),
            items=filtered_items,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc)


@router.get(
    "/api/v1/international/projects/{project_id}",
    response_model=InternationalProjectStoredResponse,
    tags=["international"],
)
def get_international_project(
    project_id: int,
    request: Request,
    user: UserProfile = Depends(require_permissions("read_international")),
) -> InternationalProjectStoredResponse:
    try:
        result = _international_engine(request).get_project(project_id)
    except ValueError as exc:
        raise _value_error_to_http(exc)
    _ensure_company_scope(request, user, result.company_name)
    return result


@router.post(
    "/api/v1/ecosystem/activate",
    response_model=EcosystemActivationResponse,
    tags=["ecosystem"],
)
def activate_strategic_ecosystem(
    payload: EcosystemActivationRequest,
    request: Request,
    user: UserProfile = Depends(
        require_permissions(
            "write_feasibility",
            "write_international",
            "write_procurement",
        )
    ),
) -> EcosystemActivationResponse:
    _ensure_company_scope(request, user, payload.company_name)
    try:
        return _ecosystem_engine(request).activate(payload)
    except ValueError as exc:
        raise _value_error_to_http(exc)


@router.post(
    "/api/v1/ecosystem/activate/portfolio",
    response_model=EcosystemPortfolioActivationResponse,
    tags=["ecosystem"],
)
def activate_strategic_ecosystem_portfolio(
    payload: EcosystemPortfolioActivationRequest,
    request: Request,
    user: UserProfile = Depends(
        require_permissions(
            "write_feasibility",
            "write_international",
            "write_procurement",
        )
    ),
) -> EcosystemPortfolioActivationResponse:
    for target in payload.companies:
        _ensure_company_scope(request, user, target.company_name)
    try:
        company_names = [company.name for company in _repo(request).list_companies()]
        company_names = [
            company_name
            for company_name in company_names
            if _user_has_company_scope(request, user, company_name)
        ]
        return _ecosystem_engine(request).activate_portfolio(
            payload,
            registered_company_names=company_names,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc)


@router.post(
    "/api/v1/holdings",
    response_model=HoldingRead,
    status_code=201,
    tags=["holding"],
)
def create_holding(
    payload: HoldingCreateRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_holdings")),
) -> HoldingRead:
    del user
    try:
        return _holding_engine(request).create_holding(payload)
    except ValueError as exc:
        raise _value_error_to_http(exc)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Holding already exists",
        ) from exc


@router.get(
    "/api/v1/holdings",
    response_model=HoldingListResponse,
    tags=["holding"],
)
def list_holdings(
    request: Request,
    limit: int = Query(default=200, ge=1, le=1000),
    user: UserProfile = Depends(require_permissions("read_holdings")),
) -> HoldingListResponse:
    del user
    return _holding_engine(request).list_holdings(limit=limit)


@router.get(
    "/api/v1/holdings/{holding_id}",
    response_model=HoldingDetailResponse,
    tags=["holding"],
)
def get_holding_detail(
    holding_id: int,
    request: Request,
    limit: int = Query(default=1000, ge=1, le=5000),
    user: UserProfile = Depends(require_permissions("read_holdings")),
) -> HoldingDetailResponse:
    del user
    try:
        return _holding_engine(request).get_holding_detail(holding_id=holding_id, limit=limit)
    except ValueError as exc:
        raise _value_error_to_http(exc)


@router.post(
    "/api/v1/holdings/{holding_id}/onboard",
    response_model=HoldingOnboardResponse,
    tags=["holding"],
)
def onboard_holding_companies(
    holding_id: int,
    payload: HoldingOnboardRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_holdings")),
) -> HoldingOnboardResponse:
    del user
    try:
        return _holding_engine(request).onboard_companies(holding_id=holding_id, payload=payload)
    except ValueError as exc:
        raise _value_error_to_http(exc)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Holding onboarding conflict",
        ) from exc


@router.post(
    "/api/v1/holdings/onboard/bulk",
    response_model=HoldingBulkOnboardResponse,
    status_code=201,
    tags=["holding"],
)
def onboard_holding_bulk(
    payload: HoldingBulkOnboardRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_holdings")),
) -> HoldingBulkOnboardResponse:
    del user
    try:
        return _holding_engine(request).onboard_bulk(payload)
    except ValueError as exc:
        raise _value_error_to_http(exc)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Holding already exists",
        ) from exc


@router.post(
    "/api/v1/connectors",
    response_model=ConnectorRead,
    status_code=201,
    tags=["connector"],
)
def create_connector(
    payload: ConnectorCreateRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_connectors")),
) -> ConnectorRead:
    _ensure_company_scope(request, user, payload.company_name)
    try:
        return _connector_engine(request).create_connector(
            payload,
            created_by=user.username,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Connector already exists",
        ) from exc


@router.get(
    "/api/v1/connectors",
    response_model=ConnectorListResponse,
    tags=["connector"],
)
def list_connectors(
    request: Request,
    company: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=200, ge=1, le=1000),
    user: UserProfile = Depends(require_permissions("read_connectors")),
) -> ConnectorListResponse:
    if company:
        _ensure_company_scope(request, user, company)
    result = _connector_engine(request).list_connectors(
        company_name=company,
        status=status_filter,
        limit=limit,
    )
    if company or _is_holding_scope(request, user):
        return result

    filtered = [
        item
        for item in result.items
        if _user_has_company_scope(request, user, item.company_name)
    ]
    return ConnectorListResponse(total=len(filtered), items=filtered)


@router.get(
    "/api/v1/connectors/{connector_id}",
    response_model=ConnectorRead,
    tags=["connector"],
)
def get_connector(
    connector_id: int,
    request: Request,
    user: UserProfile = Depends(require_permissions("read_connectors")),
) -> ConnectorRead:
    try:
        result = _connector_engine(request).get_connector(connector_id)
    except ValueError as exc:
        raise _value_error_to_http(exc)
    _ensure_company_scope(request, user, result.company_name)
    return result


@router.post(
    "/api/v1/connectors/canonical/preview",
    response_model=ConnectorCanonicalPreviewResponse,
    tags=["connector"],
)
def preview_connector_canonical_mapping(
    payload: ConnectorCanonicalPreviewRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("read_connectors")),
) -> ConnectorCanonicalPreviewResponse:
    del user
    return _connector_engine(request).preview_canonical_mapping(payload)


@router.post(
    "/api/v1/connectors/{connector_id}/sync-jobs",
    response_model=ConnectorSyncJobRead,
    status_code=201,
    tags=["connector"],
)
def create_connector_sync_job(
    connector_id: int,
    payload: ConnectorSyncJobCreateRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_connectors")),
) -> ConnectorSyncJobRead:
    try:
        connector = _connector_engine(request).get_connector(connector_id)
    except ValueError as exc:
        raise _value_error_to_http(exc)
    _ensure_company_scope(request, user, connector.company_name)
    try:
        return _connector_engine(request).create_sync_job(
            connector_id,
            payload,
            requested_by=user.username,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc)


@router.get(
    "/api/v1/connectors/{connector_id}/sync-jobs",
    response_model=ConnectorSyncJobListResponse,
    tags=["connector"],
)
def list_connector_sync_jobs(
    connector_id: int,
    request: Request,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=200, ge=1, le=2000),
    user: UserProfile = Depends(require_permissions("read_connectors")),
) -> ConnectorSyncJobListResponse:
    try:
        connector = _connector_engine(request).get_connector(connector_id)
    except ValueError as exc:
        raise _value_error_to_http(exc)
    _ensure_company_scope(request, user, connector.company_name)
    return _connector_engine(request).list_sync_jobs(
        connector_id=connector_id,
        status=status_filter,
        limit=limit,
    )


@router.get(
    "/api/v1/connectors/sync-jobs",
    response_model=ConnectorSyncJobListResponse,
    tags=["connector"],
)
def list_sync_jobs(
    request: Request,
    connector_id: int | None = Query(default=None),
    company: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=200, ge=1, le=2000),
    user: UserProfile = Depends(require_permissions("read_connectors")),
) -> ConnectorSyncJobListResponse:
    if company:
        _ensure_company_scope(request, user, company)
    if connector_id is not None:
        try:
            connector = _connector_engine(request).get_connector(connector_id)
        except ValueError as exc:
            raise _value_error_to_http(exc)
        _ensure_company_scope(request, user, connector.company_name)
        company = connector.company_name

    result = _connector_engine(request).list_sync_jobs(
        connector_id=connector_id,
        company_name=company,
        status=status_filter,
        limit=limit,
    )
    if company or _is_holding_scope(request, user):
        return result
    filtered = [
        item
        for item in result.items
        if _user_has_company_scope(request, user, item.company_name)
    ]
    return ConnectorSyncJobListResponse(total=len(filtered), items=filtered)


@router.get(
    "/api/v1/connectors/health/summary",
    response_model=ConnectorQueueHealthResponse,
    tags=["connector"],
)
def connector_health_summary(
    request: Request,
    company: str | None = Query(default=None),
    user: UserProfile = Depends(require_permissions("read_connectors")),
) -> ConnectorQueueHealthResponse:
    if company:
        _ensure_company_scope(request, user, company)
        return _connector_engine(request).build_queue_health(company_name=company)

    if _is_holding_scope(request, user):
        return _connector_engine(request).build_queue_health()

    scoped_companies = sorted({scope for scope in user.company_scopes if scope != "*"})
    if not scoped_companies:
        return _connector_engine(request).build_queue_health(company_name="__no_connector_scope__")

    # Aggregate scoped companies without exposing out-of-scope data.
    aggregate = ConnectorQueueHealthResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        total_connectors=0,
        active_connectors=0,
        staged_connectors=0,
        blocked_connectors=0,
        queued_jobs=0,
        running_jobs=0,
        success_jobs=0,
        failed_jobs=0,
        dead_letter_jobs=0,
        due_retry_jobs=0,
        average_readiness_score=0.0,
        average_security_score=0.0,
    )
    readiness_weighted = 0.0
    security_weighted = 0.0
    for company_name in scoped_companies:
        item = _connector_engine(request).build_queue_health(company_name=company_name)
        aggregate.total_connectors += item.total_connectors
        aggregate.active_connectors += item.active_connectors
        aggregate.staged_connectors += item.staged_connectors
        aggregate.blocked_connectors += item.blocked_connectors
        aggregate.queued_jobs += item.queued_jobs
        aggregate.running_jobs += item.running_jobs
        aggregate.success_jobs += item.success_jobs
        aggregate.failed_jobs += item.failed_jobs
        aggregate.dead_letter_jobs += item.dead_letter_jobs
        aggregate.due_retry_jobs += item.due_retry_jobs
        readiness_weighted += item.average_readiness_score * item.total_connectors
        security_weighted += item.average_security_score * item.total_connectors

    if aggregate.total_connectors > 0:
        aggregate.average_readiness_score = round(readiness_weighted / aggregate.total_connectors, 2)
        aggregate.average_security_score = round(security_weighted / aggregate.total_connectors, 2)
    return aggregate


@router.post(
    "/api/v1/connectors/sync-jobs/dispatch",
    response_model=ConnectorSyncDispatchResponse,
    tags=["connector"],
)
def dispatch_sync_job(
    payload: ConnectorSyncDispatchRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_connectors")),
) -> ConnectorSyncDispatchResponse:
    allowed_company_names: list[str] | None = None
    if payload.company_name:
        _ensure_company_scope(request, user, payload.company_name)
        allowed_company_names = [payload.company_name]
    elif not _is_holding_scope(request, user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scoped users must provide company_name for dispatch",
        )

    return _connector_engine(request).dispatch_next_sync_job(
        payload,
        requested_by=user.username,
        allowed_company_names=allowed_company_names,
    )


@router.get(
    "/api/v1/market/sources",
    response_model=MarketSourceCatalogResponse,
    tags=["market"],
)
def market_sources(
    request: Request,
    regions: str = Query(default="TR,EU,GLOBAL"),
    limit: int = Query(default=20, ge=1, le=50),
    user: UserProfile = Depends(require_permissions("read_market")),
) -> MarketSourceCatalogResponse:
    del user
    return _market_intelligence_engine(request).list_sources(
        regions=_parse_symbols_csv(regions),
        limit=limit,
    )


@router.get(
    "/api/v1/market/backtest",
    response_model=MarketBacktestResponse,
    tags=["market"],
)
def market_backtest(
    request: Request,
    symbol: str = Query(default="AAPL", min_length=1),
    timeframe: str = Query(default="1d"),
    days: int = Query(default=360, ge=80, le=3650),
    lookahead_days: int = Query(default=5, ge=1, le=30),
    hold_band: float = Query(default=0.01, ge=0, le=0.2),
    refresh: bool = Query(default=False),
    user: UserProfile = Depends(require_permissions("read_market")),
) -> MarketBacktestResponse:
    del user
    try:
        return _market_engine(request).backtest_signal_strategy(
            symbol=symbol,
            timeframe=timeframe,
            days=days,
            lookahead_days=lookahead_days,
            hold_band=hold_band,
            refresh=refresh,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc)


@router.post(
    "/api/v1/tender/generate",
    response_model=TenderDossierResponse,
    tags=["tender"],
)
def generate_tender_dossier(
    payload: TenderGenerationRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("prepare_tender_docs")),
) -> TenderDossierResponse:
    _ensure_company_scope(request, user, payload.company_name)
    return _tender_engine(request).build_dossier(payload)


@router.get("/analyze_all", response_model=list[LegacyAnalysisResult], tags=["legacy"])
def analyze_all_legacy(request: Request) -> list[LegacyAnalysisResult]:
    companies = _repo(request).list_companies()
    analyses = _analysis_service(request).analyze_all(companies)
    return [
        LegacyAnalysisResult(
            company=analysis.company,
            status=analysis.status,
            action=analysis.action,
            critical_stock=analysis.critical_stock,
        )
        for analysis in analyses
    ]


@router.get("/api/v1/analysis", response_model=list[AnalysisResult], tags=["analysis"])
def analyze_all(request: Request) -> list[AnalysisResult]:
    companies = _repo(request).list_companies()
    return _analysis_service(request).analyze_all(companies)


@router.get("/api/v1/summary", response_model=DashboardSummary, tags=["dashboard"])
def summary(request: Request) -> DashboardSummary:
    snapshot = _build_dashboard_data(request)
    return snapshot.summary


@router.get("/api/v1/insights", response_model=list[InsightItem], tags=["dashboard"])
def insights(request: Request) -> list[InsightItem]:
    snapshot = _build_dashboard_data(request)
    return snapshot.insights


@router.get(
    "/api/v1/dashboard-data",
    response_model=DashboardDataResponse,
    tags=["dashboard"],
)
def dashboard_data(request: Request) -> DashboardDataResponse:
    return _build_dashboard_data(request)


@router.get("/auto_update", response_model=LegacyUpdateResult, tags=["legacy"])
def auto_update_legacy(
    request: Request,
    user: UserProfile = Depends(require_permissions("run_simulation")),
) -> LegacyUpdateResult:
    del user
    _repo(request).update_random()
    return LegacyUpdateResult(message="Sistem guncellendi")


@router.post("/api/v1/simulate", response_model=UpdateResult, tags=["simulation"])
def simulate_update(
    request: Request,
    user: UserProfile = Depends(require_permissions("run_simulation")),
) -> UpdateResult:
    del user
    companies = _repo(request).update_random()
    return UpdateResult(message="Simulation completed", companies=companies)


@router.get("/api/v1/health", response_model=HealthResponse, tags=["system"])
def health(request: Request) -> HealthResponse:
    settings = request.app.state.settings
    return HealthResponse(
        status="ok",
        environment=settings.environment,
        company_count=_repo(request).company_count(),
        version=settings.app_version,
    )


def _parse_symbols_csv(raw: str) -> list[str]:
    symbols: list[str] = []
    seen: set[str] = set()
    for item in raw.split(","):
        normalized = item.strip().upper()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        symbols.append(normalized)
    return symbols


# Scope helpers `app/routers/_deps.py`'den import ediliyor (A5.1)
from app.routers._deps import (  # noqa: E402
    _ensure_company_scope,
    _filter_companies_by_user_scope,
    _is_holding_scope,
    _user_has_company_scope,
)


def _build_dashboard_data(request: Request) -> DashboardDataResponse:
    companies = _repo(request).list_companies()
    analyses = _analysis_service(request).analyze_all(companies)
    summary = _dashboard_service(request).build_summary(companies, analyses)
    insights = _dashboard_service(request).build_insights(analyses)

    return DashboardDataResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        summary=summary,
        companies=companies,
        analyses=analyses,
        insights=insights,
    )


@router.get("/dashboard", response_class=HTMLResponse, tags=["dashboard"])
def dashboard_ui(request: Request) -> HTMLResponse:
    snapshot = _build_dashboard_data(request)
    analysis_map = {analysis.company: analysis for analysis in snapshot.analyses}
    market_symbols = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "BTCUSD"]
    html = _render_dashboard(
        companies=snapshot.companies,
        analysis_map=analysis_map,
        summary=snapshot.summary,
        insights=snapshot.insights,
        market_symbols=market_symbols,
    )
    return HTMLResponse(content=html)


def _render_dashboard(
    companies: list[Company],
    analysis_map: dict[str, AnalysisResult],
    summary: DashboardSummary,
    insights: list[InsightItem],
    market_symbols: list[str],
) -> str:
    card_html = "".join(_render_company_card(company, analysis_map[company.name]) for company in companies)
    insight_html = "".join(_render_insight_item(item) for item in insights)
    market_options = "".join(
        f'<option value="{escape(symbol)}">{escape(symbol)}</option>'
        for symbol in market_symbols
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Alpha Quantum Dashboard</title>
  <style>
    :root {{
      --bg: #081426;
      --panel: #102a43;
      --panel-alt: #1f3f63;
      --accent: #2cb1bc;
      --ok: #7bd88f;
      --critical: #ff6b6b;
      --text: #f0f4f8;
      --muted: #b0beca;
      --border: rgba(255, 255, 255, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "Arial", sans-serif;
      color: var(--text);
      background: radial-gradient(circle at 20% 10%, #163d5f 0%, var(--bg) 55%);
      min-height: 100vh;
    }}
    .container {{
      width: min(1180px, 94vw);
      margin: 2rem auto 3rem;
    }}
    .header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 1rem;
      flex-wrap: wrap;
      margin-bottom: 1.5rem;
    }}
    .title {{
      margin: 0;
      font-size: clamp(1.6rem, 3vw, 2.2rem);
      letter-spacing: 0.4px;
    }}
    .muted {{
      color: var(--muted);
      margin-top: 0.2rem;
      font-size: 0.92rem;
    }}
    .actions {{
      display: flex;
      gap: 0.6rem;
      flex-wrap: wrap;
    }}
    button, .link-btn, select {{
      border: none;
      border-radius: 10px;
      padding: 0.65rem 1rem;
      cursor: pointer;
      background: var(--accent);
      color: #06202a;
      font-weight: 700;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      transition: transform 0.15s ease, opacity 0.15s ease;
    }}
    select {{
      background: #e6f7f9;
      min-width: 130px;
    }}
    button:hover, .link-btn:hover {{
      transform: translateY(-1px);
      opacity: 0.92;
    }}
    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 0.75rem;
      margin-bottom: 1rem;
    }}
    .summary-card {{
      background: linear-gradient(145deg, var(--panel), var(--panel-alt));
      border-radius: 12px;
      border: 1px solid var(--border);
      padding: 0.9rem 1rem;
      box-shadow: 0 8px 18px rgba(1, 13, 28, 0.3);
    }}
    .summary-label {{
      color: var(--muted);
      font-size: 0.82rem;
    }}
    .summary-value {{
      margin-top: 0.2rem;
      font-size: 1.25rem;
      font-weight: 700;
    }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 0.85rem;
    }}
    .card {{
      background: linear-gradient(160deg, #0f2c45, #12314d);
      border-radius: 14px;
      border: 1px solid rgba(255, 255, 255, 0.06);
      padding: 1rem;
    }}
    .card h3 {{
      margin: 0 0 0.7rem;
      font-size: 1.05rem;
    }}
    .line {{
      display: flex;
      justify-content: space-between;
      gap: 1rem;
      margin-bottom: 0.35rem;
      font-size: 0.94rem;
    }}
    .inventory {{
      margin-top: 0.75rem;
      margin-bottom: 0;
      padding-left: 1.1rem;
    }}
    .inventory li {{
      margin-bottom: 0.3rem;
    }}
    .market-grid {{
      display: grid;
      grid-template-columns: 1.55fr 1fr;
      gap: 0.85rem;
      margin-top: 1rem;
    }}
    .market-toolbar {{
      display: flex;
      gap: 0.5rem;
      align-items: center;
      flex-wrap: wrap;
      margin-top: 0.65rem;
      margin-bottom: 0.5rem;
    }}
    #market-chart {{
      width: 100%;
      height: 240px;
      border-radius: 10px;
      background: linear-gradient(180deg, rgba(26, 65, 98, 0.5), rgba(8, 20, 38, 0.3));
      border: 1px solid var(--border);
    }}
    .market-signals {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 0.45rem;
      margin-top: 0.65rem;
      max-height: 260px;
      overflow: auto;
    }}
    .signal-card {{
      border-radius: 10px;
      border: 1px solid var(--border);
      padding: 0.55rem 0.65rem;
      background: rgba(9, 27, 41, 0.55);
    }}
    .signal-card .row {{
      display: flex;
      justify-content: space-between;
      gap: 0.5rem;
      font-size: 0.9rem;
    }}
    .signal-buy {{ border-left: 4px solid var(--ok); }}
    .signal-sell {{ border-left: 4px solid var(--critical); }}
    .signal-hold {{ border-left: 4px solid #f9d65b; }}
    .report-summary {{
      margin-top: 0.65rem;
      color: var(--text);
      font-size: 0.92rem;
    }}
    .tag {{
      display: inline-block;
      margin-right: 0.4rem;
      margin-top: 0.25rem;
      padding: 0.2rem 0.48rem;
      border-radius: 999px;
      font-size: 0.74rem;
      background: rgba(44, 177, 188, 0.16);
      border: 1px solid rgba(44, 177, 188, 0.35);
      color: #d5f4f7;
    }}
    .region-set {{
      display: flex;
      gap: 0.45rem;
      flex-wrap: wrap;
      align-items: center;
    }}
    .region-pill {{
      display: inline-flex;
      align-items: center;
      gap: 0.35rem;
      border: 1px solid var(--border);
      background: rgba(5, 18, 33, 0.6);
      padding: 0.28rem 0.52rem;
      border-radius: 999px;
      font-size: 0.78rem;
      color: var(--text);
    }}
    .region-pill input {{
      margin: 0;
    }}
    #global-report {{
      margin-top: 0.75rem;
      padding: 0.75rem;
      border-radius: 10px;
      border: 1px solid var(--border);
      background: rgba(3, 11, 25, 0.62);
      color: #dce7f1;
      max-height: 260px;
      overflow: auto;
      font-size: 0.8rem;
      line-height: 1.45;
      white-space: pre-wrap;
    }}
    .critical {{ color: var(--critical); }}
    .ok {{ color: var(--ok); }}
    @media (max-width: 920px) {{
      .market-grid {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div>
        <h1 class="title">Alpha Quantum Dashboard</h1>
        <div class="muted">Professional control panel for ERP + Finance + AI operations</div>
      </div>
      <div class="actions">
        <button id="simulate-btn" onclick="simulateAndReload()">Veri Guncelle</button>
        <button id="market-refresh-btn" onclick="refreshMarketWidgets()">Market Yenile</button>
        <a class="link-btn" href="/api/v1/analysis" target="_blank" rel="noreferrer">Analiz JSON</a>
        <a class="link-btn" href="/api/v1/market/sources?regions=TR,EU,GLOBAL" target="_blank" rel="noreferrer">Market Sources</a>
      </div>
    </div>

    <section class="summary-grid">
      <article class="summary-card">
        <div class="summary-label">Sirket Sayisi</div>
        <div class="summary-value">{summary.total_companies}</div>
      </article>
      <article class="summary-card">
        <div class="summary-label">Toplam Bakiye</div>
        <div class="summary-value">{summary.total_balance:,.0f}</div>
      </article>
      <article class="summary-card">
        <div class="summary-label">Kritik Stok Kalemi</div>
        <div class="summary-value">{summary.critical_items}</div>
      </article>
      <article class="summary-card">
        <div class="summary-label">Riskli Sirket</div>
        <div class="summary-value">{summary.risk_companies}</div>
      </article>
    </section>

    <section class="cards">
      {card_html}
    </section>

    <section class="market-grid">
      <article class="summary-card">
        <div class="summary-label">Live Market Chart (OHLCV)</div>
        <div class="market-toolbar">
          <select id="market-symbol">
            {market_options}
          </select>
          <button onclick="loadMarketChart(true)">Grafik Yenile</button>
        </div>
        <svg id="market-chart" viewBox="0 0 900 260" preserveAspectRatio="none"></svg>
        <div id="market-meta" class="muted">Yukleniyor...</div>
        <div id="backtest-meta" class="muted"></div>
      </article>

      <article class="summary-card">
        <div class="summary-label">AI Market Signal Cards</div>
        <div id="market-signals" class="market-signals">
          <div class="muted">Yukleniyor...</div>
        </div>
      </article>
    </section>

    <section style="margin-top: 1rem;">
      <article class="summary-card">
        <div class="summary-label">Market Intelligence (TR + EU + Global Borsalar)</div>
        <div class="market-toolbar">
          <div class="region-set">
            <label class="region-pill"><input type="checkbox" class="intel-region" value="TR" checked />TR</label>
            <label class="region-pill"><input type="checkbox" class="intel-region" value="EU" checked />EU</label>
            <label class="region-pill"><input type="checkbox" class="intel-region" value="GLOBAL" checked />GLOBAL</label>
          </div>
          <button onclick="loadMarketIntelligence(true)">Intelligence Yenile</button>
        </div>
        <div id="intel-summary" class="report-summary">Yukleniyor...</div>
        <div id="intel-pages" class="muted"></div>
        <div id="intel-cards" class="market-signals">
          <div class="muted">Yukleniyor...</div>
        </div>
      </article>
    </section>

    <section style="margin-top: 1rem;">
      <article class="summary-card">
        <div class="summary-label">Connector Sync Health (Queue + DLQ)</div>
        <div id="connector-health" class="report-summary">Yukleniyor...</div>
        <div class="market-toolbar">
          <button onclick="loadConnectorHealth()">Health Yenile</button>
          <button onclick="dispatchConnectorQueue()">Queue'dan 1 Islem</button>
        </div>
        <div id="connector-jobs" class="market-signals">
          <div class="muted">Yukleniyor...</div>
        </div>
      </article>
    </section>

    <section style="margin-top: 1rem;">
      <article class="summary-card">
        <div class="summary-label">Global Intelligence Report</div>
        <div id="global-summary" class="report-summary">Yukleniyor...</div>
        <pre id="global-report">Global rapor bekleniyor...</pre>
      </article>
    </section>

    <section style="margin-top: 1rem;">
      <article class="summary-card">
        <div class="summary-label">AI Insight Feed</div>
        <ul style="margin: 0.75rem 0 0; padding-left: 1rem;">
          {insight_html}
        </ul>
        <div id="live-info" class="muted" style="margin-top: 0.7rem;">
          Market veri yenileme acik (30 saniye)
        </div>
      </article>
    </section>
  </div>

  <script>
    function authHeaders() {{
      const token = window.localStorage.getItem("aq_token");
      if (!token) {{
        return {{}};
      }}
      return {{ Authorization: `Bearer ${{token}}` }};
    }}

    function escapeHtml(value) {{
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;");
    }}

    async function simulateAndReload() {{
      const button = document.getElementById("simulate-btn");
      button.disabled = true;
      button.textContent = "Guncelleniyor...";
      try {{
        const response = await fetch("/api/v1/simulate", {{
          method: "POST",
          headers: authHeaders(),
        }});
        if (response.status === 401 || response.status === 403) {{
          alert("Auth gerekli. /api/v1/auth/login ile token alip localStorage.aq_token set edin.");
          return;
        }}
        if (!response.ok) {{
          alert("Simulation failed");
          return;
        }}
        window.location.reload();
      }} finally {{
        button.disabled = false;
        button.textContent = "Veri Guncelle";
      }}
    }}

    function renderChart(bars) {{
      const svg = document.getElementById("market-chart");
      if (!bars || bars.length < 2) {{
        svg.innerHTML = `<text x="16" y="28" fill="#b0beca">Yeterli market veri yok.</text>`;
        return;
      }}

      const closes = bars.map((item) => Number(item.close));
      const min = Math.min(...closes);
      const max = Math.max(...closes);
      const width = 900;
      const height = 260;
      const left = 35;
      const right = 15;
      const top = 14;
      const bottom = 24;
      const innerW = width - left - right;
      const innerH = height - top - bottom;
      const range = Math.max(max - min, 0.00001);
      const points = closes.map((value, idx) => {{
        const x = left + (idx / (closes.length - 1)) * innerW;
        const y = top + (1 - ((value - min) / range)) * innerH;
        return `${{x.toFixed(2)}},${{y.toFixed(2)}}`;
      }}).join(" ");

      svg.innerHTML = `
        <line x1="${{left}}" y1="${{top}}" x2="${{left}}" y2="${{height - bottom}}" stroke="rgba(176,190,202,0.35)" stroke-width="1" />
        <line x1="${{left}}" y1="${{height - bottom}}" x2="${{width - right}}" y2="${{height - bottom}}" stroke="rgba(176,190,202,0.35)" stroke-width="1" />
        <polyline points="${{points}}" fill="none" stroke="#2cb1bc" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round" />
        <text x="${{left + 4}}" y="${{top + 11}}" fill="#b0beca" font-size="11">${{max.toFixed(2)}}</text>
        <text x="${{left + 4}}" y="${{height - bottom - 4}}" fill="#b0beca" font-size="11">${{min.toFixed(2)}}</text>
      `;
    }}

    async function loadMarketChart(forceRefresh) {{
      const symbol = document.getElementById("market-symbol").value;
      const meta = document.getElementById("market-meta");
      const backtestMeta = document.getElementById("backtest-meta");
      const refresh = forceRefresh ? "true" : "false";
      const response = await fetch(`/api/v1/market/ohlcv?symbol=${{encodeURIComponent(symbol)}}&days=220&refresh=${{refresh}}`, {{
        headers: authHeaders(),
      }});

      if (response.status === 401 || response.status === 403) {{
        meta.textContent = "Market grafikleri icin aq_token gerekli (read_market).";
        backtestMeta.textContent = "";
        renderChart([]);
        return;
      }}
      if (!response.ok) {{
        meta.textContent = "Market grafikleri yuklenemedi.";
        backtestMeta.textContent = "";
        renderChart([]);
        return;
      }}

      const payload = await response.json();
      renderChart(payload.bars || []);
      const last = payload.bars && payload.bars.length ? payload.bars[payload.bars.length - 1] : null;
      meta.textContent = `Symbol: ${{payload.symbol}} | Source: ${{payload.source}} | Last: ${{last ? Number(last.close).toFixed(2) : "-"}}`;
      backtestMeta.textContent = "Backtest yukleniyor...";
      await loadBacktest(symbol, forceRefresh);
    }}

    async function loadBacktest(symbol, forceRefresh) {{
      const target = document.getElementById("backtest-meta");
      const refresh = forceRefresh ? "true" : "false";
      const response = await fetch(
        `/api/v1/market/backtest?symbol=${{encodeURIComponent(symbol)}}&days=540&lookahead_days=5&hold_band=0.012&refresh=${{refresh}}`,
        {{
          headers: authHeaders(),
        }},
      );
      if (!response.ok) {{
        target.textContent = "Backtest bilgisi yuklenemedi.";
        return;
      }}
      const payload = await response.json();
      target.textContent = `Backtest(win=${{(Number(payload.win_rate) * 100).toFixed(1)}}%, edge=${{(Number(payload.strategy_edge) * 100).toFixed(2)}}%, maxDD=${{(Number(payload.max_drawdown) * 100).toFixed(1)}}%)`;
    }}

    function renderSignalCards(items) {{
      const container = document.getElementById("market-signals");
      if (!items || !items.length) {{
        container.innerHTML = `<div class="muted">Signal bulunamadi.</div>`;
        return;
      }}

      container.innerHTML = items.map((item) => {{
        const cls = item.signal === "BUY" ? "signal-buy" : (item.signal === "SELL" ? "signal-sell" : "signal-hold");
        return `
          <article class="signal-card ${{cls}}">
            <div class="row"><strong>${{escapeHtml(item.symbol)}}</strong><strong>${{escapeHtml(item.signal)}}</strong></div>
            <div class="row"><span>Trend: ${{escapeHtml(item.trend)}}</span><span>Conf: ${{Number(item.confidence).toFixed(2)}}</span></div>
            <div class="row"><span>RSI14: ${{item.rsi_14 === null ? "-" : Number(item.rsi_14).toFixed(2)}}</span><span>MACD Hist: ${{item.macd_histogram === null ? "-" : Number(item.macd_histogram).toFixed(4)}}</span></div>
            <div class="row"><span>Fiyat: ${{item.last_close === null ? "-" : Number(item.last_close).toFixed(2)}}</span><span>${{escapeHtml(item.rationale)}}</span></div>
          </article>
        `;
      }}).join("");
    }}

    async function loadMarketSignals(forceRefresh) {{
      const refresh = forceRefresh ? "true" : "false";
      const symbols = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "BTCUSD"];
      const query = encodeURIComponent(symbols.join(","));
      const response = await fetch(`/api/v1/market/signals?symbols=${{query}}&days=220&refresh=${{refresh}}`, {{
        headers: authHeaders(),
      }});

      if (response.status === 401 || response.status === 403) {{
        document.getElementById("market-signals").innerHTML = `<div class="muted">Signal kartlari icin aq_token gerekli.</div>`;
        return;
      }}
      if (!response.ok) {{
        document.getElementById("market-signals").innerHTML = `<div class="muted">Signal kartlari yuklenemedi.</div>`;
        return;
      }}

      const payload = await response.json();
      renderSignalCards(payload.items || []);
    }}

    function selectedIntelRegions() {{
      const nodes = Array.from(document.querySelectorAll(".intel-region:checked"));
      return nodes.map((node) => node.value);
    }}

    function renderIntelCards(items) {{
      const container = document.getElementById("intel-cards");
      if (!items || !items.length) {{
        container.innerHTML = `<div class="muted">Oneri bulunamadi.</div>`;
        return;
      }}
      container.innerHTML = items.slice(0, 12).map((item) => {{
        const cls = item.signal === "BUY" ? "signal-buy" : (item.signal === "SELL" ? "signal-sell" : "signal-hold");
        return `
          <article class="signal-card ${{cls}}">
            <div class="row"><strong>${{escapeHtml(item.symbol)}}</strong><strong>${{escapeHtml(item.signal)}}</strong></div>
            <div class="row"><span>Risk: ${{escapeHtml(item.risk_level)}}</span><span>Conf: ${{Number(item.confidence).toFixed(2)}}</span></div>
            <div class="row"><span>${{escapeHtml(item.rationale)}}</span><span>${{escapeHtml(item.suggested_action)}}</span></div>
          </article>
        `;
      }}).join("");
    }}

    async function loadMarketIntelligence(forceRefresh) {{
      const summaryNode = document.getElementById("intel-summary");
      const pagesNode = document.getElementById("intel-pages");
      const regions = selectedIntelRegions();
      if (!regions.length) {{
        summaryNode.textContent = "En az bir bolge secin (TR/EU/GLOBAL).";
        pagesNode.textContent = "";
        return;
      }}

      const selectedSymbol = document.getElementById("market-symbol").value;
      const response = await fetch("/api/v1/market/intelligence", {{
        method: "POST",
        headers: {{
          "Content-Type": "application/json",
          ...authHeaders(),
        }},
        body: JSON.stringify({{
          pages: [],
          include_default_exchange_pages: true,
          regions,
          focus_symbols: [selectedSymbol, "AAPL", "MSFT", "NVDA", "XU100.IS", "DAX.DE", "SPX"],
          timeframe: "1d",
          days: 240,
          refresh: !!forceRefresh,
          max_symbols: 10,
          max_pages: 15,
        }}),
      }});

      if (response.status === 401 || response.status === 403) {{
        summaryNode.textContent = "Market intelligence icin aq_token gerekli (read_market + read_public_sources).";
        pagesNode.textContent = "";
        document.getElementById("intel-cards").innerHTML = `<div class="muted">Yetkisiz</div>`;
        return;
      }}

      if (!response.ok) {{
        summaryNode.textContent = "Market intelligence yuklenemedi.";
        pagesNode.textContent = "";
        document.getElementById("intel-cards").innerHTML = `<div class="muted">Hata</div>`;
        return;
      }}

      const payload = await response.json();
      summaryNode.textContent = payload.executive_summary || "";

      const tags = (payload.pages || [])
        .slice(0, 8)
        .map((item) => {{
          const exchange = item.exchange || item.source_domain || "source";
          const region = item.region || "N/A";
          return `<span class="tag">${{escapeHtml(region)}}:${{escapeHtml(exchange)}}</span>`;
        }})
        .join("");
      pagesNode.innerHTML = tags || "<span class=\"muted\">Kaynak etiketi yok.</span>";
      renderIntelCards(payload.recommendations || []);
    }}

    function renderConnectorJobs(items) {{
      const container = document.getElementById("connector-jobs");
      if (!items || !items.length) {{
        container.innerHTML = `<div class="muted">Queue is bulunamadi.</div>`;
        return;
      }}
      container.innerHTML = items.map((item) => {{
        let cls = "signal-hold";
        if (item.status === "success") cls = "signal-buy";
        if (item.status === "failed" || item.status === "dead_letter") cls = "signal-sell";
        const retryInfo = item.next_retry_at ? `next_retry=${{new Date(item.next_retry_at * 1000).toLocaleTimeString()}}` : "-";
        return `
          <article class="signal-card ${{cls}}">
            <div class="row"><strong>#${{item.id}}</strong><strong>${{escapeHtml(item.company_name)}} / ${{escapeHtml(item.status)}}</strong></div>
            <div class="row"><span>${{escapeHtml(item.connector_type)}}:${{escapeHtml(item.provider)}}</span><span>attempt ${{item.attempt_count}}/${{item.max_attempts}}</span></div>
            <div class="row"><span>retry: ${{escapeHtml(retryInfo)}}</span><span>${{item.error_code ? escapeHtml(item.error_code) : "-"}}</span></div>
          </article>
        `;
      }}).join("");
    }}

    async function loadConnectorHealth() {{
      const summaryNode = document.getElementById("connector-health");
      const jobsNode = document.getElementById("connector-jobs");

      const [healthResponse, jobsResponse] = await Promise.all([
        fetch("/api/v1/connectors/health/summary", {{ headers: authHeaders() }}),
        fetch("/api/v1/connectors/sync-jobs?limit=12", {{ headers: authHeaders() }}),
      ]);

      if (healthResponse.status === 401 || healthResponse.status === 403) {{
        summaryNode.textContent = "Connector health icin aq_token gerekli (read_connectors).";
        jobsNode.innerHTML = `<div class="muted">Yetkisiz</div>`;
        return;
      }}
      if (!healthResponse.ok) {{
        summaryNode.textContent = "Connector health yuklenemedi.";
      }} else {{
        const health = await healthResponse.json();
        summaryNode.textContent = `Connectors=${{health.total_connectors}} | active=${{health.active_connectors}} staged=${{health.staged_connectors}} blocked=${{health.blocked_connectors}} | queued=${{health.queued_jobs}} running=${{health.running_jobs}} dead_letter=${{health.dead_letter_jobs}} due_retry=${{health.due_retry_jobs}} | readiness=${{Number(health.average_readiness_score).toFixed(1)}} security=${{Number(health.average_security_score).toFixed(1)}}`;
      }}

      if (jobsResponse.status === 401 || jobsResponse.status === 403) {{
        jobsNode.innerHTML = `<div class="muted">Queue goruntuleme yetkisi yok.</div>`;
        return;
      }}
      if (!jobsResponse.ok) {{
        jobsNode.innerHTML = `<div class="muted">Queue listesi yuklenemedi.</div>`;
        return;
      }}
      const jobsPayload = await jobsResponse.json();
      renderConnectorJobs(jobsPayload.items || []);
    }}

    async function dispatchConnectorQueue() {{
      const response = await fetch("/api/v1/connectors/sync-jobs/dispatch", {{
        method: "POST",
        headers: {{
          "Content-Type": "application/json",
          ...authHeaders(),
        }},
        body: JSON.stringify({{
          auto_complete: true,
          success: true,
          allow_retry: true,
          retry_backoff_seconds: 60,
        }}),
      }});
      if (response.status === 401 || response.status === 403) {{
        alert("Connector dispatch icin aq_token gerekli (manage_connectors).");
        return;
      }}
      await loadConnectorHealth();
    }}

    async function loadGlobalReport() {{
      const summaryNode = document.getElementById("global-summary");
      const reportNode = document.getElementById("global-report");
      const response = await fetch(
        "/api/v1/global/report?countries=USA,TUR,DEU&bank_symbols=JPM,BAC,HSBC,BNP.PA&index_symbols=SPX,NDX,DAX,XU100",
        {{
          headers: authHeaders(),
        }},
      );

      if (response.status === 401 || response.status === 403) {{
        summaryNode.textContent = "Global rapor icin aq_token gerekli (read_global_intel).";
        reportNode.textContent = "Yetkisiz";
        return;
      }}
      if (!response.ok) {{
        summaryNode.textContent = "Global rapor yuklenemedi.";
        reportNode.textContent = "Hata";
        return;
      }}

      const payload = await response.json();
      summaryNode.textContent = `Risk: ${{payload.risk_level}} | ${{payload.executive_summary}}`;
      reportNode.textContent = payload.report_markdown || "";
    }}

    async function refreshMarketWidgets() {{
      const button = document.getElementById("market-refresh-btn");
      button.disabled = true;
      button.textContent = "Yenileniyor...";
      try {{
        await Promise.all([
          loadMarketChart(true),
          loadMarketSignals(true),
          loadMarketIntelligence(true),
          loadConnectorHealth(),
          loadGlobalReport(),
        ]);
      }} finally {{
        button.disabled = false;
        button.textContent = "Market Yenile";
      }}
    }}

    document.getElementById("market-symbol").addEventListener("change", () => {{
      loadMarketChart(false);
    }});

    loadMarketChart(false);
    loadMarketSignals(false);
    loadMarketIntelligence(false);
    loadConnectorHealth();
    loadGlobalReport();
    setInterval(() => {{
      loadMarketChart(false);
      loadMarketSignals(false);
      loadConnectorHealth();
    }}, 30000);
    setInterval(() => {{
      loadMarketIntelligence(false);
      loadGlobalReport();
    }}, 180000);
  </script>
</body>
</html>"""


def _render_company_card(company: Company, analysis: AnalysisResult) -> str:
    inventory_rows = "".join(
        _render_inventory_line(item.name, item.quantity, item.min_level)
        for item in company.inventory
    )
    status_class = "critical" if analysis.status == "Riskli" else "ok"

    return f"""
      <article class="card">
        <h3>{escape(company.name)}</h3>
        <div class="line"><span>Bakiye</span><strong>{company.balance:,.0f}</strong></div>
        <div class="line"><span>Risk Skoru</span><strong>{analysis.risk_score}/100</strong></div>
        <div class="line"><span>Durum</span><strong class="{status_class}">{escape(analysis.status)}</strong></div>
        <div class="line"><span>Trend</span><strong>{escape(analysis.trend)}</strong></div>
        <div class="line"><span>Oncelikli Aksiyon</span><strong>{escape(analysis.action)}</strong></div>
        <ul class="inventory">
          {inventory_rows}
        </ul>
      </article>
    """


def _render_inventory_line(name: str, quantity: int, min_level: int) -> str:
    is_critical = quantity <= min_level
    css_class = "critical" if is_critical else "ok"
    label = "Kritik" if is_critical else "Normal"
    return (
        f'<li class="{css_class}">{escape(name)}: {label} ({quantity}) '
        f'- Min: {min_level}</li>'
    )


def _render_insight_item(item: InsightItem) -> str:
    severity_class = "critical" if item.severity == "HIGH" else "ok"
    return (
        f'<li style="margin-bottom:0.45rem;">'
        f'<strong class="{severity_class}">{escape(item.severity)}</strong> '
        f'<strong>{escape(item.company)}</strong>: {escape(item.message)} '
        f'| Action: {escape(item.action)} '
        f'| Confidence: {item.confidence:.2f}'
        f"</li>"
    )
