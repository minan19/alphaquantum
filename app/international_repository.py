from __future__ import annotations

import json
from threading import Lock
from typing import Any
import sqlite3
import time


class InternationalProjectRepository:
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

    def create_project(
        self,
        *,
        project_name: str,
        company_name: str,
        base_country: str,
        target_countries: list[str],
        services: list[str],
        budget_total: float,
        currency: str,
        timeline_months: int,
        payload: dict[str, Any],
        report: dict[str, Any],
        status: str = "generated",
    ) -> dict[str, Any]:
        now = int(time.time())
        target_countries_json = json.dumps(target_countries, ensure_ascii=True)
        services_json = json.dumps(services, ensure_ascii=True)
        payload_json = json.dumps(payload, ensure_ascii=True)
        report_json = json.dumps(report, ensure_ascii=True)

        with self._lock:
            cursor = self._conn.execute(
                """
                INSERT INTO international_projects(
                    project_name,
                    company_name,
                    base_country,
                    target_countries_json,
                    services_json,
                    budget_total,
                    currency,
                    timeline_months,
                    status,
                    payload_json,
                    report_json,
                    created_at,
                    updated_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_name,
                    company_name,
                    base_country,
                    target_countries_json,
                    services_json,
                    budget_total,
                    currency,
                    timeline_months,
                    status,
                    payload_json,
                    report_json,
                    now,
                    now,
                ),
            )
            project_id = int(cursor.lastrowid)
            self._conn.commit()

        return self.get_project(project_id)

    def list_projects(
        self,
        *,
        limit: int = 100,
        status: str | None = None,
        country: str | None = None,
    ) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 500))
        base_query = """
            SELECT
                id,
                project_name,
                company_name,
                base_country,
                target_countries_json,
                services_json,
                status,
                report_json,
                created_at,
                updated_at
            FROM international_projects
        """
        normalized_country = country.strip().upper() if country else None
        if status and normalized_country:
            query = (
                base_query
                + """
                WHERE status = ?
                  AND (base_country = ? OR target_countries_json LIKE ?)
                ORDER BY updated_at DESC, id DESC
                LIMIT ?
                """
            )
            params: tuple[Any, ...] = (
                status,
                normalized_country,
                f'%"{normalized_country}"%',
                safe_limit,
            )
        elif status:
            query = (
                base_query
                + """
                WHERE status = ?
                ORDER BY updated_at DESC, id DESC
                LIMIT ?
                """
            )
            params = (status, safe_limit)
        elif normalized_country:
            query = (
                base_query
                + """
                WHERE base_country = ? OR target_countries_json LIKE ?
                ORDER BY updated_at DESC, id DESC
                LIMIT ?
                """
            )
            params = (
                normalized_country,
                f'%"{normalized_country}"%',
                safe_limit,
            )
        else:
            query = (
                base_query
                + """
                ORDER BY updated_at DESC, id DESC
                LIMIT ?
                """
            )
            params = (safe_limit,)

        with self._lock:
            rows = self._conn.execute(query, params).fetchall()

        output: list[dict[str, Any]] = []
        for row in rows:
            report = _parse_json_dict(row["report_json"])
            target_countries = _parse_json_list(row["target_countries_json"])
            services = _parse_json_list(row["services_json"])
            output.append(
                {
                    "id": int(row["id"]),
                    "project_name": str(row["project_name"]),
                    "company_name": str(row["company_name"]),
                    "base_country": str(row["base_country"]),
                    "target_country_count": len(target_countries),
                    "services": services,
                    "status": str(row["status"]),
                    "recommendation": str(report.get("recommendation") or "N/A"),
                    "confidence": float(report.get("confidence") or 0.0),
                    "created_at": int(row["created_at"]),
                    "updated_at": int(row["updated_at"]),
                }
            )
        return output

    def get_project(self, project_id: int) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT
                    id,
                    project_name,
                    company_name,
                    base_country,
                    target_countries_json,
                    services_json,
                    budget_total,
                    currency,
                    timeline_months,
                    status,
                    payload_json,
                    report_json,
                    created_at,
                    updated_at
                FROM international_projects
                WHERE id = ?
                """,
                (project_id,),
            ).fetchone()

        if row is None:
            raise ValueError("International project not found")

        return {
            "id": int(row["id"]),
            "project_name": str(row["project_name"]),
            "company_name": str(row["company_name"]),
            "base_country": str(row["base_country"]),
            "target_countries": _parse_json_list(row["target_countries_json"]),
            "services": _parse_json_list(row["services_json"]),
            "budget_total": float(row["budget_total"]),
            "currency": str(row["currency"]),
            "timeline_months": int(row["timeline_months"]),
            "status": str(row["status"]),
            "payload": _parse_json_dict(row["payload_json"]),
            "report": _parse_json_dict(row["report_json"]),
            "created_at": int(row["created_at"]),
            "updated_at": int(row["updated_at"]),
        }


def _parse_json_dict(raw: Any) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        value = json.loads(str(raw))
    except (TypeError, ValueError):
        return {}
    if isinstance(value, dict):
        return value
    return {}


def _parse_json_list(raw: Any) -> list[str]:
    if not raw:
        return []
    try:
        value = json.loads(str(raw))
    except (TypeError, ValueError):
        return []
    if not isinstance(value, list):
        return []
    output: list[str] = []
    for item in value:
        normalized = str(item).strip()
        if normalized:
            output.append(normalized)
    return output
