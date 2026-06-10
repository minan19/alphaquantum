"""Design Token Programı — Faz 1 · ColorToken repository.

Sorumluluklar:
    * `color_tokens` tablosuna CRUD (read + idempotent upsert).
    * **Governance guard** — modüller core-sahipli anahtarları EZEMEZ.
      Bu kural sql DDL constraint'iyle değil, application-layer whitelist'le
      uygulanır (token kümesi zamanla evrilir; constraint mokratlaştırma kıvrak değil).
    * Seed yardımcısı: `docs/design-tokens/wcag-report.json` → tablo.

Faz 2'de bu repo'ya yazma ucu (panel) eklenmez; o iş Faz 4'tedir. Şu an yalnız
seed + okuma.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from threading import Lock
from typing import Literal

# ----------------------------------------------------------------------------
# Governance: scope × izinli anahtar matrisi
# ----------------------------------------------------------------------------

Scope = Literal["core", "aq", "finos", "corpos"]
VALID_SCOPES: tuple[Scope, ...] = ("core", "aq", "finos", "corpos")

# `core` scope'unda izinli anahtarlar. Faz 0 foundation'ından birebir gelir.
CORE_ALLOWED_KEYS: frozenset[str] = frozenset(
    {
        # Background
        "bg_primary",
        "bg_secondary",
        "bg_tertiary",
        "surface_01",
        "surface_02",
        "surface_03",
        # Border
        "border",
        # Text
        "text_primary",
        "text_secondary",
        "text_muted",
        "text_inverse",
        # Status (success/warning/error/info + her birinin -surface variantı)
        "status_success",
        "status_success_surface",
        "status_warning",
        "status_warning_surface",
        "status_error",
        "status_error_surface",
        "status_info",
        "status_info_surface",
        # Focus
        "focus_ring",
    }
)

# Modül scope'larında izinli kimlik anahtarları.
# (CorpOS'un altın CTA'sına özel `cta_text_weight` ve `accent_light` — Faz 0
#  foundation.md'de belgelenmiş ek anahtarlar — listede.)
MODULE_ALLOWED_KEYS: frozenset[str] = frozenset(
    {
        "brand",
        "brand_hover",
        "cta",
        "cta_hover",
        "cta_text",
        "cta_text_weight",
        "on_brand",
        "accent",
        "accent_light",
        "link_back",
    }
)


class GovernanceViolation(ValueError):
    """Bir token kaydı scope/anahtar governance'ını ihlal ediyor."""


def assert_governance(scope: str, key: str) -> None:
    """Token (scope, key) çiftini governance kurallarına karşı doğrula.

    Atılan istisnalar:
        ValueError       — geçersiz scope
        GovernanceViolation — anahtar bu scope için izinli değil
                             (örn. modül core anahtarını ezmeye çalışıyor)
    """
    if scope not in VALID_SCOPES:
        raise ValueError(f"Geçersiz scope: {scope!r}. İzinli: {VALID_SCOPES}")

    if scope == "core":
        if key not in CORE_ALLOWED_KEYS:
            raise GovernanceViolation(
                f"core scope'unda izinsiz anahtar: {key!r}. "
                f"İzinli core anahtarları: {sorted(CORE_ALLOWED_KEYS)}"
            )
    else:
        if key not in MODULE_ALLOWED_KEYS:
            # Bir modül core-sahipli anahtarı ezmeye mi çalışıyor?
            if key in CORE_ALLOWED_KEYS:
                raise GovernanceViolation(
                    f"Modül {scope!r} core-sahipli anahtar {key!r} ezemez. "
                    "Core token'ları (bg/surface/border/text/status/focus) "
                    "yalnız core scope'unda tanımlanır."
                )
            raise GovernanceViolation(
                f"Modül {scope!r} için izinsiz anahtar: {key!r}. "
                f"İzinli modül anahtarları: {sorted(MODULE_ALLOWED_KEYS)}"
            )


# ----------------------------------------------------------------------------
# Repository
# ----------------------------------------------------------------------------


class ColorTokenRepository:
    """color_tokens tablosu için thread-safe CRUD."""

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

    # ---- read ---------------------------------------------------------------

    def list_tokens(self, scope: Scope | None = None) -> list[dict[str, object]]:
        """Tüm token'ları (veya scope filtreli) döndür.

        Sıralama: scope, sonra display_order, sonra key (deterministic).
        """
        with self._lock:
            if scope is not None:
                cur = self._conn.execute(
                    "SELECT scope, key, value, label, category, display_order, updated_at "
                    "FROM color_tokens WHERE scope = ? "
                    "ORDER BY display_order, key",
                    (scope,),
                )
            else:
                cur = self._conn.execute(
                    "SELECT scope, key, value, label, category, display_order, updated_at "
                    "FROM color_tokens "
                    "ORDER BY scope, display_order, key"
                )
            return [dict(row) for row in cur.fetchall()]

    def latest_updated_at(self) -> int | None:
        """En son güncelleme zamanı (seed unix timestamp), tablo boşsa None."""
        with self._lock:
            row = self._conn.execute(
                "SELECT MAX(updated_at) AS ts FROM color_tokens"
            ).fetchone()
            return int(row["ts"]) if row and row["ts"] is not None else None

    def is_empty(self) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS n FROM color_tokens"
            ).fetchone()
            return int(row["n"]) == 0

    # ---- write --------------------------------------------------------------

    def upsert(
        self,
        scope: str,
        key: str,
        value: str,
        label: str,
        category: str,
        display_order: int = 0,
    ) -> None:
        """Tek token kaydını upsert et. Governance violation → istisna."""
        assert_governance(scope, key)
        now = int(time.time())
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO color_tokens
                  (scope, key, value, label, category, display_order, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(scope, key) DO UPDATE SET
                  value         = excluded.value,
                  label         = excluded.label,
                  category      = excluded.category,
                  display_order = excluded.display_order,
                  updated_at    = excluded.updated_at
                """,
                (scope, key, value, label, category, display_order, now),
            )
            self._conn.commit()

    def upsert_many(self, items: list[dict[str, object]]) -> int:
        """Toplu idempotent upsert. Her item: {scope, key, value, label, category, display_order?}.

        Hepsi bir transaction'da. Bir item governance'ı ihlal ederse hepsi geri sarar.
        Dönüş: kaydedilen item sayısı.
        """
        # Önce hepsini doğrula (early-fail, atomic guarantee için).
        for item in items:
            assert_governance(str(item["scope"]), str(item["key"]))

        now = int(time.time())
        rows = [
            (
                str(item["scope"]),
                str(item["key"]),
                str(item["value"]),
                str(item["label"]),
                str(item["category"]),
                int(item.get("display_order", 0)),
                now,
            )
            for item in items
        ]
        with self._lock:
            self._conn.executemany(
                """
                INSERT INTO color_tokens
                  (scope, key, value, label, category, display_order, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(scope, key) DO UPDATE SET
                  value         = excluded.value,
                  label         = excluded.label,
                  category      = excluded.category,
                  display_order = excluded.display_order,
                  updated_at    = excluded.updated_at
                """,
                rows,
            )
            self._conn.commit()
        return len(rows)
