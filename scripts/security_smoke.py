from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from app import create_app


class SmokeFailure(RuntimeError):
    pass


def _check(condition: bool, label: str, detail: str, rows: list[tuple[str, str, str]]) -> None:
    rows.append(("PASS" if condition else "FAIL", label, detail))


def run_security_smoke() -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []

    with tempfile.TemporaryDirectory() as td:
        db_path = str(Path(td) / "security_smoke.db")

        env_keys = [
            "AQ_DATABASE_PATH",
            "AQ_AUTH_USERS",
            "AQ_ENABLE_DEMO_USERS",
            "AQ_JWT_SECRET",
            "AQ_ENV",
            "AQ_CORS_ORIGINS",
            "AQ_ALLOW_ALL_CORS",
            "AQ_MARKET_OFFLINE",
            "AQ_MACRO_OFFLINE",
            "AQ_WEB_OFFLINE",
        ]
        original = {key: os.getenv(key) for key in env_keys}

        os.environ["AQ_DATABASE_PATH"] = db_path
        os.environ["AQ_AUTH_USERS"] = (
            "admin:admin12345:admin,"
            "manager:manager12345:manager,"
            "viewer:viewer12345:viewer"
        )
        os.environ["AQ_ENABLE_DEMO_USERS"] = "false"
        os.environ["AQ_JWT_SECRET"] = "security-smoke-secret"
        os.environ["AQ_ENV"] = "development"
        os.environ.pop("AQ_CORS_ORIGINS", None)
        os.environ["AQ_ALLOW_ALL_CORS"] = "false"
        os.environ["AQ_MARKET_OFFLINE"] = "true"
        os.environ["AQ_MACRO_OFFLINE"] = "true"
        os.environ["AQ_WEB_OFFLINE"] = "true"

        try:
            app = create_app()
            client = TestClient(app)

            login = client.post(
                "/api/v1/auth/login",
                json={"username": "admin", "password": "admin12345"},
            )
            _check(login.status_code == 200, "auth_login", f"status={login.status_code}", rows)
            token = login.json().get("access_token", "") if login.status_code == 200 else ""

            tampered = token[:-1] + ("A" if token and token[-1] != "A" else "B") if token else "invalid"
            tampered_resp = client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {tampered}"},
            )
            _check(tampered_resp.status_code == 401, "jwt_tamper_rejected", f"status={tampered_resp.status_code}", rows)

            rate_codes: list[int] = []
            for _ in range(6):
                response = client.post(
                    "/api/v1/auth/login",
                    json={"username": "admin", "password": "wrong-pass"},
                )
                rate_codes.append(response.status_code)
            _check(rate_codes[-1] == 429, "rate_limit", f"codes={rate_codes}", rows)

            manager_login = client.post(
                "/api/v1/auth/login",
                json={"username": "manager", "password": "manager12345"},
            )
            manager_token = manager_login.json().get("access_token", "")
            migration_forbidden = client.get(
                "/api/v1/admin/migrations/status",
                headers={"Authorization": f"Bearer {manager_token}"},
            )
            _check(
                migration_forbidden.status_code == 403,
                "migration_admin_protected",
                f"status={migration_forbidden.status_code}",
                rows,
            )

            viewer_login = client.post(
                "/api/v1/auth/login",
                json={"username": "viewer", "password": "viewer12345"},
            )
            viewer_token = viewer_login.json().get("access_token", "")
            viewer_write_forbidden = client.post(
                "/api/v1/finance-engine/ledger",
                headers={"Authorization": f"Bearer {viewer_token}"},
                json={
                    "company": "ABC Holding",
                    "entry_type": "income",
                    "amount": 10,
                    "category": "smoke",
                    "description": "viewer-write-attempt",
                },
            )
            _check(
                viewer_write_forbidden.status_code == 403,
                "finance_write_permission",
                f"status={viewer_write_forbidden.status_code}",
                rows,
            )

            viewer_market_read = client.get(
                "/api/v1/market/ohlcv?symbol=AAPL&days=90",
                headers={"Authorization": f"Bearer {viewer_token}"},
            )
            _check(
                viewer_market_read.status_code == 200,
                "market_read_permission",
                f"status={viewer_market_read.status_code}",
                rows,
            )

            viewer_market_refresh_forbidden = client.post(
                "/api/v1/market/refresh",
                headers={"Authorization": f"Bearer {viewer_token}"},
                json={"symbols": ["AAPL"], "days": 60},
            )
            _check(
                viewer_market_refresh_forbidden.status_code == 403,
                "market_refresh_permission",
                f"status={viewer_market_refresh_forbidden.status_code}",
                rows,
            )

            viewer_global_report = client.get(
                "/api/v1/global/report",
                headers={"Authorization": f"Bearer {viewer_token}"},
            )
            _check(
                viewer_global_report.status_code == 200,
                "global_report_permission",
                f"status={viewer_global_report.status_code}",
                rows,
            )

            viewer_public_sources_report = client.post(
                "/api/v1/public-institutions/report",
                headers={"Authorization": f"Bearer {viewer_token}"},
                json={
                    "pages": [{"url": "https://www.worldbank.org"}],
                    "global_focus_terms": ["inflation", "policy"],
                },
            )
            _check(
                viewer_public_sources_report.status_code == 200,
                "public_sources_permission",
                f"status={viewer_public_sources_report.status_code}",
                rows,
            )

            viewer_market_intelligence = client.post(
                "/api/v1/market/intelligence",
                headers={"Authorization": f"Bearer {viewer_token}"},
                json={
                    "pages": [{"url": "https://www.worldbank.org", "focus_terms": ["market"]}],
                    "focus_symbols": ["AAPL"],
                    "days": 90,
                    "max_symbols": 2,
                },
            )
            _check(
                viewer_market_intelligence.status_code == 200,
                "market_intelligence_permission",
                f"status={viewer_market_intelligence.status_code}",
                rows,
            )

            viewer_market_backtest = client.get(
                "/api/v1/market/backtest?symbol=AAPL&days=220&lookahead_days=5",
                headers={"Authorization": f"Bearer {viewer_token}"},
            )
            _check(
                viewer_market_backtest.status_code == 200,
                "market_backtest_permission",
                f"status={viewer_market_backtest.status_code}",
                rows,
            )

            viewer_market_sources = client.get(
                "/api/v1/market/sources?regions=TR,EU,GLOBAL&limit=8",
                headers={"Authorization": f"Bearer {viewer_token}"},
            )
            _check(
                viewer_market_sources.status_code == 200,
                "market_sources_permission",
                f"status={viewer_market_sources.status_code}",
                rows,
            )

            viewer_procurement_read = client.get(
                "/api/v1/procurement/requests",
                headers={"Authorization": f"Bearer {viewer_token}"},
            )
            _check(
                viewer_procurement_read.status_code == 200,
                "procurement_read_permission",
                f"status={viewer_procurement_read.status_code}",
                rows,
            )

            viewer_procurement_write_forbidden = client.post(
                "/api/v1/procurement/requests",
                headers={"Authorization": f"Bearer {viewer_token}"},
                json={
                    "company": "Viewer Co",
                    "title": "Forbidden Procurement",
                    "items": [{"item_name": "Cable", "quantity": 1}],
                },
            )
            _check(
                viewer_procurement_write_forbidden.status_code == 403,
                "procurement_write_viewer_forbidden",
                f"status={viewer_procurement_write_forbidden.status_code}",
                rows,
            )

            manager_procurement_request = client.post(
                "/api/v1/procurement/requests",
                headers={"Authorization": f"Bearer {manager_token}"},
                json={
                    "company": "Alpha Quantum A.S.",
                    "title": "Security Smoke Procurement",
                    "strategy": "balanced",
                    "items": [
                        {
                            "item_name": "Firewall",
                            "quantity": 1,
                            "min_quality_score": 70,
                            "must_comply_tender": True,
                        }
                    ],
                },
            )
            request_payload = manager_procurement_request.json() if manager_procurement_request.status_code == 201 else {}
            item_id = (
                request_payload.get("items", [{}])[0].get("id")
                if isinstance(request_payload, dict)
                else None
            )
            request_id = request_payload.get("id") if isinstance(request_payload, dict) else None
            manager_procurement_quote = client.post(
                "/api/v1/procurement/quotes",
                headers={"Authorization": f"Bearer {manager_token}"},
                json={
                    "request_id": request_id,
                    "vendor_name": "SecureVendor",
                    "vendor_rating": 85,
                    "delivery_days": 4,
                    "compliance_score": 90,
                    "quote_items": [
                        {
                            "request_item_id": item_id,
                            "unit_price": 4500,
                            "available_quantity": 1,
                            "quality_score": 88,
                        }
                    ],
                },
            )
            manager_procurement_auto_po = client.post(
                f"/api/v1/procurement/requests/{request_id}/purchase-orders/auto",
                headers={"Authorization": f"Bearer {manager_token}"},
                json={"auto_approve": True},
            )
            _check(
                manager_procurement_request.status_code == 201
                and manager_procurement_quote.status_code == 201
                and manager_procurement_auto_po.status_code == 200,
                "procurement_manager_flow",
                (
                    f"request={manager_procurement_request.status_code} "
                    f"quote={manager_procurement_quote.status_code} "
                    f"auto_po={manager_procurement_auto_po.status_code}"
                ),
                rows,
            )

            scoped_manager_create = client.post(
                "/api/v1/users",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "username": "scope_smoke_manager",
                    "password": "ScopeSmoke123",
                    "role": "manager",
                    "is_active": True,
                    "company_scopes": ["Scope Co"],
                },
            )
            scoped_manager_login = client.post(
                "/api/v1/auth/login",
                json={"username": "scope_smoke_manager", "password": "ScopeSmoke123"},
            )
            scoped_token = (
                scoped_manager_login.json().get("access_token", "")
                if scoped_manager_login.status_code == 200
                else ""
            )
            scoped_finance_allowed = client.post(
                "/api/v1/finance-engine/ledger",
                headers={"Authorization": f"Bearer {scoped_token}"},
                json={
                    "company": "Scope Co",
                    "entry_type": "income",
                    "amount": 250,
                    "category": "scope",
                },
            )
            scoped_finance_blocked = client.post(
                "/api/v1/finance-engine/ledger",
                headers={"Authorization": f"Bearer {scoped_token}"},
                json={
                    "company": "Other Co",
                    "entry_type": "income",
                    "amount": 250,
                    "category": "scope",
                },
            )
            scoped_cashflow_blocked = client.get(
                "/api/v1/finance-engine/cashflow?lookback_days=30",
                headers={"Authorization": f"Bearer {scoped_token}"},
            )
            _check(
                scoped_manager_create.status_code == 201
                and scoped_manager_login.status_code == 200
                and scoped_finance_allowed.status_code == 201
                and scoped_finance_blocked.status_code == 403
                and scoped_cashflow_blocked.status_code == 400,
                "company_scope_isolation_flow",
                (
                    f"create={scoped_manager_create.status_code} "
                    f"login={scoped_manager_login.status_code} "
                    f"allowed={scoped_finance_allowed.status_code} "
                    f"blocked={scoped_finance_blocked.status_code} "
                    f"cashflow_no_company={scoped_cashflow_blocked.status_code}"
                ),
                rows,
            )

            manager_holding_create = client.post(
                "/api/v1/holdings",
                headers={"Authorization": f"Bearer {manager_token}"},
                json={
                    "name": "Smoke Holding",
                    "code": "SMOKE",
                    "description": "Holding smoke test portfolio",
                },
            )
            manager_holding_payload = manager_holding_create.json() if manager_holding_create.status_code == 201 else {}
            holding_id = manager_holding_payload.get("id") if isinstance(manager_holding_payload, dict) else None
            manager_holding_onboard = client.post(
                f"/api/v1/holdings/{holding_id}/onboard",
                headers={"Authorization": f"Bearer {manager_token}"},
                json={
                    "auto_register_companies": True,
                    "companies": [
                        {
                            "company_name": "Smoke Energy",
                            "sector": "Energy",
                            "country": "TR",
                            "data_quality_score": 88,
                            "integration_completeness_score": 86,
                            "security_compliance_score": 87,
                            "process_standardization_score": 84,
                            "master_data_health_score": 85,
                            "team_readiness_score": 86,
                        }
                    ],
                },
            )
            viewer_holding_read = client.get(
                "/api/v1/holdings?limit=10",
                headers={"Authorization": f"Bearer {viewer_token}"},
            )
            viewer_holding_manage_forbidden = client.post(
                "/api/v1/holdings",
                headers={"Authorization": f"Bearer {viewer_token}"},
                json={"name": "Viewer Forbidden Holding"},
            )
            _check(
                manager_holding_create.status_code == 201
                and manager_holding_onboard.status_code == 200
                and viewer_holding_read.status_code == 200
                and viewer_holding_manage_forbidden.status_code == 403,
                "holding_permission_flow",
                (
                    f"create={manager_holding_create.status_code} "
                    f"onboard={manager_holding_onboard.status_code} "
                    f"viewer_read={viewer_holding_read.status_code} "
                    f"viewer_manage={viewer_holding_manage_forbidden.status_code}"
                ),
                rows,
            )

            manager_connector_create = client.post(
                "/api/v1/connectors",
                headers={"Authorization": f"Bearer {manager_token}"},
                json={
                    "company_name": "ABC Holding",
                    "connector_type": "finance_erp",
                    "provider": "SmokeConnector",
                    "base_url": "https://connector.example",
                    "auth_mode": "oauth2",
                    "config": {
                        "token_rotate_days": 30,
                        "ip_allowlist_enabled": True,
                        "mfa_enabled": True,
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
            connector_payload = (
                manager_connector_create.json()
                if manager_connector_create.status_code == 201
                else {}
            )
            connector_id = (
                connector_payload.get("id")
                if isinstance(connector_payload, dict)
                else None
            )
            manager_connector_job = client.post(
                f"/api/v1/connectors/{connector_id}/sync-jobs",
                headers={"Authorization": f"Bearer {manager_token}"},
                json={
                    "trigger_mode": "manual",
                    "criticality": "high",
                    "request_payload": {"window": "2026-Q1"},
                },
            )
            viewer_connector_read = client.get(
                "/api/v1/connectors?company=ABC%20Holding",
                headers={"Authorization": f"Bearer {viewer_token}"},
            )
            viewer_connector_health = client.get(
                "/api/v1/connectors/health/summary",
                headers={"Authorization": f"Bearer {viewer_token}"},
            )
            viewer_connector_manage_forbidden = client.post(
                "/api/v1/connectors",
                headers={"Authorization": f"Bearer {viewer_token}"},
                json={
                    "company_name": "ABC Holding",
                    "connector_type": "inventory",
                    "provider": "ViewerForbidden",
                    "auth_mode": "api_key",
                },
            )
            viewer_connector_dispatch_forbidden = client.post(
                "/api/v1/connectors/sync-jobs/dispatch",
                headers={"Authorization": f"Bearer {viewer_token}"},
                json={
                    "company_name": "ABC Holding",
                    "auto_complete": True,
                    "success": True,
                },
            )
            manager_connector_dispatch = client.post(
                "/api/v1/connectors/sync-jobs/dispatch",
                headers={"Authorization": f"Bearer {manager_token}"},
                json={
                    "company_name": "ABC Holding",
                    "auto_complete": True,
                    "success": True,
                    "health_score": 90,
                },
            )
            _check(
                manager_connector_create.status_code == 201
                and manager_connector_job.status_code == 201
                and viewer_connector_read.status_code == 200
                and viewer_connector_health.status_code == 200
                and viewer_connector_manage_forbidden.status_code == 403
                and viewer_connector_dispatch_forbidden.status_code == 403
                and manager_connector_dispatch.status_code == 200,
                "connector_permission_flow",
                (
                    f"create={manager_connector_create.status_code} "
                    f"job={manager_connector_job.status_code} "
                    f"viewer_read={viewer_connector_read.status_code} "
                    f"viewer_health={viewer_connector_health.status_code} "
                    f"viewer_manage={viewer_connector_manage_forbidden.status_code} "
                    f"viewer_dispatch={viewer_connector_dispatch_forbidden.status_code} "
                    f"dispatch={manager_connector_dispatch.status_code}"
                ),
                rows,
            )

            manager_feasibility_create = client.post(
                "/api/v1/feasibility/report",
                headers={"Authorization": f"Bearer {manager_token}"},
                json={
                    "project_name": "Security Smoke Feasibility",
                    "sector": "Technology",
                    "geography": "TR",
                    "objective": (
                        "Validate feasibility API permission flow with a realistic investment case "
                        "for dynamic smoke security checks."
                    ),
                    "initial_investment": 5000000,
                    "annual_opex": 900000,
                    "annual_revenue_base": 1800000,
                },
            )
            manager_feasibility_payload = (
                manager_feasibility_create.json()
                if manager_feasibility_create.status_code == 201
                else {}
            )
            feasibility_id = (
                manager_feasibility_payload.get("id")
                if isinstance(manager_feasibility_payload, dict)
                else None
            )
            viewer_feasibility_read = client.get(
                "/api/v1/feasibility/reports?limit=5",
                headers={"Authorization": f"Bearer {viewer_token}"},
            )
            viewer_feasibility_detail = client.get(
                f"/api/v1/feasibility/reports/{feasibility_id}",
                headers={"Authorization": f"Bearer {viewer_token}"},
            )
            viewer_feasibility_write_forbidden = client.post(
                "/api/v1/feasibility/report",
                headers={"Authorization": f"Bearer {viewer_token}"},
                json={
                    "project_name": "Viewer Forbidden",
                    "sector": "Retail",
                    "geography": "TR",
                    "objective": "Viewer must not create feasibility reports via write endpoint.",
                    "initial_investment": 1000,
                    "annual_opex": 100,
                    "annual_revenue_base": 200,
                },
            )
            _check(
                manager_feasibility_create.status_code == 201
                and viewer_feasibility_read.status_code == 200
                and viewer_feasibility_detail.status_code == 200
                and viewer_feasibility_write_forbidden.status_code == 403,
                "feasibility_permission_flow",
                (
                    f"create={manager_feasibility_create.status_code} "
                    f"list={viewer_feasibility_read.status_code} "
                    f"detail={viewer_feasibility_detail.status_code} "
                    f"viewer_write={viewer_feasibility_write_forbidden.status_code}"
                ),
                rows,
            )

            manager_international_create = client.post(
                "/api/v1/international/projects",
                headers={"Authorization": f"Bearer {manager_token}"},
                json={
                    "project_name": "Security Smoke International",
                    "company_name": "Alpha Quantum A.S.",
                    "base_country": "TR",
                    "target_countries": ["DE", "AE"],
                    "services": ["management", "consulting", "import_export"],
                    "budget_total": 2500000,
                    "currency": "USD",
                },
            )
            manager_international_payload = (
                manager_international_create.json()
                if manager_international_create.status_code == 201
                else {}
            )
            international_id = (
                manager_international_payload.get("id")
                if isinstance(manager_international_payload, dict)
                else None
            )
            viewer_international_read = client.get(
                "/api/v1/international/projects?limit=5",
                headers={"Authorization": f"Bearer {viewer_token}"},
            )
            viewer_international_detail = client.get(
                f"/api/v1/international/projects/{international_id}",
                headers={"Authorization": f"Bearer {viewer_token}"},
            )
            viewer_international_write_forbidden = client.post(
                "/api/v1/international/projects",
                headers={"Authorization": f"Bearer {viewer_token}"},
                json={
                    "project_name": "Viewer Forbidden International",
                    "company_name": "Viewer Co",
                    "base_country": "TR",
                    "target_countries": ["DE"],
                    "services": ["consulting"],
                    "budget_total": 1000,
                },
            )
            _check(
                manager_international_create.status_code == 201
                and viewer_international_read.status_code == 200
                and viewer_international_detail.status_code == 200
                and viewer_international_write_forbidden.status_code == 403,
                "international_permission_flow",
                (
                    f"create={manager_international_create.status_code} "
                    f"list={viewer_international_read.status_code} "
                    f"detail={viewer_international_detail.status_code} "
                    f"viewer_write={viewer_international_write_forbidden.status_code}"
                ),
                rows,
            )

            manager_ecosystem_activate = client.post(
                "/api/v1/ecosystem/activate",
                headers={"Authorization": f"Bearer {manager_token}"},
                json={
                    "project_name": "Security Smoke Ecosystem",
                    "company_name": "Alpha Quantum A.S.",
                    "sector": "Energy",
                    "geography": "TR",
                    "objective": (
                        "Validate integrated orchestration endpoint security controls across feasibility, "
                        "international operations, and procurement modules."
                    ),
                    "budget_total": 3000000,
                    "currency": "USD",
                    "base_country": "TR",
                    "target_countries": ["DE", "AE"],
                    "services": ["management", "consulting", "import_export"],
                    "procurement_items": [
                        {"item_name": "Control Unit", "quantity": 1}
                    ],
                },
            )
            viewer_ecosystem_activate_forbidden = client.post(
                "/api/v1/ecosystem/activate",
                headers={"Authorization": f"Bearer {viewer_token}"},
                json={
                    "project_name": "Viewer Forbidden Ecosystem",
                    "company_name": "Viewer Co",
                    "sector": "Retail",
                    "geography": "TR",
                    "objective": "Viewer must not activate ecosystem orchestration endpoint.",
                    "budget_total": 1000,
                    "base_country": "TR",
                    "target_countries": ["DE"],
                    "services": ["consulting"],
                },
            )
            _check(
                manager_ecosystem_activate.status_code == 200
                and viewer_ecosystem_activate_forbidden.status_code == 403,
                "ecosystem_activate_permission_flow",
                (
                    f"manager_activate={manager_ecosystem_activate.status_code} "
                    f"viewer_activate={viewer_ecosystem_activate_forbidden.status_code}"
                ),
                rows,
            )

            manager_ecosystem_portfolio_activate = client.post(
                "/api/v1/ecosystem/activate/portfolio",
                headers={"Authorization": f"Bearer {manager_token}"},
                json={
                    "scope_mode": "holding",
                    "holding_name": "Alpha Holding",
                    "project_name_prefix": "Smoke Holding Program",
                    "base_country": "TR",
                    "target_countries": ["DE", "AE"],
                    "services": ["management", "consulting", "import_export"],
                    "companies": [
                        {
                            "company_name": "Alpha Energy",
                            "sector": "Energy",
                            "geography": "TR",
                            "objective": "Holding-level integrated activation for energy subsidiary.",
                            "budget_total": 5000000,
                        },
                        {
                            "company_name": "Alpha Tech",
                            "sector": "Technology",
                            "geography": "EU",
                            "objective": "Holding-level integrated activation for technology subsidiary.",
                            "budget_total": 4500000,
                        },
                    ],
                },
            )
            viewer_ecosystem_portfolio_activate_forbidden = client.post(
                "/api/v1/ecosystem/activate/portfolio",
                headers={"Authorization": f"Bearer {viewer_token}"},
                json={
                    "scope_mode": "single",
                    "project_name_prefix": "Viewer Forbidden Portfolio",
                    "base_country": "TR",
                    "target_countries": ["DE"],
                    "services": ["consulting"],
                    "companies": [
                        {
                            "company_name": "Viewer Co",
                            "sector": "Retail",
                            "geography": "TR",
                            "objective": "Viewer must not activate portfolio orchestration endpoint.",
                            "budget_total": 1000,
                        }
                    ],
                },
            )
            _check(
                manager_ecosystem_portfolio_activate.status_code == 200
                and viewer_ecosystem_portfolio_activate_forbidden.status_code == 403,
                "ecosystem_portfolio_permission_flow",
                (
                    f"manager_activate={manager_ecosystem_portfolio_activate.status_code} "
                    f"viewer_activate={viewer_ecosystem_portfolio_activate_forbidden.status_code}"
                ),
                rows,
            )

            viewer_tender_forbidden = client.post(
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
            _check(
                viewer_tender_forbidden.status_code == 403,
                "tender_permission_viewer_forbidden",
                f"status={viewer_tender_forbidden.status_code}",
                rows,
            )

            manager_tender_allowed = client.post(
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
                },
            )
            _check(
                manager_tender_allowed.status_code == 200,
                "tender_permission_manager_allowed",
                f"status={manager_tender_allowed.status_code}",
                rows,
            )

            probe_company = "ACME'; DROP TABLE users;--"
            probe_insert = client.post(
                "/api/v1/finance-engine/ledger",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "company": probe_company,
                    "entry_type": "income",
                    "amount": 100,
                    "category": "security",
                    "description": "sql-probe",
                },
            )
            probe_query = client.get(
                "/api/v1/finance-engine/ledger",
                headers={"Authorization": f"Bearer {token}"},
                params={"company": probe_company},
            )
            manager_relogin = client.post(
                "/api/v1/auth/login",
                json={"username": "manager", "password": "manager12345"},
            )
            _check(
                probe_insert.status_code == 201
                and probe_query.status_code == 200
                and manager_relogin.status_code == 200,
                "sql_probe_no_breakout",
                (
                    f"insert={probe_insert.status_code} "
                    f"query={probe_query.status_code} "
                    f"relogin={manager_relogin.status_code}"
                ),
                rows,
            )

            health = client.get("/api/v1/health")
            header_keys = {
                "x-request-id",
                "x-content-type-options",
                "x-frame-options",
                "referrer-policy",
                "cache-control",
            }
            has_security_headers = header_keys.issubset(set(health.headers.keys()))
            _check(has_security_headers, "security_headers", f"status={health.status_code}", rows)

            cors_resp = client.get(
                "/api/v1/health",
                headers={"Origin": "https://evil.example"},
            )
            allow_origin = cors_resp.headers.get("access-control-allow-origin")
            _check(allow_origin in (None, ""), "cors_not_permissive", f"allow_origin={allow_origin}", rows)

            client.close()
        finally:
            for key, value in original.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    failures = [row for row in rows if row[0] == "FAIL"]
    if failures:
        details = "; ".join(f"{name}({detail})" for _, name, detail in failures)
        raise SmokeFailure(f"Security smoke failed: {details}")

    return rows


def main() -> None:
    rows = run_security_smoke()
    for status, name, detail in rows:
        print(f"[{status}] {name} - {detail}")
    print(f"SUMMARY total={len(rows)} pass={len(rows)} fail=0")


if __name__ == "__main__":
    main()
