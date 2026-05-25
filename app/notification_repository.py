from __future__ import annotations

import sqlite3
import time
from threading import Lock
from typing import Any


class NotificationRepository:
    """Persistence layer for S-334 due-date / overdue notifications."""

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

    def insert_if_absent(
        self,
        *,
        company_name: str,
        kind: str,
        severity: str,
        subject_type: str,
        subject_id: int,
        window_key: str,
        title: str,
        message: str = "",
    ) -> int | None:
        """INSERT OR IGNORE — returns the row id if newly inserted, else None."""
        now = int(time.time())
        with self._lock:
            cur = self._conn.execute(
                """
                INSERT OR IGNORE INTO notifications(
                    company_name, kind, severity, subject_type, subject_id,
                    window_key, title, message, is_read, created_at, updated_at
                ) VALUES(?,?,?,?,?,?,?,?,0,?,?)
                """,
                (company_name, kind, severity, subject_type, subject_id,
                 window_key, title, message, now, now),
            )
            self._conn.commit()
            return int(cur.lastrowid) if cur.rowcount > 0 else None

    def get(self, notification_id: int) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM notifications WHERE id = ?", (notification_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_notifications(
        self,
        *,
        company_name: str | None,
        severity: str | None = None,
        unread_only: bool = False,
        kind: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if company_name:
            clauses.append("company_name = ?"); params.append(company_name)
        if severity:
            clauses.append("severity = ?"); params.append(severity)
        if unread_only:
            clauses.append("is_read = 0")
        if kind:
            clauses.append("kind = ?"); params.append(kind)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM notifications {where} "
                f"ORDER BY created_at DESC, id DESC LIMIT ?",
                params,
            ).fetchall()
        return [dict(r) for r in rows]

    def mark_read(self, notification_id: int) -> dict[str, Any] | None:
        now = int(time.time())
        with self._lock:
            cur = self._conn.execute(
                "UPDATE notifications SET is_read = 1, updated_at = ? WHERE id = ?",
                (now, notification_id),
            )
            self._conn.commit()
            if cur.rowcount == 0:
                return None
            row = self._conn.execute(
                "SELECT * FROM notifications WHERE id = ?", (notification_id,)
            ).fetchone()
        return dict(row) if row else None

    def summary(self, *, company_name: str | None) -> dict[str, int]:
        """Counts grouped by severity, plus an unread tally."""
        clauses: list[str] = []
        params: list[Any] = []
        if company_name:
            clauses.append("company_name = ?"); params.append(company_name)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._lock:
            sev_rows = self._conn.execute(
                f"SELECT severity, COUNT(*) AS cnt FROM notifications {where} "
                f"GROUP BY severity",
                params,
            ).fetchall()
            unread_row = self._conn.execute(
                f"SELECT COUNT(*) AS cnt FROM notifications "
                f"{where + (' AND' if where else 'WHERE')} is_read = 0",
                params,
            ).fetchone()
            total_row = self._conn.execute(
                f"SELECT COUNT(*) AS cnt FROM notifications {where}", params
            ).fetchone()
        result: dict[str, int] = {
            "info": 0, "warning": 0, "critical": 0,
            "unread": int(unread_row["cnt"]) if unread_row else 0,
            "total": int(total_row["cnt"]) if total_row else 0,
        }
        for r in sev_rows:
            sev = r["severity"]
            if sev in result:
                result[sev] = int(r["cnt"])
        return result
