from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Any
import sqlite3

from app._sqlite_helpers import new_row_id
import time


class HoldingRepository:
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
            CREATE TABLE IF NOT EXISTS holdings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                code TEXT UNIQUE,
                description TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'active',
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS holding_companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                holding_id INTEGER NOT NULL,
                company_name TEXT NOT NULL,
                sector TEXT NOT NULL DEFAULT 'General',
                country TEXT NOT NULL DEFAULT 'TR',
                registered_in_platform INTEGER NOT NULL DEFAULT 0,
                data_quality_score REAL NOT NULL,
                integration_completeness_score REAL NOT NULL,
                security_compliance_score REAL NOT NULL,
                process_standardization_score REAL NOT NULL,
                master_data_health_score REAL NOT NULL,
                team_readiness_score REAL NOT NULL,
                onboarding_readiness_score REAL NOT NULL,
                onboarding_status TEXT NOT NULL,
                recommendation TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                UNIQUE(holding_id, company_name),
                FOREIGN KEY(holding_id) REFERENCES holdings(id) ON DELETE CASCADE
            )
            """
        )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_holding_companies_holding_id
            ON holding_companies(holding_id)
            """
        )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_holding_companies_company_name
            ON holding_companies(company_name)
            """
        )
        self._conn.commit()

    def create_holding(
        self,
        *,
        name: str,
        code: str | None,
        description: str,
        status: str,
    ) -> dict[str, Any]:
        now = int(time.time())
        with self._lock:
            cursor = self._conn.execute(
                """
                INSERT INTO holdings(name, code, description, status, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                (name, code, description, status, now, now),
            )
            holding_id = new_row_id(cursor)
            self._conn.commit()
        row = self.get_holding(holding_id)
        if row is None:
            raise RuntimeError("Holding creation failed")
        return row

    def get_holding(self, holding_id: int) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT id, name, code, description, status, created_at, updated_at
                FROM holdings
                WHERE id = ?
                """,
                (holding_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_holding_by_name(self, name: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT id, name, code, description, status, created_at, updated_at
                FROM holdings
                WHERE name = ?
                """,
                (name,),
            ).fetchone()
            return dict(row) if row else None

    def list_holdings(self, limit: int = 200) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 1000))
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT id, name, code, description, status, created_at, updated_at
                FROM holdings
                ORDER BY id ASC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def upsert_holding_company(
        self,
        *,
        holding_id: int,
        company_name: str,
        sector: str,
        country: str,
        registered_in_platform: bool,
        data_quality_score: float,
        integration_completeness_score: float,
        security_compliance_score: float,
        process_standardization_score: float,
        master_data_health_score: float,
        team_readiness_score: float,
        onboarding_readiness_score: float,
        onboarding_status: str,
        recommendation: str,
        notes: str,
    ) -> dict[str, Any]:
        now = int(time.time())
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO holding_companies(
                    holding_id,
                    company_name,
                    sector,
                    country,
                    registered_in_platform,
                    data_quality_score,
                    integration_completeness_score,
                    security_compliance_score,
                    process_standardization_score,
                    master_data_health_score,
                    team_readiness_score,
                    onboarding_readiness_score,
                    onboarding_status,
                    recommendation,
                    notes,
                    created_at,
                    updated_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(holding_id, company_name)
                DO UPDATE SET
                    sector = excluded.sector,
                    country = excluded.country,
                    registered_in_platform = excluded.registered_in_platform,
                    data_quality_score = excluded.data_quality_score,
                    integration_completeness_score = excluded.integration_completeness_score,
                    security_compliance_score = excluded.security_compliance_score,
                    process_standardization_score = excluded.process_standardization_score,
                    master_data_health_score = excluded.master_data_health_score,
                    team_readiness_score = excluded.team_readiness_score,
                    onboarding_readiness_score = excluded.onboarding_readiness_score,
                    onboarding_status = excluded.onboarding_status,
                    recommendation = excluded.recommendation,
                    notes = excluded.notes,
                    updated_at = excluded.updated_at
                """,
                (
                    holding_id,
                    company_name,
                    sector,
                    country,
                    1 if registered_in_platform else 0,
                    data_quality_score,
                    integration_completeness_score,
                    security_compliance_score,
                    process_standardization_score,
                    master_data_health_score,
                    team_readiness_score,
                    onboarding_readiness_score,
                    onboarding_status,
                    recommendation,
                    notes,
                    now,
                    now,
                ),
            )
            self._conn.commit()

            row = self._conn.execute(
                """
                SELECT
                    id,
                    holding_id,
                    company_name,
                    sector,
                    country,
                    registered_in_platform,
                    data_quality_score,
                    integration_completeness_score,
                    security_compliance_score,
                    process_standardization_score,
                    master_data_health_score,
                    team_readiness_score,
                    onboarding_readiness_score,
                    onboarding_status,
                    recommendation,
                    notes,
                    created_at,
                    updated_at
                FROM holding_companies
                WHERE holding_id = ? AND company_name = ?
                """,
                (holding_id, company_name),
            ).fetchone()
        if row is None:
            raise RuntimeError("Holding company upsert failed")
        return dict(row)

    def list_holding_companies(self, holding_id: int, limit: int = 1000) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 5000))
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT
                    id,
                    holding_id,
                    company_name,
                    sector,
                    country,
                    registered_in_platform,
                    data_quality_score,
                    integration_completeness_score,
                    security_compliance_score,
                    process_standardization_score,
                    master_data_health_score,
                    team_readiness_score,
                    onboarding_readiness_score,
                    onboarding_status,
                    recommendation,
                    notes,
                    created_at,
                    updated_at
                FROM holding_companies
                WHERE holding_id = ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (holding_id, safe_limit),
            ).fetchall()
        return [dict(row) for row in rows]
