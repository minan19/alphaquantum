from __future__ import annotations

import json
from threading import Lock
from typing import Any
import sqlite3
import time


class FeasibilityRepository:
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

    def create_report(
        self,
        *,
        project_name: str,
        sector: str,
        geography: str,
        company_name: str = "",
        payload: dict[str, Any],
        report: dict[str, Any],
        status: str = "generated",
    ) -> dict[str, Any]:
        now = int(time.time())
        payload_json = json.dumps(payload, ensure_ascii=True)
        report_json = json.dumps(report, ensure_ascii=True)

        with self._lock:
            cursor = self._conn.execute(
                """
                INSERT INTO feasibility_reports(
                    project_name,
                    sector,
                    geography,
                    company_name,
                    status,
                    payload_json,
                    report_json,
                    created_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_name,
                    sector,
                    geography,
                    company_name,
                    status,
                    payload_json,
                    report_json,
                    now,
                ),
            )
            report_id = int(cursor.lastrowid)
            self._conn.commit()

        return self.get_report(report_id)

    def list_reports(
        self,
        *,
        limit: int = 100,
        sector: str | None = None,
        company_name: str | None = None,
    ) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 500))
        conditions: list[str] = []
        params_list: list[Any] = []

        if sector:
            conditions.append("sector = ?")
            params_list.append(sector)
        if company_name is not None:
            conditions.append("company_name = ?")
            params_list.append(company_name)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params_list.append(safe_limit)
        query = f"""
            SELECT
                id,
                project_name,
                sector,
                geography,
                company_name,
                status,
                created_at,
                report_json
            FROM feasibility_reports
            {where_clause}
            ORDER BY created_at DESC, id DESC
            LIMIT ?
        """

        with self._lock:
            rows = self._conn.execute(query, tuple(params_list)).fetchall()

        output: list[dict[str, Any]] = []
        for row in rows:
            report = _parse_json_dict(row["report_json"])
            output.append(
                {
                    "id": int(row["id"]),
                    "project_name": str(row["project_name"]),
                    "sector": str(row["sector"]),
                    "geography": str(row["geography"]),
                    "company_name": str(row["company_name"]),
                    "status": str(row["status"]),
                    "created_at": int(row["created_at"]),
                    "recommendation": str(report.get("recommendation") or "N/A"),
                    "confidence": float(report.get("confidence") or 0.0),
                    "npv": float(report.get("financial_metrics", {}).get("npv") or 0.0),
                }
            )
        return output

    def get_report(self, report_id: int) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT
                    id,
                    project_name,
                    sector,
                    geography,
                    company_name,
                    status,
                    payload_json,
                    report_json,
                    created_at
                FROM feasibility_reports
                WHERE id = ?
                """,
                (report_id,),
            ).fetchone()

        if row is None:
            raise ValueError("Feasibility report not found")

        payload = _parse_json_dict(row["payload_json"])
        report = _parse_json_dict(row["report_json"])
        return {
            "id": int(row["id"]),
            "project_name": str(row["project_name"]),
            "sector": str(row["sector"]),
            "geography": str(row["geography"]),
            "company_name": str(row["company_name"]),
            "status": str(row["status"]),
            "payload": payload,
            "report": report,
            "created_at": int(row["created_at"]),
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
