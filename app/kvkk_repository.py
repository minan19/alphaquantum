"""A4: KVKK (Kişisel Verilerin Korunması Kanunu) Repository.

Yönetilen tablolar:
    - account_deletion_requests  (silme talepleri)
    - security_incidents          (KVKK madde 12 ihlal raporları)
    - users.kvkk_consent_*        (kullanıcı KVKK onay alanları)

Bu modül **sadece KVKK ile ilgili kayıtları** tutar; gerçek "veri toplama"
(GET /me/data) farklı repository'lerin sorgulanmasıyla yapılır — KVKKEngine
bu birleştirmeyi yönetir.
"""
from __future__ import annotations

import json
import sqlite3
import time
from threading import Lock
from typing import Any


class KVKKRepository:
    def __init__(self, database_path: str) -> None:
        self._lock = Lock()
        self._conn = self._connect(database_path)

    @staticmethod
    def _connect(database_path: str) -> sqlite3.Connection:
        conn = sqlite3.connect(database_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def close(self) -> None:
        self._conn.close()

    # ── Deletion Requests ────────────────────────────────────────────────────

    def create_deletion_request(
        self,
        *,
        user_id: int,
        reason: str = "",
    ) -> dict[str, Any]:
        """User kendi silme talebini açar (KVKK madde 11/e)."""
        now = int(time.time())
        with self._lock:
            cur = self._conn.execute(
                """
                INSERT INTO account_deletion_requests(
                    user_id, requested_at, reason, status, created_at, updated_at
                ) VALUES(?,?,?,'pending',?,?)
                """,
                (user_id, now, reason, now, now),
            )
            row_id = int(cur.lastrowid or 0)
            self._conn.commit()
            return self._fetch_deletion(row_id)

    def get_deletion_request(self, request_id: int) -> dict[str, Any] | None:
        with self._lock:
            return self._fetch_deletion(request_id)

    def _fetch_deletion(self, request_id: int) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM account_deletion_requests WHERE id = ?", (request_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_deletion_requests(
        self,
        *,
        status: str | None = None,
        user_id: int | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status = ?"); params.append(status)
        if user_id is not None:
            clauses.append("user_id = ?"); params.append(user_id)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM account_deletion_requests {where} "
                f"ORDER BY requested_at DESC LIMIT ?",
                params,
            ).fetchall()
        return [dict(r) for r in rows]

    def decide_deletion_request(
        self,
        request_id: int,
        *,
        decision: str,           # 'approved' | 'rejected'
        decision_by: int,
        decision_note: str = "",
    ) -> dict[str, Any] | None:
        if decision not in ("approved", "rejected"):
            raise ValueError(f"invalid decision: {decision}")
        now = int(time.time())
        with self._lock:
            cur = self._conn.execute(
                """UPDATE account_deletion_requests
                   SET status=?, decision_at=?, decision_by=?,
                       decision_note=?, updated_at=?
                   WHERE id=? AND status='pending'""",
                (decision, now, decision_by, decision_note, now, request_id),
            )
            if cur.rowcount == 0:
                self._conn.commit()
                return None  # not found or already decided
            self._conn.commit()
            return self._fetch_deletion(request_id)

    def mark_deletion_completed(
        self, request_id: int, anonymized_fields: list[str]
    ) -> dict[str, Any] | None:
        """Approved silme talebinin teknik anonymize işlemi tamamlandı."""
        now = int(time.time())
        with self._lock:
            cur = self._conn.execute(
                """UPDATE account_deletion_requests
                   SET status='completed', completed_at=?,
                       anonymized_fields=?, updated_at=?
                   WHERE id=? AND status='approved'""",
                (now, json.dumps(anonymized_fields), now, request_id),
            )
            if cur.rowcount == 0:
                self._conn.commit()
                return None
            self._conn.commit()
            return self._fetch_deletion(request_id)

    # ── Security Incidents ───────────────────────────────────────────────────

    def create_incident(
        self,
        *,
        incident_type: str,
        severity: str,
        description: str,
        reported_by: int,
        affected_user_id: int | None = None,
        affected_record_count: int = 0,
    ) -> dict[str, Any]:
        """KVKK madde 12 — veri ihlali raporu kaydı.

        high/critical severity'de kvkk_notification_required=1 otomatik set.
        72 saat içinde KVK Kurumu'na bildirim takibi için.
        """
        if severity not in ("low", "medium", "high", "critical"):
            raise ValueError(f"invalid severity: {severity}")
        now = int(time.time())
        notif_required = 1 if severity in ("high", "critical") else 0
        with self._lock:
            cur = self._conn.execute(
                """
                INSERT INTO security_incidents(
                    incident_type, severity, affected_user_id,
                    affected_record_count, description, reported_by,
                    reported_at, kvkk_notification_required,
                    resolution_status, created_at, updated_at
                ) VALUES(?,?,?,?,?,?,?,?, 'open', ?, ?)
                """,
                (incident_type, severity, affected_user_id,
                 affected_record_count, description, reported_by,
                 now, notif_required, now, now),
            )
            row_id = int(cur.lastrowid or 0)
            self._conn.commit()
            return self._fetch_incident(row_id)

    def _fetch_incident(self, incident_id: int) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM security_incidents WHERE id = ?", (incident_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_incident(self, incident_id: int) -> dict[str, Any] | None:
        with self._lock:
            return self._fetch_incident(incident_id)

    def list_incidents(
        self,
        *,
        severity: str | None = None,
        status: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if severity:
            clauses.append("severity = ?"); params.append(severity)
        if status:
            clauses.append("resolution_status = ?"); params.append(status)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM security_incidents {where} "
                f"ORDER BY reported_at DESC LIMIT ?",
                params,
            ).fetchall()
        return [dict(r) for r in rows]

    # ── User KVKK fields ─────────────────────────────────────────────────────

    def record_consent(
        self, user_id: int, *, version: str = "v1"
    ) -> dict[str, Any] | None:
        now = int(time.time())
        with self._lock:
            self._conn.execute(
                """UPDATE users
                   SET kvkk_consent_at=?, kvkk_consent_version=?, updated_at=?
                   WHERE id=?""",
                (now, version, now, user_id),
            )
            self._conn.commit()
            return self._fetch_user(user_id)

    def mark_data_access(self, user_id: int) -> None:
        """GET /me/data çağırıldığında izlenir."""
        now = int(time.time())
        with self._lock:
            self._conn.execute(
                "UPDATE users SET last_data_access_at=? WHERE id=?",
                (now, user_id),
            )
            self._conn.commit()

    def mark_data_export(self, user_id: int) -> None:
        """Tam export döndüğünde izlenir."""
        now = int(time.time())
        with self._lock:
            self._conn.execute(
                "UPDATE users SET last_data_export_at=? WHERE id=?",
                (now, user_id),
            )
            self._conn.commit()

    def anonymize_user(self, user_id: int) -> list[str]:
        """KVKK madde 7 uyumlu: PII alanlarını maskele, kaydı sil değil.

        Returns: anonymize edilen alan adlarının listesi.
        """
        now = int(time.time())
        anonymized = [
            "username",      # → anonymized_user_{id}
            "is_active",     # → 0 (login engellenir)
        ]
        with self._lock:
            self._conn.execute(
                """UPDATE users
                   SET username=?, is_active=0, anonymized_at=?, updated_at=?
                   WHERE id=?""",
                (f"anonymized_user_{user_id}", now, now, user_id),
            )
            self._conn.commit()
        return anonymized

    def _fetch_user(self, user_id: int) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_user_kvkk_status(self, user_id: int) -> dict[str, Any]:
        row = self._fetch_user(user_id)
        if not row:
            return {
                "user_id": user_id,
                "consent_at": 0,
                "consent_version": "",
                "last_data_access_at": None,
                "last_data_export_at": None,
                "anonymized_at": None,
            }
        return {
            "user_id": user_id,
            "consent_at": int(row.get("kvkk_consent_at") or 0),
            "consent_version": str(row.get("kvkk_consent_version") or ""),
            "last_data_access_at": row.get("last_data_access_at"),
            "last_data_export_at": row.get("last_data_export_at"),
            "anonymized_at": row.get("anonymized_at"),
        }
