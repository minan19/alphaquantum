"""Tests for S-341 — Çok Para Birimi FX Nakit Akışı (Multi-currency FX Summary)."""
from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from app.currency_converter import CurrencyConverter, DEFAULT_FX_RATES_TO_TRY
from app.invoice_repository import InvoiceRepository
from app.engines.collections_engine import CollectionsEngine
from app.models import InvoiceCreateRequest, InvoicePaymentRequest


def _setup() -> tuple[CollectionsEngine, InvoiceRepository, tempfile.TemporaryDirectory]:
    tmp = tempfile.TemporaryDirectory()
    repo = InvoiceRepository(str(Path(tmp.name) / "fx.db"))
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


def _future(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


class CurrencyConverterTests(unittest.TestCase):
    """Unit tests for the deterministic FX rate table."""

    def test_try_to_try_is_identity(self):
        c = CurrencyConverter()
        self.assertEqual(c.to_try(1000.0, "TRY"), 1000.0)
        self.assertEqual(c.rate("TRY"), 1.0)

    def test_known_currency_returns_default_rate(self):
        c = CurrencyConverter()
        self.assertAlmostEqual(c.rate("USD"), DEFAULT_FX_RATES_TO_TRY["USD"])

    def test_unknown_currency_returns_identity(self):
        c = CurrencyConverter()
        self.assertEqual(c.rate("XYZ"), 1.0)
        # Conversion of unknown currency = pass through
        self.assertEqual(c.to_try(500.0, "XYZ"), 500.0)

    def test_case_insensitive(self):
        c = CurrencyConverter()
        self.assertEqual(c.rate("usd"), c.rate("USD"))
        self.assertEqual(c.to_try(100.0, "eur"), c.to_try(100.0, "EUR"))

    def test_explicit_override(self):
        c = CurrencyConverter(rates={"USD": 50.0})
        self.assertEqual(c.rate("USD"), 50.0)
        self.assertEqual(c.to_try(100.0, "USD"), 5000.0)

    def test_env_override(self):
        os.environ["AQ_FX_USD_TRY"] = "40.5"
        try:
            c = CurrencyConverter()
            self.assertAlmostEqual(c.rate("USD"), 40.5)
        finally:
            del os.environ["AQ_FX_USD_TRY"]

    def test_negative_rates_rejected(self):
        c = CurrencyConverter(rates={"USD": -10.0})
        # Negative is rejected, default stays
        self.assertEqual(c.rate("USD"), DEFAULT_FX_RATES_TO_TRY["USD"])

    def test_invalid_env_value_falls_back(self):
        os.environ["AQ_FX_USD_TRY"] = "not_a_number"
        try:
            c = CurrencyConverter()
            self.assertEqual(c.rate("USD"), DEFAULT_FX_RATES_TO_TRY["USD"])
        finally:
            del os.environ["AQ_FX_USD_TRY"]


class FxReceivablesSummaryTests(unittest.TestCase):
    """Engine-level tests with a controlled converter (no env / market fetches)."""

    def setUp(self):
        self.engine, self.repo, self._tmp = _setup()
        # Pin rates so assertions are stable
        self.converter = CurrencyConverter(rates={
            "TRY": 1.0, "USD": 30.0, "EUR": 35.0, "GBP": 40.0,
        })

    def tearDown(self):
        self.repo.close()
        self._tmp.cleanup()

    def _make(self, *, amount: float, currency: str = "TRY",
              paid: float = 0.0, status_paid: bool = False) -> int:
        inv = self.engine.create_invoice(payload=InvoiceCreateRequest(
            company="Alpha", title="Test",
            amount=amount, currency=currency,
            issue_date="2026-01-01",
            due_date=_future(30),
        ))
        if paid > 0:
            self.engine.record_payment(inv.id, payload=InvoicePaymentRequest(
                payment_amount=paid
            ))
        return inv.id

    def _summary(self):
        return self.engine.fx_aware_receivables_summary(
            company="Alpha", converter=self.converter
        )

    # ── Basic flow ────────────────────────────────────────────────────────────
    def test_empty_returns_zero_totals(self):
        s = self._summary()
        self.assertEqual(s.total_outstanding_try, 0.0)
        self.assertEqual(s.fx_exposure_pct, 0.0)
        self.assertEqual(s.by_currency, [])

    def test_single_try_invoice(self):
        self._make(amount=5000.0, currency="TRY")
        s = self._summary()
        self.assertEqual(s.total_outstanding_try, 5000.0)
        self.assertEqual(len(s.by_currency), 1)
        self.assertEqual(s.by_currency[0].currency, "TRY")
        self.assertEqual(s.by_currency[0].outstanding, 5000.0)
        self.assertEqual(s.by_currency[0].outstanding_try, 5000.0)
        self.assertEqual(s.fx_exposure_pct, 0.0)

    def test_usd_invoice_converted_to_try(self):
        self._make(amount=1000.0, currency="USD")
        s = self._summary()
        self.assertEqual(s.total_outstanding_try, 30000.0)  # 1000 * 30
        usd_bucket = next(b for b in s.by_currency if b.currency == "USD")
        self.assertEqual(usd_bucket.outstanding, 1000.0)
        self.assertEqual(usd_bucket.outstanding_try, 30000.0)
        self.assertEqual(usd_bucket.fx_rate, 30.0)
        self.assertEqual(usd_bucket.pct_of_total, 100.0)

    def test_mixed_currencies(self):
        self._make(amount=10000.0, currency="TRY")   # 10000 TRY
        self._make(amount=1000.0, currency="USD")    # 30000 TRY
        self._make(amount=500.0, currency="EUR")     # 17500 TRY
        s = self._summary()
        # Total should be sum of all TRY-converted
        self.assertEqual(s.total_outstanding_try, 57500.0)
        self.assertEqual(len(s.by_currency), 3)
        currencies = {b.currency for b in s.by_currency}
        self.assertEqual(currencies, {"TRY", "USD", "EUR"})

    def test_fx_exposure_pct_calculation(self):
        self._make(amount=10000.0, currency="TRY")   # 10000 TRY (local)
        self._make(amount=1000.0, currency="USD")    # 30000 TRY (foreign)
        s = self._summary()
        # foreign / total = 30000 / 40000 = 75%
        self.assertEqual(s.fx_exposure_pct, 75.0)

    def test_pure_try_has_zero_exposure(self):
        self._make(amount=5000.0, currency="TRY")
        self._make(amount=3000.0, currency="TRY")
        s = self._summary()
        self.assertEqual(s.fx_exposure_pct, 0.0)

    def test_pure_foreign_has_100_exposure(self):
        self._make(amount=1000.0, currency="USD")
        s = self._summary()
        self.assertEqual(s.fx_exposure_pct, 100.0)

    # ── Exclusions ────────────────────────────────────────────────────────────
    def test_paid_invoices_excluded(self):
        self._make(amount=1000.0, currency="USD", paid=1000.0)
        s = self._summary()
        self.assertEqual(s.total_outstanding_try, 0.0)
        self.assertEqual(s.by_currency, [])

    def test_partial_payment_only_remaining_counted(self):
        self._make(amount=1000.0, currency="USD", paid=400.0)  # 600 USD remaining
        s = self._summary()
        # 600 * 30 = 18000 TRY
        self.assertEqual(s.total_outstanding_try, 18000.0)
        usd = next(b for b in s.by_currency if b.currency == "USD")
        self.assertEqual(usd.outstanding, 600.0)

    # ── Aggregation ───────────────────────────────────────────────────────────
    def test_multiple_invoices_same_currency_aggregated(self):
        self._make(amount=500.0, currency="USD")
        self._make(amount=300.0, currency="USD")
        self._make(amount=200.0, currency="USD")
        s = self._summary()
        usd = next(b for b in s.by_currency if b.currency == "USD")
        self.assertEqual(usd.count, 3)
        self.assertEqual(usd.outstanding, 1000.0)

    # ── Sort order ────────────────────────────────────────────────────────────
    def test_try_listed_first(self):
        self._make(amount=100.0, currency="USD")     # 3000 TRY equiv
        self._make(amount=100.0, currency="TRY")     # 100 TRY (much smaller)
        s = self._summary()
        self.assertEqual(s.by_currency[0].currency, "TRY")

    def test_foreign_currencies_sorted_by_try_value_desc(self):
        self._make(amount=100.0, currency="GBP")   # 4000 TRY
        self._make(amount=100.0, currency="USD")   # 3000 TRY
        self._make(amount=100.0, currency="EUR")   # 3500 TRY
        s = self._summary()
        foreign = [b.currency for b in s.by_currency if b.currency != "TRY"]
        self.assertEqual(foreign, ["GBP", "EUR", "USD"])

    # ── Percentages add up ────────────────────────────────────────────────────
    def test_percentages_sum_to_100(self):
        self._make(amount=10000.0, currency="TRY")
        self._make(amount=500.0, currency="USD")
        self._make(amount=200.0, currency="EUR")
        s = self._summary()
        total_pct = sum(b.pct_of_total for b in s.by_currency)
        self.assertAlmostEqual(total_pct, 100.0, places=0)

    # ── as_of_date ────────────────────────────────────────────────────────────
    def test_as_of_date_is_today(self):
        self._make(amount=1000.0, currency="USD")
        s = self._summary()
        self.assertEqual(s.as_of_date, date.today().isoformat())


class FxReceivablesApiTests(unittest.TestCase):
    """API wiring tests."""

    def setUp(self):
        from fastapi.testclient import TestClient
        from app import create_app

        self._tmp = tempfile.TemporaryDirectory()
        db = Path(self._tmp.name) / "fx_api.db"
        self._orig = {k: os.getenv(k) for k in [
            "AQ_DATABASE_PATH", "AQ_AUTH_USERS", "AQ_ENABLE_DEMO_USERS",
            "AQ_JWT_SECRET", "AQ_ENV", "AQ_MARKET_OFFLINE",
            "AQ_MACRO_OFFLINE", "AQ_WEB_OFFLINE",
        ]}
        os.environ.update({
            "AQ_DATABASE_PATH": str(db),
            "AQ_AUTH_USERS": "admin:admin12345:admin",
            "AQ_ENABLE_DEMO_USERS": "false",
            "AQ_JWT_SECRET": "fx-test-secret",
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
        resp = self.client.get("/api/v1/collections/fx-summary")
        self.assertEqual(resp.status_code, 401)

    def test_returns_200_with_response_shape(self):
        company = self._company()
        resp = self.client.get(
            "/api/v1/collections/fx-summary",
            params={"company": company},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        for key in ("company", "total_outstanding_try", "fx_exposure_pct",
                    "by_currency", "as_of_date"):
            self.assertIn(key, body)

    def test_empty_company_returns_zeros(self):
        company = self._company()
        resp = self.client.get(
            "/api/v1/collections/fx-summary",
            params={"company": company},
            headers=self.headers,
        )
        body = resp.json()
        self.assertEqual(body["total_outstanding_try"], 0.0)
        self.assertEqual(body["fx_exposure_pct"], 0.0)
        self.assertEqual(body["by_currency"], [])

    def test_usd_invoice_appears_in_breakdown(self):
        company = self._company()
        self.client.post(
            "/api/v1/collections/invoices",
            json={
                "company": company, "title": "USD Invoice",
                "amount": 1000.0, "currency": "USD",
                "issue_date": "2026-01-01",
                "due_date": _future(30),
            },
            headers=self.headers,
        )
        resp = self.client.get(
            "/api/v1/collections/fx-summary",
            params={"company": company},
            headers=self.headers,
        )
        body = resp.json()
        currencies = [b["currency"] for b in body["by_currency"]]
        self.assertIn("USD", currencies)
        self.assertGreater(body["total_outstanding_try"], 0.0)
        self.assertEqual(body["fx_exposure_pct"], 100.0)


if __name__ == "__main__":
    unittest.main()
