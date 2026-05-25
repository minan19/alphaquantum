"""Tests for S-331 (aging analysis) and S-332 (cashflow projection)."""
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
    repo = InvoiceRepository(str(Path(tmp.name) / "cf.db"))
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


class AgingAnalysisTests(unittest.TestCase):
    """S-331 — Alacak Yaşlandırma Analizi."""

    def setUp(self):
        self.engine, self.repo, self._tmp = _setup()

    def tearDown(self):
        self.repo.close()
        self._tmp.cleanup()

    def _inv(self, due_offset_days: int, amount: float = 1000.0,
             paid: float = 0.0) -> None:
        """Create an invoice with due date offset from today."""
        inv = self.engine.create_invoice(payload=InvoiceCreateRequest(
            company="Alpha",
            title="Test",
            amount=amount,
            issue_date="2026-01-01",
            due_date=_past(due_offset_days) if due_offset_days > 0 else _future(-due_offset_days),
        ))
        if paid > 0:
            self.engine.record_payment(
                inv.id, payload=InvoicePaymentRequest(payment_amount=paid)
            )

    def test_aging_empty(self):
        summary = self.engine.receivables_summary(company="Alpha")
        ag = summary.aging
        self.assertEqual(ag.total_overdue_count, 0)
        self.assertEqual(ag.total_overdue_outstanding, 0.0)

    def test_aging_1_30_bucket(self):
        self._inv(15)  # 15 days overdue
        summary = self.engine.receivables_summary(company="Alpha")
        ag = summary.aging
        self.assertEqual(ag.days_1_30.count, 1)
        self.assertAlmostEqual(ag.days_1_30.outstanding, 1000.0)
        self.assertEqual(ag.total_overdue_count, 1)

    def test_aging_31_60_bucket(self):
        self._inv(45)  # 45 days overdue
        summary = self.engine.receivables_summary(company="Alpha")
        self.assertEqual(summary.aging.days_31_60.count, 1)

    def test_aging_61_90_bucket(self):
        self._inv(75)
        summary = self.engine.receivables_summary(company="Alpha")
        self.assertEqual(summary.aging.days_61_90.count, 1)

    def test_aging_90_plus_bucket(self):
        self._inv(120)
        summary = self.engine.receivables_summary(company="Alpha")
        self.assertEqual(summary.aging.days_90_plus.count, 1)

    def test_aging_multiple_buckets(self):
        self._inv(10)   # 1_30
        self._inv(40)   # 31_60
        self._inv(100)  # 90_plus
        summary = self.engine.receivables_summary(company="Alpha")
        ag = summary.aging
        self.assertEqual(ag.days_1_30.count, 1)
        self.assertEqual(ag.days_31_60.count, 1)
        self.assertEqual(ag.days_90_plus.count, 1)
        self.assertEqual(ag.total_overdue_count, 3)

    def test_aging_outstanding_excludes_paid_portion(self):
        self._inv(20, amount=1000.0, paid=400.0)  # 600 still outstanding
        summary = self.engine.receivables_summary(company="Alpha")
        self.assertAlmostEqual(summary.aging.days_1_30.outstanding, 600.0, places=1)

    def test_aging_paid_invoices_excluded(self):
        inv = self.engine.create_invoice(payload=InvoiceCreateRequest(
            company="Alpha", title="T", amount=500.0,
            issue_date="2026-01-01", due_date=_past(10),
        ))
        self.engine.record_payment(inv.id, payload=InvoicePaymentRequest(payment_amount=500.0))
        summary = self.engine.receivables_summary(company="Alpha")
        self.assertEqual(summary.aging.total_overdue_count, 0)

    def test_aging_future_invoices_not_counted(self):
        # Future-due invoice should NOT appear in aging
        self.engine.create_invoice(payload=InvoiceCreateRequest(
            company="Alpha", title="T", amount=500.0,
            issue_date="2026-01-01", due_date=_future(30),
        ))
        summary = self.engine.receivables_summary(company="Alpha")
        self.assertEqual(summary.aging.total_overdue_count, 0)

    def test_aging_company_scoped(self):
        self._inv(20)  # Alpha company
        other = self.engine.create_invoice(payload=InvoiceCreateRequest(
            company="Beta", title="T", amount=999.0,
            issue_date="2026-01-01", due_date=_past(30),
        ))
        _ = other
        summary = self.engine.receivables_summary(company="Alpha")
        self.assertEqual(summary.aging.total_overdue_count, 1)


class CashflowProjectionTests(unittest.TestCase):
    """S-332 — Nakit Akışı Projeksiyonu."""

    def setUp(self):
        self.engine, self.repo, self._tmp = _setup()

    def tearDown(self):
        self.repo.close()
        self._tmp.cleanup()

    def test_projection_empty(self):
        proj = self.engine.cashflow_projection(company="Alpha")
        self.assertEqual(len(proj.buckets), 3)
        self.assertEqual(proj.total_expected_income, 0.0)
        self.assertEqual(proj.total_net, 0.0)

    def test_projection_has_three_buckets(self):
        proj = self.engine.cashflow_projection(company="Alpha")
        labels = [b.label for b in proj.buckets]
        self.assertIn("0–30 gün", labels)
        self.assertIn("31–60 gün", labels)
        self.assertIn("61–90 gün", labels)

    def test_projection_invoice_in_0_30_bucket(self):
        self.engine.create_invoice(payload=InvoiceCreateRequest(
            company="Alpha", title="T", amount=5000.0,
            issue_date="2026-01-01", due_date=_future(15),
        ))
        proj = self.engine.cashflow_projection(company="Alpha")
        b0 = proj.buckets[0]  # 0–30
        self.assertEqual(b0.invoice_count, 1)
        self.assertAlmostEqual(b0.expected_income, 5000.0)

    def test_projection_invoice_in_31_60_bucket(self):
        self.engine.create_invoice(payload=InvoiceCreateRequest(
            company="Alpha", title="T", amount=3000.0,
            issue_date="2026-01-01", due_date=_future(45),
        ))
        proj = self.engine.cashflow_projection(company="Alpha")
        b1 = proj.buckets[1]  # 31–60
        self.assertEqual(b1.invoice_count, 1)
        self.assertAlmostEqual(b1.expected_income, 3000.0)

    def test_projection_paid_invoice_excluded(self):
        inv = self.engine.create_invoice(payload=InvoiceCreateRequest(
            company="Alpha", title="T", amount=2000.0,
            issue_date="2026-01-01", due_date=_future(10),
        ))
        self.engine.record_payment(inv.id, payload=InvoicePaymentRequest(payment_amount=2000.0))
        proj = self.engine.cashflow_projection(company="Alpha")
        self.assertEqual(proj.total_expected_income, 0.0)

    def test_projection_partial_shows_remaining(self):
        inv = self.engine.create_invoice(payload=InvoiceCreateRequest(
            company="Alpha", title="T", amount=4000.0,
            issue_date="2026-01-01", due_date=_future(20),
        ))
        self.engine.record_payment(inv.id, payload=InvoicePaymentRequest(payment_amount=1000.0))
        proj = self.engine.cashflow_projection(company="Alpha")
        self.assertAlmostEqual(proj.buckets[0].expected_income, 3000.0, places=1)

    def test_projection_recurring_expense_prorated(self):
        recurring = [{"entry_type": "expense", "amount": 3000.0,
                      "frequency": "monthly", "is_active": True}]
        proj = self.engine.cashflow_projection(company="Alpha", recurring_rows=recurring)
        # Each bucket should have ~3000 TL expense
        for b in proj.buckets:
            self.assertAlmostEqual(b.expected_expense, 3000.0, places=1)
        self.assertAlmostEqual(proj.total_expected_expense, 9000.0, places=1)

    def test_projection_income_expense_entries_excluded(self):
        # income recurring entries should NOT appear as expense
        recurring = [{"entry_type": "income", "amount": 5000.0,
                      "frequency": "monthly", "is_active": True}]
        proj = self.engine.cashflow_projection(company="Alpha", recurring_rows=recurring)
        self.assertEqual(proj.total_expected_expense, 0.0)

    def test_projection_net_calculation(self):
        self.engine.create_invoice(payload=InvoiceCreateRequest(
            company="Alpha", title="T", amount=6000.0,
            issue_date="2026-01-01", due_date=_future(10),
        ))
        recurring = [{"entry_type": "expense", "amount": 1000.0,
                      "frequency": "monthly", "is_active": True}]
        proj = self.engine.cashflow_projection(company="Alpha", recurring_rows=recurring)
        expected_net = proj.total_expected_income - proj.total_expected_expense
        self.assertAlmostEqual(proj.total_net, expected_net, places=2)

    def test_projection_as_of_date_is_today(self):
        proj = self.engine.cashflow_projection(company="Alpha")
        self.assertEqual(proj.as_of_date, date.today().isoformat())


class CashflowProjectionApiTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from app import create_app

        self._tmp = tempfile.TemporaryDirectory()
        db = Path(self._tmp.name) / "cf_api.db"
        self._orig = {k: os.getenv(k) for k in [
            "AQ_DATABASE_PATH", "AQ_AUTH_USERS", "AQ_ENABLE_DEMO_USERS",
            "AQ_JWT_SECRET", "AQ_ENV", "AQ_MARKET_OFFLINE",
            "AQ_MACRO_OFFLINE", "AQ_WEB_OFFLINE",
        ]}
        os.environ.update({
            "AQ_DATABASE_PATH": str(db),
            "AQ_AUTH_USERS": "admin:admin12345:admin",
            "AQ_ENABLE_DEMO_USERS": "false",
            "AQ_JWT_SECRET": "cf-test-secret",
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

    def test_projection_requires_auth(self):
        resp = self.client.get("/api/v1/finance/cashflow-projection")
        self.assertEqual(resp.status_code, 401)

    def test_projection_returns_200(self):
        company = self._company()
        resp = self.client.get(
            "/api/v1/finance/cashflow-projection",
            params={"company": company},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 200)

    def test_projection_response_structure(self):
        company = self._company()
        body = self.client.get(
            "/api/v1/finance/cashflow-projection",
            params={"company": company},
            headers=self.headers,
        ).json()
        self.assertIn("buckets", body)
        self.assertIn("total_expected_income", body)
        self.assertIn("total_net", body)
        self.assertEqual(len(body["buckets"]), 3)

    def test_projection_bucket_fields(self):
        company = self._company()
        body = self.client.get(
            "/api/v1/finance/cashflow-projection",
            params={"company": company},
            headers=self.headers,
        ).json()
        bucket = body["buckets"][0]
        for field in ("label", "expected_income", "expected_expense", "net", "invoice_count"):
            self.assertIn(field, bucket)

    def test_summary_includes_aging(self):
        company = self._company()
        body = self.client.get(
            "/api/v1/collections/summary",
            params={"company": company},
            headers=self.headers,
        ).json()
        self.assertIn("aging", body)
        aging = body["aging"]
        self.assertIn("days_1_30", aging)
        self.assertIn("days_31_60", aging)
        self.assertIn("days_61_90", aging)
        self.assertIn("days_90_plus", aging)
        self.assertIn("total_overdue_count", aging)


if __name__ == "__main__":
    unittest.main()
