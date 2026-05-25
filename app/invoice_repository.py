from __future__ import annotations

import sqlite3
import time
from threading import Lock
from typing import Any


class InvoiceRepository:
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

    def create_invoice(
        self,
        *,
        company_name: str,
        title: str,
        amount: float,
        issue_date: str,
        due_date: str,
        customer_id: int | None = None,
        proposal_id: int | None = None,
        invoice_number: str = "",
        currency: str = "TRY",
        description: str = "",
    ) -> dict[str, Any]:
        now = int(time.time())
        with self._lock:
            cur = self._conn.execute(
                """
                INSERT INTO invoices(
                    company_name, customer_id, proposal_id, invoice_number,
                    title, amount, paid_amount, currency, status,
                    issue_date, due_date, description, created_at, updated_at
                ) VALUES(?,?,?,?,?,?,0,?,'pending',?,?,?,?,?)
                """,
                (company_name, customer_id, proposal_id, invoice_number,
                 title, amount, currency, issue_date, due_date,
                 description, now, now),
            )
            row_id = int(cur.lastrowid)
            self._conn.commit()
            return self._fetch(row_id)

    def get_invoice(self, invoice_id: int) -> dict[str, Any] | None:
        with self._lock:
            return self._fetch(invoice_id)

    def _fetch(self, invoice_id: int) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM invoices WHERE id = ?", (invoice_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_invoices(
        self,
        *,
        company_name: str | None,
        customer_id: int | None = None,
        status: str | None = None,
        overdue_only: bool = False,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if company_name:
            clauses.append("company_name = ?"); params.append(company_name)
        if customer_id is not None:
            clauses.append("customer_id = ?"); params.append(customer_id)
        if status:
            clauses.append("status = ?"); params.append(status)
        if overdue_only:
            today = time.strftime("%Y-%m-%d")
            clauses.append("due_date < ?"); params.append(today)
            clauses.append("status NOT IN ('paid','cancelled')")
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM invoices {where} ORDER BY due_date ASC, id DESC LIMIT ?",
                params,
            ).fetchall()
        return [dict(r) for r in rows]

    def record_payment(
        self,
        invoice_id: int,
        *,
        payment_amount: float,
        paid_date: str | None = None,
    ) -> dict[str, Any] | None:
        now = int(time.time())
        today = paid_date or time.strftime("%Y-%m-%d")
        with self._lock:
            row = self._fetch(invoice_id)
            if row is None:
                return None
            new_paid = round(float(row["paid_amount"]) + payment_amount, 2)
            total = float(row["amount"])
            if new_paid >= total:
                new_paid = total
                new_status = "paid"
            elif new_paid > 0:
                new_status = "partial"
            else:
                new_status = row["status"]
            self._conn.execute(
                """UPDATE invoices
                   SET paid_amount=?, status=?, paid_date=?, updated_at=?
                   WHERE id=?""",
                (new_paid, new_status, today, now, invoice_id),
            )
            self._conn.commit()
            return self._fetch(invoice_id)

    def mark_overdue(self, *, company_name: str | None = None) -> int:
        """Set status='overdue' for all past-due unpaid invoices. Returns count updated."""
        today = time.strftime("%Y-%m-%d")
        clauses = ["due_date < ?", "status IN ('pending','partial')"]
        params: list[Any] = [today]
        if company_name:
            clauses.append("company_name = ?"); params.append(company_name)
        where = "WHERE " + " AND ".join(clauses)
        with self._lock:
            cur = self._conn.execute(
                f"UPDATE invoices SET status='overdue', updated_at=? {where}",
                [int(time.time())] + params,
            )
            self._conn.commit()
        return cur.rowcount

    def receivables_summary(self, *, company_name: str | None) -> dict[str, Any]:
        """Total pending + overdue receivables, paid this month."""
        clauses: list[str] = []
        params: list[Any] = []
        if company_name:
            clauses.append("company_name = ?"); params.append(company_name)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._lock:
            rows = self._conn.execute(
                f"""
                SELECT status,
                       COUNT(*) as count,
                       COALESCE(SUM(amount),0) as total_amount,
                       COALESCE(SUM(paid_amount),0) as total_paid
                FROM invoices {where} GROUP BY status
                """,
                params,
            ).fetchall()
        return {r["status"]: {
            "count": r["count"],
            "total_amount": r["total_amount"],
            "total_paid": r["total_paid"],
        } for r in rows}

    def aging_analysis(self, *, company_name: str | None) -> list[dict[str, Any]]:
        """Overdue invoice aging: how many days past due, grouped in bands."""
        clauses = [
            "due_date < date('now')",
            "status NOT IN ('paid', 'cancelled')",
        ]
        params: list[Any] = []
        if company_name:
            clauses.append("company_name = ?"); params.append(company_name)
        where = "WHERE " + " AND ".join(clauses)
        with self._lock:
            rows = self._conn.execute(
                f"""
                SELECT
                  CASE
                    WHEN CAST(julianday('now') - julianday(due_date) AS INTEGER) <= 30
                      THEN '1_30'
                    WHEN CAST(julianday('now') - julianday(due_date) AS INTEGER) <= 60
                      THEN '31_60'
                    WHEN CAST(julianday('now') - julianday(due_date) AS INTEGER) <= 90
                      THEN '61_90'
                    ELSE '90_plus'
                  END AS bucket,
                  COUNT(*) AS cnt,
                  COALESCE(SUM(amount - COALESCE(paid_amount, 0)), 0) AS outstanding
                FROM invoices {where}
                GROUP BY bucket
                """,
                params,
            ).fetchall()
        return [dict(r) for r in rows]

    def upcoming_cashflow(
        self,
        *,
        company_name: str | None,
        horizon_days: int = 90,
    ) -> list[dict[str, Any]]:
        """Pending/partial invoices due within horizon_days, grouped in 30-day bands."""
        clauses = [
            "due_date >= date('now')",
            f"due_date < date('now', '+{horizon_days} days')",
            "status IN ('pending', 'partial')",
        ]
        params: list[Any] = []
        if company_name:
            clauses.append("company_name = ?"); params.append(company_name)
        where = "WHERE " + " AND ".join(clauses)
        with self._lock:
            rows = self._conn.execute(
                f"""
                SELECT
                  CASE
                    WHEN CAST(julianday(due_date) - julianday('now') AS INTEGER) <= 30
                      THEN '0_30'
                    WHEN CAST(julianday(due_date) - julianday('now') AS INTEGER) <= 60
                      THEN '31_60'
                    ELSE '61_90'
                  END AS bucket,
                  COUNT(*) AS cnt,
                  COALESCE(SUM(amount - COALESCE(paid_amount, 0)), 0) AS expected
                FROM invoices {where}
                GROUP BY bucket
                """,
                params,
            ).fetchall()
        return [dict(r) for r in rows]
