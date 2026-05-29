"""A2: AnomalySignalsRepository — tespit edilen anomalileri persist.

Engine detect() çalıştırır → repository idempotent upsert ile saklar
(signature_hash UNIQUE garanti). Frontend liste + review için okur.
"""
from __future__ import annotations

import json
import sqlite3
import time
from threading import Lock
from typing import Any


class AnomalySignalsRepository:
    """Cross-company anomaly signal storage."""

    def __init__(self, database_path: str) -> None:
        self._lock = Lock()
        self._conn = self._connect(database_path)

    @staticmethod
    def _connect(database_path: str) -> sqlite3.Connection:
        conn = sqlite3.connect(database_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def close(self) -> None:
        self._conn.close()

    # ── INSERT (idempotent) ────────────────────────────────────────────

    def upsert_signal(
        self,
        *,
        holding_id: int | None,
        signal_type: str,
        severity: str,
        confidence_pct: float,
        modified_z: float,
        title: str,
        description: str,
        baseline: dict[str, Any],
        payload: dict[str, Any],
        signature_hash: str,
    ) -> int | None:
        """Insert if signature_hash yoksa; mevcut ise None döner.

        Idempotency garantisi: aynı anomali (örn. aynı counterparty +
        aynı amount + aynı gün) iki kez kaydedilmez.
        """
        now = int(time.time())
        with self._lock:
            try:
                cursor = self._conn.execute(
                    """
                    INSERT INTO anomaly_signals (
                        holding_id, signal_type, severity, confidence_pct,
                        modified_z, title, description,
                        baseline_json, payload_json,
                        signature_hash, detected_at, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open')
                    """,
                    (
                        holding_id, signal_type, severity, confidence_pct,
                        modified_z, title, description,
                        json.dumps(baseline, ensure_ascii=False, default=str),
                        json.dumps(payload, ensure_ascii=False, default=str),
                        signature_hash, now,
                    ),
                )
                self._conn.commit()
                return int(cursor.lastrowid) if cursor.lastrowid else None
            except sqlite3.IntegrityError:
                # Signature collision — zaten kaydedilmiş, skip
                return None

    # ── SELECT ─────────────────────────────────────────────────────────

    def list_open(
        self,
        *,
        holding_id: int | None,
        min_severity: str = "high",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Open anomaly'leri listele. Severity ordering ile."""
        order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        min_rank = order.get(min_severity, 2)

        query = """
            SELECT id, holding_id, signal_type, severity, confidence_pct,
                   modified_z, title, description,
                   baseline_json, payload_json,
                   detected_at, status, reviewed_by, reviewed_at, review_note
            FROM anomaly_signals
            WHERE status = 'open'
        """
        params: list[Any] = []
        if holding_id is not None:
            query += " AND holding_id = ?"
            params.append(holding_id)
        query += " ORDER BY detected_at DESC LIMIT ?"
        params.append(limit * 4)  # severity-filter sonrası yeterli pool için

        with self._lock:
            rows = self._conn.execute(query, tuple(params)).fetchall()

        results = []
        for row in rows:
            sev_rank = order.get(row["severity"], 0)
            if sev_rank >= min_rank:
                results.append(self._row_to_dict(row))
        return results[:limit]

    def count_by_severity(self, *, holding_id: int | None) -> dict[str, int]:
        """Open sinyallerin severity dağılımı — dashboard badge için."""
        query = """
            SELECT severity, COUNT(*) AS n
            FROM anomaly_signals
            WHERE status = 'open'
        """
        params: list[Any] = []
        if holding_id is not None:
            query += " AND holding_id = ?"
            params.append(holding_id)
        query += " GROUP BY severity"

        with self._lock:
            rows = self._conn.execute(query, tuple(params)).fetchall()

        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for row in rows:
            counts[row["severity"]] = int(row["n"])
        return counts

    def get(self, signal_id: int) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT id, holding_id, signal_type, severity, confidence_pct,
                       modified_z, title, description,
                       baseline_json, payload_json,
                       detected_at, status, reviewed_by, reviewed_at, review_note
                FROM anomaly_signals
                WHERE id = ?
                """,
                (signal_id,),
            ).fetchone()
        return self._row_to_dict(row) if row else None

    # ── UPDATE (review) ────────────────────────────────────────────────

    def review_signal(
        self,
        *,
        signal_id: int,
        action: str,
        reviewed_by: str,
        note: str | None,
    ) -> dict[str, Any] | None:
        """Action: 'confirm' | 'dismiss'. Status'u günceller."""
        if action not in ("confirm", "dismiss"):
            raise ValueError(f"Geçersiz action: {action}")
        status = "confirmed" if action == "confirm" else "dismissed"
        now = int(time.time())
        with self._lock:
            cursor = self._conn.execute(
                """
                UPDATE anomaly_signals
                SET status = ?, reviewed_by = ?, reviewed_at = ?, review_note = ?
                WHERE id = ? AND status = 'open'
                """,
                (status, reviewed_by, now, note, signal_id),
            )
            self._conn.commit()
            if cursor.rowcount == 0:
                return None
        return self.get(signal_id)

    # ── helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        try:
            baseline = json.loads(row["baseline_json"] or "{}")
        except (json.JSONDecodeError, TypeError):
            baseline = {}
        try:
            payload = json.loads(row["payload_json"] or "{}")
        except (json.JSONDecodeError, TypeError):
            payload = {}
        return {
            "id": int(row["id"]),
            "holding_id": int(row["holding_id"]) if row["holding_id"] is not None else None,
            "signal_type": str(row["signal_type"]),
            "severity": str(row["severity"]),
            "confidence_pct": float(row["confidence_pct"]),
            "modified_z": float(row["modified_z"]),
            "title": str(row["title"]),
            "description": str(row["description"]),
            "baseline": baseline,
            "payload": payload,
            "detected_at": int(row["detected_at"]),
            "status": str(row["status"]),
            "reviewed_by": row["reviewed_by"],
            "reviewed_at": int(row["reviewed_at"]) if row["reviewed_at"] is not None else None,
            "review_note": row["review_note"],
        }
