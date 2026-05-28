"""A5.6: Collections / Invoices router (extracted from app/api.py).

7 endpoint covering invoice CRUD, payment, receivables summary, FX exposure:

Invoices (5):
- POST /api/v1/collections/invoices                       (S-323)
- GET  /api/v1/collections/invoices                       (5 query filter)
- GET  /api/v1/collections/invoices/{invoice_id}
- GET  /api/v1/collections/invoices/{invoice_id}/pdf      (QW-2, HMAC signed)
- POST /api/v1/collections/invoices/{invoice_id}/payment  (S-323)

Summaries (2):
- GET  /api/v1/collections/summary                        (S-331 receivables)
- GET  /api/v1/collections/fx-summary                     (S-341 FX exposure)

RBAC: read_finance (list/summary/get/pdf), write_finance (create/payment).
PDF export uses `_build_export_response` from _deps.py with HMAC-SHA256.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response

from app.models import (
    FxReceivablesSummaryResponse,
    InvoiceCreateRequest,
    InvoiceListResponse,
    InvoicePaymentRequest,
    InvoiceRead,
    ReceivablesSummaryResponse,
    UserProfile,
)
from app.routers._deps import (
    _build_export_response,
    _collections_engine,
    _ensure_company_scope,
    _is_holding_scope,
    _reporting_engine,
)
from app.security import require_permissions


router = APIRouter()


# ── Invoices (S-323) ─────────────────────────────────────────────────────────


@router.post(
    "/api/v1/collections/invoices",
    response_model=InvoiceRead,
    status_code=201,
    tags=["collections"],
)
def create_invoice(
    payload: InvoiceCreateRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("write_finance")),
) -> InvoiceRead:
    _ensure_company_scope(request, user, payload.company)
    return _collections_engine(request).create_invoice(payload=payload)


@router.get(
    "/api/v1/collections/invoices",
    response_model=InvoiceListResponse,
    tags=["collections"],
)
def list_invoices(
    request: Request,
    company: str | None = Query(default=None),
    customer_id: int | None = Query(default=None),
    inv_status: str | None = Query(default=None, alias="status"),
    overdue_only: bool = Query(default=False),
    limit: int = Query(default=200, ge=1, le=1000),
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> InvoiceListResponse:
    if company:
        _ensure_company_scope(request, user, company)
    elif not _is_holding_scope(request, user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scoped users must provide company parameter",
        )
    return _collections_engine(request).list_invoices(
        company=company,
        customer_id=customer_id,
        status=inv_status,
        overdue_only=overdue_only,
        limit=limit,
    )


@router.get(
    "/api/v1/collections/invoices/{invoice_id}",
    response_model=InvoiceRead,
    tags=["collections"],
)
def get_invoice(
    invoice_id: int,
    request: Request,
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> InvoiceRead:
    result = _collections_engine(request).get_invoice(invoice_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    _ensure_company_scope(request, user, result.company)
    return result


@router.get(
    "/api/v1/collections/invoices/{invoice_id}/pdf",
    tags=["collections"],
    response_class=Response,
)
def export_invoice_pdf(
    invoice_id: int,
    request: Request,
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> Response:
    """QW-2 — İmzalı tek fatura PDF'i. Müşteriye iletmeye uygun, audit'lenebilir."""
    existing = _collections_engine(request).get_invoice(invoice_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    _ensure_company_scope(request, user, existing.company)
    invoice_row = request.app.state.invoice_repository.get_invoice(invoice_id)
    customer_row = None
    if invoice_row and invoice_row.get("customer_id"):
        customer_row = request.app.state.crm_repository.get_customer(
            int(invoice_row["customer_id"])
        )
    reporting = _reporting_engine(request)
    pdf_bytes = reporting.invoice_to_pdf(invoice_row, customer=customer_row)
    filename = f"invoice_{invoice_row.get('invoice_number') or invoice_id}.pdf"
    return _build_export_response(
        pdf_bytes,
        "application/pdf",
        filename,
        request.app.state.settings.jwt_secret,
        reporting,
    )


@router.post(
    "/api/v1/collections/invoices/{invoice_id}/payment",
    response_model=InvoiceRead,
    tags=["collections"],
)
def record_payment(
    invoice_id: int,
    payload: InvoicePaymentRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("write_finance")),
) -> InvoiceRead:
    existing = _collections_engine(request).get_invoice(invoice_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    _ensure_company_scope(request, user, existing.company)
    result = _collections_engine(request).record_payment(
        invoice_id, payload=payload
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return result


# ── Receivables summaries (S-331 / S-341) ────────────────────────────────────


@router.get(
    "/api/v1/collections/summary",
    response_model=ReceivablesSummaryResponse,
    tags=["collections"],
)
def receivables_summary(
    request: Request,
    company: str | None = Query(default=None),
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> ReceivablesSummaryResponse:
    if company:
        _ensure_company_scope(request, user, company)
    elif not _is_holding_scope(request, user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scoped users must provide company parameter",
        )
    return _collections_engine(request).receivables_summary(company=company)


@router.get(
    "/api/v1/collections/fx-summary",
    response_model=FxReceivablesSummaryResponse,
    tags=["collections"],
)
def fx_receivables_summary(
    request: Request,
    company: str | None = Query(default=None),
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> FxReceivablesSummaryResponse:
    """S-341 — FX-aware outstanding receivables: per-currency breakdown +
    TRY-normalized total + share of foreign-currency exposure."""
    if company:
        _ensure_company_scope(request, user, company)
    elif not _is_holding_scope(request, user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scoped users must provide company parameter",
        )
    return _collections_engine(request).fx_aware_receivables_summary(
        company=company
    )
