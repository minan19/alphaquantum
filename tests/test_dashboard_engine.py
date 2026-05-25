from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from app.engines.dashboard_engine import DashboardEngine
from app.models import FinanceCashflowResponse, FinanceOverviewResponse


def _make_overview(health: str = "HEALTHY", balance: float = 100_000.0) -> FinanceOverviewResponse:
    return FinanceOverviewResponse(
        total_balance=balance,
        average_balance=balance,
        negative_balance_companies=0,
        highest_balance_company="Corp A",
        lowest_balance_company="Corp A",
        health_status=health,
    )


def _make_cashflow(net: float = 5000.0, income: float = 8000.0, expense: float = 3000.0) -> FinanceCashflowResponse:
    return FinanceCashflowResponse(
        company=None,
        lookback_days=30,
        total_income=round(income, 2),
        total_expense=round(expense, 2),
        net_cashflow=round(net, 2),
        average_daily_net=round(net / 30, 2),
        transaction_count=10,
    )


class DashboardEngineUnitTests(unittest.TestCase):
    def _build(self, **kwargs):
        defaults = dict(
            company_scope=None,
            finance_overview=_make_overview(),
            cashflow=_make_cashflow(),
            low_stock_count=0,
            procurement_active_count=5,
            feasibility_pending_count=3,
            market_signal_count=12,
        )
        defaults.update(kwargs)
        return DashboardEngine().build_signals(**defaults)

    def test_healthy_no_alerts(self):
        result = self._build()
        self.assertEqual(result.alert_count, 0)
        self.assertEqual(result.warn_count, 0)

    def test_risk_finance_triggers_alert(self):
        result = self._build(finance_overview=_make_overview("RISK", -1000.0))
        self.assertGreater(result.alert_count, 0)

    def test_watch_finance_triggers_warn(self):
        result = self._build(finance_overview=_make_overview("WATCH", 10_000.0))
        self.assertGreater(result.warn_count, 0)

    def test_negative_balance_triggers_alert(self):
        result = self._build(finance_overview=_make_overview("RISK", -500.0))
        balance_signal = next(s for s in result.signals if s.label == "Total Balance")
        self.assertEqual(balance_signal.status, "ALERT")

    def test_negative_cashflow_triggers_warn(self):
        result = self._build(cashflow=_make_cashflow(net=-1000.0, income=500.0, expense=1500.0))
        cf_signal = next(s for s in result.signals if s.label == "Net Cashflow 30d")
        self.assertEqual(cf_signal.status, "WARN")

    def test_low_stock_triggers_alert(self):
        result = self._build(low_stock_count=2)
        inv_signal = next(s for s in result.signals if s.label == "Inventory Alerts")
        self.assertEqual(inv_signal.status, "ALERT")
        self.assertEqual(result.alert_count, 1)

    def test_no_market_data_triggers_warn(self):
        result = self._build(market_signal_count=0)
        market_signal = next(s for s in result.signals if s.label == "Market Data")
        self.assertEqual(market_signal.status, "WARN")

    def test_generated_at_ends_with_z(self):
        result = self._build()
        self.assertTrue(result.generated_at.endswith("Z"))

    def test_all_sources_present(self):
        result = self._build()
        sources = {s.source for s in result.signals}
        for expected in ("finance", "inventory", "procurement", "feasibility", "market"):
            self.assertIn(expected, sources)

    def test_company_scope_set(self):
        result = self._build(company_scope="Alpha Corp")
        self.assertEqual(result.company_scope, "Alpha Corp")

    def test_none_cashflow_gives_warn(self):
        result = self._build(cashflow=None)
        cf_signal = next(s for s in result.signals if s.label == "Net Cashflow 30d")
        self.assertEqual(cf_signal.status, "WARN")

    def test_none_finance_overview_gives_alert(self):
        result = self._build(finance_overview=None)
        health_signal = next(s for s in result.signals if s.label == "Finance Health")
        self.assertEqual(health_signal.status, "ALERT")

    # ── S-335 — Task & Notification signals ────────────────────────────────
    def test_overdue_tasks_signal_present(self):
        result = self._build()
        sig = next(s for s in result.signals if s.label == "Overdue Tasks")
        self.assertEqual(sig.source, "tasks")
        self.assertEqual(sig.value, 0)
        self.assertEqual(sig.status, "OK")

    def test_few_overdue_tasks_triggers_warn(self):
        result = self._build(overdue_task_count=3)
        sig = next(s for s in result.signals if s.label == "Overdue Tasks")
        self.assertEqual(sig.status, "WARN")
        self.assertGreater(result.warn_count, 0)

    def test_many_overdue_tasks_triggers_alert(self):
        result = self._build(overdue_task_count=10)
        sig = next(s for s in result.signals if s.label == "Overdue Tasks")
        self.assertEqual(sig.status, "ALERT")
        self.assertGreater(result.alert_count, 0)

    def test_critical_notification_signal_present(self):
        result = self._build()
        sig = next(s for s in result.signals
                   if s.label == "Critical Notifications")
        self.assertEqual(sig.source, "notifications")
        self.assertEqual(sig.value, 0)
        self.assertEqual(sig.status, "OK")

    def test_unread_critical_triggers_alert(self):
        result = self._build(unread_critical_notification_count=2)
        sig = next(s for s in result.signals
                   if s.label == "Critical Notifications")
        self.assertEqual(sig.status, "ALERT")


class DashboardEngineApiTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from app import create_app

        self._temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self._temp_dir.name) / "dashboard_test.db"
        self._original_env = {k: os.getenv(k) for k in [
            "AQ_DATABASE_PATH", "AQ_AUTH_USERS", "AQ_ENABLE_DEMO_USERS",
            "AQ_JWT_SECRET", "AQ_ENV", "AQ_MARKET_OFFLINE",
            "AQ_MACRO_OFFLINE", "AQ_WEB_OFFLINE",
        ]}
        os.environ["AQ_DATABASE_PATH"] = str(db_path)
        os.environ["AQ_AUTH_USERS"] = (
            "admin:admin12345:admin,"
            "manager:manager12345:manager"
        )
        os.environ["AQ_ENABLE_DEMO_USERS"] = "false"
        os.environ["AQ_JWT_SECRET"] = "test-secret"
        os.environ["AQ_ENV"] = "development"
        os.environ["AQ_MARKET_OFFLINE"] = "true"
        os.environ["AQ_MACRO_OFFLINE"] = "true"
        os.environ["AQ_WEB_OFFLINE"] = "true"

        self.client = TestClient(create_app())
        resp = self.client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin12345"},
        )
        self.admin_token = resp.json()["access_token"]
        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}

    def tearDown(self):
        self.client.close()
        for key, value in self._original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self._temp_dir.cleanup()

    def test_requires_auth(self):
        resp = self.client.get("/api/v1/dashboard/live-signals")
        self.assertEqual(resp.status_code, 401)

    def test_admin_gets_200(self):
        resp = self.client.get(
            "/api/v1/dashboard/live-signals", headers=self.admin_headers
        )
        self.assertEqual(resp.status_code, 200)

    def test_response_has_signals(self):
        resp = self.client.get(
            "/api/v1/dashboard/live-signals", headers=self.admin_headers
        )
        body = resp.json()
        self.assertIn("signals", body)
        self.assertIsInstance(body["signals"], list)
        self.assertGreater(len(body["signals"]), 0)

    def test_response_has_generated_at(self):
        resp = self.client.get(
            "/api/v1/dashboard/live-signals", headers=self.admin_headers
        )
        body = resp.json()
        self.assertIn("generated_at", body)
        self.assertTrue(body["generated_at"].endswith("Z"))

    def test_alert_and_warn_are_integers(self):
        resp = self.client.get(
            "/api/v1/dashboard/live-signals", headers=self.admin_headers
        )
        body = resp.json()
        self.assertIsInstance(body["alert_count"], int)
        self.assertIsInstance(body["warn_count"], int)

    def test_lookback_days_param(self):
        resp = self.client.get(
            "/api/v1/dashboard/live-signals",
            params={"lookback_days": 7},
            headers=self.admin_headers,
        )
        self.assertEqual(resp.status_code, 200)

    def test_scoped_user_requires_company_param(self):
        # Create a scoped user (specific company scope, not *)
        self.client.post(
            "/api/v1/users",
            json={
                "username": "scoped_dash",
                "password": "ScopedDash123",
                "role": "manager",
                "company_scopes": ["Alpha Corp"],
            },
            headers=self.admin_headers,
        )
        scoped_resp = self.client.post(
            "/api/v1/auth/login",
            json={"username": "scoped_dash", "password": "ScopedDash123"},
        )
        scoped_token = scoped_resp.json()["access_token"]
        resp = self.client.get(
            "/api/v1/dashboard/live-signals",
            headers={"Authorization": f"Bearer {scoped_token}"},
        )
        self.assertEqual(resp.status_code, 400)


if __name__ == "__main__":
    unittest.main()
