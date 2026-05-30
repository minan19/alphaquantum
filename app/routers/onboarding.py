"""BZ1: Onboarding router — self-service aktivasyon endpoint'leri.

2 endpoint:
  - GET  /api/v1/onboarding/status  (kullanıcının onboarded mı?)
  - POST /api/v1/onboarding/complete (4 adım tek-shot submission)

RBAC: tüm authenticated kullanıcılar erişebilir (read_finance permission).
Onboarding zaten ilk kullanım — kapsamlı permission gerek yok.

Audit log:
  - "onboarding.completed" event'i G+4 hash chain'e yazılır
  - G+5 observability counter "onboarding.completed_total" artar
"""
from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, Request

from app.engines import OnboardingEngine
from app.models import (
    OnboardingCompleteRequest,
    OnboardingCompleteResponse,
    OnboardingStatusResponse,
    UserProfile,
)
from app.routers._deps import _emit_audit_event, _value_error_to_http
from app.security import require_permissions


router = APIRouter()


def _onboarding_engine(request: Request) -> OnboardingEngine:
    return cast(OnboardingEngine, request.app.state.onboarding_engine)


@router.get(
    "/api/v1/onboarding/status",
    response_model=OnboardingStatusResponse,
    tags=["onboarding"],
)
def get_onboarding_status(
    request: Request,
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> OnboardingStatusResponse:
    """Mevcut kullanıcının onboarding durumu (wizard atla/devam)."""
    return _onboarding_engine(request).status(user_id=user.username)


@router.post(
    "/api/v1/onboarding/complete",
    response_model=OnboardingCompleteResponse,
    tags=["onboarding"],
)
def complete_onboarding(
    payload: OnboardingCompleteRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> OnboardingCompleteResponse:
    """Self-service onboarding tamamlama (4 adım birden).

    Ardışık:
      1. Company ensure
      2. Connector preference
      3. First invoice create
      4. Audit event emit
    """
    try:
        result = _onboarding_engine(request).complete(
            user_id=user.username,
            payload=payload,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc

    _emit_audit_event(
        request,
        user,
        "onboarding.completed",
        {
            "company_name": result.company_name,
            "invoice_id": result.invoice_id,
            "connector_registered": result.connector_registered,
        },
    )
    return result
