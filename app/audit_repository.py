from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any
import sqlite3
import time


class AuditRepository:
    def __init__(self, database_path: str) -> None:
        self._lock = Lock()
        self._conn = self._connect(database_path)
        self._ensure_schema()

    @staticmethod
    def _connect(database_path: str) -> sqlite3.Connection:
        path = Path(database_path)
        if path.parent and str(path.parent) != ".":
            path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def close(self) -> None:
        self._conn.close()

    def _ensure_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT,
                username TEXT,
                role TEXT,
                method TEXT NOT NULL,
                path TEXT NOT NULL,
                status_code INTEGER NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                duration_ms REAL NOT NULL,
                created_at INTEGER NOT NULL,
                event_type TEXT,
                event_detail TEXT
            )
            """
        )
        self._conn.commit()

    def write_log(
        self,
        *,
        request_id: str,
        username: str | None,
        role: str | None,
        method: str,
        path: str,
        status_code: int,
        ip_address: str | None,
        user_agent: str | None,
        duration_ms: float,
        event_type: str | None = None,
        event_detail: dict[str, Any] | None = None,
    ) -> None:
        now = int(time.time())
        detail_json = json.dumps(event_detail, ensure_ascii=True) if event_detail else None
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO audit_logs(
                    request_id,
                    username,
                    role,
                    method,
                    path,
                    status_code,
                    ip_address,
                    user_agent,
                    duration_ms,
                    created_at,
                    event_type,
                    event_detail
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    username,
                    role,
                    method,
                    path,
                    status_code,
                    ip_address,
                    user_agent,
                    duration_ms,
                    now,
                    event_type,
                    detail_json,
                ),
            )
            self._conn.commit()

    def write_event(
        self,
        *,
        username: str | None,
        role: str | None,
        event_type: str,
        event_detail: dict[str, Any] | None = None,
        request_id: str = "",
        ip_address: str | None = None,
    ) -> None:
        """Write a structured business event to the audit log (not tied to an HTTP request)."""
        now = int(time.time())
        detail_json = json.dumps(event_detail, ensure_ascii=True) if event_detail else None
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO audit_logs(
                    request_id,
                    username,
                    role,
                    method,
                    path,
                    status_code,
                    ip_address,
                    user_agent,
                    duration_ms,
                    created_at,
                    event_type,
                    event_detail
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    username,
                    role,
                    "EVENT",
                    f"/audit/event/{event_type}",
                    200,
                    ip_address,
                    None,
                    0.0,
                    now,
                    event_type,
                    detail_json,
                ),
            )
            self._conn.commit()

    def list_logs(self, *, limit: int = 100) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 500))
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT
                    id,
                    request_id,
                    username,
                    role,
                    method,
                    path,
                    status_code,
                    ip_address,
                    user_agent,
                    duration_ms,
                    created_at,
                    event_type,
                    event_detail
                FROM audit_logs
                ORDER BY id DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
            result: list[dict[str, Any]] = []
            for row in rows:
                row_dict = dict(row)
                raw_detail = row_dict.get("event_detail")
                if raw_detail:
                    try:
                        row_dict["event_detail"] = json.loads(str(raw_detail))
                    except (TypeError, ValueError):
                        row_dict["event_detail"] = None
                result.append(row_dict)
            return result
