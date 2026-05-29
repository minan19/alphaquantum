import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app import create_app


class ApiAuthTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._temp_dir.name) / "api_test.db"
        self._original_env = {
            "AQ_DATABASE_PATH": os.getenv("AQ_DATABASE_PATH"),
            "AQ_AUTH_USERS": os.getenv("AQ_AUTH_USERS"),
            "AQ_ENABLE_DEMO_USERS": os.getenv("AQ_ENABLE_DEMO_USERS"),
            "AQ_JWT_SECRET": os.getenv("AQ_JWT_SECRET"),
            "AQ_ENV": os.getenv("AQ_ENV"),
            "AQ_MARKET_OFFLINE": os.getenv("AQ_MARKET_OFFLINE"),
            "AQ_MACRO_OFFLINE": os.getenv("AQ_MACRO_OFFLINE"),
            "AQ_WEB_OFFLINE": os.getenv("AQ_WEB_OFFLINE"),
        }

        os.environ["AQ_DATABASE_PATH"] = str(self._db_path)
        os.environ["AQ_AUTH_USERS"] = (
            "admin:admin12345:admin,"
            "manager:manager12345:manager,"
            "viewer:viewer12345:viewer"
        )
        os.environ["AQ_ENABLE_DEMO_USERS"] = "false"
        os.environ["AQ_JWT_SECRET"] = "integration-test-secret"
        os.environ["AQ_ENV"] = "development"
        os.environ["AQ_MARKET_OFFLINE"] = "true"
        os.environ["AQ_MACRO_OFFLINE"] = "true"
        os.environ["AQ_WEB_OFFLINE"] = "true"

        self.client = TestClient(create_app())

    def tearDown(self) -> None:
        self.client.close()

        for key, value in self._original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

        self._temp_dir.cleanup()

    def test_login_refresh_logout_flow(self) -> None:
        login_response = self.client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin12345"},
        )
        self.assertEqual(login_response.status_code, 200)
        login_payload = login_response.json()

        access_token = login_payload["access_token"]
        refresh_token = login_payload["refresh_token"]
        self.assertIsNotNone(refresh_token)

        refresh_response = self.client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        self.assertEqual(refresh_response.status_code, 200)
        refresh_payload = refresh_response.json()

        second_refresh_with_old = self.client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        self.assertEqual(second_refresh_with_old.status_code, 401)

        new_access_token = refresh_payload["access_token"]
        new_refresh_token = refresh_payload["refresh_token"]

        logout_response = self.client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {new_access_token}"},
            json={"refresh_token": new_refresh_token},
        )
        self.assertEqual(logout_response.status_code, 200)

        me_after_logout = self.client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {new_access_token}"},
        )
        self.assertEqual(me_after_logout.status_code, 401)

        use_revoked_refresh = self.client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": new_refresh_token},
        )
        self.assertEqual(use_revoked_refresh.status_code, 401)

        # Access token created before logout should still be valid.
        me_with_old_access = self.client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        self.assertEqual(me_with_old_access.status_code, 200)

    def test_login_limiter_backend_outage_returns_503_fail_closed(self) -> None:
        limiter = self.client.app.state.auth_limiter
        original_backend = getattr(limiter, "_backend", None)
        original_fail_open = getattr(limiter, "_fail_open", True)

        class _BrokenLimiterBackend:
            def is_allowed(self, key: str, *, window_seconds: int, max_attempts: int) -> bool:
                raise RuntimeError("simulated_partition")

            def register_failure(
                self,
                key: str,
                *,
                window_seconds: int,
                max_attempts: int,
            ) -> None:
                raise RuntimeError("simulated_partition")

            def register_success(self, key: str) -> None:
                raise RuntimeError("simulated_partition")

            def close(self) -> None:
                return None

        limiter._backend = _BrokenLimiterBackend()
        try:
            limiter._fail_open = False
            fail_closed_response = self.client.post(
                "/api/v1/auth/login",
                json={"username": "admin", "password": "admin12345"},
            )
            self.assertEqual(fail_closed_response.status_code, 503)
            self.assertIn(
                "rate limiter unavailable",
                fail_closed_response.json()["detail"].lower(),
            )

            limiter._fail_open = True
            fail_open_response = self.client.post(
                "/api/v1/auth/login",
                json={"username": "admin", "password": "admin12345"},
            )
            self.assertEqual(fail_open_response.status_code, 200)
        finally:
            limiter._backend = original_backend
            limiter._fail_open = original_fail_open

    def test_admin_user_role_crud_and_audit(self) -> None:
        token = self._login_admin_access_token()

        create_role = self.client.post(
            "/api/v1/roles",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "auditor", "description": "Audit role"},
        )
        self.assertEqual(create_role.status_code, 201)

        create_user = self.client.post(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "username": "alice",
                "password": "alicePass123",
                "role": "auditor",
                "is_active": True,
            },
        )
        self.assertEqual(create_user.status_code, 201)
        user_id = create_user.json()["id"]

        rotate_password = self.client.post(
            f"/api/v1/users/{user_id}/password-rotate",
            headers={"Authorization": f"Bearer {token}"},
            json={"new_password": "alicePass999"},
        )
        self.assertEqual(rotate_password.status_code, 200)

        list_audit = self.client.get(
            "/api/v1/audit-logs?limit=20",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(list_audit.status_code, 200)
        audit_rows = list_audit.json()
        self.assertGreaterEqual(len(audit_rows), 1)

        known_paths = {row["path"] for row in audit_rows}
        self.assertIn("/api/v1/users", known_paths)

    def test_permission_matrix_manager_viewer(self) -> None:
        manager_token = self._login_access_token("manager", "manager12345")

        manager_simulate = self.client.post(
            "/api/v1/simulate",
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        self.assertEqual(manager_simulate.status_code, 200)

        manager_create_user = self.client.post(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {manager_token}"},
            json={
                "username": "forbidden",
                "password": "forbiddenPass123",
                "role": "viewer",
                "is_active": True,
            },
        )
        self.assertEqual(manager_create_user.status_code, 403)

        manager_tender = self.client.post(
            "/api/v1/tender/generate",
            headers={"Authorization": f"Bearer {manager_token}"},
            json={
                "institution_name": "Sample Public Institution",
                "tender_title": "Data Center Tender",
                "tender_reference": "2026/5567",
                "company_name": "Alpha Quantum A.S.",
                "administrative_spec": (
                    "Bidder must provide tax clearance certificate and signature circular "
                    "before final submission."
                ),
                "technical_spec": (
                    "Technical response matrix is mandatory and bidder shall provide detailed "
                    "architecture and support model."
                ),
                "additional_requirements": ["Temporary bid bond is mandatory."],
                "use_kik_baseline": True,
            },
        )
        self.assertEqual(manager_tender.status_code, 200)
        manager_tender_payload = manager_tender.json()
        self.assertGreaterEqual(len(manager_tender_payload["compliance_matrix"]), 2)
        self.assertGreaterEqual(len(manager_tender_payload["control_checklist"]), 2)
        self.assertIn("validation_summary", manager_tender_payload)
        self.assertIn(
            manager_tender_payload["validation_summary"]["release_recommendation"],
            {"READY", "READY_WITH_CONDITIONS", "NOT_READY"},
        )

        viewer_token = self._login_access_token("viewer", "viewer12345")
        viewer_list_users = self.client.get(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        self.assertEqual(viewer_list_users.status_code, 403)

        viewer_tender = self.client.post(
            "/api/v1/tender/generate",
            headers={"Authorization": f"Bearer {viewer_token}"},
            json={
                "institution_name": "Sample Public Institution",
                "tender_title": "Data Center Tender",
                "administrative_spec": (
                    "Bidder must provide tax clearance certificate and signature circular "
                    "before final submission."
                ),
                "technical_spec": (
                    "Technical response matrix is mandatory and bidder shall provide detailed "
                    "architecture and support model."
                ),
            },
        )
        self.assertEqual(viewer_tender.status_code, 403)

    def test_company_scope_enforcement_for_scoped_manager(self) -> None:
        admin_token = self._login_admin_access_token()
        create_scoped_manager = self.client.post(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "username": "scoped_manager",
                "password": "ScopedManager123",
                "role": "manager",
                "is_active": True,
                "company_scopes": ["Alpha Scoped Co"],
            },
        )
        self.assertEqual(create_scoped_manager.status_code, 201)
        payload = create_scoped_manager.json()
        self.assertEqual(payload["scope_mode"], "single")
        self.assertEqual(payload["company_scopes"], ["Alpha Scoped Co"])

        scoped_token = self._login_access_token("scoped_manager", "ScopedManager123")

        finance_allowed = self.client.post(
            "/api/v1/finance-engine/ledger",
            headers={"Authorization": f"Bearer {scoped_token}"},
            json={
                "company": "Alpha Scoped Co",
                "entry_type": "income",
                "amount": 1000,
                "category": "sales",
            },
        )
        self.assertEqual(finance_allowed.status_code, 201)

        finance_blocked = self.client.post(
            "/api/v1/finance-engine/ledger",
            headers={"Authorization": f"Bearer {scoped_token}"},
            json={
                "company": "Blocked Co",
                "entry_type": "income",
                "amount": 1000,
                "category": "sales",
            },
        )
        self.assertEqual(finance_blocked.status_code, 403)

        cashflow_without_company = self.client.get(
            "/api/v1/finance-engine/cashflow?lookback_days=30",
            headers={"Authorization": f"Bearer {scoped_token}"},
        )
        self.assertEqual(cashflow_without_company.status_code, 400)

        procurement_allowed = self.client.post(
            "/api/v1/procurement/requests",
            headers={"Authorization": f"Bearer {scoped_token}"},
            json={
                "company": "Alpha Scoped Co",
                "title": "Scoped Request",
                "strategy": "balanced",
                "items": [{"item_name": "Router", "quantity": 1}],
            },
        )
        self.assertEqual(procurement_allowed.status_code, 201)

        procurement_blocked = self.client.post(
            "/api/v1/procurement/requests",
            headers={"Authorization": f"Bearer {scoped_token}"},
            json={
                "company": "Blocked Co",
                "title": "Blocked Request",
                "strategy": "balanced",
                "items": [{"item_name": "Switch", "quantity": 1}],
            },
        )
        self.assertEqual(procurement_blocked.status_code, 403)

        international_allowed = self.client.post(
            "/api/v1/international/projects",
            headers={"Authorization": f"Bearer {scoped_token}"},
            json={
                "project_name": "Scoped International Program",
                "company_name": "Alpha Scoped Co",
                "base_country": "TR",
                "target_countries": ["DE"],
                "services": ["consulting"],
                "budget_total": 1000000,
            },
        )
        self.assertEqual(international_allowed.status_code, 201)

        international_blocked = self.client.post(
            "/api/v1/international/projects",
            headers={"Authorization": f"Bearer {scoped_token}"},
            json={
                "project_name": "Blocked International Program",
                "company_name": "Blocked Co",
                "base_country": "TR",
                "target_countries": ["DE"],
                "services": ["consulting"],
                "budget_total": 1000000,
            },
        )
        self.assertEqual(international_blocked.status_code, 403)

        ecosystem_allowed = self.client.post(
            "/api/v1/ecosystem/activate",
            headers={"Authorization": f"Bearer {scoped_token}"},
            json={
                "project_name": "Scoped Ecosystem Activation",
                "company_name": "Alpha Scoped Co",
                "sector": "Technology",
                "geography": "TR",
                "objective": "Run integrated activation for scoped company operations.",
                "budget_total": 5000000,
                "base_country": "TR",
                "target_countries": ["DE"],
                "services": ["consulting"],
            },
        )
        self.assertEqual(ecosystem_allowed.status_code, 200)

        ecosystem_blocked = self.client.post(
            "/api/v1/ecosystem/activate",
            headers={"Authorization": f"Bearer {scoped_token}"},
            json={
                "project_name": "Blocked Ecosystem Activation",
                "company_name": "Blocked Co",
                "sector": "Technology",
                "geography": "TR",
                "objective": "This should be blocked by company scope enforcement.",
                "budget_total": 5000000,
                "base_country": "TR",
                "target_countries": ["DE"],
                "services": ["consulting"],
            },
        )
        self.assertEqual(ecosystem_blocked.status_code, 403)

    def test_finance_ledger_cashflow_and_forecast(self) -> None:
        token = self._login_admin_access_token()

        income_entry = self.client.post(
            "/api/v1/finance-engine/ledger",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "company": "ABC Holding",
                "entry_type": "income",
                "amount": 25000,
                "category": "sales",
                "description": "March invoice",
            },
        )
        self.assertEqual(income_entry.status_code, 201)

        expense_entry = self.client.post(
            "/api/v1/finance-engine/ledger",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "company": "ABC Holding",
                "entry_type": "expense",
                "amount": 5000,
                "category": "ops",
                "description": "Warehouse cost",
            },
        )
        self.assertEqual(expense_entry.status_code, 201)

        cashflow = self.client.get(
            "/api/v1/finance-engine/cashflow?company=ABC%20Holding&lookback_days=30",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(cashflow.status_code, 200)
        cashflow_payload = cashflow.json()
        self.assertEqual(cashflow_payload["total_income"], 25000.0)
        self.assertEqual(cashflow_payload["total_expense"], 5000.0)
        self.assertEqual(cashflow_payload["net_cashflow"], 20000.0)

        forecast = self.client.get(
            "/api/v1/finance-engine/forecast?company=ABC%20Holding&lookback_days=30&horizon_days=15",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(forecast.status_code, 200)
        forecast_payload = forecast.json()
        self.assertEqual(forecast_payload["company"], "ABC Holding")
        self.assertEqual(forecast_payload["horizon_days"], 15)
        self.assertGreaterEqual(forecast_payload["projected_balance"], 50000.0)

    def test_migration_status_permission_control(self) -> None:
        admin_token = self._login_admin_access_token()
        admin_status = self.client.get(
            "/api/v1/admin/migrations/status",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        self.assertEqual(admin_status.status_code, 200)
        versions = [row["version"] for row in admin_status.json()]
        self.assertEqual(versions, list(range(1, 30)))

        manager_token = self._login_access_token("manager", "manager12345")
        manager_status = self.client.get(
            "/api/v1/admin/migrations/status",
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        self.assertEqual(manager_status.status_code, 403)

    def test_market_endpoints_with_permissions(self) -> None:
        viewer_token = self._login_access_token("viewer", "viewer12345")

        market_ohlcv = self.client.get(
            "/api/v1/market/ohlcv?symbol=AAPL&days=90",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        self.assertEqual(market_ohlcv.status_code, 200)
        ohlcv_payload = market_ohlcv.json()
        self.assertEqual(ohlcv_payload["symbol"], "AAPL")
        self.assertGreaterEqual(len(ohlcv_payload["bars"]), 20)

        signals = self.client.get(
            "/api/v1/market/signals?symbols=AAPL,MSFT,NVDA&days=90",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        self.assertEqual(signals.status_code, 200)
        signals_payload = signals.json()
        self.assertGreaterEqual(len(signals_payload["items"]), 3)

        backtest = self.client.get(
            "/api/v1/market/backtest?symbol=AAPL&days=220&lookahead_days=5",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        self.assertEqual(backtest.status_code, 200)
        backtest_payload = backtest.json()
        self.assertEqual(backtest_payload["symbol"], "AAPL")
        self.assertGreaterEqual(backtest_payload["sample_size"], 1)

        sources = self.client.get(
            "/api/v1/market/sources?regions=TR,EU,GLOBAL&limit=12",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        self.assertEqual(sources.status_code, 200)
        sources_payload = sources.json()
        self.assertGreaterEqual(sources_payload["total_sources"], 6)

        global_report = self.client.get(
            "/api/v1/global/report?countries=USA,TUR&bank_symbols=JPM,BAC&index_symbols=SPX,NDX",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        self.assertEqual(global_report.status_code, 200)
        report_payload = global_report.json()
        self.assertIn(report_payload["risk_level"], {"LOW", "MEDIUM", "HIGH"})
        self.assertIn("Global Financial Intelligence Report", report_payload["report_markdown"])
        self.assertGreaterEqual(len(report_payload["central_banks"]), 1)

        public_sources_report = self.client.post(
            "/api/v1/public-institutions/report",
            headers={"Authorization": f"Bearer {viewer_token}"},
            json={
                "pages": [
                    {
                        "url": "https://www.worldbank.org",
                        "focus_terms": ["inflation", "policy rate"],
                    },
                    {
                        "url": "https://www.imf.org",
                    },
                ],
                "global_focus_terms": ["budget", "growth"],
            },
        )
        self.assertEqual(public_sources_report.status_code, 200)
        public_payload = public_sources_report.json()
        self.assertEqual(public_payload["page_count"], 2)
        self.assertGreaterEqual(len(public_payload["pages"]), 2)

        market_intelligence = self.client.post(
            "/api/v1/market/intelligence",
            headers={"Authorization": f"Bearer {viewer_token}"},
            json={
                "pages": [
                    {
                        "url": "https://www.worldbank.org",
                        "focus_terms": ["inflation", "market"],
                    }
                ],
                "focus_symbols": ["AAPL", "MSFT"],
                "days": 90,
                "max_symbols": 3,
            },
        )
        self.assertEqual(market_intelligence.status_code, 200)
        intelligence_payload = market_intelligence.json()
        self.assertGreaterEqual(len(intelligence_payload["pages"]), 1)
        self.assertGreaterEqual(len(intelligence_payload["analyzed_symbols"]), 1)
        self.assertGreaterEqual(len(intelligence_payload["recommendations"]), 1)

        viewer_refresh_denied = self.client.post(
            "/api/v1/market/refresh",
            headers={"Authorization": f"Bearer {viewer_token}"},
            json={"symbols": ["AAPL"], "days": 60},
        )
        self.assertEqual(viewer_refresh_denied.status_code, 403)

        manager_token = self._login_access_token("manager", "manager12345")
        manager_refresh = self.client.post(
            "/api/v1/market/refresh",
            headers={"Authorization": f"Bearer {manager_token}"},
            json={"symbols": ["AAPL", "MSFT"], "days": 60},
        )
        self.assertEqual(manager_refresh.status_code, 200)
        manager_refresh_payload = manager_refresh.json()
        self.assertEqual(manager_refresh_payload["refreshed_count"], 2)

    def test_procurement_endpoints_with_permissions(self) -> None:
        manager_token = self._login_access_token("manager", "manager12345")

        create_request = self.client.post(
            "/api/v1/procurement/requests",
            headers={"Authorization": f"Bearer {manager_token}"},
            json={
                "company": "Alpha Quantum A.S.",
                "title": "Datacenter Power Procurement",
                "strategy": "balanced",
                "budget_limit": 50000,
                "currency": "TRY",
                "items": [
                    {
                        "item_name": "UPS",
                        "specification": "Online UPS 10kVA",
                        "quantity": 2,
                        "min_quality_score": 70,
                        "max_unit_price": 12000,
                        "must_comply_tender": True,
                    }
                ],
            },
        )
        self.assertEqual(create_request.status_code, 201)
        request_payload = create_request.json()
        request_id = request_payload["id"]
        request_item_id = request_payload["items"][0]["id"]

        create_quote = self.client.post(
            "/api/v1/procurement/quotes",
            headers={"Authorization": f"Bearer {manager_token}"},
            json={
                "request_id": request_id,
                "vendor_name": "PowerTech",
                "vendor_rating": 88,
                "delivery_days": 5,
                "warranty_months": 24,
                "compliance_score": 92,
                "quote_items": [
                    {
                        "request_item_id": request_item_id,
                        "unit_price": 10000,
                        "available_quantity": 2,
                        "quality_score": 90,
                    }
                ],
            },
        )
        self.assertEqual(create_quote.status_code, 201)

        evaluation = self.client.get(
            f"/api/v1/procurement/requests/{request_id}/evaluation",
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        self.assertEqual(evaluation.status_code, 200)
        evaluation_payload = evaluation.json()
        self.assertEqual(evaluation_payload["unresolved_items"], 0)
        self.assertEqual(evaluation_payload["resolved_items"], 1)

        auto_po = self.client.post(
            f"/api/v1/procurement/requests/{request_id}/purchase-orders/auto",
            headers={"Authorization": f"Bearer {manager_token}"},
            json={"auto_approve": True},
        )
        self.assertEqual(auto_po.status_code, 200)
        po_payload = auto_po.json()
        self.assertEqual(po_payload["total_orders"], 1)

        viewer_token = self._login_access_token("viewer", "viewer12345")
        viewer_read = self.client.get(
            "/api/v1/procurement/requests",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        self.assertEqual(viewer_read.status_code, 200)

        viewer_write_denied = self.client.post(
            "/api/v1/procurement/requests",
            headers={"Authorization": f"Bearer {viewer_token}"},
            json={
                "company": "Viewer Co",
                "title": "Forbidden Request",
                "items": [{"item_name": "Cable", "quantity": 1}],
            },
        )
        self.assertEqual(viewer_write_denied.status_code, 403)

    def test_feasibility_endpoints_with_permissions(self) -> None:
        manager_token = self._login_access_token("manager", "manager12345")
        create_report = self.client.post(
            "/api/v1/feasibility/report",
            headers={"Authorization": f"Bearer {manager_token}"},
            json={
                "project_name": "Ankara Solar Plant",
                "sector": "Energy",
                "geography": "TR",
                "objective": (
                    "Build a utility-scale solar generation asset to reduce energy procurement cost "
                    "and sell excess power to the grid."
                ),
                "currency": "TRY",
                "initial_investment": 150000000,
                "annual_opex": 12000000,
                "annual_revenue_base": 42000000,
                "project_lifetime_years": 12,
                "implementation_months": 9,
                "discount_rate": 0.16,
                "tax_rate": 0.2,
                "inflation_rate": 0.18,
                "revenue_growth_base": 0.1,
                "revenue_growth_upside": 0.18,
                "revenue_growth_downside": -0.06,
                "opex_growth_base": 0.11,
                "capacity_utilization": 0.78,
                "financing_debt_ratio": 0.45,
                "regulatory_requirements": [
                    "EMRA generation license",
                    "Grid connection approval",
                ],
                "constraints": ["Land permitting", "FX volatility"],
                "benchmark_symbols": ["XU100", "AAPL"],
                "additional_notes": "Strategic decarbonization alignment required.",
            },
        )
        self.assertEqual(create_report.status_code, 201)
        created_payload = create_report.json()
        report_id = created_payload["id"]
        self.assertIn(created_payload["report"]["recommendation"], {"GO", "CONDITIONAL_GO", "NO_GO"})
        self.assertIn("# Feasibility Report", created_payload["report"]["report_markdown"])

        viewer_token = self._login_access_token("viewer", "viewer12345")
        viewer_list = self.client.get(
            "/api/v1/feasibility/reports?limit=20",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        self.assertEqual(viewer_list.status_code, 200)
        viewer_items = viewer_list.json()["items"]
        self.assertGreaterEqual(len(viewer_items), 1)
        self.assertIn("recommendation", viewer_items[0])

        viewer_detail = self.client.get(
            f"/api/v1/feasibility/reports/{report_id}",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        self.assertEqual(viewer_detail.status_code, 200)
        detail_payload = viewer_detail.json()
        self.assertEqual(detail_payload["id"], report_id)
        self.assertEqual(detail_payload["project_name"], "Ankara Solar Plant")

        viewer_write_denied = self.client.post(
            "/api/v1/feasibility/report",
            headers={"Authorization": f"Bearer {viewer_token}"},
            json={
                "project_name": "Forbidden",
                "sector": "Retail",
                "geography": "TR",
                "objective": "Test feasibility write permission for viewer role only.",
                "initial_investment": 1000,
                "annual_opex": 100,
                "annual_revenue_base": 200,
            },
        )
        self.assertEqual(viewer_write_denied.status_code, 403)

    def test_international_project_endpoints_with_permissions(self) -> None:
        manager_token = self._login_access_token("manager", "manager12345")

        create_project = self.client.post(
            "/api/v1/international/projects",
            headers={"Authorization": f"Bearer {manager_token}"},
            json={
                "project_name": "Global Expansion Program 2026",
                "company_name": "Alpha Quantum A.S.",
                "base_country": "TR",
                "target_countries": ["DE", "AE", "USA"],
                "services": ["management", "consulting", "installation", "import_export"],
                "sectors": ["energy", "infrastructure"],
                "strategic_objectives": [
                    "Establish regional delivery capability",
                    "Increase cross-border recurring revenue",
                ],
                "budget_total": 25000000,
                "currency": "USD",
                "timeline_months": 18,
                "risk_appetite": "medium",
                "local_partner_required": True,
                "preferred_incoterms": ["FOB", "CIF", "DAP"],
                "trade_lanes": ["TR->DE", "TR->AE", "TR->US"],
                "notes": "Program must prioritize compliance and margin sustainability.",
            },
        )
        self.assertEqual(create_project.status_code, 201)
        created_payload = create_project.json()
        project_id = created_payload["id"]
        self.assertIn(created_payload["report"]["recommendation"], {"GO", "CONDITIONAL_GO", "NO_GO"})
        self.assertGreaterEqual(len(created_payload["report"]["country_profiles"]), 3)

        viewer_token = self._login_access_token("viewer", "viewer12345")
        viewer_list = self.client.get(
            "/api/v1/international/projects?limit=20",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        self.assertEqual(viewer_list.status_code, 200)
        list_payload = viewer_list.json()
        self.assertGreaterEqual(list_payload["total"], 1)
        self.assertGreaterEqual(len(list_payload["items"]), 1)

        viewer_detail = self.client.get(
            f"/api/v1/international/projects/{project_id}",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        self.assertEqual(viewer_detail.status_code, 200)
        detail_payload = viewer_detail.json()
        self.assertEqual(detail_payload["id"], project_id)
        self.assertEqual(detail_payload["project_name"], "Global Expansion Program 2026")

        viewer_write_denied = self.client.post(
            "/api/v1/international/projects",
            headers={"Authorization": f"Bearer {viewer_token}"},
            json={
                "project_name": "Forbidden",
                "company_name": "Viewer Co",
                "base_country": "TR",
                "target_countries": ["DE"],
                "services": ["consulting"],
                "budget_total": 1000,
            },
        )
        self.assertEqual(viewer_write_denied.status_code, 403)

    def test_ecosystem_activate_endpoint_with_permissions(self) -> None:
        manager_token = self._login_access_token("manager", "manager12345")
        activate = self.client.post(
            "/api/v1/ecosystem/activate",
            headers={"Authorization": f"Bearer {manager_token}"},
            json={
                "project_name": "Ecosystem Activation Program",
                "company_name": "Alpha Quantum A.S.",
                "sector": "Energy",
                "geography": "TR",
                "objective": (
                    "Activate integrated feasibility, international operations and procurement for "
                    "a country-based expansion roadmap."
                ),
                "budget_total": 30000000,
                "currency": "USD",
                "base_country": "TR",
                "target_countries": ["DE", "AE", "US"],
                "services": ["management", "consulting", "installation", "import_export"],
                "timeline_months": 20,
                "risk_appetite": "medium",
                "local_partner_required": True,
                "strategic_objectives": [
                    "International service footprint expansion",
                    "Integrated supply chain resilience",
                ],
                "trade_lanes": ["TR->DE", "TR->AE", "TR->US"],
                "procurement_strategy": "balanced",
                "procurement_items": [
                    {
                        "item_name": "Substation Package",
                        "quantity": 2,
                        "specification": "Substation equipment set",
                        "min_quality_score": 75,
                        "max_unit_price": 450000,
                        "must_comply_tender": True,
                    }
                ],
            },
        )
        self.assertEqual(activate.status_code, 200)
        payload = activate.json()
        self.assertGreater(payload["feasibility_report_id"], 0)
        self.assertGreater(payload["international_project_id"], 0)
        self.assertIsNotNone(payload["procurement_request_id"])
        self.assertIn(payload["recommendation"], {"GO", "CONDITIONAL_GO", "NO_GO"})
        self.assertIn("feasibility", payload["module_status"])
        self.assertIn("Feasibility Report", payload["feasibility_report_markdown_preview"])

        viewer_token = self._login_access_token("viewer", "viewer12345")
        viewer_forbidden = self.client.post(
            "/api/v1/ecosystem/activate",
            headers={"Authorization": f"Bearer {viewer_token}"},
            json={
                "project_name": "Forbidden",
                "company_name": "Viewer Co",
                "sector": "Retail",
                "geography": "TR",
                "objective": "Viewer cannot activate ecosystem orchestration due to missing permissions.",
                "budget_total": 1000,
                "base_country": "TR",
                "target_countries": ["DE"],
                "services": ["consulting"],
            },
        )
        self.assertEqual(viewer_forbidden.status_code, 403)

    def test_ecosystem_activate_portfolio_endpoint_with_permissions(self) -> None:
        manager_token = self._login_access_token("manager", "manager12345")
        activate = self.client.post(
            "/api/v1/ecosystem/activate/portfolio",
            headers={"Authorization": f"Bearer {manager_token}"},
            json={
                "scope_mode": "holding",
                "holding_name": "Alpha Holding",
                "project_name_prefix": "Holding 2026 Program",
                "base_country": "TR",
                "target_countries": ["DE", "AE"],
                "services": ["management", "consulting", "import_export"],
                "companies": [
                    {
                        "company_name": "Alpha Energy",
                        "sector": "Energy",
                        "geography": "TR",
                        "objective": "Expand energy operations with integrated procurement and compliance controls.",
                        "budget_total": 7000000,
                    },
                    {
                        "company_name": "Alpha Tech",
                        "sector": "Technology",
                        "geography": "EU",
                        "objective": "Scale technology deployment and consulting services in target countries.",
                        "budget_total": 5500000,
                    },
                ],
            },
        )
        self.assertEqual(activate.status_code, 200)
        payload = activate.json()
        self.assertEqual(payload["scope_mode"], "holding")
        self.assertEqual(payload["holding_name"], "Alpha Holding")
        self.assertEqual(payload["total_companies"], 2)
        self.assertEqual(payload["successful_companies"], 2)
        self.assertEqual(payload["failed_companies"], 0)
        self.assertIn(payload["portfolio_recommendation"], {"GO", "CONDITIONAL_GO", "NO_GO"})

        viewer_token = self._login_access_token("viewer", "viewer12345")
        viewer_forbidden = self.client.post(
            "/api/v1/ecosystem/activate/portfolio",
            headers={"Authorization": f"Bearer {viewer_token}"},
            json={
                "scope_mode": "single",
                "project_name_prefix": "Forbidden",
                "base_country": "TR",
                "target_countries": ["DE"],
                "services": ["consulting"],
                "companies": [
                    {
                        "company_name": "Viewer Co",
                        "sector": "Retail",
                        "geography": "TR",
                        "objective": "Viewer cannot activate portfolio endpoint.",
                        "budget_total": 1000,
                    }
                ],
            },
        )
        self.assertEqual(viewer_forbidden.status_code, 403)

    def test_holding_onboarding_endpoints_with_permissions(self) -> None:
        manager_token = self._login_access_token("manager", "manager12345")

        create_holding = self.client.post(
            "/api/v1/holdings",
            headers={"Authorization": f"Bearer {manager_token}"},
            json={
                "name": "Nova Holding",
                "code": "NOVA",
                "description": "Portfolio management umbrella for multiple subsidiaries.",
            },
        )
        self.assertEqual(create_holding.status_code, 201)
        holding_id = create_holding.json()["id"]

        onboard = self.client.post(
            f"/api/v1/holdings/{holding_id}/onboard",
            headers={"Authorization": f"Bearer {manager_token}"},
            json={
                "auto_register_companies": True,
                "companies": [
                    {
                        "company_name": "Nova Energy",
                        "sector": "Energy",
                        "country": "TR",
                        "initial_balance": 1000000,
                        "data_quality_score": 90,
                        "integration_completeness_score": 92,
                        "security_compliance_score": 88,
                        "process_standardization_score": 85,
                        "master_data_health_score": 89,
                        "team_readiness_score": 91,
                    },
                    {
                        "company_name": "Nova Retail",
                        "sector": "Retail",
                        "country": "TR",
                        "initial_balance": 500000,
                        "data_quality_score": 45,
                        "integration_completeness_score": 40,
                        "security_compliance_score": 35,
                        "process_standardization_score": 42,
                        "master_data_health_score": 38,
                        "team_readiness_score": 41,
                    },
                ],
            },
        )
        self.assertEqual(onboard.status_code, 200)
        onboard_payload = onboard.json()
        self.assertEqual(onboard_payload["total_companies"], 2)
        self.assertEqual(onboard_payload["go_count"], 1)
        self.assertEqual(onboard_payload["block_count"], 1)
        self.assertGreaterEqual(onboard_payload["average_readiness_score"], 60.0)
        self.assertEqual(len(onboard_payload["items"]), 2)
        self.assertTrue(all(item["registered_in_platform"] for item in onboard_payload["items"]))

        viewer_token = self._login_access_token("viewer", "viewer12345")

        viewer_list = self.client.get(
            "/api/v1/holdings?limit=20",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        self.assertEqual(viewer_list.status_code, 200)
        self.assertGreaterEqual(viewer_list.json()["total"], 1)

        viewer_detail = self.client.get(
            f"/api/v1/holdings/{holding_id}",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        self.assertEqual(viewer_detail.status_code, 200)
        self.assertEqual(viewer_detail.json()["total_companies"], 2)

        viewer_manage_forbidden = self.client.post(
            "/api/v1/holdings",
            headers={"Authorization": f"Bearer {viewer_token}"},
            json={"name": "Viewer Forbidden Holding"},
        )
        self.assertEqual(viewer_manage_forbidden.status_code, 403)

    def test_connector_endpoints_with_permissions_and_scope(self) -> None:
        manager_token = self._login_access_token("manager", "manager12345")

        create_connector = self.client.post(
            "/api/v1/connectors",
            headers={"Authorization": f"Bearer {manager_token}"},
            json={
                "company_name": "ABC Holding",
                "connector_type": "finance_erp",
                "provider": "NetSuite",
                "base_url": "https://api.netsuite.example",
                "auth_mode": "oauth2",
                "config": {
                    "token_rotate_days": 30,
                    "ip_allowlist_enabled": True,
                    "mfa_enabled": True,
                    "retry_count": 3,
                    "timeout_seconds": 30,
                },
                "mapping": {
                    "id": "external_id",
                    "company": "company_name",
                    "type": "entry_type",
                    "amount": "amount",
                    "currency": "currency",
                    "date": "entry_date",
                },
            },
        )
        self.assertEqual(create_connector.status_code, 201)
        connector_payload = create_connector.json()
        connector_id = connector_payload["id"]
        self.assertGreaterEqual(connector_payload["readiness_score"], 70.0)

        create_job = self.client.post(
            f"/api/v1/connectors/{connector_id}/sync-jobs",
            headers={"Authorization": f"Bearer {manager_token}"},
            json={
                "trigger_mode": "manual",
                "criticality": "high",
                "request_payload": {"window": "2026-Q1"},
            },
        )
        self.assertEqual(create_job.status_code, 201)

        viewer_token = self._login_access_token("viewer", "viewer12345")
        viewer_list = self.client.get(
            "/api/v1/connectors?company=ABC%20Holding",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        self.assertEqual(viewer_list.status_code, 200)
        self.assertGreaterEqual(viewer_list.json()["total"], 1)

        preview = self.client.post(
            "/api/v1/connectors/canonical/preview",
            headers={"Authorization": f"Bearer {viewer_token}"},
            json={
                "connector_type": "finance_erp",
                "mapping": {"id": "external_id", "company": "company_name"},
                "sample_payload": {
                    "id": "txn-1",
                    "company": "ABC Holding",
                    "type": "income",
                    "amount": 1500,
                    "currency": "TRY",
                    "date": "2026-03-22",
                },
            },
        )
        self.assertEqual(preview.status_code, 200)
        preview_payload = preview.json()
        self.assertEqual(preview_payload["target_entity"], "finance_ledger_entry")
        self.assertGreaterEqual(preview_payload["coverage_score"], 30.0)

        health_summary = self.client.get(
            "/api/v1/connectors/health/summary",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        self.assertEqual(health_summary.status_code, 200)
        self.assertGreaterEqual(health_summary.json()["total_connectors"], 1)

        viewer_create_forbidden = self.client.post(
            "/api/v1/connectors",
            headers={"Authorization": f"Bearer {viewer_token}"},
            json={
                "company_name": "ABC Holding",
                "connector_type": "inventory",
                "provider": "ViewerForbidden",
            },
        )
        self.assertEqual(viewer_create_forbidden.status_code, 403)

        viewer_dispatch_forbidden = self.client.post(
            "/api/v1/connectors/sync-jobs/dispatch",
            headers={"Authorization": f"Bearer {viewer_token}"},
            json={
                "company_name": "ABC Holding",
                "auto_complete": True,
                "success": True,
            },
        )
        self.assertEqual(viewer_dispatch_forbidden.status_code, 403)

        dispatch = self.client.post(
            "/api/v1/connectors/sync-jobs/dispatch",
            headers={"Authorization": f"Bearer {manager_token}"},
            json={
                "company_name": "ABC Holding",
                "auto_complete": True,
                "success": True,
                "health_score": 88,
            },
        )
        self.assertEqual(dispatch.status_code, 200)
        dispatch_payload = dispatch.json()
        self.assertTrue(dispatch_payload["claimed"])
        self.assertEqual(dispatch_payload["job"]["status"], "success")

        admin_token = self._login_admin_access_token()
        create_scoped_manager = self.client.post(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "username": "connector_scope_manager",
                "password": "ConnectorScope123",
                "role": "manager",
                "is_active": True,
                "company_scopes": ["Scope Connector Co"],
            },
        )
        self.assertEqual(create_scoped_manager.status_code, 201)
        scoped_token = self._login_access_token("connector_scope_manager", "ConnectorScope123")

        scoped_allowed = self.client.post(
            "/api/v1/connectors",
            headers={"Authorization": f"Bearer {scoped_token}"},
            json={
                "company_name": "Scope Connector Co",
                "connector_type": "inventory",
                "provider": "ScopedProvider",
                "auth_mode": "api_key",
            },
        )
        self.assertEqual(scoped_allowed.status_code, 201)

        scoped_blocked = self.client.post(
            "/api/v1/connectors",
            headers={"Authorization": f"Bearer {scoped_token}"},
            json={
                "company_name": "Blocked Connector Co",
                "connector_type": "inventory",
                "provider": "BlockedProvider",
                "auth_mode": "api_key",
            },
        )
        self.assertEqual(scoped_blocked.status_code, 403)

        scoped_list = self.client.get(
            "/api/v1/connectors?limit=50",
            headers={"Authorization": f"Bearer {scoped_token}"},
        )
        self.assertEqual(scoped_list.status_code, 200)
        scoped_items = scoped_list.json()["items"]
        self.assertTrue(all(item["company_name"] == "Scope Connector Co" for item in scoped_items))

        scoped_health = self.client.get(
            "/api/v1/connectors/health/summary",
            headers={"Authorization": f"Bearer {scoped_token}"},
        )
        self.assertEqual(scoped_health.status_code, 200)
        self.assertEqual(scoped_health.json()["total_connectors"], 1)

    def test_dashboard_includes_market_widgets(self) -> None:
        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertIn("Live Market Chart (OHLCV)", html)
        self.assertIn("AI Market Signal Cards", html)
        self.assertIn("Market Intelligence (TR + EU + Global Borsalar)", html)
        self.assertIn("id=\"market-chart\"", html)

    def _login_admin_access_token(self) -> str:
        response = self.client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin12345"})
        self.assertEqual(response.status_code, 200)
        return response.json()["access_token"]

    def _login_access_token(self, username: str, password: str) -> str:
        response = self.client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["access_token"]


if __name__ == "__main__":
    unittest.main()
