"""A5.10: Connectors router (extracted from app/api.py).

9 endpoint covering connector CRUD, sync jobs, canonical mapping, and queue
health:

Connectors (3):
- POST /api/v1/connectors                                  (create, 409 on dup)
- GET  /api/v1/connectors                                  (scope-filtered list)
- GET  /api/v1/connectors/{connector_id}                   (detail)

Canonical preview (1):
- POST /api/v1/connectors/canonical/preview                (mapping dry-run)

Sync jobs (3):
- POST /api/v1/connectors/{connector_id}/sync-jobs         (enqueue per connector)
- GET  /api/v1/connectors/{connector_id}/sync-jobs         (list per connector)
- GET  /api/v1/connectors/sync-jobs                        (cross-connector list)

Health + dispatch (2):
- GET  /api/v1/connectors/health/summary                   (queue health aggregate)
- POST /api/v1/connectors/sync-jobs/dispatch               (manual next job)

RBAC: read_connectors (queries), manage_connectors (mutations).
Holding-scope users see all; scoped users get filtered output.
Health summary aggregates per-scoped-company stats when user is not holding.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.models import (
    ConnectorCanonicalPreviewRequest,
    ConnectorCanonicalPreviewResponse,
    ConnectorCreateRequest,
    ConnectorListResponse,
    ConnectorQueueHealthResponse,
    ConnectorRead,
    ConnectorSyncDispatchRequest,
    ConnectorSyncDispatchResponse,
    ConnectorSyncJobCreateRequest,
    ConnectorSyncJobListResponse,
    ConnectorSyncJobRead,
    UserProfile,
)
from app.routers._deps import (
    _connector_engine,
    _ensure_company_scope,
    _is_holding_scope,
    _user_has_company_scope,
    _value_error_to_http,
)
from app.security import require_permissions


router = APIRouter()


# ── Connectors CRUD ──────────────────────────────────────────────────────────


@router.post(
    "/api/v1/connectors",
    response_model=ConnectorRead,
    status_code=201,
    tags=["connector"],
)
def create_connector(
    payload: ConnectorCreateRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_connectors")),
) -> ConnectorRead:
    _ensure_company_scope(request, user, payload.company_name)
    try:
        return _connector_engine(request).create_connector(
            payload,
            created_by=user.username,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Connector already exists",
        ) from exc


@router.get(
    "/api/v1/connectors",
    response_model=ConnectorListResponse,
    tags=["connector"],
)
def list_connectors(
    request: Request,
    company: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=200, ge=1, le=1000),
    user: UserProfile = Depends(require_permissions("read_connectors")),
) -> ConnectorListResponse:
    if company:
        _ensure_company_scope(request, user, company)
    result = _connector_engine(request).list_connectors(
        company_name=company,
        status=status_filter,
        limit=limit,
    )
    if company or _is_holding_scope(request, user):
        return result

    filtered = [
        item
        for item in result.items
        if _user_has_company_scope(request, user, item.company_name)
    ]
    return ConnectorListResponse(total=len(filtered), items=filtered)


@router.get(
    "/api/v1/connectors/{connector_id}",
    response_model=ConnectorRead,
    tags=["connector"],
)
def get_connector(
    connector_id: int,
    request: Request,
    user: UserProfile = Depends(require_permissions("read_connectors")),
) -> ConnectorRead:
    try:
        result = _connector_engine(request).get_connector(connector_id)
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc
    _ensure_company_scope(request, user, result.company_name)
    return result


# ── Canonical mapping preview ────────────────────────────────────────────────


@router.post(
    "/api/v1/connectors/canonical/preview",
    response_model=ConnectorCanonicalPreviewResponse,
    tags=["connector"],
)
def preview_connector_canonical_mapping(
    payload: ConnectorCanonicalPreviewRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("read_connectors")),
) -> ConnectorCanonicalPreviewResponse:
    del user
    return _connector_engine(request).preview_canonical_mapping(payload)


# ── Sync jobs ────────────────────────────────────────────────────────────────


@router.post(
    "/api/v1/connectors/{connector_id}/sync-jobs",
    response_model=ConnectorSyncJobRead,
    status_code=201,
    tags=["connector"],
)
def create_connector_sync_job(
    connector_id: int,
    payload: ConnectorSyncJobCreateRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_connectors")),
) -> ConnectorSyncJobRead:
    try:
        connector = _connector_engine(request).get_connector(connector_id)
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc
    _ensure_company_scope(request, user, connector.company_name)
    try:
        return _connector_engine(request).create_sync_job(
            connector_id,
            payload,
            requested_by=user.username,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


@router.get(
    "/api/v1/connectors/{connector_id}/sync-jobs",
    response_model=ConnectorSyncJobListResponse,
    tags=["connector"],
)
def list_connector_sync_jobs(
    connector_id: int,
    request: Request,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=200, ge=1, le=2000),
    user: UserProfile = Depends(require_permissions("read_connectors")),
) -> ConnectorSyncJobListResponse:
    try:
        connector = _connector_engine(request).get_connector(connector_id)
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc
    _ensure_company_scope(request, user, connector.company_name)
    return _connector_engine(request).list_sync_jobs(
        connector_id=connector_id,
        status=status_filter,
        limit=limit,
    )


@router.get(
    "/api/v1/connectors/sync-jobs",
    response_model=ConnectorSyncJobListResponse,
    tags=["connector"],
)
def list_sync_jobs(
    request: Request,
    connector_id: int | None = Query(default=None),
    company: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=200, ge=1, le=2000),
    user: UserProfile = Depends(require_permissions("read_connectors")),
) -> ConnectorSyncJobListResponse:
    if company:
        _ensure_company_scope(request, user, company)
    if connector_id is not None:
        try:
            connector = _connector_engine(request).get_connector(connector_id)
        except ValueError as exc:
            raise _value_error_to_http(exc) from exc
        _ensure_company_scope(request, user, connector.company_name)
        company = connector.company_name

    result = _connector_engine(request).list_sync_jobs(
        connector_id=connector_id,
        company_name=company,
        status=status_filter,
        limit=limit,
    )
    if company or _is_holding_scope(request, user):
        return result
    filtered = [
        item
        for item in result.items
        if _user_has_company_scope(request, user, item.company_name)
    ]
    return ConnectorSyncJobListResponse(total=len(filtered), items=filtered)


# ── Health summary + dispatch ────────────────────────────────────────────────


@router.get(
    "/api/v1/connectors/health/summary",
    response_model=ConnectorQueueHealthResponse,
    tags=["connector"],
)
def connector_health_summary(
    request: Request,
    company: str | None = Query(default=None),
    user: UserProfile = Depends(require_permissions("read_connectors")),
) -> ConnectorQueueHealthResponse:
    """Aggregate queue health.

    - Explicit `company` parameter → that company's health (scope-checked).
    - Holding-scope user → global health.
    - Scoped user without company param → aggregate over user's scoped
      companies (weighted readiness/security scores), never exposing
      out-of-scope data.
    """
    if company:
        _ensure_company_scope(request, user, company)
        return _connector_engine(request).build_queue_health(company_name=company)

    if _is_holding_scope(request, user):
        return _connector_engine(request).build_queue_health()

    scoped_companies = sorted(
        {scope for scope in user.company_scopes if scope != "*"}
    )
    if not scoped_companies:
        return _connector_engine(request).build_queue_health(
            company_name="__no_connector_scope__"
        )

    # Aggregate scoped companies without exposing out-of-scope data.
    aggregate = ConnectorQueueHealthResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        total_connectors=0,
        active_connectors=0,
        staged_connectors=0,
        blocked_connectors=0,
        queued_jobs=0,
        running_jobs=0,
        success_jobs=0,
        failed_jobs=0,
        dead_letter_jobs=0,
        due_retry_jobs=0,
        average_readiness_score=0.0,
        average_security_score=0.0,
    )
    readiness_weighted = 0.0
    security_weighted = 0.0
    for company_name in scoped_companies:
        item = _connector_engine(request).build_queue_health(
            company_name=company_name
        )
        aggregate.total_connectors += item.total_connectors
        aggregate.active_connectors += item.active_connectors
        aggregate.staged_connectors += item.staged_connectors
        aggregate.blocked_connectors += item.blocked_connectors
        aggregate.queued_jobs += item.queued_jobs
        aggregate.running_jobs += item.running_jobs
        aggregate.success_jobs += item.success_jobs
        aggregate.failed_jobs += item.failed_jobs
        aggregate.dead_letter_jobs += item.dead_letter_jobs
        aggregate.due_retry_jobs += item.due_retry_jobs
        readiness_weighted += item.average_readiness_score * item.total_connectors
        security_weighted += item.average_security_score * item.total_connectors

    if aggregate.total_connectors > 0:
        aggregate.average_readiness_score = round(
            readiness_weighted / aggregate.total_connectors, 2
        )
        aggregate.average_security_score = round(
            security_weighted / aggregate.total_connectors, 2
        )
    return aggregate


@router.post(
    "/api/v1/connectors/sync-jobs/dispatch",
    response_model=ConnectorSyncDispatchResponse,
    tags=["connector"],
)
def dispatch_sync_job(
    payload: ConnectorSyncDispatchRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_connectors")),
) -> ConnectorSyncDispatchResponse:
    allowed_company_names: list[str] | None = None
    if payload.company_name:
        _ensure_company_scope(request, user, payload.company_name)
        allowed_company_names = [payload.company_name]
    elif not _is_holding_scope(request, user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scoped users must provide company_name for dispatch",
        )

    return _connector_engine(request).dispatch_next_sync_job(
        payload,
        requested_by=user.username,
        allowed_company_names=allowed_company_names,
    )
