"""Design Token Programı — Faz 6 · CustomFont repository.

Sorumluluklar:
    * `custom_fonts` tablosuna CRUD (panel'den yükle/sil/varsayılan-ata).
    * **Magic-byte doğrulama** (upload kaynağı için) — uzantı + boyut + sihir.
    * **URL whitelist** (google kaynağı için) — yalnız https + Google Fonts host.
    * Scope başına tek `is_default` (atanırken diğerleri sıfırlanır).

Renk sisteminin defansını birebir taklit eder — modüller core'u ezemez
ilkesi font tarafında scope ekseninde uygulanır (panel UI'da scope seçilir;
bir scope'a yazılan kayıt başka scope'u etkilemez).
"""

from __future__ import annotations

import base64
import sqlite3
import time
from pathlib import Path
from threading import Lock
from typing import Any, Literal
from urllib.parse import urlparse

Scope = Literal["core", "aq", "finos", "corpos"]
VALID_SCOPES: tuple[Scope, ...] = ("core", "aq", "finos", "corpos")
VALID_SOURCES: tuple[str, ...] = ("google", "upload")

# Yalnız Google Fonts host'larına izin (CSP ile uyumlu).
ALLOWED_FONT_CSS_HOSTS: frozenset[str] = frozenset({"fonts.googleapis.com"})

# Upload kabul limitleri.
MAX_UPLOAD_BYTES: int = 1_500_000  # ~1.5 MB; tipik woff2 < 200 KB
ALLOWED_UPLOAD_FORMATS: frozenset[str] = frozenset({"woff2", "woff", "ttf", "otf"})

# format → magic-byte ön ek tablosu.
_MAGIC_BYTES: dict[str, tuple[bytes, ...]] = {
    "woff2": (b"wOF2",),
    "woff":  (b"wOFF",),
    "ttf":   (b"\x00\x01\x00\x00", b"true"),
    "otf":   (b"OTTO",),
}


class FontValidationError(ValueError):
    """Kaynak (URL veya bytes) panel sözleşmesini ihlal ediyor."""


def assert_valid_google_url(css_url: str) -> None:
    """Google Fonts CSS URL'sini güvenli liste'ye karşı doğrula."""
    if not isinstance(css_url, str) or not css_url:
        raise FontValidationError("css_url boş")
    parsed = urlparse(css_url)
    if parsed.scheme != "https":
        raise FontValidationError("css_url yalnız https:// olabilir")
    if parsed.hostname not in ALLOWED_FONT_CSS_HOSTS:
        raise FontValidationError(
            f"css_url yalnız izinli host'lardan olabilir: {sorted(ALLOWED_FONT_CSS_HOSTS)}"
        )


def assert_valid_upload(data: bytes, declared_format: str) -> None:
    """Upload baytlarını magic-byte + boyut + format ile doğrula."""
    if not isinstance(data, (bytes, bytearray)):
        raise FontValidationError("upload verisi byte değil")
    fmt = declared_format.lower().strip()
    if fmt not in ALLOWED_UPLOAD_FORMATS:
        raise FontValidationError(
            f"izinsiz format: {fmt!r}. İzinli: {sorted(ALLOWED_UPLOAD_FORMATS)}"
        )
    if len(data) > MAX_UPLOAD_BYTES:
        raise FontValidationError(
            f"upload çok büyük: {len(data)} bayt (limit {MAX_UPLOAD_BYTES})"
        )
    prefixes = _MAGIC_BYTES.get(fmt, ())
    if not any(bytes(data).startswith(p) for p in prefixes):
        raise FontValidationError(
            f"magic-byte {fmt!r} format'ıyla uyuşmuyor (beklenen ön ek: {prefixes})"
        )


class CustomFontRepository:
    """custom_fonts tablosu için thread-safe CRUD."""

    def __init__(self, database_path: str) -> None:
        self._lock = Lock()
        self._conn = self._connect(database_path)

    @staticmethod
    def _connect(database_path: str) -> sqlite3.Connection:
        path = Path(database_path)
        if path.parent and str(path.parent) != ".":
            path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def close(self) -> None:
        self._conn.close()

    # ---- read ----

    def list_fonts(self, scope: str | None = None) -> list[dict[str, Any]]:
        """Tüm fontları (veya scope filtreli) döndür — data_b64 dahil edilmez (liste hafif)."""
        if scope is not None and scope not in VALID_SCOPES:
            raise ValueError(f"Geçersiz scope: {scope!r}")
        with self._lock:
            if scope is not None:
                cur = self._conn.execute(
                    """
                    SELECT id, scope, family, source, css_url, format, weight, style,
                           is_default, created_at
                    FROM custom_fonts
                    WHERE scope = ?
                    ORDER BY is_default DESC, created_at DESC, id DESC
                    """,
                    (scope,),
                )
            else:
                cur = self._conn.execute(
                    """
                    SELECT id, scope, family, source, css_url, format, weight, style,
                           is_default, created_at
                    FROM custom_fonts
                    ORDER BY scope, is_default DESC, created_at DESC, id DESC
                    """
                )
            return [dict(row) for row in cur.fetchall()]

    def get_font(self, font_id: int) -> dict[str, Any] | None:
        """Tek font kaydı — bayt indirme için data_b64 dahil."""
        with self._lock:
            row = self._conn.execute(
                """
                SELECT id, scope, family, source, css_url, data_b64, format,
                       weight, style, is_default, created_at
                FROM custom_fonts
                WHERE id = ?
                """,
                (font_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    # ---- write ----

    def create_google_font(
        self,
        scope: str,
        family: str,
        css_url: str,
        weight: str | None = None,
        style: str | None = None,
        make_default: bool = False,
    ) -> int:
        if scope not in VALID_SCOPES:
            raise ValueError(f"Geçersiz scope: {scope!r}")
        if not family.strip():
            raise FontValidationError("family boş")
        assert_valid_google_url(css_url)
        now = int(time.time())
        with self._lock:
            if make_default:
                self._conn.execute(
                    "UPDATE custom_fonts SET is_default = 0 WHERE scope = ?",
                    (scope,),
                )
            cur = self._conn.execute(
                """
                INSERT INTO custom_fonts
                  (scope, family, source, css_url, data_b64, format, weight, style,
                   is_default, created_at)
                VALUES (?, ?, 'google', ?, NULL, NULL, ?, ?, ?, ?)
                """,
                (
                    scope,
                    family.strip(),
                    css_url,
                    weight,
                    style,
                    1 if make_default else 0,
                    now,
                ),
            )
            self._conn.commit()
            return int(cur.lastrowid or 0)

    def create_upload_font(
        self,
        scope: str,
        family: str,
        data: bytes,
        fmt: str,
        weight: str | None = None,
        style: str | None = None,
        make_default: bool = False,
    ) -> int:
        if scope not in VALID_SCOPES:
            raise ValueError(f"Geçersiz scope: {scope!r}")
        if not family.strip():
            raise FontValidationError("family boş")
        assert_valid_upload(data, fmt)
        b64 = base64.b64encode(bytes(data)).decode("ascii")
        now = int(time.time())
        with self._lock:
            if make_default:
                self._conn.execute(
                    "UPDATE custom_fonts SET is_default = 0 WHERE scope = ?",
                    (scope,),
                )
            cur = self._conn.execute(
                """
                INSERT INTO custom_fonts
                  (scope, family, source, css_url, data_b64, format, weight, style,
                   is_default, created_at)
                VALUES (?, ?, 'upload', NULL, ?, ?, ?, ?, ?, ?)
                """,
                (
                    scope,
                    family.strip(),
                    b64,
                    fmt.lower().strip(),
                    weight,
                    style,
                    1 if make_default else 0,
                    now,
                ),
            )
            self._conn.commit()
            return int(cur.lastrowid or 0)

    def set_default(self, font_id: int) -> bool:
        """Bir fontu scope'unda 'varsayılan' yap (diğerlerini sıfırla).

        Dönüş: True if updated, False if font not found.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT scope FROM custom_fonts WHERE id = ?",
                (font_id,),
            ).fetchone()
            if row is None:
                return False
            self._conn.execute(
                "UPDATE custom_fonts SET is_default = 0 WHERE scope = ?",
                (row["scope"],),
            )
            self._conn.execute(
                "UPDATE custom_fonts SET is_default = 1 WHERE id = ?",
                (font_id,),
            )
            self._conn.commit()
            return True

    def delete_font(self, font_id: int) -> bool:
        """Tek fontu sil. Dönüş: True if deleted, False if not found."""
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM custom_fonts WHERE id = ?",
                (font_id,),
            )
            self._conn.commit()
            return cur.rowcount > 0

    def get_font_bytes(self, font_id: int) -> tuple[bytes, str] | None:
        """Upload'lu fontun ham baytları + format döndür (CDN için).

        Dönüş: (bytes, format) veya None (font yoksa / upload değilse).
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT data_b64, format, source FROM custom_fonts WHERE id = ?",
                (font_id,),
            ).fetchone()
        if row is None or row["source"] != "upload" or not row["data_b64"]:
            return None
        try:
            data = base64.b64decode(str(row["data_b64"]))
        except (ValueError, TypeError):
            return None
        return data, str(row["format"] or "")
