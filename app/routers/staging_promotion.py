"""I2: Staging promotion router."""
from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, Query, Request

from app.engines.staging_promotion_engine import StagingPromotionEngine
from app.models import (
    PromotionPlanRecord,
    PromotionPlanResponse,
    PromotionPreviewRequest,
    PromotionResultResponse,
    StagedRecord,
    StagingListResponse,
    UserProfile,
)
from app.routers._deps import _value_error_to_http
from app.security import require_permissions


router = APIRouter()


def _engine(request: Request) -> StagingPromotionEngine:
    return cast(
        StagingPromotionEngine,
        request.app.state.staging_promotion_engine,
    )


@router.get(
    "/api/v1/connectors/staging",
    response_model=StagingListResponse,
    tags=["connectors"],
)
def list_staging(
    request: Request,
    limit: int = Query(default=200, ge=1, le=2000),
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> StagingListResponse:
    """Logo'dan stage edilmiş ham kayıtlar."""
    data = _engine(request).list_staged(user_id=user.username, limit=limit)
    return StagingListResponse(
        customers=[StagedRecord(**c) for c in data["customers"]],
        invoices=[StagedRecord(**i) for i in data["invoices"]],
        customer_count=data["customer_count"],
        invoice_count=data["invoice_count"],
    )


@router.post(
    "/api/v1/connectors/staging/preview",
    response_model=PromotionPlanResponse,
    tags=["connectors"],
)
def preview_promotion(
    payload: PromotionPreviewRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_finance")),
) -> PromotionPlanResponse:
    """Dry-run: stage → gerçek tablolarda ne olur?"""
    try:
        plan = _engine(request).preview_promotion(
            user_id=user.username,
            company_name=payload.company_name,
            policy=payload.policy,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc
    return PromotionPlanResponse(
        new_customers=plan.new_customers,
        new_invoices=plan.new_invoices,
        conflict_customers=plan.conflict_customers,
        conflict_invoices=plan.conflict_invoices,
        already_promoted_customers=plan.already_promoted_customers,
        already_promoted_invoices=plan.already_promoted_invoices,
        ledger_entries_to_create=plan.ledger_entries_to_create,
        customer_details=[
            PromotionPlanRecord(**d) for d in (plan.customer_details or [])
        ],
        invoice_details=[
            PromotionPlanRecord(**d) for d in (plan.invoice_details or [])
        ],
    )


@router.post(
    "/api/v1/connectors/staging/promote",
    response_model=PromotionResultResponse,
    tags=["connectors"],
)
def promote_records(
    payload: PromotionPreviewRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_finance")),
) -> PromotionResultResponse:
    """Stage → gerçek tablolar. Idempotent: 2× çağrı 0 yeni kayıt."""
    try:
        result = _engine(request).promote(
            user_id=user.username,
            company_name=payload.company_name,
            policy=payload.policy,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc
    return PromotionResultResponse(
        customers_created=result.customers_created,
        customers_updated=result.customers_updated,
        customers_skipped=result.customers_skipped,
        invoices_created=result.invoices_created,
        invoices_skipped=result.invoices_skipped,
        ledger_entries_created=result.ledger_entries_created,
        errors=result.errors or [],
    )
