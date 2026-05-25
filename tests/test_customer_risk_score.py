"""Tests for S-333 — Müşteri Ödeme Risk Skoru (Customer Payment Risk Score)."""
from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from app.invoice_repository import InvoiceRepository
from app.engines.collections_engine import CollectionsEngine
from app.models import InvoiceCreateRequest, InvoicePaymentRequest


def _setup() -> tuple[CollectionsEngine, InvoiceRepository, tempfile.TemporaryDirectory]:
    tmp = tempfile.TemporaryDirectory()
    repo = InvoiceRepository(str(Path(tmp.name) / "rs.db"))
    repo._conn.executescript("""
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            customer_id INTEGER,
            proposal_id INTEGER,
            invoice_number TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL,
            amount REAL NOT NULL,
            paid_amount REAL NOT NULL DEFAULT 0,
            currency TEXT NOT NULL DEFAULT 'TRY',
            status TEXT NOT NULL DEFAULT 'pending',
            issue_date TEXT NOT NULL,
            due_date TEXT NOT NULL,
            paid_date TEXT,
            description TEXT NOT NULL DEFAULT '',
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        );
    """)
    repo._conn.commit()
    return CollectionsEngine(repo), repo, tmp


def _past(days: int) -> str:
    return (date.today() - timedelta(days=days)).isoformat()


def _future(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


class CustomerRiskScoreTests(unittest.TestCase):
    """Engine-level scoring algorithm."""

    def setUp(self):
        self.engine, self.repo, self._tmp = _setup()

    def tearDown(self):
        self.repo.close()
        self._tmp.cleanup()

    def _make_invoice(
        self,
        *,
        customer_id: int = 1,
        amount: float = 1000.0,
        due_offset: int = -10,         # negative=future, positive=past
        paid_amount: float = 0.0,
        paid_offset: int | None = None,  # days from today; None means unpaid
    ) -> int:
        """Create one invoice; optionally record a payment with a given paid_date."""
        if due_offset >= 0:
            due = _past(due_offset)
        else:
            due = _future(-due_offset)
        inv = self.engine.create_invoice(payload=InvoiceCreateRequest(
            company="Alpha",
            customer_id=customer_id,
            title="Test",
            amount=amount,
            issue_date="2026-01-01",
            due_date=due,
        ))
        if paid_amount > 0:
            paid_date = (
                _past(paid_offset) if paid_offset is not None and paid_offset >= 0
                else (_future(-paid_offset) if paid_offset is not None else None)
            )
            self.engine.record_payment(
                inv.id,
                payload=InvoicePaymentRequest(
                    payment_amount=paid_amount,
                    paid_date=paid_date,
                ),
            )
        return inv.id

    def _score(self) -> object:
        return self.engine.customer_risk_score(
            customer_id=1, customer_name="Test Müşteri", company="Alpha"
        )

    # ── NO_HISTORY ────────────────────────────────────────────────────────────
    def test_no_invoices_returns_no_history(self):
        result = self._score()
        self.assertEqual(result.risk_level, "NO_HISTORY")
        self.assertEqual(result.confidence, "LOW")
        self.assertEqual(result.score, 50.0)
        self.assertEqual(result.invoice_count, 0)

    # ── Perfect payer ─────────────────────────────────────────────────────────
    def test_all_on_time_paid_returns_low_risk(self):
        # 3 invoices, all paid before due date
        for _ in range(3):
            self._make_invoice(
                due_offset=-5, paid_amount=1000.0, paid_offset=10
            )
        r = self._score()
        self.assertEqual(r.risk_level, "LOW")
        self.assertEqual(r.score, 100.0)
        self.assertEqual(r.on_time_count, 3)
        self.assertEqual(r.late_paid_count, 0)
        self.assertEqual(r.active_overdue_count, 0)

    # ── High risk (all overdue) ───────────────────────────────────────────────
    def test_all_active_overdue_high_risk(self):
        for _ in range(3):
            self._make_invoice(due_offset=45)  # 45 days past due, unpaid
        r = self._score()
        self.assertEqual(r.active_overdue_count, 3)
        self.assertLess(r.score, 60.0)  # significant penalty from overdue + outstanding
        self.assertIn(r.risk_level, ("MEDIUM", "HIGH"))

    # ── Late payer (paid but late) ────────────────────────────────────────────
    def test_late_paid_lowers_score(self):
        # Paid 30 days after due date
        for _ in range(2):
            self._make_invoice(
                due_offset=40, paid_amount=1000.0, paid_offset=10
            )
        r = self._score()
        self.assertGreater(r.late_paid_count, 0)
        self.assertGreater(r.avg_late_days, 0)
        self.assertLess(r.score, 100.0)

    # ── Confidence levels ─────────────────────────────────────────────────────
    def test_confidence_low_with_one_invoice(self):
        self._make_invoice(due_offset=-30, paid_amount=1000.0, paid_offset=15)
        r = self._score()
        self.assertEqual(r.confidence, "LOW")
        self.assertEqual(r.invoice_count, 1)

    def test_confidence_medium_with_3_invoices(self):
        for _ in range(3):
            self._make_invoice(due_offset=-30, paid_amount=1000.0, paid_offset=15)
        r = self._score()
        self.assertEqual(r.confidence, "MEDIUM")

    def test_confidence_high_with_5plus_invoices(self):
        for _ in range(6):
            self._make_invoice(due_offset=-30, paid_amount=1000.0, paid_offset=15)
        r = self._score()
        self.assertEqual(r.confidence, "HIGH")

    # ── Score bounded [0,100] ─────────────────────────────────────────────────
    def test_score_bounded_at_zero(self):
        # Many heavily overdue invoices
        for _ in range(10):
            self._make_invoice(due_offset=200, amount=10000.0)
        r = self._score()
        self.assertGreaterEqual(r.score, 0.0)
        self.assertLessEqual(r.score, 100.0)

    # ── On-time ratio ─────────────────────────────────────────────────────────
    def test_on_time_ratio_calculation(self):
        # 2 on-time, 2 late
        for _ in range(2):
            self._make_invoice(due_offset=-30, paid_amount=1000.0, paid_offset=10)
        for _ in range(2):
            self._make_invoice(due_offset=30, paid_amount=1000.0, paid_offset=0)
        r = self._score()
        self.assertEqual(r.paid_count, 4)
        self.assertEqual(r.on_time_count, 2)
        self.assertAlmostEqual(r.on_time_ratio, 0.5, places=2)

    # ── Outstanding ratio ─────────────────────────────────────────────────────
    def test_partial_payment_contributes_to_outstanding(self):
        self._make_invoice(
            due_offset=-30, amount=10000.0, paid_amount=4000.0, paid_offset=5
        )
        r = self._score()
        self.assertAlmostEqual(r.total_outstanding, 6000.0, places=1)
        self.assertAlmostEqual(r.total_billed, 10000.0, places=1)

    # ── Factors are populated ─────────────────────────────────────────────────
    def test_factors_listed_for_late_payments(self):
        self._make_invoice(due_offset=30, paid_amount=1000.0, paid_offset=0)
        r = self._score()
        self.assertTrue(any("gecikme" in f.lower() for f in r.factors))

    def test_factors_listed_for_active_overdue(self):
        self._make_invoice(due_offset=45)
        r = self._score()
        self.assertTrue(any("gecikmiş" in f.lower() for f in r.factors))

    def test_factors_for_perfect_payer(self):
        self._make_invoice(due_offset=-30, paid_amount=1000.0, paid_offset=10)
        r = self._score()
        self.assertTrue(any("zamanında" in f.lower() for f in r.factors))

    # ── Company isolation ─────────────────────────────────────────────────────
    def test_other_company_invoices_not_counted(self):
        # invoice for Alpha customer 1
        self._make_invoice(customer_id=1, due_offset=-30, paid_amount=1000.0, paid_offset=10)
        # invoice for Alpha customer 99 — shouldn't pollute customer 1
        self._make_invoice(customer_id=99, due_offset=200, amount=99999.0)
        r = self._score()  # asks for customer_id=1
        self.assertEqual(r.invoice_count, 1)
        self.assertEqual(r.score, 100.0)


class CustomerRiskScoreApiTests(unittest.TestCase):
    """API-level wiring tests."""

    def setUp(self):
        from fastapi.testclient import TestClient
        from app import create_app

        self._tmp = tempfile.TemporaryDirectory()
        db = Path(self._tmp.name) / "rs_api.db"
        self._orig = {k: os.getenv(k) for k in [
            "AQ_DATABASE_PATH", "AQ_AUTH_USERS", "AQ_ENABLE_DEMO_USERS",
            "AQ_JWT_SECRET", "AQ_ENV", "AQ_MARKET_OFFLINE",
            "AQ_MACRO_OFFLINE", "AQ_WEB_OFFLINE",
        ]}
        os.environ.update({
            "AQ_DATABASE_PATH": str(db),
            "AQ_AUTH_USERS": "admin:admin12345:admin",
            "AQ_ENABLE_DEMO_USERS": "false",
            "AQ_JWT_SECRET": "rs-test-secret",
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

    def test_requires_auth(self):
        resp = self.client.get("/api/v1/crm/customers/1/risk-score")
        self.assertEqual(resp.status_code, 401)

    def test_404_for_missing_customer(self):
        resp = self.client.get(
            "/api/v1/crm/customers/99999/risk-score", headers=self.headers
        )
        self.assertEqual(resp.status_code, 404)

    def test_no_history_for_new_customer(self):
        company = self._company()
        c = self.client.post(
            "/api/v1/crm/customers",
            json={"company": company, "full_name": "Test Müşteri"},
            headers=self.headers,
        ).json()
        resp = self.client.get(
            f"/api/v1/crm/customers/{c['id']}/risk-score", headers=self.headers
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["risk_level"], "NO_HISTORY")
        self.assertEqual(body["invoice_count"], 0)
        self.assertEqual(body["score"], 50.0)

    def test_score_reflects_invoice_history(self):
        company = self._company()
        c = self.client.post(
            "/api/v1/crm/customers",
            json={"company": company, "full_name": "Düzenli Ödeyici"},
            headers=self.headers,
        ).json()
        # create + fully pay one invoice on time
        inv = self.client.post(
            "/api/v1/collections/invoices",
            json={
                "company": company, "customer_id": c["id"],
                "title": "Test", "amount": 1000.0,
                "issue_date": _past(60),
                "due_date": _past(30),
            },
            headers=self.headers,
        ).json()
        self.client.post(
            f"/api/v1/collections/invoices/{inv['id']}/payment",
            json={"payment_amount": 1000.0, "paid_date": _past(35)},
            headers=self.headers,
        )
        resp = self.client.get(
            f"/api/v1/crm/customers/{c['id']}/risk-score", headers=self.headers
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["invoice_count"], 1)
        self.assertEqual(body["on_time_count"], 1)
        self.assertEqual(body["risk_level"], "LOW")
        self.assertEqual(body["score"], 100.0)

    def test_response_includes_factors(self):
        company = self._company()
        c = self.client.post(
            "/api/v1/crm/customers",
            json={"company": company, "full_name": "Y"},
            headers=self.headers,
        ).json()
        resp = self.client.get(
            f"/api/v1/crm/customers/{c['id']}/risk-score", headers=self.headers
        )
        self.assertIn("factors", resp.json())
        self.assertIsInstance(resp.json()["factors"], list)


if __name__ == "__main__":
    unittest.main()
