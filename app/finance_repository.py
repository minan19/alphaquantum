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

    # ── Recurring entries ─────────────────────────────────────────────────────

    def create_recurring_entry(
        self,
        *,
        company_name: str,
        entry_type: str,
        amount: float,
        category: str,
        description: str,
        frequency: str,
        start_date: str,
        end_date: str | None,
    ) -> dict[str, Any]:
        now = int(time.time())
        with self._lock:
            cursor = self._conn.execute(
                """
                INSERT INTO finance_recurring_entries(
                    company_name, entry_type, amount, category, description,
                    frequency, start_date, end_date, last_generated_date,
                    is_active, created_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, NULL, 1, ?)
                """,
                (company_name, entry_type, amount, category, description,
                 frequency, start_date, end_date, now),
            )
            row_id = int(cursor.lastrowid)
            self._conn.commit()
        return self.get_recurring_entry(row_id)

    def get_recurring_entry(self, entry_id: int) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT id, company_name, entry_type, amount, category, description,
                       frequency, start_date, end_date, last_generated_date,
                       is_active, created_at
                FROM finance_recurring_entries WHERE id = ?
                """,
                (entry_id,),
            ).fetchone()
        if row is None:
            raise ValueError("Recurring entry not found")
        return dict(row)

    def list_recurring_entries(
        self, *, company_name: str | None = None, active_only: bool = True
    ) -> list[dict[str, Any]]:
        conditions: list[str] = []
        params: list[Any] = []
        if company_name:
            conditions.append("company_name = ?")
            params.append(company_name)
        if active_only:
            conditions.append("is_active = 1")
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self._lock:
            rows = self._conn.execute(
                f"""
                SELECT id, company_name, entry_type, amount, category, description,
                       frequency, start_date, end_date, last_generated_date,
                       is_active, created_at
                FROM finance_recurring_entries {where}
                ORDER BY company_name, id
                """,
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def get_due_recurring_entries(self, as_of_date: str) -> list[dict[str, Any]]:
        """Return active recurring entries that are due to generate a ledger entry on or before as_of_date."""
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT id, company_name, entry_type, amount, category, description,
                       frequency, start_date, end_date, last_generated_date,
                       is_active, created_at
                FROM finance_recurring_entries
                WHERE is_active = 1
                  AND start_date <= ?
                  AND (end_date IS NULL OR end_date >= ?)
                ORDER BY id
                """,
                (as_of_date, as_of_date),
            ).fetchall()
        return [dict(row) for row in rows]

    def update_recurring_last_generated(self, entry_id: int, generated_date: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE finance_recurring_entries SET last_generated_date = ? WHERE id = ?",
                (generated_date, entry_id),
            )
            self._conn.commit()

    # ── Budgets ───────────────────────────────────────────────────────────────

    def upsert_budget(
        self,
        *,
        company_name: str,
        year: int,
        month: int | None,
        category: str,
        entry_type: str,
        budget_amount: float,
    ) -> dict[str, Any]:
        now = int(time.time())
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO finance_budgets(
                    company_name, year, month, category, entry_type,
                    budget_amount, created_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(company_name, year, month, category, entry_type)
                DO UPDATE SET budget_amount = excluded.budget_amount
                """,
                (company_name, year, month, category, entry_type, budget_amount, now),
            )
            self._conn.commit()
            row = self._conn.execute(
                """
                SELECT id, company_name, year, month, category, entry_type,
                       budget_amount, created_at
                FROM finance_budgets
                WHERE company_name = ? AND year = ?
                  AND (month IS ? OR (month IS NULL AND ? IS NULL))
                  AND category = ? AND entry_type = ?
                """,
                (company_name, year, month, month, category, entry_type),
            ).fetchone()
        if row is None:
            raise RuntimeError("Budget upsert failed")
        return dict(row)

    def list_budgets(
        self,
        *,
        company_name: str | None = None,
        year: int | None = None,
        month: int | None = None,
    ) -> list[dict[str, Any]]:
        conditions: list[str] = []
        params: list[Any] = []
        if company_name:
            conditions.append("company_name = ?")
            params.append(company_name)
        if year is not None:
            conditions.append("year = ?")
            params.append(year)
        if month is not None:
            conditions.append("month = ?")
            params.append(month)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self._lock:
            rows = self._conn.execute(
                f"""
                SELECT id, company_name, year, month, category, entry_type,
                       budget_amount, created_at
                FROM finance_budgets {where}
                ORDER BY year DESC, month DESC, company_name, category
                """,
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def get_actuals_by_category(
        self,
        *,
        company_name: str | None,
        year: int,
        month: int | None,
    ) -> list[dict[str, Any]]:
        """Sum ledger amounts by category+entry_type for a given year/month."""
        if month is not None:
            start_date = f"{year:04d}-{month:02d}-01"
            # Last day of month approximation via next month
            import calendar
            last_day = calendar.monthrange(year, month)[1]
            end_date = f"{year:04d}-{month:02d}-{last_day:02d}"
        else:
            start_date = f"{year:04d}-01-01"
            end_date = f"{year:04d}-12-31"

        conditions: list[str] = ["entry_date >= ?", "entry_date <= ?"]
        params: list[Any] = [start_date, end_date]
        if company_name:
            conditions.append("company_name = ?")
            params.append(company_name)

        where = f"WHERE {' AND '.join(conditions)}"
        with self._lock:
            rows = self._conn.execute(
                f"""
                SELECT category, entry_type, SUM(amount) AS actual_amount
                FROM finance_ledger_entries
                {where}
                GROUP BY category, entry_type
                """,
                params,
            ).fetchall()
        return [dict(row) for row in rows]
