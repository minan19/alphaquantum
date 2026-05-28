"""A5.12 (part 1): Financial instruments router (S-342, extracted from api.py).

5 endpoint covering senet (promissory note), çek (check), bono (bond) tracking:

- POST  /api/v1/financial-instruments                       (create)
- GET   /api/v1/financial-instruments                       (filtered list)
- GET   /api/v1/financial-instruments/summary               (status summary)
- GET   /api/v1/financial-instruments/{instrument_id}       (detail)
- PATCH /api/v1/financial-instruments/{instrument_id}       (status update)

RBAC: read_finance (queries), write_finance (mutations).
List filters: company, kind (senet|cek|bono), status (pending|cleared|bounced|cancelled), customer_id.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.models import (
    FinancialInstrumentCreateRequest,
    FinancialInstrumentListResponse,
    FinancialInstrumentRead,
    FinancialInstrumentStatusUpdateRequest,
    FinancialInstrumentSummaryResponse,
    UserProfile,
)
from app.routers._deps import (
    _ensure_company_scope,
    _financial_instrument_engine,
    _is_holding_scope,
)
from app.security import require_permissions


router = APIRouter()


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
    instr_status: str | None = Query(
        default=None,
        alias="status",
        pattern="^(pending|cleared|bounced|cancelled)$",
    ),
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
        company=company,
        kind=kind,
        status=instr_status,
        customer_id=customer_id,
        limit=limit,
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
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Instrument not found")
    return result
