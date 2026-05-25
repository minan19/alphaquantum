"""Tests for S-343 — Tahsilat Kanalı (delivery engine + providers + consent)."""
from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from app.channel_providers import (
    ChannelProvider,
    ConsoleProvider,
    ProviderRegistry,
    ProviderResult,
    SendGridEmailProvider,
)
from app.crm_repository import CRMRepository
from app.delivery_log_repository import DeliveryLogRepository
from app.engines.collections_engine import CollectionsEngine
from app.engines.crm_engine import CRMEngine
from app.engines.delivery_engine import DeliveryEngine
from app.engines.notification_engine import NotificationEngine
from app.invoice_repository import InvoiceRepository
from app.notification_repository import NotificationRepository
from app.models import (
    CustomerCreateRequest,
    CustomerUpdateRequest,
    InvoiceCreateRequest,
)


def _future(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def _past(days: int) -> str:
    return (date.today() - timedelta(days=days)).isoformat()


def _setup() -> tuple[
    DeliveryEngine, CRMEngine, NotificationEngine, CollectionsEngine,
    CRMRepository, InvoiceRepository, NotificationRepository,
    DeliveryLogRepository, tempfile.TemporaryDirectory,
]:
    tmp = tempfile.TemporaryDirectory()
    db = str(Path(tmp.name) / "delivery.db")
    crm_repo = CRMRepository(db)
    inv_repo = InvoiceRepository(db)
    notif_repo = NotificationRepository(db)
    log_repo = DeliveryLogRepository(db)
    crm_repo._conn.executescript("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL, full_name TEXT NOT NULL,
            email TEXT NOT NULL DEFAULT '', phone TEXT NOT NULL DEFAULT '',
            sector TEXT NOT NULL DEFAULT 'general', tags TEXT NOT NULL DEFAULT '[]',
            notes TEXT NOT NULL DEFAULT '', is_active INTEGER NOT NULL DEFAULT 1,
            email_consent INTEGER NOT NULL DEFAULT 0,
            sms_consent INTEGER NOT NULL DEFAULT 0,
            whatsapp_consent INTEGER NOT NULL DEFAULT 0,
            consent_updated_at INTEGER NOT NULL DEFAULT 0,
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
            company_name TEXT NOT NULL, customer_id INTEGER,
            proposal_id INTEGER, invoice_number TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL, amount REAL NOT NULL,
            paid_amount REAL NOT NULL DEFAULT 0,
            currency TEXT NOT NULL DEFAULT 'TRY',
            status TEXT NOT NULL DEFAULT 'pending',
            issue_date TEXT NOT NULL, due_date TEXT NOT NULL,
            paid_date TEXT, description TEXT NOT NULL DEFAULT '',
            created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL, kind TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'info',
            subject_type TEXT NOT NULL, subject_id INTEGER NOT NULL,
            window_key TEXT NOT NULL, title TEXT NOT NULL,
            message TEXT NOT NULL DEFAULT '',
            is_read INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL,
            UNIQUE(subject_type, subject_id, window_key)
        );
        CREATE TABLE IF NOT EXISTS delivery_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            notification_id INTEGER NOT NULL,
            channel TEXT NOT NULL, provider TEXT NOT NULL,
            recipient TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'queued',
            error_message TEXT NOT NULL DEFAULT '',
            provider_message_id TEXT NOT NULL DEFAULT '',
            subject TEXT NOT NULL DEFAULT '', body TEXT NOT NULL DEFAULT '',
            sent_at INTEGER, created_at INTEGER NOT NULL
        );
    """)
    crm_repo._conn.commit()
    crm_engine = CRMEngine(crm_repo)
    coll_engine = CollectionsEngine(inv_repo)
    notif_engine = NotificationEngine(notif_repo=notif_repo, invoice_repo=inv_repo)
    delivery_engine = DeliveryEngine(
        delivery_log_repo=log_repo,
        notification_repo=notif_repo,
        crm_repo=crm_repo,
        invoice_repo=inv_repo,
    )
    return (
        delivery_engine, crm_engine, notif_engine, coll_engine,
        crm_repo, inv_repo, notif_repo, log_repo, tmp,
    )


# ─── ChannelProvider unit tests ──────────────────────────────────────────────

class ChannelProviderTests(unittest.TestCase):
    def test_console_provider_always_succeeds(self):
        p = ConsoleProvider()
        r = p.send(recipient="x", subject="Test", body="Hello")
        self.assertTrue(r.success)
        self.assertEqual(r.status, "sent")

    def test_sendgrid_without_key_is_sandbox(self):
        # Ensure no key in env
        prev = os.environ.pop("AQ_SENDGRID_API_KEY", None)
        try:
            p = SendGridEmailProvider()
            r = p.send(recipient="someone@example.com",
                       subject="Test", body="Hi")
            self.assertTrue(r.success)
            self.assertEqual(r.status, "sandbox")
        finally:
            if prev is not None:
                os.environ["AQ_SENDGRID_API_KEY"] = prev

    def test_sendgrid_invalid_email_fails(self):
        p = SendGridEmailProvider(api_key="dummy")  # never called for invalid
        r = p.send(recipient="not-an-email", subject="x", body="y")
        self.assertFalse(r.success)
        self.assertEqual(r.status, "failed")

    def test_provider_registry_default(self):
        reg = ProviderRegistry.default()
        self.assertIsNotNone(reg.get("console"))
        self.assertIsNotNone(reg.get("email"))

    def test_provider_registry_register(self):
        reg = ProviderRegistry()
        reg.register(ConsoleProvider())
        self.assertEqual(reg.channels(), ["console"])


# ─── Custom provider for capturing send arguments in tests ───────────────────

class _CapturingProvider(ChannelProvider):
    channel = "email"
    name = "capture-test"

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def send(self, *, recipient: str, subject: str, body: str) -> ProviderResult:
        self.calls.append({"recipient": recipient, "subject": subject, "body": body})
        return ProviderResult(success=True, status="sent", provider_message_id="cap-1")


# ─── DeliveryEngine integration tests ────────────────────────────────────────

class DeliveryEngineTests(unittest.TestCase):
    def setUp(self):
        (self.delivery, self.crm_engine, self.notif_engine,
         self.coll, self.crm_repo, self.inv_repo, self.notif_repo,
         self.log_repo, self._tmp) = _setup()

    def tearDown(self):
        self.log_repo.close()
        self.notif_repo.close()
        self.inv_repo.close()
        self.crm_repo.close()
        self._tmp.cleanup()

    def _seed(self, *, email_consent: bool = False,
              email: str = "test@example.com") -> tuple[int, int]:
        """Create a customer + invoice + notification. Returns (customer_id, notif_id)."""
        c = self.crm_engine.create_customer(payload=CustomerCreateRequest(
            company="Alpha", full_name="Test", email=email,
        ))
        if email_consent:
            self.crm_engine.update_consent(c.id, email_consent=True)
        inv = self.coll.create_invoice(payload=InvoiceCreateRequest(
            company="Alpha", title="Test invoice",
            amount=1000.0, issue_date="2026-01-01",
            due_date=_past(5), customer_id=c.id,
        ))
        scan = self.notif_engine.scan_invoices(company="Alpha")
        # Pick one notification
        notif = self.notif_engine.list_notifications(company="Alpha").notifications[0]
        return c.id, notif.id

    # ── Basic dispatch ────────────────────────────────────────────────────────
    def test_dispatch_unknown_notification_returns_none(self):
        result = self.delivery.dispatch(notification_id=99999)
        self.assertIsNone(result)

    def test_dispatch_via_console_default(self):
        _, notif_id = self._seed()
        result = self.delivery.dispatch(
            notification_id=notif_id, channels=["console"]
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.successful, 1)
        self.assertEqual(result.attempts[0].channel, "console")
        self.assertEqual(result.attempts[0].status, "sent")

    def test_dispatch_logs_to_delivery_log(self):
        _, notif_id = self._seed()
        self.delivery.dispatch(notification_id=notif_id, channels=["console"])
        log = self.delivery.list_log(company="Alpha").entries
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0].notification_id, notif_id)
        self.assertEqual(log[0].channel, "console")
        self.assertIsNotNone(log[0].sent_at)

    # ── Consent gating ────────────────────────────────────────────────────────
    def test_email_without_consent_is_skipped(self):
        _, notif_id = self._seed(email_consent=False)
        result = self.delivery.dispatch(
            notification_id=notif_id, channels=["email"]
        )
        self.assertEqual(result.attempts[0].status, "skipped_no_consent")
        self.assertEqual(result.skipped, 1)

    def test_email_with_consent_proceeds_to_sandbox(self):
        # SendGrid without API key → sandbox (success in test env)
        _, notif_id = self._seed(email_consent=True)
        result = self.delivery.dispatch(
            notification_id=notif_id, channels=["email"]
        )
        self.assertEqual(result.successful, 1)
        self.assertIn(result.attempts[0].status, ("sandbox", "sent"))

    def test_no_customer_email_is_skipped(self):
        _, notif_id = self._seed(email_consent=True, email="")
        result = self.delivery.dispatch(
            notification_id=notif_id, channels=["email"]
        )
        self.assertEqual(result.attempts[0].status, "skipped_no_contact")

    def test_notification_with_no_invoice_link_skips_email(self):
        # Create a notification that doesn't point at any invoice
        self.notif_repo.insert_if_absent(
            company_name="Alpha", kind="invoice_due_soon",
            severity="info", subject_type="invoice",
            subject_id=99999, window_key="T-3",
            title="orphan", message="no invoice",
        )
        notif = self.notif_engine.list_notifications(company="Alpha").notifications[0]
        result = self.delivery.dispatch(
            notification_id=notif.id, channels=["email"]
        )
        self.assertEqual(result.attempts[0].status, "skipped_no_contact")

    # ── Provider registry override ────────────────────────────────────────────
    def test_custom_provider_receives_payload(self):
        # Swap the email provider for our capturing one
        capturer = _CapturingProvider()
        self.delivery._registry.register(capturer)
        _, notif_id = self._seed(email_consent=True)
        result = self.delivery.dispatch(
            notification_id=notif_id, channels=["email"]
        )
        self.assertEqual(len(capturer.calls), 1)
        self.assertEqual(capturer.calls[0]["recipient"], "test@example.com")
        self.assertEqual(result.attempts[0].provider, "capture-test")

    def test_unknown_channel_is_filtered_out(self):
        _, notif_id = self._seed()
        result = self.delivery.dispatch(
            notification_id=notif_id, channels=["console", "telegram"]
        )
        # telegram has no provider → filtered out, only console attempted
        self.assertEqual(result.attempted_channels, ["console"])

    # ── Multi-channel dispatch ────────────────────────────────────────────────
    def test_multi_channel_aggregates_results(self):
        _, notif_id = self._seed(email_consent=True)
        result = self.delivery.dispatch(
            notification_id=notif_id, channels=["console", "email"]
        )
        self.assertEqual(result.successful, 2)
        self.assertEqual(len(result.attempts), 2)
        channels = {a.channel for a in result.attempts}
        self.assertEqual(channels, {"console", "email"})

    # ── Consent update flow ───────────────────────────────────────────────────
    def test_consent_update_persists(self):
        c = self.crm_engine.create_customer(payload=CustomerCreateRequest(
            company="Alpha", full_name="Y", email="y@y.com",
        ))
        self.assertFalse(c.email_consent)
        updated = self.crm_engine.update_consent(c.id, email_consent=True)
        self.assertTrue(updated.email_consent)
        # Round-trip
        fetched = self.crm_engine.get_customer(c.id)
        self.assertTrue(fetched.email_consent)

    def test_consent_update_unset_fields_preserved(self):
        c = self.crm_engine.create_customer(payload=CustomerCreateRequest(
            company="Alpha", full_name="Z",
        ))
        self.crm_engine.update_consent(c.id, email_consent=True, sms_consent=True)
        # Now only flip whatsapp
        updated = self.crm_engine.update_consent(c.id, whatsapp_consent=True)
        # email + sms should still be True
        self.assertTrue(updated.email_consent)
        self.assertTrue(updated.sms_consent)
        self.assertTrue(updated.whatsapp_consent)

    # ── Log filtering ─────────────────────────────────────────────────────────
    def test_log_filter_by_status(self):
        _, notif_id = self._seed(email_consent=False)
        self.delivery.dispatch(notification_id=notif_id, channels=["email"])
        self.delivery.dispatch(notification_id=notif_id, channels=["console"])
        skipped = self.delivery.list_log(
            company="Alpha", status="skipped_no_consent"
        ).entries
        self.assertEqual(len(skipped), 1)


# ─── API tests ───────────────────────────────────────────────────────────────

class DeliveryApiTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from app import create_app

        self._tmp = tempfile.TemporaryDirectory()
        db = Path(self._tmp.name) / "delivery_api.db"
        self._orig = {k: os.getenv(k) for k in [
            "AQ_DATABASE_PATH", "AQ_AUTH_USERS", "AQ_ENABLE_DEMO_USERS",
            "AQ_JWT_SECRET", "AQ_ENV", "AQ_MARKET_OFFLINE",
            "AQ_MACRO_OFFLINE", "AQ_WEB_OFFLINE",
        ]}
        os.environ.update({
            "AQ_DATABASE_PATH": str(db),
            "AQ_AUTH_USERS": "admin:admin12345:admin",
            "AQ_ENABLE_DEMO_USERS": "false",
            "AQ_JWT_SECRET": "delivery-test-secret",
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

    def _seed_overdue_invoice_and_notif(self, company: str) -> int:
        # customer
        c = self.client.post("/api/v1/crm/customers",
            json={"company": company, "full_name": "Customer A",
                  "email": "ca@example.com"},
            headers=self.headers,
        ).json()
        # invoice
        self.client.post("/api/v1/collections/invoices",
            json={"company": company, "customer_id": c["id"],
                  "title": "Overdue", "amount": 1000.0,
                  "issue_date": "2026-01-01", "due_date": _past(10)},
            headers=self.headers,
        )
        # generate notifications
        self.client.post("/api/v1/notifications/generate",
            params={"company": company},
            headers=self.headers,
        )
        # pick one
        items = self.client.get("/api/v1/notifications",
            params={"company": company},
            headers=self.headers,
        ).json()["notifications"]
        return items[0]["id"]

    def test_dispatch_requires_auth(self):
        resp = self.client.post("/api/v1/notifications/1/dispatch")
        self.assertEqual(resp.status_code, 401)

    def test_dispatch_missing_notification_404(self):
        resp = self.client.post(
            "/api/v1/notifications/99999/dispatch", headers=self.headers
        )
        self.assertEqual(resp.status_code, 404)

    def test_dispatch_via_console_succeeds(self):
        company = self._company()
        nid = self._seed_overdue_invoice_and_notif(company)
        resp = self.client.post(
            f"/api/v1/notifications/{nid}/dispatch",
            params={"channels": "console"},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["successful"], 1)
        self.assertEqual(len(body["attempts"]), 1)

    def test_delivery_log_endpoint(self):
        company = self._company()
        nid = self._seed_overdue_invoice_and_notif(company)
        self.client.post(
            f"/api/v1/notifications/{nid}/dispatch",
            params={"channels": "console"},
            headers=self.headers,
        )
        resp = self.client.get(
            "/api/v1/delivery-log",
            params={"company": company},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.json()["total"], 1)

    def test_consent_update_endpoint(self):
        company = self._company()
        c = self.client.post(
            "/api/v1/crm/customers",
            json={"company": company, "full_name": "Consent Test",
                  "email": "ct@x.com"},
            headers=self.headers,
        ).json()
        resp = self.client.patch(
            f"/api/v1/crm/customers/{c['id']}/consent",
            json={"email_consent": True, "sms_consent": True},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["email_consent"])
        self.assertTrue(body["sms_consent"])
        self.assertFalse(body["whatsapp_consent"])

    def test_consent_update_missing_customer_404(self):
        resp = self.client.patch(
            "/api/v1/crm/customers/99999/consent",
            json={"email_consent": True},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
