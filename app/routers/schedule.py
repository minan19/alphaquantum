"""A5.2: Scheduled Reports router (extracted from app/api.py).

Bu modül S-312 kapsamındaki 4 endpoint'i taşır:
- POST   /api/v1/reports/schedule              → yeni schedule oluştur
- GET    /api/v1/reports/schedule              → listele
- POST   /api/v1/reports/schedule/{id}/trigger → manuel tetikle
- DELETE /api/v1/reports/schedule/{id}         → pasifleştir

Strangler-fig migration: api.py monolith'inden ilk küçük domain modülü.
RBAC: manage_roles (write) + read_finance (list).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from app.models import (
    ScheduledReportCreateRequest,
    ScheduledReportListResponse,
    ScheduledReportRead,
    ScheduledReportTriggerResponse,
    UserProfile,
)
from app.routers._deps import _schedule_engine, _value_error_to_http
from app.security import require_permissions


router = APIRouter()


@router.post(
    "/api/v1/reports/schedule",
    response_model=ScheduledReportRead,
    tags=["schedule"],
)
def create_scheduled_report(
    payload: ScheduledReportCreateRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_roles")),
) -> ScheduledReportRead:
    return _schedule_engine(request).create_job(
        payload=payload, created_by=user.username
    )


@router.get(
    "/api/v1/reports/schedule",
    response_model=ScheduledReportListResponse,
    tags=["schedule"],
)
def list_scheduled_reports(
    request: Request,
    active_only: bool = Query(default=False),
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> ScheduledReportListResponse:
    del user
    return _schedule_engine(request).list_jobs(active_only=active_only)


@router.post(
    "/api/v1/reports/schedule/{job_id}/trigger",
    response_model=ScheduledReportTriggerResponse,
    tags=["schedule"],
)
def trigger_scheduled_report(
    job_id: int,
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_roles")),
) -> ScheduledReportTriggerResponse:
    del user
    try:
        return _schedule_engine(request).trigger_job(job_id=job_id)
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


@router.delete(
    "/api/v1/reports/schedule/{job_id}",
    response_model=ScheduledReportRead,
    tags=["schedule"],
)
def deactivate_scheduled_report(
    job_id: int,
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_roles")),
) -> ScheduledReportRead:
    del user
    try:
        return _schedule_engine(request).deactivate_job(job_id=job_id)
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc
