"""Design Token Programı — Faz 6 · Custom Fonts backend testleri.

Doğrulamalar:
  * Migration 036 → custom_fonts tablosu doğru şemada.
  * Repository: google/upload create + set_default + delete + list_fonts.
  * URL whitelist (yalnız fonts.googleapis.com + https://).
  * Magic-byte: doğru ön ek → kabul, yanlış ön ek / yanlış format /
    çok büyük dosya → reddedilir.
  * scope başına tek is_default invariant'ı (yeni default eskiyi sıfırlar).
  * API: auth/permission, governance, file serving (cache header).
"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.custom_font_repository import (
    ALLOWED_FONT_CSS_HOSTS,
    MAX_UPLOAD_BYTES,
    CustomFontRepository,
    FontValidationError,
    assert_valid_google_url,
    assert_valid_upload,
)
from app.identity_repository import IdentityRepository
from app.migration_manager import MigrationManager

REPO_ROOT = Path(__file__).resolve().parent.parent


# --- Magic-byte fixtures (minimal geçerli header'lar) ---------------------

def _woff2_bytes(payload_extra: bytes = b"") -> bytes:
    # wOF2 magic + 44-byte header'a kadar dolgu (gerçek WOFF2 değil ama
    # magic kontrolü için yeterli; tablo eklenmez).
    return b"wOF2" + b"\x00" * 44 + payload_extra


def _woff_bytes() -> bytes:
    return b"wOFF" + b"\x00" * 40


def _ttf_bytes() -> bytes:
    # 00 01 00 00 = SFNT version 1.0
    return b"\x00\x01\x00\x00" + b"\x00" * 60


def _otf_bytes() -> bytes:
    return b"OTTO" + b"\x00" * 60


# ============================================================================
# Schema + Pure repo (no app)
# ============================================================================


class CustomFontSchemaTests(unittest.TestCase):
    """Migration 036 → custom_fonts şeması."""

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

    def test_custom_fonts_table_shape(self) -> None:
        cur = self.manager._conn.execute("PRAGMA table_info(custom_fonts)")
        cols = {row["name"] for row in cur.fetchall()}
        for required in (
            "id", "scope", "family", "source", "css_url", "data_b64",
            "format", "weight", "style", "is_default", "created_at",
        ):
            self.assertIn(required, cols, f"eksik kolon: {required}")

    def test_scope_check_constraint(self) -> None:
        with self.assertRaises(Exception):
            self.manager._conn.execute(
                "INSERT INTO custom_fonts (scope, family, source, is_default, created_at) "
                "VALUES ('bogus', 'X', 'google', 0, 0)"
            )

    def test_source_check_constraint(self) -> None:
        with self.assertRaises(Exception):
            self.manager._conn.execute(
                "INSERT INTO custom_fonts (scope, family, source, is_default, created_at) "
                "VALUES ('core', 'X', 'sketchy', 0, 0)"
            )

    def test_unique_scope_family(self) -> None:
        self.manager._conn.execute(
            "INSERT INTO custom_fonts (scope, family, source, is_default, created_at) "
            "VALUES ('finos', 'Inter', 'google', 0, 0)"
        )
        self.manager._conn.commit()
        with self.assertRaises(Exception):
            self.manager._conn.execute(
                "INSERT INTO custom_fonts (scope, family, source, is_default, created_at) "
                "VALUES ('finos', 'Inter', 'google', 0, 0)"
            )
            self.manager._conn.commit()


class FontValidationTests(unittest.TestCase):
    """Pure-function validate'lar — repo'dan bağımsız."""

    def test_google_url_https_only(self) -> None:
        with self.assertRaises(FontValidationError):
            assert_valid_google_url("http://fonts.googleapis.com/css2?family=Inter")

    def test_google_url_host_whitelist(self) -> None:
        with self.assertRaises(FontValidationError):
            assert_valid_google_url("https://evil.com/css2?family=Inter")
        # Yalnız tek host izinli (CSP ile uyumlu).
        for host in ALLOWED_FONT_CSS_HOSTS:
            assert_valid_google_url(f"https://{host}/css2?family=Playfair+Display")

    def test_upload_woff2_ok(self) -> None:
        assert_valid_upload(_woff2_bytes(), "woff2")

    def test_upload_woff_ok(self) -> None:
        assert_valid_upload(_woff_bytes(), "woff")

    def test_upload_ttf_ok(self) -> None:
        assert_valid_upload(_ttf_bytes(), "ttf")

    def test_upload_otf_ok(self) -> None:
        assert_valid_upload(_otf_bytes(), "otf")

    def test_upload_format_whitelist(self) -> None:
        with self.assertRaises(FontValidationError):
            assert_valid_upload(_woff2_bytes(), "pfb")

    def test_upload_magic_byte_mismatch(self) -> None:
        # PNG header — magic yanlış.
        with self.assertRaises(FontValidationError):
            assert_valid_upload(b"\x89PNG\r\n\x1a\n" + b"\x00" * 40, "woff2")

    def test_upload_size_limit(self) -> None:
        big = b"wOF2" + b"\x00" * (MAX_UPLOAD_BYTES + 10)
        with self.assertRaises(FontValidationError):
            assert_valid_upload(big, "woff2")


class CustomFontRepositoryTests(unittest.TestCase):
    """Repo: create/list/set_default/delete + bytes serving."""

    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._temp_dir.name) / "repo.db"
        bootstrap = IdentityRepository(str(self._db_path))
        bootstrap.close()
        MigrationManager(
            str(self._db_path),
            str(REPO_ROOT / "migrations"),
        ).apply_all()
        self.repo = CustomFontRepository(str(self._db_path))

    def tearDown(self) -> None:
        self.repo.close()
        self._temp_dir.cleanup()

    def test_create_google_and_list(self) -> None:
        fid = self.repo.create_google_font(
            scope="finos",
            family="Playfair Display",
            css_url="https://fonts.googleapis.com/css2?family=Playfair+Display&display=swap",
        )
        self.assertGreaterEqual(fid, 1)
        rows = self.repo.list_fonts(scope="finos")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["family"], "Playfair Display")
        self.assertEqual(rows[0]["source"], "google")

    def test_set_default_singleton_per_scope(self) -> None:
        a = self.repo.create_google_font(
            scope="finos",
            family="A Font",
            css_url="https://fonts.googleapis.com/css2?family=A+Font",
            make_default=True,
        )
        b = self.repo.create_google_font(
            scope="finos",
            family="B Font",
            css_url="https://fonts.googleapis.com/css2?family=B+Font",
        )
        # B'yi default yap → A artık default değil
        self.assertTrue(self.repo.set_default(b))
        rows = {r["id"]: r for r in self.repo.list_fonts(scope="finos")}
        self.assertFalse(bool(rows[a]["is_default"]))
        self.assertTrue(bool(rows[b]["is_default"]))

    def test_scope_isolated(self) -> None:
        self.repo.create_google_font(
            scope="finos",
            family="OnlyFinos",
            css_url="https://fonts.googleapis.com/css2?family=OnlyFinos",
        )
        self.assertEqual(len(self.repo.list_fonts(scope="finos")), 1)
        self.assertEqual(len(self.repo.list_fonts(scope="corpos")), 0)

    def test_upload_and_serve_bytes(self) -> None:
        data = _woff2_bytes()
        fid = self.repo.create_upload_font(
            scope="corpos",
            family="MyDisplay",
            data=data,
            fmt="woff2",
        )
        served = self.repo.get_font_bytes(fid)
        self.assertIsNotNone(served)
        assert served is not None
        bytes_out, fmt_out = served
        self.assertEqual(bytes_out, data)
        self.assertEqual(fmt_out, "woff2")

    def test_get_font_bytes_not_upload_returns_none(self) -> None:
        fid = self.repo.create_google_font(
            scope="aq",
            family="GoogleOne",
            css_url="https://fonts.googleapis.com/css2?family=GoogleOne",
        )
        self.assertIsNone(self.repo.get_font_bytes(fid))

    def test_delete_font(self) -> None:
        fid = self.repo.create_google_font(
            scope="aq",
            family="ToDelete",
            css_url="https://fonts.googleapis.com/css2?family=ToDelete",
        )
        self.assertTrue(self.repo.delete_font(fid))
        self.assertFalse(self.repo.delete_font(fid))
        self.assertEqual(len(self.repo.list_fonts(scope="aq")), 0)


# ============================================================================
# API tests (uvicorn ile değil, TestClient ile create_app üzerinden)
# ============================================================================


class CustomFontApiTests(unittest.TestCase):
    """REST uçları — auth/permission + governance + serving."""

    def setUp(self) -> None:
        from app import create_app

        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._temp_dir.name) / "api.db"
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
        os.environ["AQ_JWT_SECRET"] = "faz6-fonts-secret"
        os.environ["AQ_ENV"] = "development"

        self.client = TestClient(create_app())

    def tearDown(self) -> None:
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

    def _h(self, t: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {t}"}

    # ---- list (public) ----

    def test_list_is_public(self) -> None:
        resp = self.client.get("/api/v1/fonts")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("fonts", resp.json())

    # ---- google: auth + whitelist ----

    def test_google_create_requires_auth(self) -> None:
        resp = self.client.post(
            "/api/v1/fonts/google",
            json={
                "scope": "finos",
                "family": "Inter",
                "css_url": "https://fonts.googleapis.com/css2?family=Inter",
            },
        )
        self.assertEqual(resp.status_code, 401)

    def test_google_create_requires_manage_permission(self) -> None:
        token = self._manager_token()
        resp = self.client.post(
            "/api/v1/fonts/google",
            headers=self._h(token),
            json={
                "scope": "finos",
                "family": "Inter",
                "css_url": "https://fonts.googleapis.com/css2?family=Inter",
            },
        )
        self.assertEqual(resp.status_code, 403)

    def test_google_create_rejects_non_https(self) -> None:
        token = self._admin_token()
        resp = self.client.post(
            "/api/v1/fonts/google",
            headers=self._h(token),
            json={
                "scope": "finos",
                "family": "Inter",
                "css_url": "http://fonts.googleapis.com/css2?family=Inter",
            },
        )
        self.assertEqual(resp.status_code, 422)

    def test_google_create_rejects_unknown_host(self) -> None:
        token = self._admin_token()
        resp = self.client.post(
            "/api/v1/fonts/google",
            headers=self._h(token),
            json={
                "scope": "finos",
                "family": "Inter",
                "css_url": "https://evil.com/css2?family=Inter",
            },
        )
        self.assertEqual(resp.status_code, 422)

    def test_google_create_happy_path(self) -> None:
        token = self._admin_token()
        resp = self.client.post(
            "/api/v1/fonts/google",
            headers=self._h(token),
            json={
                "scope": "finos",
                "family": "Playfair Display",
                "css_url": (
                    "https://fonts.googleapis.com/css2?family=Playfair+Display"
                    "&display=swap"
                ),
                "make_default": True,
            },
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertGreaterEqual(body["id"], 1)
        self.assertEqual(body["family"], "Playfair Display")
        self.assertTrue(body["is_default"])

        listing = self.client.get("/api/v1/fonts?scope=finos").json()
        self.assertEqual(len(listing["fonts"]), 1)
        self.assertTrue(listing["fonts"][0]["is_default"])

    # ---- upload: auth + magic-byte ----

    def test_upload_requires_auth(self) -> None:
        resp = self.client.post(
            "/api/v1/fonts/upload",
            data={"scope": "corpos", "family": "MyDisplay", "format": "woff2"},
            files={"file": ("x.woff2", _woff2_bytes(), "application/octet-stream")},
        )
        self.assertEqual(resp.status_code, 401)

    def test_upload_rejects_bad_magic_byte(self) -> None:
        token = self._admin_token()
        # PNG bayts declared as woff2
        resp = self.client.post(
            "/api/v1/fonts/upload",
            headers=self._h(token),
            data={"scope": "corpos", "family": "MyDisplay", "format": "woff2"},
            files={"file": ("x.woff2", b"\x89PNG\r\n\x1a\n" + b"\x00" * 40, "application/octet-stream")},
        )
        self.assertEqual(resp.status_code, 422)
        self.assertIn("magic", resp.json()["detail"].lower())

    def test_upload_rejects_format_outside_whitelist(self) -> None:
        token = self._admin_token()
        resp = self.client.post(
            "/api/v1/fonts/upload",
            headers=self._h(token),
            data={"scope": "corpos", "family": "X", "format": "pfb"},
            files={"file": ("x.pfb", b"BLOB" + b"\x00" * 40, "application/octet-stream")},
        )
        self.assertEqual(resp.status_code, 422)

    def test_upload_happy_path_and_serve_bytes(self) -> None:
        token = self._admin_token()
        resp = self.client.post(
            "/api/v1/fonts/upload",
            headers=self._h(token),
            data={"scope": "corpos", "family": "MyDisplay", "format": "woff2"},
            files={"file": ("x.woff2", _woff2_bytes(), "application/octet-stream")},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        fid = resp.json()["id"]
        # /file ucu public + cache header
        file_resp = self.client.get(f"/api/v1/fonts/{fid}/file")
        self.assertEqual(file_resp.status_code, 200)
        self.assertIn("immutable", file_resp.headers.get("cache-control", ""))
        self.assertEqual(file_resp.headers.get("content-type"), "font/woff2")
        self.assertTrue(file_resp.content.startswith(b"wOF2"))

    def test_file_404_on_unknown(self) -> None:
        resp = self.client.get("/api/v1/fonts/99999/file")
        self.assertEqual(resp.status_code, 404)

    def test_set_default_and_delete(self) -> None:
        token = self._admin_token()
        a = self.client.post(
            "/api/v1/fonts/google",
            headers=self._h(token),
            json={
                "scope": "aq",
                "family": "FontA",
                "css_url": "https://fonts.googleapis.com/css2?family=FontA",
                "make_default": True,
            },
        ).json()
        b = self.client.post(
            "/api/v1/fonts/google",
            headers=self._h(token),
            json={
                "scope": "aq",
                "family": "FontB",
                "css_url": "https://fonts.googleapis.com/css2?family=FontB",
            },
        ).json()

        # B'yi default yap
        resp = self.client.post(
            f"/api/v1/fonts/{b['id']}/default",
            headers=self._h(token),
        )
        self.assertEqual(resp.status_code, 200)

        listing = self.client.get("/api/v1/fonts?scope=aq").json()
        by_id = {r["id"]: r for r in listing["fonts"]}
        self.assertFalse(by_id[a["id"]]["is_default"])
        self.assertTrue(by_id[b["id"]]["is_default"])

        # B'yi sil
        resp = self.client.delete(
            f"/api/v1/fonts/{b['id']}", headers=self._h(token)
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["deleted"])

    def test_delete_requires_auth(self) -> None:
        resp = self.client.delete("/api/v1/fonts/1")
        self.assertEqual(resp.status_code, 401)


if __name__ == "__main__":
    unittest.main()
