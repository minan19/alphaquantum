"""Design Token Programı — Faz 1 · Backend testleri.

Doğrulamalar:
    * Migration 034 uygulandığında color_tokens tablosu doğru şemada.
    * Repository upsert idempotent (aynı seed iki kez çağrılınca aynı sonuç).
    * Governance guard çalışıyor:
        - core scope'unda izinsiz anahtar reddedilir
        - modül scope'unda core-sahipli anahtar reddedilir
    * Seed wcag-report.json'dan birebir okunur ve eşleşir.
    * /api/v1/design-tokens endpoint'i seed sonrası kayıtları döndürür.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.color_token_repository import (
    CORE_ALLOWED_KEYS,
    MODULE_ALLOWED_KEYS,
    ColorTokenRepository,
    GovernanceViolation,
    assert_governance,
)
from app.color_token_seed import build_seed_items, seed_color_tokens
from app.identity_repository import IdentityRepository
from app.migration_manager import MigrationManager

REPO_ROOT = Path(__file__).resolve().parent.parent
WCAG_REPORT = REPO_ROOT / "docs" / "design-tokens" / "wcag-report.json"


class ColorTokenSchemaTests(unittest.TestCase):
    """Migration 034 → color_tokens tablo şeması."""

    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._temp_dir.name) / "schema.db"
        bootstrap = IdentityRepository(str(self._db_path))
        bootstrap.close()
        self.manager = MigrationManager(
            str(self._db_path),
            str(REPO_ROOT / "migrations"),
        )
        self.manager.apply_all()

    def tearDown(self) -> None:
        self.manager.close()
        self._temp_dir.cleanup()

    def test_color_tokens_table_shape(self) -> None:
        cur = self.manager._conn.execute("PRAGMA table_info(color_tokens)")
        cols = {row["name"]: row for row in cur.fetchall()}
        for required in (
            "id", "scope", "key", "value", "label",
            "category", "display_order", "updated_at",
        ):
            self.assertIn(required, cols, f"missing column: {required}")

    def test_color_tokens_scope_check_constraint(self) -> None:
        """CHECK(scope IN ('core', 'aq', 'finos', 'corpos'))."""
        with self.assertRaises(Exception):
            self.manager._conn.execute(
                "INSERT INTO color_tokens "
                "(scope, key, value, label, category, display_order, updated_at) "
                "VALUES ('invalid', 'k', 'v', 'l', 'c', 0, 0)"
            )

    def test_color_tokens_unique_scope_key(self) -> None:
        """UNIQUE(scope, key) — aynı çift iki kez insert edilemez."""
        self.manager._conn.execute(
            "INSERT INTO color_tokens "
            "(scope, key, value, label, category, display_order, updated_at) "
            "VALUES ('core', 'border', '#1F242D', 'Kenarlık', 'border', 30, 0)"
        )
        self.manager._conn.commit()
        with self.assertRaises(Exception):
            self.manager._conn.execute(
                "INSERT INTO color_tokens "
                "(scope, key, value, label, category, display_order, updated_at) "
                "VALUES ('core', 'border', '#FFFFFF', 'X', 'border', 0, 0)"
            )
            self.manager._conn.commit()


class GovernanceGuardTests(unittest.TestCase):
    """Modül core anahtarlarını EZEMEZ — application-layer guard."""

    def test_core_allowed_keys_pass(self) -> None:
        for key in CORE_ALLOWED_KEYS:
            assert_governance("core", key)  # raises on failure

    def test_module_allowed_keys_pass(self) -> None:
        for scope in ("aq", "finos", "corpos"):
            for key in MODULE_ALLOWED_KEYS:
                assert_governance(scope, key)

    def test_core_invalid_key_rejected(self) -> None:
        with self.assertRaises(GovernanceViolation) as ctx:
            assert_governance("core", "brand")  # 'brand' is module-only
        self.assertIn("izinsiz", str(ctx.exception).lower())

    def test_module_overriding_core_key_rejected(self) -> None:
        """Asıl governance: modül core-sahipli anahtarı ezemez."""
        # bg_primary core-sahipli — bir modülde geçmesi tamamen yasak.
        for scope in ("aq", "finos", "corpos"):
            with self.assertRaises(GovernanceViolation) as ctx:
                assert_governance(scope, "bg_primary")
            self.assertIn("core-sahipli", str(ctx.exception))

        for scope in ("aq", "finos", "corpos"):
            with self.assertRaises(GovernanceViolation):
                assert_governance(scope, "status_error")

        for scope in ("aq", "finos", "corpos"):
            with self.assertRaises(GovernanceViolation):
                assert_governance(scope, "focus_ring")

    def test_invalid_scope_rejected(self) -> None:
        with self.assertRaises(ValueError):
            assert_governance("invalid", "brand")


class SeedFromFoundationTests(unittest.TestCase):
    """Faz 0 wcag-report.json → DB seed — birebir eşleşme."""

    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._temp_dir.name) / "seed.db"
        bootstrap = IdentityRepository(str(self._db_path))
        bootstrap.close()
        self.manager = MigrationManager(
            str(self._db_path),
            str(REPO_ROOT / "migrations"),
        )
        self.manager.apply_all()
        self.manager.close()
        self.repo = ColorTokenRepository(str(self._db_path))

    def tearDown(self) -> None:
        self.repo.close()
        self._temp_dir.cleanup()

    def test_seed_items_match_wcag_report_core(self) -> None:
        """build_seed_items() core çıktısı wcag-report.json ile birebir."""
        report = json.loads(WCAG_REPORT.read_text(encoding="utf-8"))
        items = build_seed_items(WCAG_REPORT)
        core_items = {item["key"]: item["value"] for item in items if item["scope"] == "core"}

        for key, expected in report["core"].items():
            if key == "theme" or expected is None:
                continue
            self.assertIn(key, core_items, f"core.{key} seed'de yok")
            self.assertEqual(
                core_items[key],
                expected,
                f"core.{key} mismatch: seed={core_items[key]!r} report={expected!r}",
            )

    def test_seed_items_match_wcag_report_modules(self) -> None:
        """Aynı şey 3 modül için."""
        report = json.loads(WCAG_REPORT.read_text(encoding="utf-8"))
        items = build_seed_items(WCAG_REPORT)
        for scope in ("aq", "finos", "corpos"):
            mod_items = {it["key"]: it["value"] for it in items if it["scope"] == scope}
            for key, expected in report["modules"][scope].items():
                if key == "scope" or expected is None:
                    continue
                self.assertIn(key, mod_items, f"{scope}.{key} seed'de yok")
                self.assertEqual(
                    mod_items[key],
                    str(expected),
                    f"{scope}.{key} mismatch",
                )

    def test_seed_into_db_idempotent(self) -> None:
        """seed_color_tokens iki kez çağrılınca aynı toplam satırı verir."""
        count1 = seed_color_tokens(self.repo, foundation_path=WCAG_REPORT)
        rows1 = self.repo.list_tokens()
        count2 = seed_color_tokens(self.repo, foundation_path=WCAG_REPORT)
        rows2 = self.repo.list_tokens()
        self.assertEqual(count1, count2)
        self.assertEqual(len(rows1), len(rows2))
        # Tüm değerler aynı kalmalı (sadece updated_at değişebilir)
        for r1, r2 in zip(rows1, rows2):
            self.assertEqual(r1["scope"], r2["scope"])
            self.assertEqual(r1["key"], r2["key"])
            self.assertEqual(r1["value"], r2["value"])

    def test_db_round_trip_matches_wcag_report(self) -> None:
        """DB'ye seed et, oku, wcag-report.json ile karşılaştır."""
        seed_color_tokens(self.repo, foundation_path=WCAG_REPORT)
        report = json.loads(WCAG_REPORT.read_text(encoding="utf-8"))

        # core
        core_rows = {r["key"]: r["value"] for r in self.repo.list_tokens(scope="core")}
        for key, expected in report["core"].items():
            if key == "theme" or expected is None:
                continue
            self.assertEqual(core_rows[key], expected, f"core.{key} DB mismatch")

        # finos (örnek: CTA = #CD4A00 — Kapı 1)
        finos_rows = {r["key"]: r["value"] for r in self.repo.list_tokens(scope="finos")}
        self.assertEqual(finos_rows["cta"], "#CD4A00")
        self.assertEqual(finos_rows["cta_text"], "#FFFFFF")
        self.assertEqual(finos_rows["link_back"], "#94A3B8")

        # corpos (örnek: accent = slate, teal değil — Kapı 4)
        corpos_rows = {r["key"]: r["value"] for r in self.repo.list_tokens(scope="corpos")}
        self.assertEqual(corpos_rows["accent"], "#475569")


class DesignTokensApiTests(unittest.TestCase):
    """GET /api/v1/design-tokens endpoint — seed sonrası okuma."""

    def setUp(self) -> None:
        from app import create_app
        self.client = TestClient(create_app())

    def test_list_all_scopes(self) -> None:
        resp = self.client.get("/api/v1/design-tokens")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("tokens", data)
        # Foundation kilidi → en az 20 (core) + ~25 (modül toplamı) ≈ 45+
        self.assertGreaterEqual(len(data["tokens"]), 40)
        self.assertIsNotNone(data["seeded_at"], "seed yapılmamış")

    def test_filter_by_scope_finos(self) -> None:
        resp = self.client.get("/api/v1/design-tokens?scope=finos")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(all(t["scope"] == "finos" for t in data["tokens"]))
        # FinOS Kapı 1: CTA orange #CD4A00 mevcut
        ctas = [t for t in data["tokens"] if t["key"] == "cta"]
        self.assertEqual(len(ctas), 1)
        self.assertEqual(ctas[0]["value"], "#CD4A00")

    def test_invalid_scope_rejected(self) -> None:
        resp = self.client.get("/api/v1/design-tokens?scope=invalid")
        # FastAPI Literal-based query param 422 döner; özel 400 handler eklemedik
        self.assertIn(resp.status_code, (400, 422))


if __name__ == "__main__":
    unittest.main()
