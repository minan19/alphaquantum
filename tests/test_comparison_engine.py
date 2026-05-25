from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from app.engines.comparison_engine import ComparisonEngine
from app.models import (
    Company,
    FinanceBudgetVsActualResponse,
    FinanceCashflowResponse,
)


def _company(name: str, balance: float = 10_000.0) -> Company:
    return Company(name=name, balance=balance, inventory=[])


def _cashflow(company: str, net: float, income: float = 0.0, expense: float = 0.0) -> FinanceCashflowResponse:
    return FinanceCashflowResponse(
        company=company,
        lookback_days=30,
        total_income=round(income, 2),
        total_expense=round(expense, 2),
        net_cashflow=round(net, 2),
        average_daily_net=round(net / 30, 2),
        transaction_count=5,
    )


def _budget_report(company: str, net_budget: float = 8000.0, net_actual: float = 7500.0) -> FinanceBudgetVsActualResponse:
    return FinanceBudgetVsActualResponse(
        company=company,
        year=2026,
        month=None,
        items=[],
        total_budget_income=net_budget,
        total_budget_expense=0.0,
        total_actual_income=net_actual,
        total_actual_expense=0.0,
        net_budget=net_budget,
        net_actual=net_actual,
        net_variance=net_actual - net_budget,
    )


class ComparisonEngineTests(unittest.TestCase):
    def test_empty_companies(self):
        result = ComparisonEngine.build_comparison(
            companies=[], cashflows={}, budget_reports={}, year=None, lookback_days=30
        )
        self.assertEqual(result.total_companies, 0)
        self.assertEqual(result.snapshots, [])
        self.assertIsNone(result.top_performer)
        self.assertIsNone(result.bottom_performer)

    def test_single_company_rank_1(self):
        c = _company("Alpha")
        cf = _cashflow("Alpha", net=5000.0, income=8000.0, expense=3000.0)
        result = ComparisonEngine.build_comparison(
            companies=[c], cashflows={"Alpha": cf}, budget_reports={}, year=None, lookback_days=30
        )
        self.assertEqual(result.total_companies, 1)
        self.assertEqual(result.snapshots[0].rank, 1)
        self.assertEqual(result.top_performer, "Alpha")
        self.assertIsNone(result.bottom_performer)

    def test_two_companies_sorted_by_cashflow(self):
        companies = [_company("Low", 5000.0), _company("High", 80_000.0)]
        cashflows = {
            "Low": _cashflow("Low", net=100.0, income=500.0, expense=400.0),
            "High": _cashflow("High", net=9000.0, income=12000.0, expense=3000.0),
        }
        result = ComparisonEngine.build_comparison(
            companies=companies, cashflows=cashflows, budget_reports={}, year=None, lookback_days=30
        )
        self.assertEqual(result.top_performer, "High")
        self.assertEqual(result.bottom_performer, "Low")
        self.assertEqual(result.snapshots[0].company, "High")
        self.assertEqual(result.snapshots[0].rank, 1)
        self.assertEqual(result.snapshots[1].rank, 2)

    def test_negative_balance_health_risk(self):
        c = _company("Risk Corp", balance=-1000.0)
        cf = _cashflow("Risk Corp", net=100.0)
        result = ComparisonEngine.build_comparison(
            companies=[c], cashflows={"Risk Corp": cf}, budget_reports={}, year=None, lookback_days=30
        )
        self.assertEqual(result.snapshots[0].health_status, "RISK")

    def test_healthy_company(self):
        c = _company("Healthy Corp", balance=100_000.0)
        cf = _cashflow("Healthy Corp", net=5000.0)
        result = ComparisonEngine.build_comparison(
            companies=[c], cashflows={"Healthy Corp": cf}, budget_reports={}, year=None, lookback_days=30
        )
        self.assertEqual(result.snapshots[0].health_status, "HEALTHY")

    def test_watch_status_low_balance(self):
        c = _company("Watch Corp", balance=20_000.0)
        cf = _cashflow("Watch Corp", net=100.0)
        result = ComparisonEngine.build_comparison(
            companies=[c], cashflows={"Watch Corp": cf}, budget_reports={}, year=None, lookback_days=30
        )
        self.assertEqual(result.snapshots[0].health_status, "WATCH")

    def test_no_cashflow_gives_no_data(self):
        c = _company("Unknown")
        result = ComparisonEngine.build_comparison(
            companies=[c], cashflows={"Unknown": None}, budget_reports={}, year=None, lookback_days=30
        )
        self.assertEqual(result.snapshots[0].health_status, "NO_DATA")
        self.assertEqual(result.snapshots[0].net_cashflow_30d, 0.0)

    def test_budget_report_populated(self):
        c = _company("Budget Corp", balance=60_000.0)
        cf = _cashflow("Budget Corp", net=3000.0)
        br = _budget_report("Budget Corp", net_budget=8000.0, net_actual=7200.0)
        result = ComparisonEngine.build_comparison(
            companies=[c],
            cashflows={"Budget Corp": cf},
            budget_reports={"Budget Corp": br},
            year=2026,
            lookback_days=30,
        )
        snap = result.snapshots[0]
        self.assertEqual(snap.net_budget, 8000.0)
        self.assertEqual(snap.net_actual, 7200.0)
        self.assertEqual(snap.net_variance, -800.0)
        self.assertEqual(snap.budget_vs_actual_year, 2026)

    def test_lookback_days_in_response(self):
        result = ComparisonEngine.build_comparison(
            companies=[], cashflows={}, budget_reports={}, year=None, lookback_days=90
        )
        self.assertEqual(result.lookback_days, 90)

    def test_year_in_response(self):
        result = ComparisonEngine.build_comparison(
            companies=[], cashflows={}, budget_reports={}, year=2026, lookback_days=30
        )
        self.assertEqual(result.year, 2026)


class ComparisonEngineApiTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from app import create_app

        self._temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self._temp_dir.name) / "comparison_test.db"
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
        os.environ["AQ_JWT_SECRET"] = "test-comparison-secret"
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

        resp2 = self.client.post(
            "/api/v1/auth/login",
            json={"username": "manager", "password": "manager12345"},
        )
        self.manager_token = resp2.json()["access_token"]
        self.manager_headers = {"Authorization": f"Bearer {self.manager_token}"}

    def tearDown(self):
        self.client.close()
        for key, value in self._original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self._temp_dir.cleanup()

    def test_requires_auth(self):
        resp = self.client.get("/api/v1/analytics/company-comparison")
        self.assertEqual(resp.status_code, 401)

    def test_admin_gets_200(self):
        resp = self.client.get(
            "/api/v1/analytics/company-comparison", headers=self.admin_headers
        )
        self.assertEqual(resp.status_code, 200)

    def test_response_has_snapshots(self):
        resp = self.client.get(
            "/api/v1/analytics/company-comparison", headers=self.admin_headers
        )
        body = resp.json()
        self.assertIn("snapshots", body)
        self.assertIn("total_companies", body)
        self.assertIn("lookback_days", body)

    def test_lookback_days_param(self):
        resp = self.client.get(
            "/api/v1/analytics/company-comparison",
            params={"lookback_days": 60},
            headers=self.admin_headers,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["lookback_days"], 60)

    def test_scoped_manager_gets_403(self):
        # Create a scoped user with a specific company scope (not *)
        self.client.post(
            "/api/v1/users",
            json={
                "username": "scoped_comp",
                "password": "ScopedComp123",
                "role": "manager",
                "company_scopes": ["Alpha Corp"],
            },
            headers=self.admin_headers,
        )
        scoped_resp = self.client.post(
            "/api/v1/auth/login",
            json={"username": "scoped_comp", "password": "ScopedComp123"},
        )
        scoped_token = scoped_resp.json()["access_token"]
        resp = self.client.get(
            "/api/v1/analytics/company-comparison",
            headers={"Authorization": f"Bearer {scoped_token}"},
        )
        self.assertEqual(resp.status_code, 403)

    def test_year_param(self):
        resp = self.client.get(
            "/api/v1/analytics/company-comparison",
            params={"year": 2026},
            headers=self.admin_headers,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["year"], 2026)


if __name__ == "__main__":
    unittest.main()
