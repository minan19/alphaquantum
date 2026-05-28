"""A5.7: Finance router (extracted from app/api.py).

12 endpoint covering cashflow projection + finance engine operations:

Cashflow projection (1, S-332):
- GET  /api/v1/finance/cashflow-projection            (forward 30/60/90 day)

Overview (1):
- GET  /api/v1/finance-engine/overview                (scope-filtered)

Ledger (2):
- POST /api/v1/finance-engine/ledger                  (create entry)
- GET  /api/v1/finance-engine/ledger                  (list, date range filter)

Cashflow + forecast (2):
- GET  /api/v1/finance-engine/cashflow                (lookback aggregation)
- GET  /api/v1/finance-engine/forecast                (forward forecast)

Recurring entries (3):
- POST /api/v1/finance-engine/recurring               (create template)
- GET  /api/v1/finance-engine/recurring               (list, active filter)
- POST /api/v1/finance-engine/recurring/generate      (bulk generate due)

Budgets (3):
- POST /api/v1/finance-engine/budgets                 (create)
- GET  /api/v1/finance-engine/budgets                 (year/month filter)
- GET  /api/v1/finance-engine/budget-vs-actual        (variance analysis)

RBAC: read_finance (queries), write_finance (mutations).
`_ensure_company_scope` per endpoint; recurring/generate sadece holding-scope.
ValueError → `_value_error_to_http` (404 if "not found", else 400).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.models import (
    CashflowProjectionResponse,
    FinanceBudgetCreateRequest,
    FinanceBudgetListResponse,
    FinanceBudgetRead,
    FinanceBudgetVsActualResponse,
    FinanceCashflowResponse,
    FinanceForecastResponse,
    FinanceLedgerEntryCreateRequest,
    FinanceLedgerEntryRead,
    FinanceLedgerResponse,
    FinanceOverviewResponse,
    FinanceRecurringEntryCreateRequest,
    FinanceRecurringEntryRead,
    FinanceRecurringGenerateResponse,
    FinanceRecurringListResponse,
    UserProfile,
)
from app.routers._deps import (
    _collections_engine,
    _ensure_company_scope,
    _filter_companies_by_user_scope,
    _finance_engine,
    _is_holding_scope,
    _repo,
    _value_error_to_http,
)
from app.security import require_permissions


router = APIRouter()


# ── Cashflow projection (S-332) ──────────────────────────────────────────────


@router.get(
    "/api/v1/finance/cashflow-projection",
    response_model=CashflowProjectionResponse,
    tags=["finance"],
)
def cashflow_projection(
    request: Request,
    company: str | None = Query(default=None),
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> CashflowProjectionResponse:
    """S-332 — 30/60/90-day forward cashflow projection.

    Combines pending/partial invoices (expected income) with active recurring
    expenses (expected outflows) to produce a 90-day outlook in three 30-day
    buckets. Uses CollectionsEngine (not FinanceEngine) because the invoice
    side dominates; recurring expenses come from `finance_repository`.
    """
    if company:
        _ensure_company_scope(request, user, company)
    elif not _is_holding_scope(request, user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scoped users must provide company parameter",
        )
    finance_repo = request.app.state.finance_repository
    recurring_rows = finance_repo.list_recurring_entries(
        company_name=company, active_only=True
    )
    return _collections_engine(request).cashflow_projection(
        company=company,
        recurring_rows=recurring_rows,
    )


# ── Finance engine overview ──────────────────────────────────────────────────


@router.get(
    "/api/v1/finance-engine/overview",
    response_model=FinanceOverviewResponse,
    tags=["finance_engine"],
)
def finance_engine_overview(
    request: Request,
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> FinanceOverviewResponse:
    companies = _filter_companies_by_user_scope(
        request,
        user,
        _repo(request).list_companies(),
    )
    return _finance_engine(request).build_overview(companies)


# ── Ledger (CRUD) ────────────────────────────────────────────────────────────


@router.post(
    "/api/v1/finance-engine/ledger",
    response_model=FinanceLedgerEntryRead,
    status_code=201,
    tags=["finance_engine"],
)
def create_finance_ledger_entry(
    payload: FinanceLedgerEntryCreateRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("write_finance")),
) -> FinanceLedgerEntryRead:
    _ensure_company_scope(request, user, payload.company)
    try:
        return _finance_engine(request).create_ledger_entry(payload=payload)
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


@router.get(
    "/api/v1/finance-engine/ledger",
    response_model=FinanceLedgerResponse,
    tags=["finance_engine"],
)
def list_finance_ledger_entries(
    request: Request,
    company: str | None = Query(default=None),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> FinanceLedgerResponse:
    if company:
        _ensure_company_scope(request, user, company)
    elif not _is_holding_scope(request, user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scoped users must provide company parameter",
        )
    try:
        return _finance_engine(request).list_ledger_entries(
            company=company,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


# ── Cashflow + forecast ──────────────────────────────────────────────────────


@router.get(
    "/api/v1/finance-engine/cashflow",
    response_model=FinanceCashflowResponse,
    tags=["finance_engine"],
)
def finance_cashflow(
    request: Request,
    company: str | None = Query(default=None),
    lookback_days: int = Query(default=30, ge=1, le=365),
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> FinanceCashflowResponse:
    if company:
        _ensure_company_scope(request, user, company)
    elif not _is_holding_scope(request, user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scoped users must provide company parameter",
        )
    try:
        return _finance_engine(request).build_cashflow(
            company=company,
            lookback_days=lookback_days,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


@router.get(
    "/api/v1/finance-engine/forecast",
    response_model=FinanceForecastResponse,
    tags=["finance_engine"],
)
def finance_forecast(
    request: Request,
    company: str | None = Query(default=None),
    lookback_days: int = Query(default=30, ge=1, le=365),
    horizon_days: int = Query(default=30, ge=1, le=365),
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> FinanceForecastResponse:
    if company:
        _ensure_company_scope(request, user, company)
    elif not _is_holding_scope(request, user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scoped users must provide company parameter",
        )
    companies = _filter_companies_by_user_scope(
        request,
        user,
        _repo(request).list_companies(),
    )
    try:
        return _finance_engine(request).forecast_cashflow(
            companies=companies,
            company=company,
            lookback_days=lookback_days,
            horizon_days=horizon_days,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


# ── Recurring entries ────────────────────────────────────────────────────────


@router.post(
    "/api/v1/finance-engine/recurring",
    response_model=FinanceRecurringEntryRead,
    tags=["finance_engine"],
    status_code=status.HTTP_201_CREATED,
)
def create_recurring_entry(
    request: Request,
    payload: FinanceRecurringEntryCreateRequest,
    user: UserProfile = Depends(require_permissions("write_finance")),
) -> FinanceRecurringEntryRead:
    _ensure_company_scope(request, user, payload.company)
    return _finance_engine(request).create_recurring_entry(payload=payload)


@router.get(
    "/api/v1/finance-engine/recurring",
    response_model=FinanceRecurringListResponse,
    tags=["finance_engine"],
)
def list_recurring_entries(
    request: Request,
    company: str | None = Query(default=None),
    active_only: bool = Query(default=True),
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> FinanceRecurringListResponse:
    if company:
        _ensure_company_scope(request, user, company)
    elif not _is_holding_scope(request, user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scoped users must provide company parameter",
        )
    return _finance_engine(request).list_recurring_entries(
        company=company, active_only=active_only
    )


@router.post(
    "/api/v1/finance-engine/recurring/generate",
    response_model=FinanceRecurringGenerateResponse,
    tags=["finance_engine"],
)
def generate_due_recurring_entries(
    request: Request,
    as_of_date: str | None = Query(default=None),
    user: UserProfile = Depends(require_permissions("write_finance")),
) -> FinanceRecurringGenerateResponse:
    if not _is_holding_scope(request, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only holding-scope users can trigger bulk recurring generation",
        )
    try:
        return _finance_engine(request).generate_due_entries(
            as_of_date=as_of_date
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


# ── Budgets ──────────────────────────────────────────────────────────────────


@router.post(
    "/api/v1/finance-engine/budgets",
    response_model=FinanceBudgetRead,
    tags=["finance_engine"],
    status_code=status.HTTP_201_CREATED,
)
def create_budget(
    request: Request,
    payload: FinanceBudgetCreateRequest,
    user: UserProfile = Depends(require_permissions("write_finance")),
) -> FinanceBudgetRead:
    _ensure_company_scope(request, user, payload.company)
    return _finance_engine(request).create_budget(payload=payload)


@router.get(
    "/api/v1/finance-engine/budgets",
    response_model=FinanceBudgetListResponse,
    tags=["finance_engine"],
)
def list_budgets(
    request: Request,
    company: str | None = Query(default=None),
    year: int | None = Query(default=None),
    month: int | None = Query(default=None, ge=1, le=12),
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> FinanceBudgetListResponse:
    if company:
        _ensure_company_scope(request, user, company)
    elif not _is_holding_scope(request, user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scoped users must provide company parameter",
        )
    return _finance_engine(request).list_budgets(
        company=company, year=year, month=month
    )


@router.get(
    "/api/v1/finance-engine/budget-vs-actual",
    response_model=FinanceBudgetVsActualResponse,
    tags=["finance_engine"],
)
def budget_vs_actual(
    request: Request,
    year: int = Query(..., ge=2000, le=2100),
    company: str | None = Query(default=None),
    month: int | None = Query(default=None, ge=1, le=12),
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> FinanceBudgetVsActualResponse:
    if company:
        _ensure_company_scope(request, user, company)
    elif not _is_holding_scope(request, user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scoped users must provide company parameter",
        )
    return _finance_engine(request).budget_vs_actual(
        company=company, year=year, month=month
    )
