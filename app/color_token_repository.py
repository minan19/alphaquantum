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
from typing import Any, Literal

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

    def list_tokens(self, scope: Scope | None = None) -> list[dict[str, Any]]:
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

    def upsert_many(self, items: list[dict[str, Any]]) -> int:
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

    def update_value(self, scope: str, key: str, value: str) -> bool:
        """Tek token'ın value'sunu güncelle. Governance checked.

        Dönüş: True if updated, False if not found.
        """
        assert_governance(scope, key)
        now = int(time.time())
        with self._lock:
            cur = self._conn.execute(
                """
                UPDATE color_tokens
                SET value = ?, updated_at = ?
                WHERE scope = ? AND key = ?
                """,
                (value, now, scope, key),
            )
            self._conn.commit()
            return cur.rowcount > 0

    def delete_scope(self, scope: str) -> int:
        """Bir scope'taki tüm token'ları sil (reset için pre-step).

        Dönüş: silinen satır sayısı.
        """
        if scope not in VALID_SCOPES:
            raise ValueError(f"Geçersiz scope: {scope!r}")
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM color_tokens WHERE scope = ?",
                (scope,),
            )
            self._conn.commit()
            return cur.rowcount

    # ---- snapshots (Faz 5) --------------------------------------------------

    # Scope başına saklanacak max snapshot sayısı (rotation).
    SNAPSHOT_RETENTION: int = 20

    def snapshot_payload(self, scope: str) -> list[dict[str, Any]]:
        """Bir scope'un anlık tam token kümesini snapshot payload'una dönüştür.

        Restore sırasında upsert_many'e direkt verilebilir; bu yüzden upsert'in
        beklediği alanları (scope/key/value/label/category/display_order) içerir.
        """
        if scope not in VALID_SCOPES:
            raise ValueError(f"Geçersiz scope: {scope!r}")
        rows = self.list_tokens(scope=scope)
        return [
            {
                "scope": str(r["scope"]),
                "key": str(r["key"]),
                "value": str(r["value"]),
                "label": str(r["label"]),
                "category": str(r["category"]),
                "display_order": int(r["display_order"]),
            }
            for r in rows
        ]

    def create_snapshot(
        self,
        scope: str,
        source: str,
        label: str,
        payload: list[dict[str, Any]],
        created_by: str | None = None,
    ) -> int:
        """Anlık görüntü yaz + retention rotation.

        source: 'pre_save' | 'pre_restore' | 'pre_reset' | 'manual'
        Dönüş: yeni snapshot id.
        """
        if scope not in VALID_SCOPES:
            raise ValueError(f"Geçersiz scope: {scope!r}")
        if source not in {"pre_save", "pre_restore", "pre_reset", "manual"}:
            raise ValueError(f"Geçersiz snapshot source: {source!r}")
        now = int(time.time())
        payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        with self._lock:
            cur = self._conn.execute(
                """
                INSERT INTO color_token_snapshots
                  (scope, source, label, payload_json, created_by, taken_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (scope, source, label, payload_json, created_by, now),
            )
            snapshot_id = int(cur.lastrowid or 0)
            # Retention: bu scope için en eski fazlalıkları sil.
            self._conn.execute(
                """
                DELETE FROM color_token_snapshots
                WHERE scope = ?
                  AND id NOT IN (
                    SELECT id FROM color_token_snapshots
                    WHERE scope = ?
                    ORDER BY taken_at DESC, id DESC
                    LIMIT ?
                  )
                """,
                (scope, scope, self.SNAPSHOT_RETENTION),
            )
            self._conn.commit()
            return snapshot_id

    def list_snapshots(self, scope: str, limit: int = 20) -> list[dict[str, Any]]:
        """Snapshot listesi (yeni→eski). payload_json dahil edilmez (liste hafif).

        Tek snapshot detayı için `get_snapshot(id)` kullan.
        """
        if scope not in VALID_SCOPES:
            raise ValueError(f"Geçersiz scope: {scope!r}")
        with self._lock:
            cur = self._conn.execute(
                """
                SELECT id, scope, source, label, created_by, taken_at
                FROM color_token_snapshots
                WHERE scope = ?
                ORDER BY taken_at DESC, id DESC
                LIMIT ?
                """,
                (scope, max(1, min(int(limit), 100))),
            )
            return [dict(row) for row in cur.fetchall()]

    def get_snapshot(self, snapshot_id: int) -> dict[str, Any] | None:
        """Tek snapshot kaydı (payload_json parse edilmiş halde)."""
        with self._lock:
            row = self._conn.execute(
                """
                SELECT id, scope, source, label, payload_json, created_by, taken_at
                FROM color_token_snapshots
                WHERE id = ?
                """,
                (snapshot_id,),
            ).fetchone()
        if row is None:
            return None
        data = dict(row)
        try:
            data["payload"] = json.loads(data.pop("payload_json"))
        except (TypeError, ValueError):
            data["payload"] = []
        return data
