"""A5.13 (part 2): Reports router — signed file exports.

4 endpoint covering ledger + budget-vs-actual file exports (XLSX/PDF):

- GET /api/v1/reports/finance/ledger.xlsx
- GET /api/v1/reports/finance/ledger.pdf
- GET /api/v1/reports/finance/budget-vs-actual.xlsx
- GET /api/v1/reports/finance/budget-vs-actual.pdf

Tüm export'lar HMAC-SHA256 imzalı (`X-Export-Signature` header) — client
tamper detection için. Aynı `_build_export_response` helper'ı invoice PDF
(collections.py) ile paylaşılıyor (A5.6'da _deps.py'a alındı).

RBAC: read_finance (queries). `_ensure_company_scope` per-call.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response

from app.models import FinanceBudgetVsActualResponse, UserProfile
from app.routers._deps import (
    _build_export_response,
    _ensure_company_scope,
    _finance_engine,
    _is_holding_scope,
    _reporting_engine,
)
from app.security import require_permissions


router = APIRouter()


# ── Ledger exports ───────────────────────────────────────────────────────────


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
        content,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "finance_ledger.xlsx",
        request.app.state.settings.jwt_secret,
        reporting,
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
        content,
        "application/pdf",
        "finance_ledger.pdf",
        request.app.state.settings.jwt_secret,
        reporting,
    )


# ── Budget vs Actual exports ─────────────────────────────────────────────────


def _budget_vs_actual_payload(
    report: FinanceBudgetVsActualResponse,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Convert engine report to (items, totals) tuple — shared by XLSX/PDF."""
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
    return items, totals


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
    items, totals = _budget_vs_actual_payload(report)
    reporting = _reporting_engine(request)
    content = reporting.budget_vs_actual_to_xlsx(
        company=company, year=year, month=month, items=items, totals=totals
    )
    return _build_export_response(
        content,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "budget_vs_actual.xlsx",
        request.app.state.settings.jwt_secret,
        reporting,
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
    items, totals = _budget_vs_actual_payload(report)
    reporting = _reporting_engine(request)
    content = reporting.budget_vs_actual_to_pdf(
        company=company, year=year, month=month, items=items, totals=totals
    )
    return _build_export_response(
        content,
        "application/pdf",
        "budget_vs_actual.pdf",
        request.app.state.settings.jwt_secret,
        reporting,
    )
