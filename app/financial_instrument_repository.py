from __future__ import annotations

import sqlite3
import time
from threading import Lock
from typing import Any


class FinancialInstrumentRepository:
    """S-342 — Persistence for promissory notes / cheques / bonds."""

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

    # ── CRUD ────────────────────────────────────────────────────────────────

    def create(
        self,
        *,
        company_name: str,
        kind: str,
        amount: float,
        issue_date: str,
        due_date: str,
        currency: str = "TRY",
        customer_id: int | None = None,
        instrument_number: str = "",
        payer_name: str = "",
        bank_name: str = "",
        notes: str = "",
    ) -> dict[str, Any]:
        now = int(time.time())
        with self._lock:
            cur = self._conn.execute(
                """
                INSERT INTO financial_instruments(
                    company_name, customer_id, kind, instrument_number,
                    amount, currency, issue_date, due_date,
                    payer_name, bank_name, status, notes,
                    created_at, updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,'pending',?,?,?)
                """,
                (
                    company_name, customer_id, kind, instrument_number,
                    amount, currency, issue_date, due_date,
                    payer_name, bank_name, notes,
                    now, now,
                ),
            )
            row_id = int(cur.lastrowid)
            self._conn.commit()
            return self._fetch(row_id)

    def get(self, instrument_id: int) -> dict[str, Any] | None:
        with self._lock:
            return self._fetch(instrument_id)

    def _fetch(self, instrument_id: int) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM financial_instruments WHERE id = ?", (instrument_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_instruments(
        self,
        *,
        company_name: str | None,
        kind: str | None = None,
        status: str | None = None,
        customer_id: int | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if company_name:
            clauses.append("company_name = ?"); params.append(company_name)
        if kind:
            clauses.append("kind = ?"); params.append(kind)
        if status:
            clauses.append("status = ?"); params.append(status)
        if customer_id is not None:
            clauses.append("customer_id = ?"); params.append(customer_id)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM financial_instruments {where} "
                f"ORDER BY due_date ASC, id DESC LIMIT ?",
                params,
            ).fetchall()
        return [dict(r) for r in rows]

    def update_status(
        self,
        instrument_id: int,
        *,
        new_status: str,
        cleared_date: str | None = None,
    ) -> dict[str, Any] | None:
        """Transition status; only valid if current status is 'pending'.

        Returns None if instrument doesn't exist, raises ValueError if the
        transition is illegal.
        """
        now = int(time.time())
        with self._lock:
            row = self._fetch(instrument_id)
            if row is None:
                return None
            current = str(row.get("status"))
            if current != "pending":
                raise ValueError(
                    f"cannot transition from terminal status {current!r}"
                )
            if new_status not in ("cleared", "bounced", "cancelled"):
                raise ValueError(f"invalid target status {new_status!r}")

            cleared = cleared_date or (
                time.strftime("%Y-%m-%d") if new_status == "cleared" else None
            )
            self._conn.execute(
                """UPDATE financial_instruments
                   SET status=?, cleared_date=?, updated_at=?
                   WHERE id=?""",
                (new_status, cleared, now, instrument_id),
            )
            self._conn.commit()
            return self._fetch(instrument_id)

    # ── Summary ─────────────────────────────────────────────────────────────

    def summary(self, *, company_name: str | None) -> dict[str, Any]:
        """Aggregate metrics for outstanding & realized instruments."""
        clauses: list[str] = []
        params: list[Any] = []
        if company_name:
            clauses.append("company_name = ?"); params.append(company_name)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        today = time.strftime("%Y-%m-%d")
        with self._lock:
            # Group by status
            status_rows = self._conn.execute(
                f"""SELECT status, COUNT(*) AS cnt,
                           COALESCE(SUM(amount), 0) AS total_amount
                    FROM financial_instruments {where}
                    GROUP BY status""",
                params,
            ).fetchall()
            # Group by kind (only pending instruments — what's still on the books)
            pending_clauses = clauses + ["status = 'pending'"]
            pending_where = "WHERE " + " AND ".join(pending_clauses)
            kind_rows = self._conn.execute(
                f"""SELECT kind, COUNT(*) AS cnt,
                           COALESCE(SUM(amount), 0) AS total_amount
                    FROM financial_instruments {pending_where}
                    GROUP BY kind""",
                params,
            ).fetchall()
            # Overdue pending
            overdue_clauses = clauses + ["status = 'pending'", "due_date < ?"]
            overdue_where = "WHERE " + " AND ".join(overdue_clauses)
            overdue_row = self._conn.execute(
                f"""SELECT COUNT(*) AS cnt,
                           COALESCE(SUM(amount), 0) AS total_amount
                    FROM financial_instruments {overdue_where}""",
                params + [today],
            ).fetchone()
        return {
            "by_status": {
                r["status"]: {"count": int(r["cnt"]), "total_amount": float(r["total_amount"])}
                for r in status_rows
            },
            "by_kind_pending": {
                r["kind"]: {"count": int(r["cnt"]), "total_amount": float(r["total_amount"])}
                for r in kind_rows
            },
            "overdue_pending_count": int(overdue_row["cnt"]) if overdue_row else 0,
            "overdue_pending_amount": (
                float(overdue_row["total_amount"]) if overdue_row else 0.0
            ),
        }
