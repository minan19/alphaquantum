from __future__ import annotations

from datetime import date
from threading import Lock
from typing import Any
import sqlite3
import time


class FinanceRepository:
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

    def create_ledger_entry(
        self,
        *,
        company_name: str,
        entry_type: str,
        amount: float,
        category: str,
        description: str,
        entry_date: str,
    ) -> dict[str, Any]:
        now = int(time.time())

        with self._lock:
            cursor = self._conn.execute(
                """
                INSERT INTO finance_ledger_entries(
                    company_name,
                    entry_type,
                    amount,
                    category,
                    description,
                    entry_date,
                    created_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    company_name,
                    entry_type,
                    amount,
                    category,
                    description,
                    entry_date,
                    now,
                ),
            )
            entry_id = int(cursor.lastrowid)
            self._conn.commit()

            row = self._conn.execute(
                """
                SELECT
                    id,
                    company_name,
                    entry_type,
                    amount,
                    category,
                    description,
                    entry_date,
                    created_at
                FROM finance_ledger_entries
                WHERE id = ?
                """,
                (entry_id,),
            ).fetchone()

        if row is None:
            raise RuntimeError("Ledger entry create failed")
        return dict(row)

    def list_ledger_entries(
        self,
        *,
        company_name: str | None,
        start_date: str,
        end_date: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 1000))
        if company_name:
            query = """
                SELECT
                    id,
                    company_name,
                    entry_type,
                    amount,
                    category,
                    description,
                    entry_date,
                    created_at
                FROM finance_ledger_entries
                WHERE entry_date >= ? AND entry_date <= ? AND company_name = ?
                ORDER BY entry_date DESC, id DESC
                LIMIT ?
            """
            params: list[Any] = [start_date, end_date, company_name, safe_limit]
        else:
            query = """
                SELECT
                    id,
                    company_name,
                    entry_type,
                    amount,
                    category,
                    description,
                    entry_date,
                    created_at
                FROM finance_ledger_entries
                WHERE entry_date >= ? AND entry_date <= ?
                ORDER BY entry_date DESC, id DESC
                LIMIT ?
            """
            params = [start_date, end_date, safe_limit]

        with self._lock:
            rows = self._conn.execute(query, params).fetchall()

        return [dict(row) for row in rows]

    def today(self) -> str:
        return date.today().isoformat()
