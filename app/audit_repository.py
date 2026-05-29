from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any
import sqlite3
import time

from app.audit_hash import (
    GENESIS_PREV_HASH,
    compute_entry_hash,
    verify_chain_link,
    verify_entry,
)


class AuditRepository:
    def __init__(self, database_path: str) -> None:
        self._lock = Lock()
        self._conn = self._connect(database_path)
        self._ensure_schema()

    @staticmethod
    def _connect(database_path: str) -> sqlite3.Connection:
        path = Path(database_path)
        if path.parent and str(path.parent) != ".":
            path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def close(self) -> None:
        self._conn.close()

    def _ensure_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT,
                username TEXT,
                role TEXT,
                method TEXT NOT NULL,
                path TEXT NOT NULL,
                status_code INTEGER NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                duration_ms REAL NOT NULL,
                created_at INTEGER NOT NULL,
                event_type TEXT,
                event_detail TEXT
            )
            """
        )
        # G+4: Hash chain kolonları idempotent eklenir.
        # AuditRepository migration olmadan başlatılırsa (test fixture'lar,
        # initial bootstrap) bu kolonları otomatik ekler — production'da
        # migration 024 zaten ekledi.
        for ddl in (
            "ALTER TABLE audit_logs ADD COLUMN prev_hash TEXT",
            "ALTER TABLE audit_logs ADD COLUMN entry_hash TEXT",
        ):
            try:
                self._conn.execute(ddl)
            except sqlite3.OperationalError as exc:
                # "duplicate column name" → kolon zaten var, geç
                if "duplicate column name" not in str(exc).lower():
                    raise
        self._conn.commit()

    def write_log(
        self,
        *,
        request_id: str,
        username: str | None,
        role: str | None,
        method: str,
        path: str,
        status_code: int,
        ip_address: str | None,
        user_agent: str | None,
        duration_ms: float,
        event_type: str | None = None,
        event_detail: dict[str, Any] | None = None,
    ) -> None:
        """G+4: Hash chain — her entry önceki entry'nin hash'ini içerir.

        prev_hash = son entry'nin entry_hash'i (yoksa GENESIS_PREV_HASH).
        entry_hash = SHA-256(canonical_payload + prev_hash).

        Lock altında atomic: prev_hash okuma → hash hesaplama → INSERT.
        Yarış koşulunda zincirin doğruluğu garanti.
        """
        now = int(time.time())
        detail_json = json.dumps(event_detail, ensure_ascii=True) if event_detail else None
        with self._lock:
            prev_hash = self._fetch_last_hash() or GENESIS_PREV_HASH
            entry_payload = {
                "request_id": request_id,
                "username": username,
                "role": role,
                "method": method,
                "path": path,
                "status_code": status_code,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "duration_ms": duration_ms,
                "created_at": now,
                "event_type": event_type,
                "event_detail": detail_json,
                "prev_hash": prev_hash,
            }
            entry_hash = compute_entry_hash(entry_payload)
            self._conn.execute(
                """
                INSERT INTO audit_logs(
                    request_id,
                    username,
                    role,
                    method,
                    path,
                    status_code,
                    ip_address,
                    user_agent,
                    duration_ms,
                    created_at,
                    event_type,
                    event_detail,
                    prev_hash,
                    entry_hash
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    username,
                    role,
                    method,
                    path,
                    status_code,
                    ip_address,
                    user_agent,
                    duration_ms,
                    now,
                    event_type,
                    detail_json,
                    prev_hash,
                    entry_hash,
                ),
            )
            self._conn.commit()

    def write_event(
        self,
        *,
        username: str | None,
        role: str | None,
        event_type: str,
        event_detail: dict[str, Any] | None = None,
        request_id: str = "",
        ip_address: str | None = None,
    ) -> None:
        """Write a structured business event to the audit log (not tied to an HTTP request).

        G+4: Hash chain — write_log ile aynı pattern. prev_hash + entry_hash.
        """
        now = int(time.time())
        detail_json = json.dumps(event_detail, ensure_ascii=True) if event_detail else None
        with self._lock:
            prev_hash = self._fetch_last_hash() or GENESIS_PREV_HASH
            entry_payload = {
                "request_id": request_id,
                "username": username,
                "role": role,
                "method": "EVENT",
                "path": f"/audit/event/{event_type}",
                "status_code": 200,
                "ip_address": ip_address,
                "user_agent": None,
                "duration_ms": 0.0,
                "created_at": now,
                "event_type": event_type,
                "event_detail": detail_json,
                "prev_hash": prev_hash,
            }
            entry_hash = compute_entry_hash(entry_payload)
            self._conn.execute(
                """
                INSERT INTO audit_logs(
                    request_id,
                    username,
                    role,
                    method,
                    path,
                    status_code,
                    ip_address,
                    user_agent,
                    duration_ms,
                    created_at,
                    event_type,
                    event_detail,
                    prev_hash,
                    entry_hash
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    username,
                    role,
                    "EVENT",
                    f"/audit/event/{event_type}",
                    200,
                    ip_address,
                    None,
                    0.0,
                    now,
                    event_type,
                    detail_json,
                    prev_hash,
                    entry_hash,
                ),
            )
            self._conn.commit()

    # ── G+4: Hash chain helpers + verify ──────────────────────────────────

    def _fetch_last_hash(self) -> str | None:
        """Get last entry's entry_hash for chain link. None if empty table."""
        row = self._conn.execute(
            "SELECT entry_hash FROM audit_logs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        return row["entry_hash"]

    def verify_chain(self, *, limit: int = 10_000) -> dict[str, Any]:
        """Verify the entire hash chain.

        Returns: {
            verified: bool,            # True if zincir bütünüyle sağlam
            checked_count: int,        # Kontrol edilen entry sayısı
            first_break_id: int | None,# Zincir nerede kırıldı? (None = sağlam)
            first_break_reason: str,   # "entry_hash_mismatch" | "prev_hash_mismatch" | ""
            genesis_id: int | None,    # İlk hash-chain entry'sinin id'si
            legacy_count: int,         # Pre-G+4 entries (entry_hash NULL) sayısı
        }

        Pre-G+4 entries (legacy, entry_hash NULL) atlanır — genesis sonrası
        zincir kontrol edilir.
        """
        with self._lock:
            rows = self._conn.execute(
                f"""
                SELECT
                    id, request_id, username, role, method, path,
                    status_code, ip_address, user_agent, duration_ms,
                    created_at, event_type, event_detail,
                    prev_hash, entry_hash
                FROM audit_logs
                ORDER BY id ASC
                LIMIT {int(max(1, min(limit, 100_000)))}
                """
            ).fetchall()

        legacy_count = 0
        prev_entry: dict[str, Any] | None = None
        genesis_id: int | None = None
        checked_count = 0

        for raw in rows:
            entry = dict(raw)
            # Legacy pre-G+4 entries: entry_hash NULL → atla
            if entry.get("entry_hash") is None:
                legacy_count += 1
                continue

            # İlk hash-chain entry: genesis
            if genesis_id is None:
                genesis_id = int(entry["id"])

            # Entry hash bütünlüğü
            if not verify_entry(entry):
                return {
                    "verified": False,
                    "checked_count": checked_count,
                    "first_break_id": int(entry["id"]),
                    "first_break_reason": "entry_hash_mismatch",
                    "genesis_id": genesis_id,
                    "legacy_count": legacy_count,
                }

            # Zincir bağlantısı
            if not verify_chain_link(prev_entry, entry):
                return {
                    "verified": False,
                    "checked_count": checked_count,
                    "first_break_id": int(entry["id"]),
                    "first_break_reason": "prev_hash_mismatch",
                    "genesis_id": genesis_id,
                    "legacy_count": legacy_count,
                }

            checked_count += 1
            prev_entry = entry

        return {
            "verified": True,
            "checked_count": checked_count,
            "first_break_id": None,
            "first_break_reason": "",
            "genesis_id": genesis_id,
            "legacy_count": legacy_count,
        }

    def list_logs(self, *, limit: int = 100) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 500))
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT
                    id,
                    request_id,
                    username,
                    role,
                    method,
                    path,
                    status_code,
                    ip_address,
                    user_agent,
                    duration_ms,
                    created_at,
                    event_type,
                    event_detail,
                    prev_hash,
                    entry_hash
                FROM audit_logs
                ORDER BY id DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
            result: list[dict[str, Any]] = []
            for row in rows:
                row_dict = dict(row)
                raw_detail = row_dict.get("event_detail")
                if raw_detail:
                    try:
                        row_dict["event_detail"] = json.loads(str(raw_detail))
                    except (TypeError, ValueError):
                        row_dict["event_detail"] = None
                result.append(row_dict)
            return result
