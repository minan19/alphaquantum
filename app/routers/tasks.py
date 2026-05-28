"""A5.5: Task tracking router (extracted from app/api.py).

Bu modül S-322 kapsamındaki 4 endpoint'i taşır:

- POST  /api/v1/tasks            → yeni görev oluştur
- GET   /api/v1/tasks            → listele (assigned_to, status, priority,
                                   overdue_only filtreleri)
- GET   /api/v1/tasks/summary    → status bazlı sayım
- PATCH /api/v1/tasks/{task_id}  → görev güncelle

RBAC: read_finance (list/summary), write_finance (mutate).
`_ensure_company_scope` çoklu-şirket koruması her endpoint'te.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.models import (
    TaskCreateRequest,
    TaskListResponse,
    TaskRead,
    TaskStatusSummaryResponse,
    TaskUpdateRequest,
    UserProfile,
)
from app.routers._deps import (
    _ensure_company_scope,
    _is_holding_scope,
    _task_engine,
)
from app.security import require_permissions


router = APIRouter()


@router.post(
    "/api/v1/tasks",
    response_model=TaskRead,
    status_code=201,
    tags=["tasks"],
)
def create_task(
    payload: TaskCreateRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("write_finance")),
) -> TaskRead:
    _ensure_company_scope(request, user, payload.company)
    return _task_engine(request).create_task(
        payload=payload, created_by=user.username
    )


@router.get(
    "/api/v1/tasks",
    response_model=TaskListResponse,
    tags=["tasks"],
)
def list_tasks(
    request: Request,
    company: str | None = Query(default=None),
    assigned_to: str | None = Query(default=None),
    task_status: str | None = Query(default=None, alias="status"),
    priority: str | None = Query(default=None),
    overdue_only: bool = Query(default=False),
    limit: int = Query(default=200, ge=1, le=1000),
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> TaskListResponse:
    if company:
        _ensure_company_scope(request, user, company)
    elif not _is_holding_scope(request, user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scoped users must provide company parameter",
        )
    return _task_engine(request).list_tasks(
        company=company,
        assigned_to=assigned_to,
        status=task_status,
        priority=priority,
        overdue_only=overdue_only,
        limit=limit,
    )


@router.get(
    "/api/v1/tasks/summary",
    response_model=TaskStatusSummaryResponse,
    tags=["tasks"],
)
def task_summary(
    request: Request,
    company: str | None = Query(default=None),
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> TaskStatusSummaryResponse:
    if company:
        _ensure_company_scope(request, user, company)
    elif not _is_holding_scope(request, user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scoped users must provide company parameter",
        )
    return _task_engine(request).status_summary(company=company)


@router.patch(
    "/api/v1/tasks/{task_id}",
    response_model=TaskRead,
    tags=["tasks"],
)
def update_task(
    task_id: int,
    payload: TaskUpdateRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("write_finance")),
) -> TaskRead:
    existing = _task_engine(request).get_task(task_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Task not found")
    _ensure_company_scope(request, user, existing.company)
    result = _task_engine(request).update_task(task_id, payload=payload)
    if result is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return result
