"""SEC1: Audit log review + analytics — admin panel için."""
from __future__ import annotations

import time
from typing import Any, cast

from fastapi import APIRouter, Depends, Query, Request

from app.audit_repository import AuditRepository
from app.models import UserProfile
from app.security import require_permissions


router = APIRouter()


def _repo(request: Request) -> AuditRepository:
    return cast(AuditRepository, request.app.state.audit_repository)


@router.get(
    "/api/v1/admin/audit/search",
    response_model=list[dict[str, Any]],
    tags=["audit"],
)
def search_audit_logs(
    request: Request,
    username: str | None = Query(default=None, max_length=120),
    method: str | None = Query(default=None, pattern="^(GET|POST|PUT|PATCH|DELETE|EVENT)$"),
    path_contains: str | None = Query(default=None, max_length=200),
    status_code_min: int | None = Query(default=None, ge=100, le=599),
    status_code_max: int | None = Query(default=None, ge=100, le=599),
    from_hours_ago: int | None = Query(default=None, ge=1, le=8760),
    event_type: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=100, ge=1, le=500),
    _user: UserProfile = Depends(require_permissions("view_audit_logs")),
) -> list[dict[str, Any]]:
    """Audit logları filtreli arama. Admin panel için optimize."""
    from_ts: int | None = None
    if from_hours_ago is not None:
        from_ts = int(time.time()) - from_hours_ago * 3600
    return _repo(request).search_logs(
        username=username,
        method=method,
        path_contains=path_contains,
        status_code_min=status_code_min,
        status_code_max=status_code_max,
        from_ts=from_ts,
        event_type=event_type,
        limit=limit,
    )


@router.get(
    "/api/v1/admin/audit/summary",
    response_model=dict[str, Any],
    tags=["audit"],
)
def audit_summary(
    request: Request,
    window_hours: int = Query(default=24, ge=1, le=720),
    _user: UserProfile = Depends(require_permissions("view_audit_logs")),
) -> dict[str, Any]:
    """Son N saatlik özet — error rate, by_method, by_user, slow_routes."""
    return _repo(request).summary(window_hours=window_hours)
