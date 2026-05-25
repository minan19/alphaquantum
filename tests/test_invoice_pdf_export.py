"""Tests for QW-2 — Single-invoice PDF export."""
from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from app.engines.reporting_engine import ReportingEngine


_OPENPYXL_OK = False
try:
    # reportlab is the dependency we actually need — but it doesn't depend on
    # pyexpat so it works fine on this macOS dev box. We mirror the pattern
    # used in test_reporting_engine.py for consistency.
    from reportlab.platypus import SimpleDocTemplate  # noqa: F401
    _REPORTLAB_OK = True
except Exception:
    _REPORTLAB_OK = False


def _future(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def _past(days: int) -> str:
    return (date.today() - timedelta(days=days)).isoformat()


SAMPLE_INVOICE = {
    "id": 42,
    "company_name": "Alpha Corp",
    "customer_id": 7,
    "invoice_number": "INV-2026-001",
    "title": "Aylık Danışmanlık",
    "amount": 12500.0,
    "paid_amount": 5000.0,
    "currency": "TRY",
    "status": "partial",
    "issue_date": "2026-04-01",
    "due_date": "2026-05-15",
    "paid_date": None,
    "description": "Mart ayı consultancy faturası.",
    "created_at": 1700000000,
    "updated_at": 1700000100,
}

SAMPLE_CUSTOMER = {
    "id": 7,
    "company_name": "Alpha Corp",
    "full_name": "Mehmet Demir",
    "email": "mehmet@example.com",
    "phone": "05551234567",
}


@unittest.skipUnless(_REPORTLAB_OK, "reportlab unavailable")
class InvoicePdfRenderTests(unittest.TestCase):
    """Unit tests for ReportingEngine.invoice_to_pdf."""

    def test_returns_pdf_bytes(self):
        engine = ReportingEngine()
        result = engine.invoice_to_pdf(SAMPLE_INVOICE, customer=SAMPLE_CUSTOMER)
        self.assertIsInstance(result, bytes)
        self.assertTrue(result.startswith(b"%PDF"))
        self.assertGreater(len(result), 1000)  # non-trivial size

    def test_pdf_without_customer(self):
        engine = ReportingEngine()
        result = engine.invoice_to_pdf(SAMPLE_INVOICE)  # no customer
        self.assertIsInstance(result, bytes)
        self.assertTrue(result.startswith(b"%PDF"))

    def test_paid_invoice_renders(self):
        engine = ReportingEngine()
        paid_inv = dict(SAMPLE_INVOICE,
                        status="paid", paid_amount=12500.0,
                        paid_date="2026-05-10")
        result = engine.invoice_to_pdf(paid_inv)
        self.assertTrue(result.startswith(b"%PDF"))

    def test_no_description_skips_section(self):
        engine = ReportingEngine()
        inv = dict(SAMPLE_INVOICE, description="")
        result = engine.invoice_to_pdf(inv)
        self.assertTrue(result.startswith(b"%PDF"))

    def test_zero_paid_amount(self):
        engine = ReportingEngine()
        inv = dict(SAMPLE_INVOICE, paid_amount=0, status="pending")
        result = engine.invoice_to_pdf(inv)
        self.assertTrue(result.startswith(b"%PDF"))

    def test_unknown_status_still_renders(self):
        engine = ReportingEngine()
        inv = dict(SAMPLE_INVOICE, status="weird_unknown")
        result = engine.invoice_to_pdf(inv)
        self.assertTrue(result.startswith(b"%PDF"))


@unittest.skipUnless(_REPORTLAB_OK, "reportlab unavailable")
class InvoicePdfApiTests(unittest.TestCase):
    """API integration tests for /api/v1/collections/invoices/{id}.pdf."""

    def setUp(self):
        from fastapi.testclient import TestClient
        from app import create_app

        self._tmp = tempfile.TemporaryDirectory()
        db = Path(self._tmp.name) / "inv_pdf.db"
        self._orig = {k: os.getenv(k) for k in [
            "AQ_DATABASE_PATH", "AQ_AUTH_USERS", "AQ_ENABLE_DEMO_USERS",
            "AQ_JWT_SECRET", "AQ_ENV", "AQ_MARKET_OFFLINE",
            "AQ_MACRO_OFFLINE", "AQ_WEB_OFFLINE",
        ]}
        os.environ.update({
            "AQ_DATABASE_PATH": str(db),
            "AQ_AUTH_USERS": "admin:admin12345:admin",
            "AQ_ENABLE_DEMO_USERS": "false",
            "AQ_JWT_SECRET": "inv-pdf-test-secret",
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

    def _create_invoice(self, company: str, customer_id: int | None = None) -> dict:
        payload = {
            "company": company, "title": "Test PDF Inv",
            "amount": 1000.0,
            "issue_date": _past(30),
            "due_date": _future(15),
        }
        if customer_id is not None:
            payload["customer_id"] = customer_id
        return self.client.post(
            "/api/v1/collections/invoices",
            json=payload, headers=self.headers,
        ).json()

    def test_requires_auth(self):
        resp = self.client.get("/api/v1/collections/invoices/1/pdf")
        self.assertEqual(resp.status_code, 401)

    def test_returns_404_for_missing(self):
        resp = self.client.get(
            "/api/v1/collections/invoices/99999/pdf", headers=self.headers
        )
        self.assertEqual(resp.status_code, 404)

    def test_returns_pdf_content_type(self):
        company = self._company()
        inv = self._create_invoice(company)
        resp = self.client.get(
            f"/api/v1/collections/invoices/{inv['id']}/pdf",
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers["content-type"], "application/pdf")
        self.assertTrue(resp.content.startswith(b"%PDF"))

    def test_has_signature_header(self):
        company = self._company()
        inv = self._create_invoice(company)
        resp = self.client.get(
            f"/api/v1/collections/invoices/{inv['id']}/pdf",
            headers=self.headers,
        )
        sig = resp.headers.get("x-export-signature", "")
        self.assertTrue(sig.startswith("hmac-sha256="))

    def test_content_disposition_attachment(self):
        company = self._company()
        inv = self._create_invoice(company)
        resp = self.client.get(
            f"/api/v1/collections/invoices/{inv['id']}/pdf",
            headers=self.headers,
        )
        cd = resp.headers.get("content-disposition", "")
        self.assertIn("attachment", cd)
        self.assertIn(".pdf", cd)

    def test_pdf_with_linked_customer(self):
        company = self._company()
        c = self.client.post(
            "/api/v1/crm/customers",
            json={"company": company, "full_name": "PDF Test Customer",
                  "email": "pdf@test.com"},
            headers=self.headers,
        ).json()
        inv = self._create_invoice(company, customer_id=c["id"])
        resp = self.client.get(
            f"/api/v1/collections/invoices/{inv['id']}/pdf",
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.content.startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
