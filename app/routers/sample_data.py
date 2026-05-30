"""OBS1: Sample data seed router — empty state'in karanlığını kır."""
from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, Request

from app.engines.sample_data_engine import SampleDataEngine
from app.models import (
    SampleDataClearResponse,
    SampleDataSeedRequest,
    SampleDataSeedResponse,
    SampleDataStatusResponse,
    UserProfile,
)
from app.security import require_permissions


router = APIRouter()


def _engine(request: Request) -> SampleDataEngine:
    return cast(SampleDataEngine, request.app.state.sample_data_engine)


@router.get(
    "/api/v1/sample-data/status",
    response_model=SampleDataStatusResponse,
    tags=["onboarding"],
)
def get_sample_status(
    request: Request,
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> SampleDataStatusResponse:
    """Sample data zaten yüklenmiş mi?"""
    return SampleDataStatusResponse(
        has_sample_data=_engine(request).has_sample_data(user_id=user.username),
    )


@router.post(
    "/api/v1/sample-data/seed",
    response_model=SampleDataSeedResponse,
    tags=["onboarding"],
)
def seed_sample_data(
    payload: SampleDataSeedRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_finance")),
) -> SampleDataSeedResponse:
    """Yeni kullanıcı için demo veri oluştur. Idempotent."""
    summary = _engine(request).seed(
        user_id=user.username,
        company_name=payload.company_name,
    )
    return SampleDataSeedResponse(
        customers_created=summary.customers_created,
        invoices_created=summary.invoices_created,
        ledger_entries_created=summary.ledger_entries_created,
        anomaly_signals_created=summary.anomaly_signals_created,
        already_seeded=summary.already_seeded,
    )


@router.delete(
    "/api/v1/sample-data",
    response_model=SampleDataClearResponse,
    tags=["onboarding"],
)
def clear_sample_data(
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_finance")),
) -> SampleDataClearResponse:
    """Sample data'yı temizle (gerçek user data'sına dokunmaz)."""
    result = _engine(request).clear(user_id=user.username)
    return SampleDataClearResponse(**result)
