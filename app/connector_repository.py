from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Any
import json
import sqlite3

from app._sqlite_helpers import new_row_id
import time


class ConnectorRepository:
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
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def close(self) -> None:
        self._conn.close()

    def _ensure_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS integration_connectors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT NOT NULL,
                connector_type TEXT NOT NULL,
                provider TEXT NOT NULL,
                base_url TEXT,
                auth_mode TEXT NOT NULL,
                config_json TEXT NOT NULL DEFAULT '{}',
                mapping_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'active',
                readiness_score REAL NOT NULL DEFAULT 0,
                mapping_coverage_score REAL NOT NULL DEFAULT 0,
                security_score REAL NOT NULL DEFAULT 0,
                created_by TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                last_sync_at INTEGER,
                UNIQUE(company_name, connector_type, provider)
            )
            """
        )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_integration_connectors_company
            ON integration_connectors(company_name)
            """
        )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_integration_connectors_status
            ON integration_connectors(status)
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS integration_sync_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                connector_id INTEGER NOT NULL,
                trigger_mode TEXT NOT NULL,
                priority_score REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                requested_by TEXT,
                request_payload_json TEXT NOT NULL DEFAULT '{}',
                result_summary TEXT NOT NULL DEFAULT '',
                error_message TEXT,
                last_error_code TEXT,
                attempt_count INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL DEFAULT 3,
                requested_at INTEGER NOT NULL,
                next_retry_at INTEGER,
                dead_lettered_at INTEGER,
                started_at INTEGER,
                finished_at INTEGER,
                FOREIGN KEY(connector_id) REFERENCES integration_connectors(id) ON DELETE CASCADE
            )
            """
        )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_integration_sync_jobs_status_priority
            ON integration_sync_jobs(status, priority_score DESC, requested_at ASC)
            """
        )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_integration_sync_jobs_connector_id
            ON integration_sync_jobs(connector_id)
            """
        )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_integration_sync_jobs_retry_due
            ON integration_sync_jobs(status, next_retry_at)
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS integration_worker_leases (
                worker_name TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                acquired_at INTEGER NOT NULL,
                heartbeat_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_integration_worker_leases_expires
            ON integration_worker_leases(expires_at)
            """
        )
        self._ensure_sync_job_columns()
        self._conn.commit()

    def _ensure_sync_job_columns(self) -> None:
        rows = self._conn.execute("PRAGMA table_info(integration_sync_jobs)").fetchall()
        existing = {str(row["name"]) for row in rows}
        migrations: list[str] = []
        if "last_error_code" not in existing:
            migrations.append("ALTER TABLE integration_sync_jobs ADD COLUMN last_error_code TEXT")
        if "attempt_count" not in existing:
            migrations.append(
                "ALTER TABLE integration_sync_jobs ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0"
            )
        if "max_attempts" not in existing:
            migrations.append(
                "ALTER TABLE integration_sync_jobs ADD COLUMN max_attempts INTEGER NOT NULL DEFAULT 3"
            )
        if "next_retry_at" not in existing:
            migrations.append("ALTER TABLE integration_sync_jobs ADD COLUMN next_retry_at INTEGER")
        if "dead_lettered_at" not in existing:
            migrations.append("ALTER TABLE integration_sync_jobs ADD COLUMN dead_lettered_at INTEGER")

        for statement in migrations:
            self._conn.execute(statement)

    def create_connector(
        self,
        *,
        company_name: str,
        connector_type: str,
        provider: str,
        base_url: str | None,
        auth_mode: str,
        config: dict[str, object],
        mapping: dict[str, str],
        status: str,
        readiness_score: float,
        mapping_coverage_score: float,
        security_score: float,
        created_by: str | None,
    ) -> dict[str, Any]:
        now = int(time.time())
        with self._lock:
            cursor = self._conn.execute(
                """
                INSERT INTO integration_connectors(
                    company_name,
                    connector_type,
                    provider,
                    base_url,
                    auth_mode,
                    config_json,
                    mapping_json,
                    status,
                    readiness_score,
                    mapping_coverage_score,
                    security_score,
                    created_by,
                    created_at,
                    updated_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    company_name,
                    connector_type,
                    provider,
                    base_url,
                    auth_mode,
                    json.dumps(config, separators=(",", ":"), ensure_ascii=True),
                    json.dumps(mapping, separators=(",", ":"), ensure_ascii=True),
                    status,
                    readiness_score,
                    mapping_coverage_score,
                    security_score,
                    created_by,
                    now,
                    now,
                ),
            )
            connector_id = new_row_id(cursor)
            self._conn.commit()

        row = self.get_connector(connector_id)
        if row is None:
            raise RuntimeError("Connector creation failed")
        return row

    def get_connector(self, connector_id: int) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT
                    id,
                    company_name,
                    connector_type,
                    provider,
                    base_url,
                    auth_mode,
                    config_json,
                    mapping_json,
                    status,
                    readiness_score,
                    mapping_coverage_score,
                    security_score,
                    created_by,
                    created_at,
                    updated_at,
                    last_sync_at
                FROM integration_connectors
                WHERE id = ?
                """,
                (connector_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_connector_by_signature(
        self,
        *,
        company_name: str,
        connector_type: str,
        provider: str,
    ) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT
                    id,
                    company_name,
                    connector_type,
                    provider,
                    base_url,
                    auth_mode,
                    config_json,
                    mapping_json,
                    status,
                    readiness_score,
                    mapping_coverage_score,
                    security_score,
                    created_by,
                    created_at,
                    updated_at,
                    last_sync_at
                FROM integration_connectors
                WHERE company_name = ? AND connector_type = ? AND provider = ?
                """,
                (company_name, connector_type, provider),
            ).fetchone()
            return dict(row) if row else None

    def list_connectors(
        self,
        *,
        company_name: str | None = None,
        status: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 1000))
        sql = """
            SELECT
                id,
                company_name,
                connector_type,
                provider,
                base_url,
                auth_mode,
                config_json,
                mapping_json,
                status,
                readiness_score,
                mapping_coverage_score,
                security_score,
                created_by,
                created_at,
                updated_at,
                last_sync_at
            FROM integration_connectors
            WHERE 1=1
        """
        params: list[Any] = []
        if company_name:
            sql += " AND company_name = ?"
            params.append(company_name)
        if status:
            sql += " AND status = ?"
            params.append(status)

        sql += " ORDER BY id ASC LIMIT ?"
        params.append(safe_limit)

        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def create_sync_job(
        self,
        *,
        connector_id: int,
        trigger_mode: str,
        priority_score: float,
        max_attempts: int,
        requested_by: str | None,
        request_payload: dict[str, object],
    ) -> dict[str, Any]:
        now = int(time.time())
        with self._lock:
            cursor = self._conn.execute(
                """
                INSERT INTO integration_sync_jobs(
                    connector_id,
                    trigger_mode,
                    priority_score,
                    max_attempts,
                    status,
                    requested_by,
                    request_payload_json,
                    requested_at
                )
                VALUES(?, ?, ?, ?, 'queued', ?, ?, ?)
                """,
                (
                    connector_id,
                    trigger_mode,
                    priority_score,
                    max_attempts,
                    requested_by,
                    json.dumps(request_payload, separators=(",", ":"), ensure_ascii=True),
                    now,
                ),
            )
            job_id = new_row_id(cursor)
            self._conn.commit()

        row = self.get_sync_job(job_id)
        if row is None:
            raise RuntimeError("Sync job creation failed")
        return row

    def get_sync_job(self, job_id: int) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT
                    j.id,
                    j.connector_id,
                    c.company_name,
                    c.connector_type,
                    c.provider,
                    j.trigger_mode,
                    j.priority_score,
                    j.status,
                    j.requested_by,
                    j.request_payload_json,
                    j.result_summary,
                    j.error_message,
                    j.last_error_code,
                    j.attempt_count,
                    j.max_attempts,
                    j.requested_at,
                    j.next_retry_at,
                    j.dead_lettered_at,
                    j.started_at,
                    j.finished_at
                FROM integration_sync_jobs j
                JOIN integration_connectors c ON c.id = j.connector_id
                WHERE j.id = ?
                """,
                (job_id,),
            ).fetchone()
            return dict(row) if row else None

    def list_sync_jobs(
        self,
        *,
        connector_id: int | None = None,
        company_name: str | None = None,
        status: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 2000))
        sql = """
            SELECT
                j.id,
                j.connector_id,
                c.company_name,
                c.connector_type,
                c.provider,
                j.trigger_mode,
                j.priority_score,
                j.status,
                j.requested_by,
                j.request_payload_json,
                j.result_summary,
                j.error_message,
                j.last_error_code,
                j.attempt_count,
                j.max_attempts,
                j.requested_at,
                j.next_retry_at,
                j.dead_lettered_at,
                j.started_at,
                j.finished_at
            FROM integration_sync_jobs j
            JOIN integration_connectors c ON c.id = j.connector_id
            WHERE 1=1
        """
        params: list[Any] = []
        if connector_id is not None:
            sql += " AND j.connector_id = ?"
            params.append(connector_id)
        if company_name:
            sql += " AND c.company_name = ?"
            params.append(company_name)
        if status:
            sql += " AND j.status = ?"
            params.append(status)

        sql += " ORDER BY j.priority_score DESC, j.requested_at ASC LIMIT ?"
        params.append(safe_limit)

        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def claim_next_sync_job(self, *, allowed_company_names: list[str] | None = None) -> dict[str, Any] | None:
        now = int(time.time())
        with self._lock:
            sql = """
                SELECT j.id
                FROM integration_sync_jobs j
                JOIN integration_connectors c ON c.id = j.connector_id
                WHERE j.status = 'queued'
                  AND (j.next_retry_at IS NULL OR j.next_retry_at <= ?)
            """
            params: list[Any] = [now]
            if allowed_company_names:
                placeholders = ",".join("?" for _ in allowed_company_names)
                sql += f" AND c.company_name IN ({placeholders})"
                params.extend(allowed_company_names)
            sql += " ORDER BY j.priority_score DESC, j.requested_at ASC LIMIT 1"

            row = self._conn.execute(sql, params).fetchone()
            if row is None:
                return None

            job_id = int(row["id"])
            self._conn.execute(
                """
                UPDATE integration_sync_jobs
                SET status = 'running',
                    started_at = ?,
                    attempt_count = attempt_count + 1,
                    next_retry_at = NULL
                WHERE id = ?
                """,
                (now, job_id),
            )
            self._conn.commit()

        return self.get_sync_job(job_id)

    def complete_sync_job(
        self,
        *,
        job_id: int,
        status: str,
        result_summary: str,
        error_message: str | None = None,
        error_code: str | None = None,
    ) -> dict[str, Any]:
        finished_at = int(time.time())
        dead_lettered_at = finished_at if status == "dead_letter" else None
        with self._lock:
            self._conn.execute(
                """
                UPDATE integration_sync_jobs
                SET status = ?,
                    result_summary = ?,
                    error_message = ?,
                    last_error_code = ?,
                    dead_lettered_at = ?,
                    finished_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    result_summary,
                    error_message,
                    error_code,
                    dead_lettered_at,
                    finished_at,
                    job_id,
                ),
            )
            self._conn.commit()
        row = self.get_sync_job(job_id)
        if row is None:
            raise ValueError("Sync job not found")
        return row

    def fail_or_retry_sync_job(
        self,
        *,
        job_id: int,
        error_message: str,
        error_code: str | None,
        retry_backoff_seconds: int,
        max_retries_default: int,
    ) -> dict[str, Any]:
        now = int(time.time())
        with self._lock:
            row = self._conn.execute(
                """
                SELECT id, attempt_count, max_attempts
                FROM integration_sync_jobs
                WHERE id = ?
                """,
                (job_id,),
            ).fetchone()
            if row is None:
                raise ValueError("Sync job not found")

            attempt_count = int(row["attempt_count"])
            max_attempts = int(row["max_attempts"] or max_retries_default)
            if max_attempts <= 0:
                max_attempts = max_retries_default

            should_retry = attempt_count < max_attempts
            if should_retry:
                next_retry_at = now + max(5, retry_backoff_seconds)
                summary = (
                    f"Retry scheduled after failure. attempt={attempt_count}/{max_attempts}, "
                    f"next_retry_at={next_retry_at}"
                )
                self._conn.execute(
                    """
                    UPDATE integration_sync_jobs
                    SET status = 'queued',
                        result_summary = ?,
                        error_message = ?,
                        last_error_code = ?,
                        next_retry_at = ?,
                        started_at = NULL,
                        finished_at = NULL
                    WHERE id = ?
                    """,
                    (
                        summary,
                        error_message,
                        error_code,
                        next_retry_at,
                        job_id,
                    ),
                )
            else:
                summary = (
                    f"Moved to dead_letter after retries exhausted. "
                    f"attempt={attempt_count}/{max_attempts}"
                )
                self._conn.execute(
                    """
                    UPDATE integration_sync_jobs
                    SET status = 'dead_letter',
                        result_summary = ?,
                        error_message = ?,
                        last_error_code = ?,
                        dead_lettered_at = ?,
                        finished_at = ?
                    WHERE id = ?
                    """,
                    (
                        summary,
                        error_message,
                        error_code,
                        now,
                        now,
                        job_id,
                    ),
                )
            self._conn.commit()

        result = self.get_sync_job(job_id)
        if result is None:
            raise ValueError("Sync job not found")
        return result

    def queue_health(self, *, company_name: str | None = None) -> dict[str, Any]:
        now = int(time.time())
        with self._lock:
            connector_sql = """
                SELECT status, readiness_score, security_score
                FROM integration_connectors
                WHERE 1=1
            """
            connector_params: list[Any] = []
            if company_name:
                connector_sql += " AND company_name = ?"
                connector_params.append(company_name)
            connector_rows = self._conn.execute(connector_sql, connector_params).fetchall()

            job_sql = """
                SELECT j.status, j.next_retry_at
                FROM integration_sync_jobs j
                JOIN integration_connectors c ON c.id = j.connector_id
                WHERE 1=1
            """
            job_params: list[Any] = []
            if company_name:
                job_sql += " AND c.company_name = ?"
                job_params.append(company_name)
            job_rows = self._conn.execute(job_sql, job_params).fetchall()

        connector_status_counts = {"active": 0, "staged": 0, "blocked": 0}
        readiness_total = 0.0
        security_total = 0.0
        for row in connector_rows:
            status = str(row["status"])
            if status in connector_status_counts:
                connector_status_counts[status] += 1
            readiness_total += float(row["readiness_score"] or 0)
            security_total += float(row["security_score"] or 0)

        job_status_counts = {
            "queued": 0,
            "running": 0,
            "success": 0,
            "failed": 0,
            "dead_letter": 0,
        }
        due_retry_jobs = 0
        for row in job_rows:
            status = str(row["status"])
            if status in job_status_counts:
                job_status_counts[status] += 1
            if status == "queued":
                next_retry_at = row["next_retry_at"]
                if next_retry_at is None or int(next_retry_at) <= now:
                    due_retry_jobs += 1

        total_connectors = len(connector_rows)
        avg_readiness = round(readiness_total / total_connectors, 2) if total_connectors > 0 else 0.0
        avg_security = round(security_total / total_connectors, 2) if total_connectors > 0 else 0.0
        return {
            "total_connectors": total_connectors,
            "active_connectors": connector_status_counts["active"],
            "staged_connectors": connector_status_counts["staged"],
            "blocked_connectors": connector_status_counts["blocked"],
            "queued_jobs": job_status_counts["queued"],
            "running_jobs": job_status_counts["running"],
            "success_jobs": job_status_counts["success"],
            "failed_jobs": job_status_counts["failed"],
            "dead_letter_jobs": job_status_counts["dead_letter"],
            "due_retry_jobs": due_retry_jobs,
            "average_readiness_score": avg_readiness,
            "average_security_score": avg_security,
        }

    def mark_connector_synced(self, connector_id: int, *, health_score: float, status: str) -> None:
        now = int(time.time())
        with self._lock:
            self._conn.execute(
                """
                UPDATE integration_connectors
                SET status = ?, security_score = ?, last_sync_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, health_score, now, now, connector_id),
            )
            self._conn.commit()

    def acquire_worker_lease(
        self,
        *,
        worker_name: str,
        owner_id: str,
        lease_seconds: int,
    ) -> bool:
        now = int(time.time())
        expires_at = now + max(5, lease_seconds)
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO integration_worker_leases(
                    worker_name,
                    owner_id,
                    acquired_at,
                    heartbeat_at,
                    expires_at
                )
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(worker_name) DO UPDATE SET
                    owner_id = excluded.owner_id,
                    acquired_at = CASE
                        WHEN integration_worker_leases.owner_id = excluded.owner_id
                        THEN integration_worker_leases.acquired_at
                        ELSE excluded.acquired_at
                    END,
                    heartbeat_at = excluded.heartbeat_at,
                    expires_at = excluded.expires_at
                WHERE integration_worker_leases.expires_at <= ?
                   OR integration_worker_leases.owner_id = excluded.owner_id
                """,
                (
                    worker_name,
                    owner_id,
                    now,
                    now,
                    expires_at,
                    now,
                ),
            )
            row = self._conn.execute(
                """
                SELECT owner_id, expires_at
                FROM integration_worker_leases
                WHERE worker_name = ?
                """,
                (worker_name,),
            ).fetchone()
            self._conn.commit()

        if row is None:
            return False
        return str(row["owner_id"]) == owner_id and int(row["expires_at"]) > now

    def renew_worker_lease(
        self,
        *,
        worker_name: str,
        owner_id: str,
        lease_seconds: int,
    ) -> bool:
        now = int(time.time())
        expires_at = now + max(5, lease_seconds)
        with self._lock:
            cursor = self._conn.execute(
                """
                UPDATE integration_worker_leases
                SET heartbeat_at = ?, expires_at = ?
                WHERE worker_name = ?
                  AND owner_id = ?
                  AND expires_at > ?
                """,
                (
                    now,
                    expires_at,
                    worker_name,
                    owner_id,
                    now,
                ),
            )
            self._conn.commit()
            return cursor.rowcount > 0

    def release_worker_lease(self, *, worker_name: str, owner_id: str) -> None:
        with self._lock:
            self._conn.execute(
                """
                DELETE FROM integration_worker_leases
                WHERE worker_name = ? AND owner_id = ?
                """,
                (worker_name, owner_id),
            )
            self._conn.commit()

    def get_worker_lease(self, *, worker_name: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT worker_name, owner_id, acquired_at, heartbeat_at, expires_at
                FROM integration_worker_leases
                WHERE worker_name = ?
                """,
                (worker_name,),
            ).fetchone()
            return dict(row) if row else None
