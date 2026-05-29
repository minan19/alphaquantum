"""VR1: Vendor risk scoring router."""
from __future__ import annotations

from dataclasses import asdict
from typing import cast

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from app.engines.vendor_risk_engine import VendorRiskEngine
from app.models import UserProfile
from app.routers._deps import _value_error_to_http
from app.security import require_permissions


router = APIRouter()


class VendorRiskResponse(BaseModel):
    vkn: str
    composite_score: int = Field(ge=0, le=100)
    severity: str = Field(pattern="^(low|medium|high|critical)$")
    is_taxpayer_active: bool
    credit_rating: str
    internal_payment_history_score: int = Field(ge=0, le=100)
    anomaly_signal_count: int = Field(ge=0)
    recommendations: list[str]


def _engine(request: Request) -> VendorRiskEngine:
    return cast(VendorRiskEngine, request.app.state.vendor_risk_engine)


@router.get(
    "/api/v1/vendors/risk-score",
    response_model=VendorRiskResponse,
    tags=["vendors"],
)
def score_vendor(
    request: Request,
    vkn: str = Query(..., min_length=10, max_length=15),
    counterparty_name: str | None = Query(default=None, max_length=200),
    _user: UserProfile = Depends(require_permissions("read_finance")),
) -> VendorRiskResponse:
    """Tedarikçi VKN için risk skoru üret (mock GİB/KKB + internal ledger)."""
    try:
        score = _engine(request).score_vendor(
            vkn=vkn, counterparty_name=counterparty_name,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc
    return VendorRiskResponse(**asdict(score))
