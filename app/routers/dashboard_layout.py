"""F4: Dashboard layout router — kullanıcı widget customization endpoint'leri.

3 endpoint:
  - GET    /api/v1/dashboard/layout  (mevcut + default fallback)
  - PUT    /api/v1/dashboard/layout  (save, validate)
  - DELETE /api/v1/dashboard/layout  (reset → default)

RBAC: read_finance permission (basit — kullanıcı kendi layout'unu yönetir).
"""
from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, Request

from app.engines.dashboard_layout_engine import DashboardLayoutEngine
from app.models import (
    DashboardLayoutResponse,
    DashboardLayoutSaveRequest,
    UserProfile,
)
from app.routers._deps import _value_error_to_http
from app.security import require_permissions


router = APIRouter()


def _engine(request: Request) -> DashboardLayoutEngine:
    return cast(DashboardLayoutEngine, request.app.state.dashboard_layout_engine)


@router.get(
    "/api/v1/dashboard/layout",
    response_model=DashboardLayoutResponse,
    tags=["dashboard"],
)
def get_dashboard_layout(
    request: Request,
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> DashboardLayoutResponse:
    """Mevcut kullanıcının dashboard layout'u (yoksa default)."""
    return _engine(request).get_layout(user_id=user.username)


@router.put(
    "/api/v1/dashboard/layout",
    response_model=DashboardLayoutResponse,
    tags=["dashboard"],
)
def save_dashboard_layout(
    payload: DashboardLayoutSaveRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> DashboardLayoutResponse:
    """Layout'u kaydet (validate edilir)."""
    try:
        return _engine(request).save_layout(
            user_id=user.username,
            widgets=payload.widgets,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


@router.delete(
    "/api/v1/dashboard/layout",
    response_model=DashboardLayoutResponse,
    tags=["dashboard"],
)
def reset_dashboard_layout(
    request: Request,
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> DashboardLayoutResponse:
    """Default layout'a sıfırla."""
    return _engine(request).reset_layout(user_id=user.username)
