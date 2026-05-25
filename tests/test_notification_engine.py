"""Tests for S-334 — Vade Uyarı / Bildirim Motoru (Notification Engine)."""
from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from app.invoice_repository import InvoiceRepository
from app.notification_repository import NotificationRepository
from app.engines.collections_engine import CollectionsEngine
from app.engines.notification_engine import NotificationEngine
from app.models import InvoiceCreateRequest, InvoicePaymentRequest


def _setup() -> tuple[
    NotificationEngine, CollectionsEngine,
    InvoiceRepository, NotificationRepository,
    tempfile.TemporaryDirectory,
]:
    tmp = tempfile.TemporaryDirectory()
    db = str(Path(tmp.name) / "notif.db")
    inv_repo = InvoiceRepository(db)
    notif_repo = NotificationRepository(db)
    notif_repo._conn.executescript("""
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
        CREATE TABLE IF NOT EXISTS notifications (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name  TEXT NOT NULL,
            kind          TEXT NOT NULL,
            severity      TEXT NOT NULL DEFAULT 'info',
            subject_type  TEXT NOT NULL,
            subject_id    INTEGER NOT NULL,
            window_key    TEXT NOT NULL,
            title         TEXT NOT NULL,
            message       TEXT NOT NULL DEFAULT '',
            is_read       INTEGER NOT NULL DEFAULT 0,
            created_at    INTEGER NOT NULL,
            updated_at    INTEGER NOT NULL,
            UNIQUE(subject_type, subject_id, window_key)
        );
    """)
    notif_repo._conn.commit()
    coll = CollectionsEngine(inv_repo)
    engine = NotificationEngine(notif_repo=notif_repo, invoice_repo=inv_repo)
    return engine, coll, inv_repo, notif_repo, tmp


def _future(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def _past(days: int) -> str:
    return (date.today() - timedelta(days=days)).isoformat()


class NotificationScanTests(unittest.TestCase):
    def setUp(self):
        self.engine, self.coll, self.inv_repo, self.notif_repo, self._tmp = _setup()

    def tearDown(self):
        self.notif_repo.close()
        self.inv_repo.close()
        self._tmp.cleanup()

    def _make(self, due_offset: int, amount: float = 1000.0) -> int:
        """due_offset > 0 means past due; < 0 means future due."""
        due = _past(due_offset) if due_offset > 0 else _future(-due_offset)
        return self.coll.create_invoice(payload=InvoiceCreateRequest(
            company="Alpha", title="Test",
            amount=amount,
            issue_date="2026-01-01",
            due_date=due,
        )).id

    # ── Window triggers ──────────────────────────────────────────────────────
    def test_due_in_3_days_creates_T_minus_3(self):
        self._make(due_offset=-3)  # due in 3 days
        result = self.engine.scan_invoices(company="Alpha")
        windows = {n.window_key for n in self.engine.list_notifications(
            company="Alpha"
        ).notifications}
        self.assertIn("T-3", windows)

    def test_due_in_1_day_creates_T_minus_1(self):
        self._make(due_offset=-1)
        self.engine.scan_invoices(company="Alpha")
        windows = {n.window_key for n in self.engine.list_notifications(
            company="Alpha"
        ).notifications}
        self.assertIn("T-1", windows)

    def test_overdue_1_day_creates_T_plus_1(self):
        self._make(due_offset=1)  # 1 day past
        self.engine.scan_invoices(company="Alpha")
        windows = {n.window_key for n in self.engine.list_notifications(
            company="Alpha"
        ).notifications}
        self.assertIn("T+1", windows)

    def test_overdue_7_days_creates_T_plus_7(self):
        self._make(due_offset=7)
        self.engine.scan_invoices(company="Alpha")
        windows = {n.window_key for n in self.engine.list_notifications(
            company="Alpha"
        ).notifications}
        # Both T+1 and T+7 should fire when 7+ days overdue
        self.assertIn("T+1", windows)
        self.assertIn("T+7", windows)

    def test_overdue_14_days_creates_all_overdue_windows(self):
        self._make(due_offset=14)
        self.engine.scan_invoices(company="Alpha")
        windows = {n.window_key for n in self.engine.list_notifications(
            company="Alpha"
        ).notifications}
        self.assertIn("T+1", windows)
        self.assertIn("T+7", windows)
        self.assertIn("T+14", windows)

    def test_future_invoice_creates_no_notification(self):
        self._make(due_offset=-30)  # due in 30 days, far away
        self.engine.scan_invoices(company="Alpha")
        items = self.engine.list_notifications(company="Alpha").notifications
        self.assertEqual(len(items), 0)

    def test_paid_invoice_not_scanned(self):
        inv_id = self._make(due_offset=5)
        self.coll.record_payment(inv_id, payload=InvoicePaymentRequest(
            payment_amount=1000.0
        ))
        self.engine.scan_invoices(company="Alpha")
        items = self.engine.list_notifications(company="Alpha").notifications
        self.assertEqual(len(items), 0)

    # ── Idempotency ──────────────────────────────────────────────────────────
    def test_scan_is_idempotent(self):
        self._make(due_offset=5)
        first = self.engine.scan_invoices(company="Alpha")
        second = self.engine.scan_invoices(company="Alpha")
        self.assertGreater(first.created, 0)
        self.assertEqual(second.created, 0)

    def test_scan_reports_scanned_count(self):
        self._make(due_offset=5)
        self._make(due_offset=10)
        result = self.engine.scan_invoices(company="Alpha")
        self.assertEqual(result.scanned, 2)

    # ── Severity assignment ──────────────────────────────────────────────────
    def test_T_minus_3_is_info(self):
        self._make(due_offset=-3)
        self.engine.scan_invoices(company="Alpha")
        items = self.engine.list_notifications(company="Alpha").notifications
        t_minus_3 = next(n for n in items if n.window_key == "T-3")
        self.assertEqual(t_minus_3.severity, "info")

    def test_T_plus_7_is_critical(self):
        self._make(due_offset=7)
        self.engine.scan_invoices(company="Alpha")
        items = self.engine.list_notifications(company="Alpha").notifications
        t_plus_7 = next(n for n in items if n.window_key == "T+7")
        self.assertEqual(t_plus_7.severity, "critical")

    # ── Filtering ────────────────────────────────────────────────────────────
    def test_list_filter_by_severity(self):
        self._make(due_offset=7)  # creates info+warning+critical mix
        self.engine.scan_invoices(company="Alpha")
        critical = self.engine.list_notifications(
            company="Alpha", severity="critical"
        ).notifications
        self.assertTrue(all(n.severity == "critical" for n in critical))

    def test_list_unread_only(self):
        self._make(due_offset=5)
        self.engine.scan_invoices(company="Alpha")
        items = self.engine.list_notifications(company="Alpha").notifications
        self.engine.mark_read(items[0].id)
        unread = self.engine.list_notifications(
            company="Alpha", unread_only=True
        ).notifications
        self.assertNotIn(items[0].id, [n.id for n in unread])

    # ── mark_read ─────────────────────────────────────────────────────────────
    def test_mark_read_flips_flag(self):
        self._make(due_offset=5)
        self.engine.scan_invoices(company="Alpha")
        items = self.engine.list_notifications(company="Alpha").notifications
        self.assertFalse(items[0].is_read)
        updated = self.engine.mark_read(items[0].id)
        self.assertIsNotNone(updated)
        self.assertTrue(updated.is_read)

    def test_mark_read_missing_returns_none(self):
        result = self.engine.mark_read(99999)
        self.assertIsNone(result)

    # ── Summary ──────────────────────────────────────────────────────────────
    def test_summary_counts(self):
        self._make(due_offset=7)
        self.engine.scan_invoices(company="Alpha")
        summary = self.engine.summary(company="Alpha")
        self.assertGreater(summary.total, 0)
        self.assertGreater(summary.unread, 0)
        self.assertGreater(summary.critical, 0)

    def test_summary_unread_decrements_after_mark(self):
        self._make(due_offset=5)
        self.engine.scan_invoices(company="Alpha")
        items = self.engine.list_notifications(company="Alpha").notifications
        before = self.engine.summary(company="Alpha").unread
        self.engine.mark_read(items[0].id)
        after = self.engine.summary(company="Alpha").unread
        self.assertEqual(after, before - 1)

    # ── Company isolation ─────────────────────────────────────────────────────
    def test_other_company_invoices_not_scanned(self):
        # Beta invoice
        self.coll.create_invoice(payload=InvoiceCreateRequest(
            company="Beta", title="X", amount=1000,
            issue_date="2026-01-01", due_date=_past(5),
        ))
        result = self.engine.scan_invoices(company="Alpha")
        self.assertEqual(result.created, 0)


class NotificationApiTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from app import create_app

        self._tmp = tempfile.TemporaryDirectory()
        db = Path(self._tmp.name) / "notif_api.db"
        self._orig = {k: os.getenv(k) for k in [
            "AQ_DATABASE_PATH", "AQ_AUTH_USERS", "AQ_ENABLE_DEMO_USERS",
            "AQ_JWT_SECRET", "AQ_ENV", "AQ_MARKET_OFFLINE",
            "AQ_MACRO_OFFLINE", "AQ_WEB_OFFLINE",
        ]}
        os.environ.update({
            "AQ_DATABASE_PATH": str(db),
            "AQ_AUTH_USERS": "admin:admin12345:admin",
            "AQ_ENABLE_DEMO_USERS": "false",
            "AQ_JWT_SECRET": "notif-test-secret",
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

    def _seed_overdue_invoice(self, company: str) -> dict:
        return self.client.post(
            "/api/v1/collections/invoices",
            json={
                "company": company, "title": "Test",
                "amount": 1000.0,
                "issue_date": _past(60),
                "due_date": _past(10),
            },
            headers=self.headers,
        ).json()

    def test_list_requires_auth(self):
        resp = self.client.get("/api/v1/notifications")
        self.assertEqual(resp.status_code, 401)

    def test_generate_requires_auth(self):
        resp = self.client.post("/api/v1/notifications/generate")
        self.assertEqual(resp.status_code, 401)

    def test_generate_creates_notifications_for_overdue(self):
        company = self._company()
        self._seed_overdue_invoice(company)
        resp = self.client.post(
            "/api/v1/notifications/generate",
            params={"company": company},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertGreater(body["scanned"], 0)
        self.assertGreater(body["created"], 0)

    def test_list_returns_generated_notifications(self):
        company = self._company()
        self._seed_overdue_invoice(company)
        self.client.post(
            "/api/v1/notifications/generate",
            params={"company": company},
            headers=self.headers,
        )
        resp = self.client.get(
            "/api/v1/notifications",
            params={"company": company},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertGreater(resp.json()["total"], 0)

    def test_summary_endpoint(self):
        company = self._company()
        self._seed_overdue_invoice(company)
        self.client.post(
            "/api/v1/notifications/generate",
            params={"company": company},
            headers=self.headers,
        )
        resp = self.client.get(
            "/api/v1/notifications/summary",
            params={"company": company},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        for key in ("total", "unread", "info", "warning", "critical"):
            self.assertIn(key, body)

    def test_mark_read_endpoint(self):
        company = self._company()
        self._seed_overdue_invoice(company)
        self.client.post(
            "/api/v1/notifications/generate",
            params={"company": company},
            headers=self.headers,
        )
        items = self.client.get(
            "/api/v1/notifications",
            params={"company": company},
            headers=self.headers,
        ).json()["notifications"]
        nid = items[0]["id"]
        resp = self.client.patch(
            f"/api/v1/notifications/{nid}/read", headers=self.headers
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["is_read"])

    def test_mark_read_404_for_missing(self):
        resp = self.client.patch(
            "/api/v1/notifications/99999/read", headers=self.headers
        )
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
