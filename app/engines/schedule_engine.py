from __future__ import annotations

from typing import Any
import time
from app.scheduled_report_repository import ScheduledReportRepository
from app.models import (
    ScheduledReportCreateRequest,
    ScheduledReportListResponse,
    ScheduledReportRead,
    ScheduledReportTriggerResponse,
)

class ScheduleEngine:
    def __init__(self, repo: ScheduledReportRepository) -> None:
        self._repo = repo

    def create_job(self, *, payload: ScheduledReportCreateRequest, created_by: str) -> ScheduledReportRead:
        row = self._repo.create_job(
            name=payload.name,
            report_type=payload.report_type,
            format=payload.format,
            company_name=payload.company_name,
            params_json=payload.params_json,
            schedule_cron=payload.schedule_cron,
            recipient=payload.recipient,
            created_by=created_by,
        )
        return self._to_read(row)

    def list_jobs(self, *, active_only: bool = False) -> ScheduledReportListResponse:
        rows = self._repo.list_jobs(active_only=active_only)
        jobs = [self._to_read(r) for r in rows]
        return ScheduledReportListResponse(total=len(jobs), jobs=jobs)

    def trigger_job(self, *, job_id: int) -> ScheduledReportTriggerResponse:
        """Mark the job as run now and return a download path."""
        job = self._repo.get_job(job_id)
        if job is None:
            raise ValueError(f"Scheduled report job {job_id} not found")
        now = int(time.time())
        self._repo.update_job_status(job_id, last_run_at=now, last_status="triggered")
        fmt = str(job["format"])
        rtype = str(job["report_type"])
        download_path = f"/api/v1/reports/finance/{rtype}.{fmt}"
        return ScheduledReportTriggerResponse(
            id=job_id,
            message=f"Job '{job['name']}' triggered. Download at {download_path}",
            download_path=download_path,
        )

    def deactivate_job(self, *, job_id: int) -> ScheduledReportRead:
        job = self._repo.get_job(job_id)
        if job is None:
            raise ValueError(f"Scheduled report job {job_id} not found")
        self._repo.deactivate_job(job_id)
        updated = self._repo.get_job(job_id)
        if updated is None:
            raise ValueError("Scheduled job not found after deactivate")
        return self._to_read(updated)

    @staticmethod
    def _to_read(row: dict[str, Any]) -> ScheduledReportRead:
        import json as _json
        params = row.get("params_json")
        if isinstance(params, str):
            try:
                params = _json.loads(params)
            except Exception:
                params = {}
        return ScheduledReportRead(
            id=int(row["id"]),
            name=str(row["name"]),
            report_type=str(row["report_type"]),
            format=str(row["format"]),
            company_name=row.get("company_name"),
            params_json=params or {},
            schedule_cron=str(row["schedule_cron"]),
            recipient=str(row.get("recipient") or ""),
            is_active=bool(row["is_active"]),
            last_run_at=row.get("last_run_at"),
            last_status=row.get("last_status"),
            created_by=str(row.get("created_by") or ""),
            created_at=int(row["created_at"]),
        )
