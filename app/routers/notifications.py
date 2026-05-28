"""A5.12 (part 2): Notifications + Delivery router (S-334 + S-343).

7 endpoint covering invoice notification engine and KVKK-aware multi-channel
dispatch:

Notifications (5, S-334):
- POST  /api/v1/notifications/generate                  (idempotent scan)
- GET   /api/v1/notifications                           (filtered list)
- GET   /api/v1/notifications/summary                   (status summary)
- PATCH /api/v1/notifications/{id}/read                 (mark read)
- POST  /api/v1/notifications/{id}/dispatch             (S-343 channel dispatch)

Delivery log (2, S-343):
- GET   /api/v1/delivery-log                            (delivery audit)

RBAC: read_finance (queries), write_finance (mutations + dispatch).
Dispatch endpoint KVKK consent enforcement — consent yoksa kanal skipped.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.models import (
    DeliveryLogListResponse,
    DispatchResponse,
    NotificationGenerateResponse,
    NotificationListResponse,
    NotificationRead,
    NotificationSummaryResponse,
    UserProfile,
)
from app.routers._deps import (
    _delivery_engine,
    _ensure_company_scope,
    _is_holding_scope,
    _notification_engine,
)
from app.security import require_permissions


router = APIRouter()


# ── Notifications (S-334) ────────────────────────────────────────────────────


@router.post(
    "/api/v1/notifications/generate",
    response_model=NotificationGenerateResponse,
    tags=["notifications"],
)
def generate_notifications(
    request: Request,
    company: str | None = Query(default=None),
    user: UserProfile = Depends(require_permissions("write_finance")),
) -> NotificationGenerateResponse:
    """Scan unpaid invoices and create any missing window notifications.

    Idempotent — duplicates are dropped by a UNIQUE constraint at the DB layer.
    """
    if company:
        _ensure_company_scope(request, user, company)
    elif not _is_holding_scope(request, user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scoped users must provide company parameter",
        )
    return _notification_engine(request).scan_invoices(company=company)


@router.get(
    "/api/v1/notifications",
    response_model=NotificationListResponse,
    tags=["notifications"],
)
def list_notifications(
    request: Request,
    company: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    unread_only: bool = Query(default=False),
    kind: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> NotificationListResponse:
    if company:
        _ensure_company_scope(request, user, company)
    elif not _is_holding_scope(request, user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scoped users must provide company parameter",
        )
    return _notification_engine(request).list_notifications(
        company=company,
        severity=severity,
        unread_only=unread_only,
        kind=kind,
        limit=limit,
    )


@router.get(
    "/api/v1/notifications/summary",
    response_model=NotificationSummaryResponse,
    tags=["notifications"],
)
def notification_summary(
    request: Request,
    company: str | None = Query(default=None),
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> NotificationSummaryResponse:
    if company:
        _ensure_company_scope(request, user, company)
    elif not _is_holding_scope(request, user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scoped users must provide company parameter",
        )
    return _notification_engine(request).summary(company=company)


@router.patch(
    "/api/v1/notifications/{notification_id}/read",
    response_model=NotificationRead,
    tags=["notifications"],
)
def mark_notification_read(
    notification_id: int,
    request: Request,
    user: UserProfile = Depends(require_permissions("write_finance")),
) -> NotificationRead:
    existing = _notification_engine(request).get(notification_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    _ensure_company_scope(request, user, existing.company)
    result = _notification_engine(request).mark_read(notification_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    return result


# ── Dispatch + Delivery log (S-343) ──────────────────────────────────────────


@router.post(
    "/api/v1/notifications/{notification_id}/dispatch",
    response_model=DispatchResponse,
    tags=["notifications"],
)
def dispatch_notification(
    notification_id: int,
    request: Request,
    channels: str | None = Query(
        default=None,
        description="Comma-separated channel list. Defaults to env config.",
    ),
    user: UserProfile = Depends(require_permissions("write_finance")),
) -> DispatchResponse:
    """S-343 — Send a notification across configured channels.

    Honors per-customer KVKK consent flags. Channels without consent are
    skipped (status='skipped_no_consent' in delivery_log). Missing contact
    info → status='skipped_no_contact'.
    """
    existing = _notification_engine(request).get(notification_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    _ensure_company_scope(request, user, existing.company)
    channel_list = (
        [c.strip() for c in channels.split(",") if c.strip()]
        if channels
        else None
    )
    result = _delivery_engine(request).dispatch(
        notification_id=notification_id, channels=channel_list
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    return result


@router.get(
    "/api/v1/delivery-log",
    response_model=DeliveryLogListResponse,
    tags=["notifications"],
)
def list_delivery_log(
    request: Request,
    company: str | None = Query(default=None),
    notification_id: int | None = Query(default=None),
    channel: str | None = Query(default=None),
    delivery_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=200, ge=1, le=1000),
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> DeliveryLogListResponse:
    if company:
        _ensure_company_scope(request, user, company)
    elif not _is_holding_scope(request, user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scoped users must provide company parameter",
        )
    return _delivery_engine(request).list_log(
        company=company,
        notification_id=notification_id,
        channel=channel,
        status=delivery_status,
        limit=limit,
    )
