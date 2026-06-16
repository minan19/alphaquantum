"""M3: Copilot guardrail kanıt testleri.

Mevcut test_copilot.py (intent + engine smoke) bozulmadan, M3 emirin
beş guardrail'ini kanıtlar:
  1. Salt-okunur SQL (DDL/DML reddi — sunucuda)
  2. Tenant izolasyonu (A scope'lu kullanıcı B verisi göremez)
  3. Onay kapısı (confirm=False → çalıştırma yok)
  4. Hız sınırı (eşik aşılınca 429)
  5. Hata sızıntısı yok (iç schema/trace yanıta sızmaz)
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app import create_app
from app.copilot_limiter import CopilotRateLimitExceeded, CopilotRateLimiter
from app.engines.copilot_engine import CopilotEngine
from app.engines.sql_guard import ReadOnlyViolation, assert_select_only
from app.identity_repository import IdentityRepository
from app.migration_manager import MigrationManager


# ───────────────────────────── Guardrail 1: SQL guard ──────────────────


class SqlGuardTests(unittest.TestCase):
    def test_select_allowed(self) -> None:
        assert_select_only("SELECT * FROM customers")
        assert_select_only("  SELECT 1  ")
        assert_select_only("WITH x AS (SELECT 1) SELECT * FROM x")

    def test_trailing_semicolon_allowed(self) -> None:
        assert_select_only("SELECT 1;")

    def test_insert_rejected(self) -> None:
        with self.assertRaises(ReadOnlyViolation):
            assert_select_only("INSERT INTO customers (id) VALUES (1)")

    def test_drop_rejected(self) -> None:
        with self.assertRaises(ReadOnlyViolation):
            assert_select_only("DROP TABLE customers")

    def test_multi_statement_rejected(self) -> None:
        with self.assertRaises(ReadOnlyViolation):
            assert_select_only("SELECT 1; DELETE FROM customers")

    def test_comment_hidden_keyword_rejected(self) -> None:
        # `-- ` öncesi SELECT, sonrası DELETE → yorum çıkarılınca da
        # yine reject çünkü trailing `; DELETE` kalır.
        with self.assertRaises(ReadOnlyViolation):
            assert_select_only("SELECT 1 -- comment\n; DELETE FROM x")

    def test_block_comment_hidden_keyword_stripped(self) -> None:
        # /* ... */ yorum içine saklanan keyword: yorumlar strip edilir,
        # sonrası salt-SELECT kaldığı için kabul edilir.
        assert_select_only("SELECT /* DROP */ 1")

    def test_empty_rejected(self) -> None:
        with self.assertRaises(ReadOnlyViolation):
            assert_select_only("")


# ───────────────────────── Guardrail 2: Tenant izolasyonu ──────────────


class _EngineFixture(unittest.TestCase):
    """Migrations + iki şirketin seed verisi."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp.name) / "guardrail_test.db"
        migrations_dir = (
            Path(__file__).resolve().parent.parent / "migrations"
        )
        IdentityRepository(str(self._db_path)).close()
        self.manager = MigrationManager(
            str(self._db_path), str(migrations_dir),
        )
        self.manager.apply_all()
        self.engine = CopilotEngine(database_path=str(self._db_path))
        self._seed_two_companies()

    def tearDown(self) -> None:
        self.manager.close()
        self._tmp.cleanup()

    def _seed_two_companies(self) -> None:
        conn = sqlite3.connect(str(self._db_path))
        # 5 müşteri CompanyA, 3 müşteri CompanyB
        for i in range(5):
            conn.execute(
                "INSERT INTO customers "
                "(company_name, full_name, email, sector, is_active, "
                " created_at, updated_at) "
                "VALUES (?, ?, ?, 'general', 1, 1700000000, 1700000000)",
                ("CompanyA", f"A-cust-{i}", f"a{i}@a.com"),
            )
        for i in range(3):
            conn.execute(
                "INSERT INTO customers "
                "(company_name, full_name, email, sector, is_active, "
                " created_at, updated_at) "
                "VALUES (?, ?, ?, 'general', 1, 1700000000, 1700000000)",
                ("CompanyB", f"B-cust-{i}", f"b{i}@b.com"),
            )
        # Ledger: A 1000 gelir, B 500 gider
        conn.execute(
            "INSERT INTO finance_ledger_entries "
            "(company_name, entry_type, amount, category, description, "
            " entry_date, created_at, intercompany_flag) "
            "VALUES ('CompanyA', 'income', 1000, 'g', '', date('now'), "
            "1700000000, 0)",
        )
        conn.execute(
            "INSERT INTO finance_ledger_entries "
            "(company_name, entry_type, amount, category, description, "
            " entry_date, created_at, intercompany_flag) "
            "VALUES ('CompanyB', 'expense', 500, 'g', '', date('now'), "
            "1700000000, 0)",
        )
        conn.commit()
        conn.close()


class TenantIsolationTests(_EngineFixture):
    def test_company_a_user_sees_only_a_customers(self) -> None:
        response = self.engine.ask(
            query="Müşterilerimi göster",
            company_scopes=["CompanyA"],
        )
        self.assertEqual(response.intent.intent, "list_customers")
        self.assertTrue(response.executed)
        full_names = [r["full_name"] for r in response.results]
        self.assertEqual(len(full_names), 5)
        for name in full_names:
            self.assertTrue(name.startswith("A-cust-"))

    def test_company_b_user_does_not_see_a_data(self) -> None:
        response = self.engine.ask(
            query="Müşterilerimi göster",
            company_scopes=["CompanyB"],
        )
        for r in response.results:
            self.assertFalse(r["full_name"].startswith("A-cust-"))
        self.assertEqual(len(response.results), 3)

    def test_balance_scoped_to_a_only(self) -> None:
        response = self.engine.ask(
            query="Bakiyem ne kadar?",
            company_scopes=["CompanyA"],
        )
        # A: income 1000, expense 0 → balance 1000
        self.assertEqual(response.results[0]["balance"], 1000.0)

    def test_wildcard_scope_sees_all(self) -> None:
        response = self.engine.ask(
            query="Müşterilerimi göster",
            company_scopes=["*"],
        )
        self.assertEqual(len(response.results), 8)

    def test_empty_scope_returns_no_rows(self) -> None:
        response = self.engine.ask(
            query="Müşterilerimi göster",
            company_scopes=[],
        )
        self.assertEqual(response.results, [])

    def test_anomaly_scoped_user_rejected(self) -> None:
        response = self.engine.ask(
            query="Aktif anomalileri listele",
            company_scopes=["CompanyA"],
        )
        # anomaly_signals tablosu company_name taşımıyor → reddedildi
        self.assertFalse(response.executed)
        self.assertIn("scope", response.summary_text.lower())


# ───────────────────────── Guardrail 3: Onay kapısı ────────────────────


class ConsentGateTests(_EngineFixture):
    def test_preview_does_not_execute(self) -> None:
        response = self.engine.ask(
            query="Müşterilerimi göster",
            company_scopes=["CompanyA"],
            execute=False,
        )
        self.assertFalse(response.executed)
        self.assertEqual(response.results, [])
        # SQL + params kullanıcıya gösterilmeli — M4.2 sonrası filtre
        # company_id üstünden (sunucuda name → id çözümü).
        self.assertIsNotNone(response.sql)
        assert response.sql is not None
        self.assertIn("SELECT", response.sql.upper())
        self.assertIn("company_id IN", response.sql)
        self.assertTrue(
            all(isinstance(p, int) for p in response.params),
            f"params id listesi olmalı: {response.params}",
        )

    def test_confirm_true_executes(self) -> None:
        response = self.engine.ask(
            query="Müşterilerimi göster",
            company_scopes=["CompanyA"],
            execute=True,
        )
        self.assertTrue(response.executed)
        self.assertEqual(len(response.results), 5)


# ───────────────────────── Guardrail 4: Rate limit ─────────────────────


class RateLimiterTests(unittest.TestCase):
    def test_blocks_after_threshold(self) -> None:
        limiter = CopilotRateLimiter(window_seconds=60, max_requests=3)
        for _ in range(3):
            limiter.hit("user:1")
        with self.assertRaises(CopilotRateLimitExceeded):
            limiter.hit("user:1")

    def test_different_users_isolated(self) -> None:
        limiter = CopilotRateLimiter(window_seconds=60, max_requests=2)
        limiter.hit("user:1")
        limiter.hit("user:1")
        # user:2 ayrı kovada — engellenmez
        limiter.hit("user:2")
        with self.assertRaises(CopilotRateLimitExceeded):
            limiter.hit("user:1")


# ───────────────────── Guardrail 5: Hata sızıntısı (HTTP) ──────────────


class _HttpFixture(unittest.TestCase):
    """create_app() + login admin (wildcard scope ile)."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp.name) / "http_test.db"
        self._original_env = {
            k: os.getenv(k) for k in (
                "AQ_DATABASE_PATH", "AQ_AUTH_USERS",
                "AQ_ENABLE_DEMO_USERS", "AQ_JWT_SECRET", "AQ_ENV",
                "AQ_MARKET_OFFLINE", "AQ_MACRO_OFFLINE", "AQ_WEB_OFFLINE",
            )
        }
        os.environ["AQ_DATABASE_PATH"] = str(self._db_path)
        os.environ["AQ_AUTH_USERS"] = "admin:admin12345:admin"
        os.environ["AQ_ENABLE_DEMO_USERS"] = "false"
        os.environ["AQ_JWT_SECRET"] = "guardrail-test-secret"
        os.environ["AQ_ENV"] = "development"
        os.environ["AQ_MARKET_OFFLINE"] = "true"
        os.environ["AQ_MACRO_OFFLINE"] = "true"
        os.environ["AQ_WEB_OFFLINE"] = "true"

        self.client = TestClient(create_app())
        login = self.client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin12345"},
        )
        self.assertEqual(login.status_code, 200)
        self.token = login.json()["access_token"]
        self.auth_headers = {"Authorization": f"Bearer {self.token}"}

    def tearDown(self) -> None:
        self.client.close()
        for k, v in self._original_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self._tmp.cleanup()


class HttpGuardrailTests(_HttpFixture):
    def test_confirm_false_returns_preview_not_results(self) -> None:
        response = self.client.post(
            "/api/v1/copilot/ask",
            headers=self.auth_headers,
            json={"query": "Müşterilerimi göster", "confirm": False},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["executed"])
        self.assertEqual(payload["results"], [])
        self.assertIsNotNone(payload["sql"])

    def test_rate_limit_returns_429_after_threshold(self) -> None:
        # Default app state limit = 10/dk. 11. çağrı → 429.
        for _ in range(10):
            self.client.post(
                "/api/v1/copilot/ask",
                headers=self.auth_headers,
                json={"query": "Müşterilerimi göster", "confirm": False},
            )
        eleventh = self.client.post(
            "/api/v1/copilot/ask",
            headers=self.auth_headers,
            json={"query": "Müşterilerimi göster", "confirm": False},
        )
        self.assertEqual(eleventh.status_code, 429)

    def test_internal_error_does_not_leak_schema(self) -> None:
        from app.engines.copilot_engine import CopilotEngine

        def boom(*_a: object, **_kw: object) -> None:
            raise RuntimeError(
                "internal error mentioning invoices.amount and "
                "finance_ledger_entries.entry_type"
            )

        original = CopilotEngine.ask
        CopilotEngine.ask = boom  # type: ignore[method-assign]
        try:
            response = self.client.post(
                "/api/v1/copilot/ask",
                headers=self.auth_headers,
                json={"query": "Müşterilerimi göster", "confirm": True},
            )
        finally:
            CopilotEngine.ask = original  # type: ignore[method-assign]
        self.assertEqual(response.status_code, 500)
        body_text = response.text.lower()
        # Schema isimleri yanıta sızmamalı
        self.assertNotIn("invoices.amount", body_text)
        self.assertNotIn("finance_ledger_entries", body_text)
        self.assertNotIn("traceback", body_text)


if __name__ == "__main__":
    unittest.main()
