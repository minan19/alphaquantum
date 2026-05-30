"""I1: ConnectorImportRepository — import job + error tracking."""
from __future__ import annotations

import json
import sqlite3
import time
from threading import Lock
from typing import Any


class ConnectorImportRepository:
    """Import job audit + error log storage."""

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

    # ── Import job CRUD ────────────────────────────────────────────────

    def create_job(
        self,
        *,
        user_id: str,
        connector_type: str,
        mode: str,
        source_filename: str | None,
        source_size_bytes: int,
    ) -> int:
        now = int(time.time())
        with self._lock:
            cur = self._conn.execute(
                """
                INSERT INTO connector_import_jobs
                    (user_id, connector_type, mode, status,
                     source_filename, source_size_bytes, started_at)
                VALUES (?, ?, ?, 'pending', ?, ?, ?)
                """,
                (
                    user_id, connector_type, mode,
                    source_filename, source_size_bytes, now,
                ),
            )
            self._conn.commit()
        return int(cur.lastrowid or 0)

    def update_status(
        self,
        *,
        job_id: int,
        status: str,
        summary: dict[str, Any] | None = None,
        preview: list[dict[str, Any]] | None = None,
        error_message: str | None = None,
    ) -> None:
        now = int(time.time())
        sets = ["status = ?"]
        params: list[Any] = [status]
        if summary is not None:
            sets.append("record_summary_json = ?")
            params.append(json.dumps(summary, ensure_ascii=False, default=str))
        if preview is not None:
            sets.append("preview_json = ?")
            params.append(json.dumps(preview, ensure_ascii=False, default=str))
        if error_message is not None:
            sets.append("error_message = ?")
            params.append(error_message)
        if status in ("completed", "failed", "cancelled"):
            sets.append("finished_at = ?")
            params.append(now)
        if status == "completed":
            sets.append("committed_at = ?")
            params.append(now)
        params.append(job_id)
        with self._lock:
            self._conn.execute(
                f"UPDATE connector_import_jobs SET {', '.join(sets)} WHERE id = ?",
                tuple(params),
            )
            self._conn.commit()

    def get_job(self, job_id: int) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT id, user_id, connector_type, mode, status,
                       source_filename, source_size_bytes,
                       record_summary_json, preview_json, error_message,
                       started_at, finished_at, committed_at
                FROM connector_import_jobs
                WHERE id = ?
                """,
                (job_id,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_dict(row)

    def list_jobs(
        self, *, user_id: str, limit: int = 20,
    ) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT id, user_id, connector_type, mode, status,
                       source_filename, source_size_bytes,
                       record_summary_json, preview_json, error_message,
                       started_at, finished_at, committed_at
                FROM connector_import_jobs
                WHERE user_id = ?
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    # ── Error log ─────────────────────────────────────────────────────

    def insert_errors(
        self, *, job_id: int, errors: list[dict[str, Any]],
    ) -> int:
        if not errors:
            return 0
        with self._lock:
            cur = self._conn.executemany(
                """
                INSERT INTO connector_import_errors
                    (job_id, row_index, record_type, error_code,
                     error_message, raw_payload)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        job_id, e["row_index"], e["record_type"],
                        e["error_code"], e["error_message"], e.get("raw_payload"),
                    )
                    for e in errors
                ],
            )
            self._conn.commit()
            return int(cur.rowcount or 0)

    def list_errors(
        self, *, job_id: int, limit: int = 50,
    ) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT id, job_id, row_index, record_type,
                       error_code, error_message, raw_payload
                FROM connector_import_errors
                WHERE job_id = ?
                ORDER BY row_index ASC
                LIMIT ?
                """,
                (job_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        try:
            summary = json.loads(row["record_summary_json"] or "{}")
        except (json.JSONDecodeError, TypeError):
            summary = {}
        preview: list[dict[str, Any]] = []
        try:
            preview = json.loads(row["preview_json"] or "[]") or []
        except (json.JSONDecodeError, TypeError):
            preview = []
        return {
            "id": int(row["id"]),
            "user_id": str(row["user_id"]),
            "connector_type": str(row["connector_type"]),
            "mode": str(row["mode"]),
            "status": str(row["status"]),
            "source_filename": row["source_filename"],
            "source_size_bytes": int(row["source_size_bytes"] or 0),
            "summary": summary,
            "preview": preview,
            "error_message": row["error_message"],
            "started_at": int(row["started_at"]),
            "finished_at": (
                int(row["finished_at"]) if row["finished_at"] is not None else None
            ),
            "committed_at": (
                int(row["committed_at"]) if row["committed_at"] is not None else None
            ),
        }
