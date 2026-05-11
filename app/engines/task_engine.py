from __future__ import annotations

from app.task_repository import TaskRepository
from app.models import (
    TaskCreateRequest,
    TaskRead,
    TaskListResponse,
    TaskUpdateRequest,
    TaskStatusSummaryResponse,
)


class TaskEngine:
    def __init__(self, repo: TaskRepository) -> None:
        self._repo = repo

    def create_task(self, *, payload: TaskCreateRequest, created_by: str = "") -> TaskRead:
        row = self._repo.create_task(
            company_name=payload.company,
            title=payload.title,
            description=payload.description,
            assigned_to=payload.assigned_to,
            priority=payload.priority,
            due_date=payload.due_date,
            customer_id=payload.customer_id,
            created_by=created_by,
        )
        return self._to_read(row)

    def get_task(self, task_id: int) -> TaskRead | None:
        row = self._repo.get_task(task_id)
        return self._to_read(row) if row else None

    def list_tasks(
        self,
        *,
        company: str | None,
        assigned_to: str | None = None,
        status: str | None = None,
        priority: str | None = None,
        overdue_only: bool = False,
        limit: int = 200,
    ) -> TaskListResponse:
        rows = self._repo.list_tasks(
            company_name=company,
            assigned_to=assigned_to,
            status=status,
            priority=priority,
            overdue_only=overdue_only,
            limit=limit,
        )
        items = [self._to_read(r) for r in rows]
        return TaskListResponse(total=len(items), tasks=items)

    def update_task(
        self, task_id: int, *, payload: TaskUpdateRequest
    ) -> TaskRead | None:
        row = self._repo.update_task(
            task_id,
            title=payload.title,
            description=payload.description,
            assigned_to=payload.assigned_to,
            priority=payload.priority,
            status=payload.status,
            due_date=payload.due_date,
        )
        return self._to_read(row) if row else None

    def status_summary(self, *, company: str | None) -> TaskStatusSummaryResponse:
        counts = self._repo.count_by_status(company_name=company)
        overdue = self._repo.count_overdue(company_name=company)
        return TaskStatusSummaryResponse(
            company=company,
            open=counts.get("open", 0),
            in_progress=counts.get("in_progress", 0),
            done=counts.get("done", 0),
            cancelled=counts.get("cancelled", 0),
            overdue=overdue,
            total=sum(counts.values()),
        )

    @staticmethod
    def _to_read(row: dict) -> TaskRead:
        return TaskRead(
            id=int(row["id"]),
            company=str(row["company_name"]),
            title=str(row["title"]),
            description=str(row.get("description") or ""),
            assigned_to=str(row.get("assigned_to") or ""),
            priority=str(row.get("priority") or "medium"),
            status=str(row.get("status") or "open"),
            due_date=row.get("due_date"),
            customer_id=row.get("customer_id"),
            created_by=str(row.get("created_by") or ""),
            created_at=int(row["created_at"]),
            updated_at=int(row["updated_at"]),
        )
