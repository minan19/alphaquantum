from __future__ import annotations

import json
import sqlite3
import time
from threading import Lock
from typing import Any


class ScheduledReportRepository:
    def __init__(self, db_path: str) -> None:
        self._lock = Lock()
        self._conn = self._connect(db_path)
        self._ensure_schema()

    @staticmethod
    def _connect(db_path: str) -> sqlite3.Connection:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def _ensure_schema(self) -> None:
        with self._lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS scheduled_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    report_type TEXT NOT NULL CHECK(report_type IN ('ledger', 'budget_vs_actual')),
                    format TEXT NOT NULL CHECK(format IN ('xlsx', 'pdf')),
                    company_name TEXT,
                    params_json TEXT NOT NULL DEFAULT '{}',
                    schedule_cron TEXT NOT NULL,
                    recipient TEXT NOT NULL DEFAULT '',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    last_run_at INTEGER,
                    last_status TEXT,
                    created_by TEXT NOT NULL DEFAULT '',
                    created_at INTEGER NOT NULL
                )
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_scheduled_reports_active ON scheduled_reports(is_active)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_scheduled_reports_report_type ON scheduled_reports(report_type)"
            )
            self._conn.commit()

    def create_job(
        self,
        *,
        name: str,
        report_type: str,
        format: str,
        company_name: str | None,
        params_json: dict,
        schedule_cron: str,
        recipient: str,
        created_by: str,
    ) -> dict[str, Any]:
        now = int(time.time())
        params_str = json.dumps(params_json)

        with self._lock:
            cursor = self._conn.execute(
                """
                INSERT INTO scheduled_reports(
                    name, report_type, format, company_name, params_json,
                    schedule_cron, recipient, is_active, created_by, created_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    name,
                    report_type,
                    format,
                    company_name,
                    params_str,
                    schedule_cron,
                    recipient,
                    created_by,
                    now,
                ),
            )
            row_id = int(cursor.lastrowid)
            self._conn.commit()

            row = self._conn.execute(
                """
                SELECT id, name, report_type, format, company_name, params_json,
                       schedule_cron, recipient, is_active, last_run_at, last_status,
                       created_by, created_at
                FROM scheduled_reports WHERE id = ?
                """,
                (row_id,),
            ).fetchone()

        if row is None:
            raise RuntimeError("Scheduled report job create failed")
        return dict(row)

    def list_jobs(self, *, active_only: bool = False) -> list[dict[str, Any]]:
        where = "WHERE is_active = 1" if active_only else ""
        with self._lock:
            rows = self._conn.execute(
                f"""
                SELECT id, name, report_type, format, company_name, params_json,
                       schedule_cron, recipient, is_active, last_run_at, last_status,
                       created_by, created_at
                FROM scheduled_reports {where}
                ORDER BY id DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_job(self, job_id: int) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT id, name, report_type, format, company_name, params_json,
                       schedule_cron, recipient, is_active, last_run_at, last_status,
                       created_by, created_at
                FROM scheduled_reports WHERE id = ?
                """,
                (job_id,),
            ).fetchone()
        if row is None:
            return None
        return dict(row)

    def update_job_status(
        self, job_id: int, *, last_run_at: int, last_status: str
    ) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE scheduled_reports SET last_run_at = ?, last_status = ? WHERE id = ?",
                (last_run_at, last_status, job_id),
            )
            self._conn.commit()

    def deactivate_job(self, job_id: int) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE scheduled_reports SET is_active = 0 WHERE id = ?",
                (job_id,),
            )
            self._conn.commit()

    def close(self) -> None:
        self._conn.close()
