from __future__ import annotations

import sqlite3

from app._sqlite_helpers import new_row_id
import time
from threading import Lock
from typing import Any


class TaskRepository:
    def __init__(self, database_path: str) -> None:
        self._lock = Lock()
        self._conn = self._connect(database_path)

    @staticmethod
    def _connect(database_path: str) -> sqlite3.Connection:
        conn = sqlite3.connect(database_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def close(self) -> None:
        self._conn.close()

    def create_task(
        self,
        *,
        company_name: str,
        title: str,
        description: str = "",
        assigned_to: str = "",
        priority: str = "medium",
        due_date: str | None = None,
        customer_id: int | None = None,
        created_by: str = "",
    ) -> dict[str, Any]:
        now = int(time.time())
        with self._lock:
            cur = self._conn.execute(
                """
                INSERT INTO tasks(
                    company_name, title, description, assigned_to,
                    priority, status, due_date, customer_id,
                    created_by, created_at, updated_at
                ) VALUES(?,?,?,?,?,'open',?,?,?,?,?)
                """,
                (company_name, title, description, assigned_to,
                 priority, due_date, customer_id, created_by, now, now),
            )
            row_id = new_row_id(cur)
            self._conn.commit()
            row = self._fetch(row_id)
            assert row is not None  # just inserted, must exist
            return row

    def get_task(self, task_id: int) -> dict[str, Any] | None:
        with self._lock:
            return self._fetch(task_id)

    def _fetch(self, task_id: int) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_tasks(
        self,
        *,
        company_name: str | None,
        assigned_to: str | None = None,
        status: str | None = None,
        priority: str | None = None,
        overdue_only: bool = False,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if company_name:
            clauses.append("company_name = ?"); params.append(company_name)
        if assigned_to:
            clauses.append("assigned_to = ?"); params.append(assigned_to)
        if status:
            clauses.append("status = ?"); params.append(status)
        if priority:
            clauses.append("priority = ?"); params.append(priority)
        if overdue_only:
            today = time.strftime("%Y-%m-%d")
            clauses.append("due_date < ?"); params.append(today)
            clauses.append("status NOT IN ('done','cancelled')")
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM tasks {where} ORDER BY due_date ASC NULLS LAST, id DESC LIMIT ?",
                params,
            ).fetchall()
        return [dict(r) for r in rows]

    def update_task(
        self,
        task_id: int,
        *,
        title: str | None = None,
        description: str | None = None,
        assigned_to: str | None = None,
        priority: str | None = None,
        status: str | None = None,
        due_date: str | None = None,
    ) -> dict[str, Any] | None:
        now = int(time.time())
        fields = ["updated_at = ?"]
        values: list[Any] = [now]
        for col, val in [
            ("title", title), ("description", description),
            ("assigned_to", assigned_to), ("priority", priority),
            ("status", status), ("due_date", due_date),
        ]:
            if val is not None:
                fields.append(f"{col} = ?"); values.append(val)
        values.append(task_id)
        with self._lock:
            self._conn.execute(
                f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?", values
            )
            self._conn.commit()
            return self._fetch(task_id)

    def count_by_status(self, *, company_name: str | None) -> dict[str, int]:
        clauses: list[str] = []
        params: list[Any] = []
        if company_name:
            clauses.append("company_name = ?"); params.append(company_name)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._lock:
            rows = self._conn.execute(
                f"SELECT status, COUNT(*) as cnt FROM tasks {where} GROUP BY status",
                params,
            ).fetchall()
        return {r["status"]: r["cnt"] for r in rows}

    def count_overdue(self, *, company_name: str | None) -> int:
        today = time.strftime("%Y-%m-%d")
        clauses = ["due_date < ?", "status NOT IN ('done','cancelled')"]
        params: list[Any] = [today]
        if company_name:
            clauses.append("company_name = ?"); params.append(company_name)
        where = "WHERE " + " AND ".join(clauses)
        with self._lock:
            row = self._conn.execute(
                f"SELECT COUNT(*) as cnt FROM tasks {where}", params
            ).fetchone()
        return row["cnt"] if row else 0
