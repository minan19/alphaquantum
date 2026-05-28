"""A5.11: Procurement + Tender + Feasibility router (extracted from app/api.py).

13 endpoint covering the B2B operations pipeline — request → quote →
evaluation → purchase order, plus tender dossier generation and
feasibility reports:

Procurement requests (3):
- POST /api/v1/procurement/requests                            (create)
- GET  /api/v1/procurement/requests                            (scope-filtered)
- GET  /api/v1/procurement/requests/{request_id}               (detail)

Procurement from tender (1):
- POST /api/v1/procurement/requests/from-tender                (composite RBAC)

Quotes (2):
- POST /api/v1/procurement/quotes                              (submit)
- GET  /api/v1/procurement/requests/{id}/quotes                (list per request)

Evaluation + purchase orders (3):
- GET  /api/v1/procurement/requests/{id}/evaluation
- POST /api/v1/procurement/requests/{id}/purchase-orders/auto  (approve_procurement)
- GET  /api/v1/procurement/requests/{id}/purchase-orders

Feasibility (3):
- POST /api/v1/feasibility/report                              (write_feasibility)
- GET  /api/v1/feasibility/reports                             (read_feasibility)
- GET  /api/v1/feasibility/reports/{report_id}

Tender (1):
- POST /api/v1/tender/generate                                 (prepare_tender_docs)

RBAC tablosu:
- read/write_procurement, approve_procurement (PO),
  read/write_feasibility, prepare_tender_docs
- procurement/from-tender composite: write_procurement + prepare_tender_docs

`_ensure_company_scope` her endpoint'te; list endpoint'leri scope-filtered output.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.models import (
    FeasibilityReportListResponse,
    FeasibilityReportRequest,
    FeasibilityReportStoredResponse,
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
    UserProfile,
)
from app.routers._deps import (
    _ensure_company_scope,
    _feasibility_engine,
    _is_holding_scope,
    _procurement_engine,
    _tender_engine,
    _user_has_company_scope,
    _value_error_to_http,
)
from app.security import require_permissions


router = APIRouter()


# ── Procurement requests ─────────────────────────────────────────────────────


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
        raise _value_error_to_http(exc) from exc


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
        raise _value_error_to_http(exc) from exc
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
    user: UserProfile = Depends(
        require_permissions("write_procurement", "prepare_tender_docs")
    ),
) -> ProcurementTenderPlanResponse:
    _ensure_company_scope(request, user, payload.tender.company_name)
    try:
        return _procurement_engine(request).create_request_from_tender(payload)
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


# ── Quotes ───────────────────────────────────────────────────────────────────


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
        raise _value_error_to_http(exc) from exc
    _ensure_company_scope(request, user, target_request.company)

    try:
        return _procurement_engine(request).submit_quote(payload)
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


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
        raise _value_error_to_http(exc) from exc


# ── Evaluation + Purchase orders ─────────────────────────────────────────────


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
        raise _value_error_to_http(exc) from exc


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
        return _procurement_engine(request).create_auto_purchase_orders(
            request_id, payload
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


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
        raise _value_error_to_http(exc) from exc


# ── Feasibility ──────────────────────────────────────────────────────────────


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
        raise _value_error_to_http(exc) from exc


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
        return _feasibility_engine(request).list_reports(
            limit=limit, sector=sector, company_name=company
        )
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
        raise _value_error_to_http(exc) from exc
    if result.company_name:
        _ensure_company_scope(request, user, result.company_name)
    elif not _is_holding_scope(request, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Scoped users cannot access unscoped feasibility reports",
        )
    return result


# ── Tender ───────────────────────────────────────────────────────────────────


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
