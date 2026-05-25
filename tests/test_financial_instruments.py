"""Tests for S-342 — Senet / Çek / Bono Takibi (Financial Instruments)."""
from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from app.financial_instrument_repository import FinancialInstrumentRepository
from app.engines.financial_instrument_engine import FinancialInstrumentEngine
from app.models import (
    FinancialInstrumentCreateRequest,
    FinancialInstrumentStatusUpdateRequest,
)


def _setup() -> tuple[
    FinancialInstrumentEngine, FinancialInstrumentRepository,
    tempfile.TemporaryDirectory,
]:
    tmp = tempfile.TemporaryDirectory()
    repo = FinancialInstrumentRepository(str(Path(tmp.name) / "fi.db"))
    repo._conn.executescript("""
        CREATE TABLE IF NOT EXISTS financial_instruments (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name      TEXT NOT NULL,
            customer_id       INTEGER,
            kind              TEXT NOT NULL CHECK (kind IN ('senet','cek','bono')),
            instrument_number TEXT NOT NULL DEFAULT '',
            amount            REAL NOT NULL,
            currency          TEXT NOT NULL DEFAULT 'TRY',
            issue_date        TEXT NOT NULL,
            due_date          TEXT NOT NULL,
            payer_name        TEXT NOT NULL DEFAULT '',
            bank_name         TEXT NOT NULL DEFAULT '',
            status            TEXT NOT NULL DEFAULT 'pending'
                              CHECK (status IN ('pending','cleared','bounced','cancelled')),
            cleared_date      TEXT,
            notes             TEXT NOT NULL DEFAULT '',
            created_at        INTEGER NOT NULL,
            updated_at        INTEGER NOT NULL
        );
    """)
    repo._conn.commit()
    return FinancialInstrumentEngine(repo), repo, tmp


def _future(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def _past(days: int) -> str:
    return (date.today() - timedelta(days=days)).isoformat()


class FinancialInstrumentEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine, self.repo, self._tmp = _setup()

    def tearDown(self):
        self.repo.close()
        self._tmp.cleanup()

    def _create(self, *, kind: str = "senet", amount: float = 5000.0,
                due_offset: int = -30, **kwargs) -> object:
        return self.engine.create(payload=FinancialInstrumentCreateRequest(
            company="Alpha", kind=kind, amount=amount,
            issue_date="2026-01-01",
            due_date=(_future(-due_offset) if due_offset < 0 else _past(due_offset)),
            **kwargs,
        ))

    # ── Create ────────────────────────────────────────────────────────────────
    def test_create_returns_read(self):
        inst = self._create()
        self.assertEqual(inst.status, "pending")
        self.assertEqual(inst.kind, "senet")
        self.assertEqual(inst.amount, 5000.0)
        self.assertIsNone(inst.cleared_date)

    def test_create_with_all_fields(self):
        inst = self._create(
            kind="cek", amount=12000.0, customer_id=1,
            instrument_number="CK-12345", payer_name="Ahmet Yılmaz",
            bank_name="Garanti BBVA", notes="3 ay vade",
        )
        self.assertEqual(inst.kind, "cek")
        self.assertEqual(inst.instrument_number, "CK-12345")
        self.assertEqual(inst.bank_name, "Garanti BBVA")
        self.assertEqual(inst.payer_name, "Ahmet Yılmaz")

    def test_create_all_three_kinds(self):
        for k in ("senet", "cek", "bono"):
            inst = self._create(kind=k)
            self.assertEqual(inst.kind, k)

    # ── Get ───────────────────────────────────────────────────────────────────
    def test_get_existing(self):
        inst = self._create()
        fetched = self.engine.get(inst.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.id, inst.id)

    def test_get_missing_returns_none(self):
        self.assertIsNone(self.engine.get(99999))

    # ── List & filter ─────────────────────────────────────────────────────────
    def test_list_all(self):
        self._create(kind="senet")
        self._create(kind="cek")
        self._create(kind="bono")
        result = self.engine.list_instruments(company="Alpha")
        self.assertEqual(result.total, 3)

    def test_list_filter_by_kind(self):
        self._create(kind="senet")
        self._create(kind="cek")
        self._create(kind="cek")
        result = self.engine.list_instruments(company="Alpha", kind="cek")
        self.assertEqual(result.total, 2)
        self.assertTrue(all(i.kind == "cek" for i in result.instruments))

    def test_list_filter_by_status(self):
        a = self._create()
        b = self._create()
        self.engine.update_status(b.id, payload=FinancialInstrumentStatusUpdateRequest(
            status="cleared"
        ))
        pending = self.engine.list_instruments(company="Alpha", status="pending")
        cleared = self.engine.list_instruments(company="Alpha", status="cleared")
        self.assertEqual(pending.total, 1)
        self.assertEqual(cleared.total, 1)

    def test_list_filter_by_customer(self):
        self._create(customer_id=1)
        self._create(customer_id=2)
        result = self.engine.list_instruments(company="Alpha", customer_id=1)
        self.assertEqual(result.total, 1)

    # ── Status transitions ────────────────────────────────────────────────────
    def test_clear_instrument(self):
        inst = self._create()
        updated = self.engine.update_status(
            inst.id,
            payload=FinancialInstrumentStatusUpdateRequest(status="cleared"),
        )
        self.assertEqual(updated.status, "cleared")
        self.assertEqual(updated.cleared_date, date.today().isoformat())

    def test_clear_with_explicit_date(self):
        inst = self._create()
        updated = self.engine.update_status(
            inst.id,
            payload=FinancialInstrumentStatusUpdateRequest(
                status="cleared", cleared_date="2026-04-15"
            ),
        )
        self.assertEqual(updated.cleared_date, "2026-04-15")

    def test_bounce_instrument(self):
        inst = self._create(kind="cek")
        updated = self.engine.update_status(
            inst.id,
            payload=FinancialInstrumentStatusUpdateRequest(status="bounced"),
        )
        self.assertEqual(updated.status, "bounced")
        # bounced should NOT auto-populate cleared_date
        self.assertIsNone(updated.cleared_date)

    def test_cancel_instrument(self):
        inst = self._create()
        updated = self.engine.update_status(
            inst.id,
            payload=FinancialInstrumentStatusUpdateRequest(status="cancelled"),
        )
        self.assertEqual(updated.status, "cancelled")

    def test_cannot_transition_from_terminal(self):
        inst = self._create()
        self.engine.update_status(
            inst.id,
            payload=FinancialInstrumentStatusUpdateRequest(status="cleared"),
        )
        with self.assertRaises(ValueError):
            self.engine.update_status(
                inst.id,
                payload=FinancialInstrumentStatusUpdateRequest(status="bounced"),
            )

    def test_update_missing_returns_none(self):
        result = self.engine.update_status(
            99999,
            payload=FinancialInstrumentStatusUpdateRequest(status="cleared"),
        )
        self.assertIsNone(result)

    # ── Summary ───────────────────────────────────────────────────────────────
    def test_summary_empty(self):
        s = self.engine.summary(company="Alpha")
        self.assertEqual(s.total_count, 0)
        self.assertEqual(s.pending_count, 0)
        self.assertEqual(s.overdue_pending_count, 0)

    def test_summary_counts_by_status(self):
        self._create(amount=1000.0)  # pending
        b = self._create(amount=2000.0)
        c = self._create(amount=3000.0)
        d = self._create(amount=4000.0)
        self.engine.update_status(b.id, payload=FinancialInstrumentStatusUpdateRequest(
            status="cleared"))
        self.engine.update_status(c.id, payload=FinancialInstrumentStatusUpdateRequest(
            status="bounced"))
        self.engine.update_status(d.id, payload=FinancialInstrumentStatusUpdateRequest(
            status="cancelled"))
        s = self.engine.summary(company="Alpha")
        self.assertEqual(s.total_count, 4)
        self.assertEqual(s.pending_count, 1)
        self.assertEqual(s.cleared_count, 1)
        self.assertEqual(s.bounced_count, 1)
        self.assertEqual(s.cancelled_count, 1)
        self.assertEqual(s.pending_amount, 1000.0)
        self.assertEqual(s.cleared_amount, 2000.0)
        self.assertEqual(s.bounced_amount, 3000.0)

    def test_summary_by_kind_pending_only(self):
        self._create(kind="senet")
        self._create(kind="cek")
        cleared = self._create(kind="bono")
        self.engine.update_status(cleared.id,
            payload=FinancialInstrumentStatusUpdateRequest(status="cleared"))
        s = self.engine.summary(company="Alpha")
        self.assertEqual(s.by_kind_pending.get("senet"), 1)
        self.assertEqual(s.by_kind_pending.get("cek"), 1)
        # bono was cleared → not in pending breakdown
        self.assertNotIn("bono", s.by_kind_pending)

    def test_summary_overdue_pending(self):
        self._create(amount=1000.0, due_offset=10)   # 10 days past due, pending
        self._create(amount=2000.0, due_offset=-30)  # future, pending
        cleared = self._create(amount=3000.0, due_offset=10)
        self.engine.update_status(cleared.id,
            payload=FinancialInstrumentStatusUpdateRequest(status="cleared"))
        s = self.engine.summary(company="Alpha")
        self.assertEqual(s.overdue_pending_count, 1)
        self.assertEqual(s.overdue_pending_amount, 1000.0)

    # ── Company isolation ────────────────────────────────────────────────────
    def test_other_company_not_listed(self):
        self._create()
        # Beta instrument via direct repo to avoid changing the helper
        self.engine.create(payload=FinancialInstrumentCreateRequest(
            company="Beta", kind="cek", amount=999.0,
            issue_date="2026-01-01", due_date=_future(30),
        ))
        result = self.engine.list_instruments(company="Alpha")
        self.assertEqual(result.total, 1)


class FinancialInstrumentApiTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from app import create_app

        self._tmp = tempfile.TemporaryDirectory()
        db = Path(self._tmp.name) / "fi_api.db"
        self._orig = {k: os.getenv(k) for k in [
            "AQ_DATABASE_PATH", "AQ_AUTH_USERS", "AQ_ENABLE_DEMO_USERS",
            "AQ_JWT_SECRET", "AQ_ENV", "AQ_MARKET_OFFLINE",
            "AQ_MACRO_OFFLINE", "AQ_WEB_OFFLINE",
        ]}
        os.environ.update({
            "AQ_DATABASE_PATH": str(db),
            "AQ_AUTH_USERS": "admin:admin12345:admin",
            "AQ_ENABLE_DEMO_USERS": "false",
            "AQ_JWT_SECRET": "fi-test-secret",
            "AQ_ENV": "development",
            "AQ_MARKET_OFFLINE": "true",
            "AQ_MACRO_OFFLINE": "true",
            "AQ_WEB_OFFLINE": "true",
        })
        self.client = TestClient(create_app())
        token = self.client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin12345"},
        ).json()["access_token"]
        self.headers = {"Authorization": f"Bearer {token}"}

    def tearDown(self):
        self.client.close()
        for k, v in self._orig.items():
            if v is None: os.environ.pop(k, None)
            else: os.environ[k] = v
        self._tmp.cleanup()

    def _company(self) -> str:
        companies = self.client.get("/api/v1/companies", headers=self.headers).json()
        return companies[0]["name"] if companies else "Alpha"

    def _create(self, company: str, *, kind: str = "senet", amount: float = 5000.0) -> dict:
        return self.client.post(
            "/api/v1/financial-instruments",
            json={
                "company": company, "kind": kind, "amount": amount,
                "issue_date": "2026-01-01",
                "due_date": _future(30),
                "payer_name": "Test",
            },
            headers=self.headers,
        ).json()

    def test_create_requires_auth(self):
        resp = self.client.post(
            "/api/v1/financial-instruments",
            json={"company": "X", "kind": "senet", "amount": 100,
                  "issue_date": "2026-01-01", "due_date": "2026-06-30"},
        )
        self.assertEqual(resp.status_code, 401)

    def test_create_returns_201(self):
        company = self._company()
        resp = self.client.post(
            "/api/v1/financial-instruments",
            json={
                "company": company, "kind": "cek", "amount": 7500.0,
                "issue_date": "2026-01-01", "due_date": _future(60),
                "bank_name": "İş Bankası", "instrument_number": "CK-001",
            },
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 201)
        body = resp.json()
        self.assertEqual(body["status"], "pending")
        self.assertEqual(body["kind"], "cek")

    def test_invalid_kind_rejected(self):
        company = self._company()
        resp = self.client.post(
            "/api/v1/financial-instruments",
            json={
                "company": company, "kind": "tahvil", "amount": 100,
                "issue_date": "2026-01-01", "due_date": "2026-06-30",
            },
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 422)

    def test_get_by_id(self):
        company = self._company()
        inst = self._create(company)
        resp = self.client.get(
            f"/api/v1/financial-instruments/{inst['id']}", headers=self.headers
        )
        self.assertEqual(resp.status_code, 200)

    def test_get_missing_404(self):
        resp = self.client.get(
            "/api/v1/financial-instruments/99999", headers=self.headers
        )
        self.assertEqual(resp.status_code, 404)

    def test_list_endpoint(self):
        company = self._company()
        self._create(company, kind="senet")
        self._create(company, kind="cek")
        resp = self.client.get(
            "/api/v1/financial-instruments",
            params={"company": company},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.json()["total"], 2)

    def test_list_filter_by_kind(self):
        company = self._company()
        self._create(company, kind="senet")
        self._create(company, kind="cek")
        resp = self.client.get(
            "/api/v1/financial-instruments",
            params={"company": company, "kind": "cek"},
            headers=self.headers,
        )
        self.assertEqual(resp.json()["total"], 1)

    def test_update_status_endpoint(self):
        company = self._company()
        inst = self._create(company)
        resp = self.client.patch(
            f"/api/v1/financial-instruments/{inst['id']}",
            json={"status": "cleared"},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "cleared")

    def test_terminal_transition_returns_400(self):
        company = self._company()
        inst = self._create(company)
        # First transition succeeds
        self.client.patch(
            f"/api/v1/financial-instruments/{inst['id']}",
            json={"status": "cleared"},
            headers=self.headers,
        )
        # Second attempt should fail
        resp = self.client.patch(
            f"/api/v1/financial-instruments/{inst['id']}",
            json={"status": "bounced"},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 400)

    def test_summary_endpoint(self):
        company = self._company()
        self._create(company, kind="senet", amount=1000.0)
        self._create(company, kind="cek", amount=2000.0)
        resp = self.client.get(
            "/api/v1/financial-instruments/summary",
            params={"company": company},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        for k in ("total_count", "pending_count", "pending_amount",
                  "overdue_pending_count", "by_kind_pending"):
            self.assertIn(k, body)
        self.assertEqual(body["pending_count"], 2)


if __name__ == "__main__":
    unittest.main()
