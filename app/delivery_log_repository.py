from __future__ import annotations

import sqlite3

from app._sqlite_helpers import new_row_id
import time
from threading import Lock
from typing import Any


class DeliveryLogRepository:
    """S-343 — Append-only log of every channel dispatch attempt."""

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

    def insert(
        self,
        *,
        company_name: str,
        notification_id: int,
        channel: str,
        provider: str,
        recipient: str,
        status: str,
        error_message: str = "",
        provider_message_id: str = "",
        subject: str = "",
        body: str = "",
    ) -> dict[str, Any]:
        now = int(time.time())
        sent_at = now if status in ("sent", "sandbox") else None
        with self._lock:
            cur = self._conn.execute(
                """
                INSERT INTO delivery_log(
                    company_name, notification_id, channel, provider,
                    recipient, status, error_message, provider_message_id,
                    subject, body, sent_at, created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (company_name, notification_id, channel, provider,
                 recipient, status, error_message, provider_message_id,
                 subject, body, sent_at, now),
            )
            row_id = new_row_id(cur)
            self._conn.commit()
            return self._fetch(row_id)

    def _fetch(self, log_id: int) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM delivery_log WHERE id = ?", (log_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_log(
        self,
        *,
        company_name: str | None,
        notification_id: int | None = None,
        channel: str | None = None,
        status: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if company_name:
            clauses.append("company_name = ?"); params.append(company_name)
        if notification_id is not None:
            clauses.append("notification_id = ?"); params.append(notification_id)
        if channel:
            clauses.append("channel = ?"); params.append(channel)
        if status:
            clauses.append("status = ?"); params.append(status)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM delivery_log {where} "
                f"ORDER BY created_at DESC, id DESC LIMIT ?",
                params,
            ).fetchall()
        return [dict(r) for r in rows]
