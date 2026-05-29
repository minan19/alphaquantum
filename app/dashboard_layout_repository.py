"""F4: DashboardLayoutRepository — kullanıcı dashboard layout persist.

JSON formatı validation engine katmanında yapılır — repository sadece
saklama/erişim.
"""
from __future__ import annotations

import sqlite3
import time
from threading import Lock
from typing import Any

from app._sqlite_helpers import new_row_id


class DashboardLayoutRepository:
    """User-scoped dashboard layout storage."""

    def __init__(self, database_path: str) -> None:
        self._lock = Lock()
        self._conn = self._connect(database_path)

    @staticmethod
    def _connect(database_path: str) -> sqlite3.Connection:
        conn = sqlite3.connect(database_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def close(self) -> None:
        self._conn.close()

    def get_layout(self, user_id: str) -> dict[str, Any] | None:
        """User'ın layout'unu döner. None → henüz set edilmemiş."""
        with self._lock:
            row = self._conn.execute(
                """
                SELECT user_id, layout_json, updated_at
                FROM user_dashboard_layouts
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    def upsert_layout(self, *, user_id: str, layout_json: str) -> dict[str, Any]:
        """Upsert layout (last write wins).

        SQLite ON CONFLICT(user_id) DO UPDATE — atomic, 1 query.
        """
        now = int(time.time())
        with self._lock:
            cursor = self._conn.execute(
                """
                INSERT INTO user_dashboard_layouts(user_id, layout_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    layout_json = excluded.layout_json,
                    updated_at = excluded.updated_at
                """,
                (user_id, layout_json, now),
            )
            # SQLite upsert lastrowid'i için fetch
            _ = new_row_id(cursor) if cursor.lastrowid else 0
            self._conn.commit()
        result = self.get_layout(user_id)
        if result is None:
            raise RuntimeError("Layout disappeared after upsert")
        return result

    def delete_layout(self, user_id: str) -> bool:
        """Reset için — kullanıcı default'a döner."""
        with self._lock:
            cursor = self._conn.execute(
                "DELETE FROM user_dashboard_layouts WHERE user_id = ?",
                (user_id,),
            )
            self._conn.commit()
        return cursor.rowcount > 0
