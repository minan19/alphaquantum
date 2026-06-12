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


class DesignTokensPatchTests(unittest.TestCase):
    """Faz 4: PATCH/reset uçları — governance + auth + write-cycle."""

    def setUp(self) -> None:
        import os
        from app import create_app

        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._temp_dir.name) / "patch_test.db"
        self._original_env = {
            "AQ_DATABASE_PATH": os.getenv("AQ_DATABASE_PATH"),
            "AQ_AUTH_USERS": os.getenv("AQ_AUTH_USERS"),
            "AQ_ENABLE_DEMO_USERS": os.getenv("AQ_ENABLE_DEMO_USERS"),
            "AQ_JWT_SECRET": os.getenv("AQ_JWT_SECRET"),
            "AQ_ENV": os.getenv("AQ_ENV"),
        }
        os.environ["AQ_DATABASE_PATH"] = str(self._db_path)
        os.environ["AQ_AUTH_USERS"] = (
            "admin:admin12345:admin,manager:manager12345:manager"
        )
        os.environ["AQ_ENABLE_DEMO_USERS"] = "false"
        os.environ["AQ_JWT_SECRET"] = "faz4-test-secret"
        os.environ["AQ_ENV"] = "development"

        self.client = TestClient(create_app())

    def tearDown(self) -> None:
        import os
        self.client.close()
        for k, v in self._original_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self._temp_dir.cleanup()

    def _admin_token(self) -> str:
        resp = self.client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin12345"},
        )
        self.assertEqual(resp.status_code, 200)
        return str(resp.json()["access_token"])

    def _manager_token(self) -> str:
        resp = self.client.post(
            "/api/v1/auth/login",
            json={"username": "manager", "password": "manager12345"},
        )
        self.assertEqual(resp.status_code, 200)
        return str(resp.json()["access_token"])

    # ---- AUTH ----

    def test_patch_requires_auth(self) -> None:
        resp = self.client.patch(
            "/api/v1/design-tokens",
            json={"scope": "finos", "changes": {"cta": "#AABBCC"}},
        )
        self.assertEqual(resp.status_code, 401)

    def test_patch_requires_manage_permission(self) -> None:
        """Manager rolünde manage_design_tokens YOK — 403 dönmeli."""
        token = self._manager_token()
        resp = self.client.patch(
            "/api/v1/design-tokens",
            headers={"Authorization": f"Bearer {token}"},
            json={"scope": "finos", "changes": {"cta": "#AABBCC"}},
        )
        self.assertEqual(resp.status_code, 403)

    def test_reset_requires_auth(self) -> None:
        resp = self.client.post(
            "/api/v1/design-tokens/reset",
            json={"scope": "finos"},
        )
        self.assertEqual(resp.status_code, 401)

    # ---- GOVERNANCE (API'de zorlanır) ----

    def test_patch_module_cannot_override_core_key(self) -> None:
        """Modül scope'unda core-sahipli key → 422 (governance)."""
        token = self._admin_token()
        for scope in ("aq", "finos", "corpos"):
            for core_key in ("bg_primary", "status_error", "focus_ring"):
                resp = self.client.patch(
                    "/api/v1/design-tokens",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"scope": scope, "changes": {core_key: "#AABBCC"}},
                )
                self.assertEqual(
                    resp.status_code, 422,
                    f"{scope}.{core_key} reddedilmeliydi",
                )
                self.assertIn("core-sahipli", resp.json()["detail"])

    def test_patch_unknown_key_rejected(self) -> None:
        """Bilinmeyen key → 422."""
        token = self._admin_token()
        resp = self.client.patch(
            "/api/v1/design-tokens",
            headers={"Authorization": f"Bearer {token}"},
            json={"scope": "finos", "changes": {"made_up_key": "#FFFFFF"}},
        )
        self.assertEqual(resp.status_code, 422)

    def test_patch_invalid_hex_rejected(self) -> None:
        """Geçersiz renk değeri → 422."""
        token = self._admin_token()
        for bad in ("not-a-hex", "#XYZ123", "rgb(1,2,3)", "#FFF"):
            resp = self.client.patch(
                "/api/v1/design-tokens",
                headers={"Authorization": f"Bearer {token}"},
                json={"scope": "finos", "changes": {"cta": bad}},
            )
            self.assertEqual(resp.status_code, 422, f"'{bad}' reddedilmeliydi")

    # ---- HAPPY PATH ----

    def test_patch_finos_cta_then_read_back(self) -> None:
        """Yazma → okuma zinciri çalışıyor."""
        token = self._admin_token()
        resp = self.client.patch(
            "/api/v1/design-tokens",
            headers={"Authorization": f"Bearer {token}"},
            json={"scope": "finos", "changes": {"cta": "#FF8800"}},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["updated_count"], 1)
        self.assertIn("cta", body["updated"])

        # Okumayla doğrula
        read = self.client.get("/api/v1/design-tokens?scope=finos")
        self.assertEqual(read.status_code, 200)
        tokens = {t["key"]: t["value"] for t in read.json()["tokens"]}
        self.assertEqual(tokens["cta"], "#FF8800")

    def test_patch_multiple_keys(self) -> None:
        """Birden fazla key tek atomik update."""
        token = self._admin_token()
        resp = self.client.patch(
            "/api/v1/design-tokens",
            headers={"Authorization": f"Bearer {token}"},
            json={"scope": "finos", "changes": {"cta": "#112233", "brand": "#445566"}},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["updated_count"], 2)
        self.assertEqual(set(body["updated"]), {"cta", "brand"})

    def test_patch_partial_governance_violation_atomic_reject(self) -> None:
        """Bir değişiklikte governance ihlali varsa hiçbiri yazılmamalı."""
        token = self._admin_token()
        # Önce mevcut değeri sakla
        before = self.client.get("/api/v1/design-tokens?scope=finos").json()
        before_cta = {t["key"]: t["value"] for t in before["tokens"]}["cta"]

        # cta (legal) + bg_primary (governance violation) birlikte gönder
        resp = self.client.patch(
            "/api/v1/design-tokens",
            headers={"Authorization": f"Bearer {token}"},
            json={"scope": "finos", "changes": {
                "cta": "#DEADBE",
                "bg_primary": "#000000",
            }},
        )
        self.assertEqual(resp.status_code, 422)

        # cta DEĞİŞMEDİĞİNİ doğrula (atomic)
        after = self.client.get("/api/v1/design-tokens?scope=finos").json()
        after_cta = {t["key"]: t["value"] for t in after["tokens"]}["cta"]
        self.assertEqual(before_cta, after_cta, "Atomic update bozuldu")

    # ---- RESET ----

    def test_reset_restores_finos_cta_to_kapi_1_value(self) -> None:
        """Reset finos scope → cta tekrar #CD4A00 (Kapı 1 değeri)."""
        token = self._admin_token()
        # Önce değiştir
        self.client.patch(
            "/api/v1/design-tokens",
            headers={"Authorization": f"Bearer {token}"},
            json={"scope": "finos", "changes": {"cta": "#000000"}},
        )

        # Reset
        resp = self.client.post(
            "/api/v1/design-tokens/reset",
            headers={"Authorization": f"Bearer {token}"},
            json={"scope": "finos"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertGreater(body["inserted"], 0)

        # Doğrula
        read = self.client.get("/api/v1/design-tokens?scope=finos").json()
        tokens = {t["key"]: t["value"] for t in read["tokens"]}
        self.assertEqual(tokens["cta"], "#CD4A00", "Kapı 1 değeri restore edilmedi")
        self.assertEqual(tokens["link_back"], "#94A3B8", "Kapı 2 değeri restore edilmedi")

    def test_reset_other_scope_isolated(self) -> None:
        """finos reset edilince corpos değişmemeli (scope izolasyonu)."""
        token = self._admin_token()
        # corpos.cta değiştir
        self.client.patch(
            "/api/v1/design-tokens",
            headers={"Authorization": f"Bearer {token}"},
            json={"scope": "corpos", "changes": {"cta": "#ABCDEF"}},
        )
        # finos reset
        self.client.post(
            "/api/v1/design-tokens/reset",
            headers={"Authorization": f"Bearer {token}"},
            json={"scope": "finos"},
        )
        # corpos.cta hâlâ #ABCDEF olmalı
        corpos = self.client.get("/api/v1/design-tokens?scope=corpos").json()
        ctas = {t["key"]: t["value"] for t in corpos["tokens"]}
        self.assertEqual(ctas["cta"], "#ABCDEF")


# ---------------------------------------------------------------------------
# Faz 5 — Snapshot/Restore zinciri
# ---------------------------------------------------------------------------


class DesignTokensSnapshotTests(unittest.TestCase):
    """Faz 5: snapshot zinciri — pre-save hook + list/restore + retention."""

    def setUp(self) -> None:
        import os
        from app import create_app

        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._temp_dir.name) / "snapshot_test.db"
        self._original_env = {
            "AQ_DATABASE_PATH": os.getenv("AQ_DATABASE_PATH"),
            "AQ_AUTH_USERS": os.getenv("AQ_AUTH_USERS"),
            "AQ_ENABLE_DEMO_USERS": os.getenv("AQ_ENABLE_DEMO_USERS"),
            "AQ_JWT_SECRET": os.getenv("AQ_JWT_SECRET"),
            "AQ_ENV": os.getenv("AQ_ENV"),
        }
        os.environ["AQ_DATABASE_PATH"] = str(self._db_path)
        os.environ["AQ_AUTH_USERS"] = (
            "admin:admin12345:admin,manager:manager12345:manager"
        )
        os.environ["AQ_ENABLE_DEMO_USERS"] = "false"
        os.environ["AQ_JWT_SECRET"] = "faz5-test-secret"
        os.environ["AQ_ENV"] = "development"

        self.client = TestClient(create_app())

    def tearDown(self) -> None:
        import os
        self.client.close()
        for k, v in self._original_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self._temp_dir.cleanup()

    def _admin_token(self) -> str:
        resp = self.client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin12345"},
        )
        self.assertEqual(resp.status_code, 200)
        return str(resp.json()["access_token"])

    def _manager_token(self) -> str:
        resp = self.client.post(
            "/api/v1/auth/login",
            json={"username": "manager", "password": "manager12345"},
        )
        self.assertEqual(resp.status_code, 200)
        return str(resp.json()["access_token"])

    def _h(self, token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    # ---- AUTH/permissions ----

    def test_snapshots_list_requires_auth(self) -> None:
        resp = self.client.get("/api/v1/design-tokens/snapshots?scope=finos")
        self.assertEqual(resp.status_code, 401)

    def test_snapshots_list_requires_manage_permission(self) -> None:
        token = self._manager_token()
        resp = self.client.get(
            "/api/v1/design-tokens/snapshots?scope=finos",
            headers=self._h(token),
        )
        self.assertEqual(resp.status_code, 403)

    def test_manual_snapshot_requires_auth(self) -> None:
        resp = self.client.post(
            "/api/v1/design-tokens/snapshot",
            json={"scope": "finos", "label": "v1"},
        )
        self.assertEqual(resp.status_code, 401)

    def test_restore_requires_auth(self) -> None:
        resp = self.client.post(
            "/api/v1/design-tokens/restore",
            json={"snapshot_id": 1},
        )
        self.assertEqual(resp.status_code, 401)

    # ---- pre_save hook ----

    def test_patch_creates_pre_save_snapshot(self) -> None:
        """Her PATCH öncesi otomatik pre_save snapshot yazılır."""
        token = self._admin_token()
        # Önce 0 snapshot
        snaps = self.client.get(
            "/api/v1/design-tokens/snapshots?scope=finos",
            headers=self._h(token),
        ).json()
        self.assertEqual(len(snaps["snapshots"]), 0)

        # PATCH
        self.client.patch(
            "/api/v1/design-tokens",
            headers=self._h(token),
            json={"scope": "finos", "changes": {"cta": "#112233"}},
        )

        # 1 pre_save snapshot olmalı
        snaps = self.client.get(
            "/api/v1/design-tokens/snapshots?scope=finos",
            headers=self._h(token),
        ).json()
        self.assertEqual(len(snaps["snapshots"]), 1)
        self.assertEqual(snaps["snapshots"][0]["source"], "pre_save")

    def test_patch_failure_does_not_create_snapshot(self) -> None:
        """Validation hatası varsa snapshot da YAZILMAMALI (early-fail)."""
        token = self._admin_token()
        # Governance violation
        self.client.patch(
            "/api/v1/design-tokens",
            headers=self._h(token),
            json={"scope": "finos", "changes": {"bg_primary": "#000000"}},
        )
        snaps = self.client.get(
            "/api/v1/design-tokens/snapshots?scope=finos",
            headers=self._h(token),
        ).json()
        self.assertEqual(
            len(snaps["snapshots"]), 0,
            "Validation hatasında pre_save snapshot oluşmamalıydı",
        )

    # ---- pre_reset hook ----

    def test_reset_creates_pre_reset_snapshot(self) -> None:
        """Fabrika reset öncesi pre_reset snapshot."""
        token = self._admin_token()
        # Önce bir değişiklik yap (snapshot 1 = pre_save)
        self.client.patch(
            "/api/v1/design-tokens",
            headers=self._h(token),
            json={"scope": "finos", "changes": {"cta": "#000000"}},
        )
        # Reset (snapshot 2 = pre_reset)
        self.client.post(
            "/api/v1/design-tokens/reset",
            headers=self._h(token),
            json={"scope": "finos"},
        )

        snaps = self.client.get(
            "/api/v1/design-tokens/snapshots?scope=finos",
            headers=self._h(token),
        ).json()
        sources = [s["source"] for s in snaps["snapshots"]]
        self.assertIn("pre_reset", sources)
        self.assertIn("pre_save", sources)

    # ---- manual snapshot ----

    def test_manual_snapshot_create_and_list(self) -> None:
        token = self._admin_token()
        resp = self.client.post(
            "/api/v1/design-tokens/snapshot",
            headers=self._h(token),
            json={"scope": "finos", "label": "Versiyonum 1.0"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertGreaterEqual(body["snapshot_id"], 1)
        self.assertEqual(body["scope"], "finos")
        self.assertEqual(body["label"], "Versiyonum 1.0")

        snaps = self.client.get(
            "/api/v1/design-tokens/snapshots?scope=finos",
            headers=self._h(token),
        ).json()
        self.assertEqual(len(snaps["snapshots"]), 1)
        self.assertEqual(snaps["snapshots"][0]["source"], "manual")
        self.assertEqual(snaps["snapshots"][0]["label"], "Versiyonum 1.0")

    # ---- restore ----

    def test_restore_round_trip(self) -> None:
        """Snapshot al → değiştir → restore → ilk değere döner."""
        token = self._admin_token()
        # Başlangıç değeri (Kapı 1)
        before = self.client.get("/api/v1/design-tokens?scope=finos").json()
        initial_cta = {t["key"]: t["value"] for t in before["tokens"]}["cta"]

        # Manuel snapshot al
        snap = self.client.post(
            "/api/v1/design-tokens/snapshot",
            headers=self._h(token),
            json={"scope": "finos", "label": "Başlangıç"},
        ).json()
        snap_id = snap["snapshot_id"]

        # Değiştir
        self.client.patch(
            "/api/v1/design-tokens",
            headers=self._h(token),
            json={"scope": "finos", "changes": {"cta": "#AABBCC"}},
        )
        # Restore
        restore = self.client.post(
            "/api/v1/design-tokens/restore",
            headers=self._h(token),
            json={"snapshot_id": snap_id},
        )
        self.assertEqual(restore.status_code, 200)
        body = restore.json()
        self.assertEqual(body["snapshot_id"], snap_id)
        self.assertGreater(body["restored_count"], 0)
        self.assertGreaterEqual(body["pre_restore_snapshot_id"], 1)

        # Değer geri dönmeli
        after = self.client.get("/api/v1/design-tokens?scope=finos").json()
        ctas = {t["key"]: t["value"] for t in after["tokens"]}
        self.assertEqual(ctas["cta"], initial_cta, "Restore başarısız — değer geri gelmedi")

    def test_restore_invalid_snapshot_404(self) -> None:
        token = self._admin_token()
        resp = self.client.post(
            "/api/v1/design-tokens/restore",
            headers=self._h(token),
            json={"snapshot_id": 999999},
        )
        self.assertEqual(resp.status_code, 404)

    def test_restore_chain_is_reversible(self) -> None:
        """Restore'un kendisi de snapshot bırakır → undo zincirine 'redo' eklenir."""
        token = self._admin_token()
        # v1 snap'ı al (orijinal seed)
        v1 = self.client.post(
            "/api/v1/design-tokens/snapshot",
            headers=self._h(token),
            json={"scope": "finos", "label": "v1"},
        ).json()

        # Değiştir + v2 snap
        self.client.patch(
            "/api/v1/design-tokens",
            headers=self._h(token),
            json={"scope": "finos", "changes": {"cta": "#001122"}},
        )
        v2 = self.client.post(
            "/api/v1/design-tokens/snapshot",
            headers=self._h(token),
            json={"scope": "finos", "label": "v2"},
        ).json()

        # v1'e geri dön
        self.client.post(
            "/api/v1/design-tokens/restore",
            headers=self._h(token),
            json={"snapshot_id": v1["snapshot_id"]},
        )
        # v2'ye tekrar git
        self.client.post(
            "/api/v1/design-tokens/restore",
            headers=self._h(token),
            json={"snapshot_id": v2["snapshot_id"]},
        )
        # cta v2'deki değere geri dönmeli
        after = self.client.get("/api/v1/design-tokens?scope=finos").json()
        ctas = {t["key"]: t["value"] for t in after["tokens"]}
        self.assertEqual(ctas["cta"], "#001122")

    # ---- retention ----

    def test_snapshot_retention_cap(self) -> None:
        """Scope başına en fazla 20 snapshot tutulur (en eski silinir)."""
        from app.color_token_repository import ColorTokenRepository

        token = self._admin_token()
        # 25 PATCH → 25 pre_save snapshot ama 20'yi geçmemeli
        for i in range(25):
            self.client.patch(
                "/api/v1/design-tokens",
                headers=self._h(token),
                json={"scope": "finos", "changes": {"cta": f"#{i:06X}"}},
            )

        snaps = self.client.get(
            "/api/v1/design-tokens/snapshots?scope=finos&limit=100",
            headers=self._h(token),
        ).json()
        self.assertLessEqual(
            len(snaps["snapshots"]), ColorTokenRepository.SNAPSHOT_RETENTION,
            "Retention çalışmıyor — 20'den fazla snapshot tutuluyor",
        )

    # ---- governance ----

    def test_snapshot_governance_invalid_scope(self) -> None:
        token = self._admin_token()
        resp = self.client.post(
            "/api/v1/design-tokens/snapshot",
            headers=self._h(token),
            json={"scope": "bogus", "label": "x"},
        )
        # Pydantic Literal → 422
        self.assertEqual(resp.status_code, 422)

    def test_snapshot_isolated_per_scope(self) -> None:
        """finos snapshot'ları corpos listesinde görünmemeli."""
        token = self._admin_token()
        self.client.post(
            "/api/v1/design-tokens/snapshot",
            headers=self._h(token),
            json={"scope": "finos", "label": "yalnız-finos"},
        )
        corpos_list = self.client.get(
            "/api/v1/design-tokens/snapshots?scope=corpos",
            headers=self._h(token),
        ).json()
        self.assertEqual(len(corpos_list["snapshots"]), 0)


if __name__ == "__main__":
    unittest.main()
