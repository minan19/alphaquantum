from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from app.invoice_repository import InvoiceRepository
from app.engines.collections_engine import CollectionsEngine
from app.models import InvoiceCreateRequest, InvoicePaymentRequest


def _setup() -> tuple[CollectionsEngine, InvoiceRepository, tempfile.TemporaryDirectory]:
    tmp = tempfile.TemporaryDirectory()
    repo = InvoiceRepository(str(Path(tmp.name) / "invoices.db"))
    repo._conn.executescript("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL, full_name TEXT NOT NULL,
            created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS proposals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL, customer_id INTEGER NOT NULL,
            title TEXT NOT NULL, amount REAL NOT NULL,
            currency TEXT NOT NULL DEFAULT 'TRY',
            status TEXT NOT NULL DEFAULT 'draft',
            created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
        );
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


class CollectionsEngineUnitTests(unittest.TestCase):
    def setUp(self):
        self.engine, self.repo, self._tmp = _setup()

    def tearDown(self):
        self.repo.close()
        self._tmp.cleanup()

    def _create(self, company="Alpha", amount=10000.0,
                due="2099-12-31", issue="2026-01-01") -> object:
        return self.engine.create_invoice(
            payload=InvoiceCreateRequest(
                company=company, title="Test Faturası",
                amount=amount, issue_date=issue, due_date=due,
                invoice_number="INV-001",
            )
        )

    def test_create_invoice(self):
        inv = self._create()
        self.assertEqual(inv.status, "pending")
        self.assertEqual(inv.amount, 10000.0)
        self.assertEqual(inv.paid_amount, 0.0)

    def test_get_invoice(self):
        inv = self._create()
        fetched = self.engine.get_invoice(inv.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.id, inv.id)

    def test_get_missing_returns_none(self):
        self.assertIsNone(self.engine.get_invoice(9999))

    def test_list_invoices(self):
        self._create(amount=5000.0)
        self._create(amount=8000.0)
        result = self.engine.list_invoices(company="Alpha")
        self.assertEqual(result.total, 2)

    def test_partial_payment(self):
        inv = self._create(amount=10000.0)
        updated = self.engine.record_payment(
            inv.id,
            payload=InvoicePaymentRequest(payment_amount=3000.0),
        )
        self.assertEqual(updated.paid_amount, 3000.0)
        self.assertEqual(updated.status, "partial")

    def test_full_payment(self):
        inv = self._create(amount=10000.0)
        updated = self.engine.record_payment(
            inv.id,
            payload=InvoicePaymentRequest(payment_amount=10000.0, paid_date="2026-03-15"),
        )
        self.assertEqual(updated.status, "paid")
        self.assertEqual(updated.paid_amount, 10000.0)
        self.assertEqual(updated.paid_date, "2026-03-15")

    def test_overpayment_capped_at_full(self):
        inv = self._create(amount=5000.0)
        updated = self.engine.record_payment(
            inv.id,
            payload=InvoicePaymentRequest(payment_amount=9999.0),
        )
        self.assertEqual(updated.paid_amount, 5000.0)
        self.assertEqual(updated.status, "paid")

    def test_overdue_detection(self):
        self._create(due="2020-01-01")  # past due date
        result = self.engine.list_invoices(company="Alpha")
        self.assertEqual(result.invoices[0].status, "overdue")

    def test_list_overdue_only(self):
        self._create(due="2020-01-01")   # overdue
        self._create(due="2099-12-31")   # future
        result = self.engine.list_invoices(company="Alpha", overdue_only=True)
        self.assertEqual(result.total, 1)

    def test_receivables_summary(self):
        self._create(amount=5000.0)   # pending
        inv2 = self._create(amount=8000.0)
        self.engine.record_payment(inv2.id,
                                   payload=InvoicePaymentRequest(payment_amount=8000.0))
        summary = self.engine.receivables_summary(company="Alpha")
        self.assertEqual(summary.paid_count, 1)
        self.assertGreaterEqual(summary.pending_amount, 0)

    def test_total_outstanding_excludes_paid(self):
        inv = self._create(amount=10000.0)
        self.engine.record_payment(inv.id,
                                   payload=InvoicePaymentRequest(payment_amount=10000.0))
        self._create(amount=3000.0)  # pending
        summary = self.engine.receivables_summary(company="Alpha")
        self.assertAlmostEqual(summary.total_outstanding, 3000.0, places=1)


class CollectionsApiTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from app import create_app

        self._tmp = tempfile.TemporaryDirectory()
        db = Path(self._tmp.name) / "coll_api.db"
        self._orig = {k: os.getenv(k) for k in [
            "AQ_DATABASE_PATH", "AQ_AUTH_USERS", "AQ_ENABLE_DEMO_USERS",
            "AQ_JWT_SECRET", "AQ_ENV", "AQ_MARKET_OFFLINE",
            "AQ_MACRO_OFFLINE", "AQ_WEB_OFFLINE",
        ]}
        os.environ.update({
            "AQ_DATABASE_PATH": str(db),
            "AQ_AUTH_USERS": "admin:admin12345:admin",
            "AQ_ENABLE_DEMO_USERS": "false",
            "AQ_JWT_SECRET": "coll-test-secret",
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

    def _create_invoice(self, company: str, amount: float = 5000.0) -> dict:
        return self.client.post(
            "/api/v1/collections/invoices",
            json={
                "company": company, "title": "Test Fatura",
                "amount": amount, "issue_date": "2026-01-01",
                "due_date": "2026-06-30",
            },
            headers=self.headers,
        ).json()

    def test_create_requires_auth(self):
        resp = self.client.post("/api/v1/collections/invoices",
                                json={"company": "X", "title": "Y",
                                      "amount": 100, "issue_date": "2026-01-01",
                                      "due_date": "2026-02-01"})
        self.assertEqual(resp.status_code, 401)

    def test_create_invoice(self):
        company = self._company()
        resp = self.client.post(
            "/api/v1/collections/invoices",
            json={"company": company, "title": "API Fatura",
                  "amount": 12000, "issue_date": "2026-01-01",
                  "due_date": "2026-06-30", "currency": "TRY"},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["status"], "pending")

    def test_get_invoice(self):
        company = self._company()
        inv = self._create_invoice(company)
        resp = self.client.get(
            f"/api/v1/collections/invoices/{inv['id']}", headers=self.headers
        )
        self.assertEqual(resp.status_code, 200)

    def test_list_invoices(self):
        company = self._company()
        self._create_invoice(company)
        resp = self.client.get("/api/v1/collections/invoices",
                               params={"company": company},
                               headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.json()["total"], 1)

    def test_record_payment(self):
        company = self._company()
        inv = self._create_invoice(company, 5000.0)
        resp = self.client.post(
            f"/api/v1/collections/invoices/{inv['id']}/payment",
            json={"payment_amount": 5000.0},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "paid")

    def test_receivables_summary(self):
        company = self._company()
        resp = self.client.get("/api/v1/collections/summary",
                               params={"company": company},
                               headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("total_outstanding", resp.json())

    def test_get_missing_invoice_404(self):
        resp = self.client.get("/api/v1/collections/invoices/99999",
                               headers=self.headers)
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
