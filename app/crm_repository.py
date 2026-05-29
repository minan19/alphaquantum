from __future__ import annotations

import json
import sqlite3

from app._sqlite_helpers import new_row_id
import time
from threading import Lock
from typing import Any


class CRMRepository:
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

    # ── Customers ──────────────────────────────────────────────────────────────

    def create_customer(
        self,
        *,
        company_name: str,
        full_name: str,
        email: str = "",
        phone: str = "",
        sector: str = "general",
        tags: list[str] | None = None,
        notes: str = "",
    ) -> dict[str, Any]:
        now = int(time.time())
        tags_json = json.dumps(tags or [], ensure_ascii=False)
        with self._lock:
            cur = self._conn.execute(
                """
                INSERT INTO customers(
                    company_name, full_name, email, phone, sector,
                    tags, notes, is_active, created_at, updated_at
                ) VALUES(?,?,?,?,?,?,?,1,?,?)
                """,
                (company_name, full_name, email, phone, sector,
                 tags_json, notes, now, now),
            )
            row_id = new_row_id(cur)
            self._conn.commit()
            created = self._fetch_customer(row_id)
            assert created is not None, "Customer disappeared after insert"
            return created

    def get_customer(self, customer_id: int) -> dict[str, Any] | None:
        with self._lock:
            return self._fetch_customer(customer_id)

    def _fetch_customer(self, customer_id: int) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM customers WHERE id = ?", (customer_id,)
        ).fetchone()
        if row is None:
            return None
        return self._parse_customer(dict(row))

    def list_customers(
        self,
        *,
        company_name: str | None,
        active_only: bool = True,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if company_name:
            clauses.append("company_name = ?")
            params.append(company_name)
        if active_only:
            clauses.append("is_active = 1")
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM customers {where} ORDER BY id DESC LIMIT ?", params
            ).fetchall()
        return [self._parse_customer(dict(r)) for r in rows]

    def update_customer(
        self,
        customer_id: int,
        *,
        full_name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        sector: str | None = None,
        tags: list[str] | None = None,
        notes: str | None = None,
        is_active: bool | None = None,
    ) -> dict[str, Any] | None:
        now = int(time.time())
        fields: list[str] = ["updated_at = ?"]
        values: list[Any] = [now]
        if full_name is not None:
            fields.append("full_name = ?"); values.append(full_name)
        if email is not None:
            fields.append("email = ?"); values.append(email)
        if phone is not None:
            fields.append("phone = ?"); values.append(phone)
        if sector is not None:
            fields.append("sector = ?"); values.append(sector)
        if tags is not None:
            fields.append("tags = ?"); values.append(json.dumps(tags, ensure_ascii=False))
        if notes is not None:
            fields.append("notes = ?"); values.append(notes)
        if is_active is not None:
            fields.append("is_active = ?"); values.append(1 if is_active else 0)
        values.append(customer_id)
        with self._lock:
            self._conn.execute(
                f"UPDATE customers SET {', '.join(fields)} WHERE id = ?", values
            )
            self._conn.commit()
            return self._fetch_customer(customer_id)

    # ── S-343: KVKK consent flags ──────────────────────────────────────────────

    def update_consent(
        self,
        customer_id: int,
        *,
        email_consent: bool | None = None,
        sms_consent: bool | None = None,
        whatsapp_consent: bool | None = None,
    ) -> dict[str, Any] | None:
        now = int(time.time())
        fields: list[str] = ["updated_at = ?", "consent_updated_at = ?"]
        values: list[Any] = [now, now]
        if email_consent is not None:
            fields.append("email_consent = ?")
            values.append(1 if email_consent else 0)
        if sms_consent is not None:
            fields.append("sms_consent = ?")
            values.append(1 if sms_consent else 0)
        if whatsapp_consent is not None:
            fields.append("whatsapp_consent = ?")
            values.append(1 if whatsapp_consent else 0)
        if len(fields) == 2:
            # Nothing actually changed; nothing to do.
            return self.get_customer(customer_id)
        values.append(customer_id)
        with self._lock:
            self._conn.execute(
                f"UPDATE customers SET {', '.join(fields)} WHERE id = ?", values
            )
            self._conn.commit()
            return self._fetch_customer(customer_id)

    # ── Proposals ──────────────────────────────────────────────────────────────

    def create_proposal(
        self,
        *,
        company_name: str,
        customer_id: int,
        title: str,
        amount: float,
        currency: str = "TRY",
        valid_until: str | None = None,
        description: str = "",
    ) -> dict[str, Any]:
        now = int(time.time())
        with self._lock:
            cur = self._conn.execute(
                """
                INSERT INTO proposals(
                    company_name, customer_id, title, amount, currency,
                    status, valid_until, description, created_at, updated_at
                ) VALUES(?,?,?,?,?,'draft',?,?,?,?)
                """,
                (company_name, customer_id, title, amount, currency,
                 valid_until, description, now, now),
            )
            row_id = new_row_id(cur)
            self._conn.commit()
            created = self._fetch_proposal(row_id)
            assert created is not None, "Proposal disappeared after insert"
            return created

    def get_proposal(self, proposal_id: int) -> dict[str, Any] | None:
        with self._lock:
            return self._fetch_proposal(proposal_id)

    def _fetch_proposal(self, proposal_id: int) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM proposals WHERE id = ?", (proposal_id,)
        ).fetchone()
        if row is None:
            return None
        return dict(row)

    def list_proposals(
        self,
        *,
        company_name: str | None,
        customer_id: int | None = None,
        status: str | None = None,
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
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM proposals {where} ORDER BY id DESC LIMIT ?", params
            ).fetchall()
        return [dict(r) for r in rows]

    def update_proposal_status(
        self,
        proposal_id: int,
        *,
        status: str,
        amount: float | None = None,
        valid_until: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any] | None:
        now = int(time.time())
        fields = ["status = ?", "updated_at = ?"]
        values: list[Any] = [status, now]
        if amount is not None:
            fields.append("amount = ?"); values.append(amount)
        if valid_until is not None:
            fields.append("valid_until = ?"); values.append(valid_until)
        if description is not None:
            fields.append("description = ?"); values.append(description)
        values.append(proposal_id)
        with self._lock:
            self._conn.execute(
                f"UPDATE proposals SET {', '.join(fields)} WHERE id = ?", values
            )
            self._conn.commit()
            return self._fetch_proposal(proposal_id)

    def proposal_summary(
        self, *, company_name: str | None
    ) -> dict[str, Any]:
        """Return count and total amount by status."""
        clauses: list[str] = []
        params: list[Any] = []
        if company_name:
            clauses.append("company_name = ?"); params.append(company_name)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._lock:
            rows = self._conn.execute(
                f"""
                SELECT status, COUNT(*) as count, COALESCE(SUM(amount),0) as total_amount
                FROM proposals {where} GROUP BY status
                """,
                params,
            ).fetchall()
        return {r["status"]: {"count": r["count"], "total_amount": r["total_amount"]} for r in rows}

    @staticmethod
    def _parse_customer(row: dict[str, Any]) -> dict[str, Any]:
        tags = row.get("tags", "[]")
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except Exception:
                tags = []
        row["tags"] = tags
        return row
