"""A5.4: CRM router (extracted from app/api.py).

10 endpoint covering customers + proposals + risk score + KVKK consent:

Customers (4):
- POST   /api/v1/crm/customers
- GET    /api/v1/crm/customers                  (company scope filter)
- GET    /api/v1/crm/customers/{customer_id}
- PATCH  /api/v1/crm/customers/{customer_id}

Risk score (1, S-333):
- GET    /api/v1/crm/customers/{customer_id}/risk-score

Proposals (4):
- POST   /api/v1/crm/proposals
- GET    /api/v1/crm/proposals                  (company/customer/status filters)
- GET    /api/v1/crm/proposals/summary
- PATCH  /api/v1/crm/proposals/{proposal_id}

KVKK consent (1, S-343):
- PATCH  /api/v1/crm/customers/{customer_id}/consent

RBAC: read_finance (list/get), write_finance (mutate). Tüm endpoint'ler
`_ensure_company_scope` ile çoklu-şirket koruması sağlar.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.models import (
    CustomerConsentUpdateRequest,
    CustomerCreateRequest,
    CustomerListResponse,
    CustomerRead,
    CustomerRiskScoreResponse,
    CustomerUpdateRequest,
    ProposalCreateRequest,
    ProposalListResponse,
    ProposalRead,
    ProposalStatusUpdateRequest,
    ProposalSummaryResponse,
    UserProfile,
)
from app.routers._deps import (
    _collections_engine,
    _crm_engine,
    _ensure_company_scope,
    _is_holding_scope,
)
from app.security import require_permissions


router = APIRouter()


# ── Customers (S-321) ────────────────────────────────────────────────────────


@router.post(
    "/api/v1/crm/customers",
    response_model=CustomerRead,
    status_code=201,
    tags=["crm"],
)
def create_customer(
    payload: CustomerCreateRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("write_finance")),
) -> CustomerRead:
    _ensure_company_scope(request, user, payload.company)
    return _crm_engine(request).create_customer(payload=payload)


@router.get(
    "/api/v1/crm/customers",
    response_model=CustomerListResponse,
    tags=["crm"],
)
def list_customers(
    request: Request,
    company: str | None = Query(default=None),
    active_only: bool = Query(default=True),
    limit: int = Query(default=200, ge=1, le=1000),
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> CustomerListResponse:
    if company:
        _ensure_company_scope(request, user, company)
    elif not _is_holding_scope(request, user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scoped users must provide company parameter",
        )
    return _crm_engine(request).list_customers(
        company=company, active_only=active_only, limit=limit
    )


@router.get(
    "/api/v1/crm/customers/{customer_id}",
    response_model=CustomerRead,
    tags=["crm"],
)
def get_customer(
    customer_id: int,
    request: Request,
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> CustomerRead:
    result = _crm_engine(request).get_customer(customer_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    _ensure_company_scope(request, user, result.company)
    return result


@router.patch(
    "/api/v1/crm/customers/{customer_id}",
    response_model=CustomerRead,
    tags=["crm"],
)
def update_customer(
    customer_id: int,
    payload: CustomerUpdateRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("write_finance")),
) -> CustomerRead:
    existing = _crm_engine(request).get_customer(customer_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    _ensure_company_scope(request, user, existing.company)
    result = _crm_engine(request).update_customer(customer_id, payload=payload)
    if result is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return result


# ── Risk score (S-333) ───────────────────────────────────────────────────────


@router.get(
    "/api/v1/crm/customers/{customer_id}/risk-score",
    response_model=CustomerRiskScoreResponse,
    tags=["crm"],
)
def customer_risk_score(
    customer_id: int,
    request: Request,
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> CustomerRiskScoreResponse:
    """S-333 — 0-100 payment-reliability score derived from invoice history."""
    customer = _crm_engine(request).get_customer(customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    _ensure_company_scope(request, user, customer.company)
    return _collections_engine(request).customer_risk_score(
        customer_id=customer.id,
        customer_name=customer.full_name,
        company=customer.company,
    )


# ── Proposals (S-321) ────────────────────────────────────────────────────────


@router.post(
    "/api/v1/crm/proposals",
    response_model=ProposalRead,
    status_code=201,
    tags=["crm"],
)
def create_proposal(
    payload: ProposalCreateRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("write_finance")),
) -> ProposalRead:
    _ensure_company_scope(request, user, payload.company)
    return _crm_engine(request).create_proposal(payload=payload)


@router.get(
    "/api/v1/crm/proposals",
    response_model=ProposalListResponse,
    tags=["crm"],
)
def list_proposals(
    request: Request,
    company: str | None = Query(default=None),
    customer_id: int | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=200, ge=1, le=1000),
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> ProposalListResponse:
    if company:
        _ensure_company_scope(request, user, company)
    elif not _is_holding_scope(request, user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scoped users must provide company parameter",
        )
    return _crm_engine(request).list_proposals(
        company=company, customer_id=customer_id, status=status_filter, limit=limit
    )


@router.get(
    "/api/v1/crm/proposals/summary",
    response_model=ProposalSummaryResponse,
    tags=["crm"],
)
def proposal_summary(
    request: Request,
    company: str | None = Query(default=None),
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> ProposalSummaryResponse:
    if company:
        _ensure_company_scope(request, user, company)
    elif not _is_holding_scope(request, user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scoped users must provide company parameter",
        )
    return _crm_engine(request).proposal_summary(company=company)


@router.patch(
    "/api/v1/crm/proposals/{proposal_id}",
    response_model=ProposalRead,
    tags=["crm"],
)
def update_proposal_status(
    proposal_id: int,
    payload: ProposalStatusUpdateRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("write_finance")),
) -> ProposalRead:
    existing = _crm_engine(request).get_proposal(proposal_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    _ensure_company_scope(request, user, existing.company)
    result = _crm_engine(request).update_proposal_status(proposal_id, payload=payload)
    if result is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return result


# ── KVKK consent (S-343) ─────────────────────────────────────────────────────


@router.patch(
    "/api/v1/crm/customers/{customer_id}/consent",
    response_model=CustomerRead,
    tags=["crm"],
)
def update_customer_consent(
    customer_id: int,
    payload: CustomerConsentUpdateRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("write_finance")),
) -> CustomerRead:
    """S-343 — Update per-channel KVKK consent flags on a customer."""
    existing = _crm_engine(request).get_customer(customer_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    _ensure_company_scope(request, user, existing.company)
    result = _crm_engine(request).update_consent(
        customer_id,
        email_consent=payload.email_consent,
        sms_consent=payload.sms_consent,
        whatsapp_consent=payload.whatsapp_consent,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return result
