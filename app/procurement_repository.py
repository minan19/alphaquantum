from __future__ import annotations

import json
from threading import Lock
from typing import Any
import sqlite3

from app._sqlite_helpers import new_row_id
import time


class ProcurementRepository:
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

    def create_request(
        self,
        *,
        company_name: str,
        title: str,
        strategy: str,
        budget_limit: float | None,
        currency: str,
        tender_reference: str | None,
        tender_requirements: list[str],
        items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        now = int(time.time())
        requirements_json = json.dumps(tender_requirements, ensure_ascii=True)

        with self._lock:
            cursor = self._conn.execute(
                """
                INSERT INTO procurement_requests(
                    company_name,
                    title,
                    strategy,
                    budget_limit,
                    currency,
                    tender_reference,
                    tender_requirements,
                    status,
                    created_at,
                    updated_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)
                """,
                (
                    company_name,
                    title,
                    strategy,
                    budget_limit,
                    currency,
                    tender_reference,
                    requirements_json,
                    now,
                    now,
                ),
            )
            request_id = new_row_id(cursor)

            for item in items:
                self._conn.execute(
                    """
                    INSERT INTO procurement_request_items(
                        request_id,
                        item_name,
                        specification,
                        quantity,
                        min_quality_score,
                        max_unit_price,
                        required_by_date,
                        must_comply_tender,
                        created_at
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        request_id,
                        str(item["item_name"]),
                        str(item.get("specification") or ""),
                        int(item["quantity"]),
                        float(item.get("min_quality_score") or 0),
                        _to_nullable_float(item.get("max_unit_price")),
                        item.get("required_by_date"),
                        1 if bool(item.get("must_comply_tender")) else 0,
                        now,
                    ),
                )
            self._conn.commit()

        return self.get_request(request_id)

    def list_requests(self, *, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 500))
        if status:
            query = """
                SELECT
                    id,
                    company_name,
                    title,
                    strategy,
                    budget_limit,
                    currency,
                    tender_reference,
                    tender_requirements,
                    status,
                    created_at,
                    updated_at
                FROM procurement_requests
                WHERE status = ?
                ORDER BY updated_at DESC, id DESC
                LIMIT ?
            """
            params: tuple[Any, ...] = (status, safe_limit)
        else:
            query = """
                SELECT
                    id,
                    company_name,
                    title,
                    strategy,
                    budget_limit,
                    currency,
                    tender_reference,
                    tender_requirements,
                    status,
                    created_at,
                    updated_at
                FROM procurement_requests
                ORDER BY updated_at DESC, id DESC
                LIMIT ?
            """
            params = (safe_limit,)

        with self._lock:
            rows = self._conn.execute(query, params).fetchall()

        request_rows = [self._row_to_request_header(dict(row)) for row in rows]
        item_map = self._list_items_for_request_ids([int(row["id"]) for row in request_rows])
        for row in request_rows:
            row["items"] = item_map.get(int(row["id"]), [])
        return request_rows

    def get_request(self, request_id: int) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT
                    id,
                    company_name,
                    title,
                    strategy,
                    budget_limit,
                    currency,
                    tender_reference,
                    tender_requirements,
                    status,
                    created_at,
                    updated_at
                FROM procurement_requests
                WHERE id = ?
                """,
                (request_id,),
            ).fetchone()
            if row is None:
                raise ValueError("Procurement request not found")

            item_rows = self._conn.execute(
                """
                SELECT
                    id,
                    request_id,
                    item_name,
                    specification,
                    quantity,
                    min_quality_score,
                    max_unit_price,
                    required_by_date,
                    must_comply_tender
                FROM procurement_request_items
                WHERE request_id = ?
                ORDER BY id ASC
                """,
                (request_id,),
            ).fetchall()

        request = self._row_to_request_header(dict(row))
        request["items"] = [self._row_to_request_item(dict(item_row)) for item_row in item_rows]
        return request

    def create_vendor_quote(
        self,
        *,
        request_id: int,
        vendor_name: str,
        vendor_rating: float,
        delivery_days: int,
        warranty_months: int,
        compliance_score: float,
        status: str,
        quote_items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        now = int(time.time())
        with self._lock:
            request_row = self._conn.execute(
                "SELECT id FROM procurement_requests WHERE id = ?",
                (request_id,),
            ).fetchone()
            if request_row is None:
                raise ValueError("Procurement request not found")

            valid_item_rows = self._conn.execute(
                "SELECT id FROM procurement_request_items WHERE request_id = ?",
                (request_id,),
            ).fetchall()
            valid_item_ids = {int(row["id"]) for row in valid_item_rows}

            cursor = self._conn.execute(
                """
                INSERT INTO procurement_vendor_quotes(
                    request_id,
                    vendor_name,
                    vendor_rating,
                    delivery_days,
                    warranty_months,
                    compliance_score,
                    status,
                    created_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    vendor_name,
                    vendor_rating,
                    delivery_days,
                    warranty_months,
                    compliance_score,
                    status,
                    now,
                ),
            )
            quote_id = new_row_id(cursor)

            for item in quote_items:
                request_item_id = int(item["request_item_id"])
                if request_item_id not in valid_item_ids:
                    raise ValueError(f"Request item {request_item_id} does not belong to request {request_id}")

                self._conn.execute(
                    """
                    INSERT INTO procurement_quote_items(
                        quote_id,
                        request_item_id,
                        unit_price,
                        available_quantity,
                        quality_score,
                        brand,
                        model,
                        note
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        quote_id,
                        request_item_id,
                        float(item["unit_price"]),
                        int(item["available_quantity"]),
                        float(item["quality_score"]),
                        str(item.get("brand") or ""),
                        str(item.get("model") or ""),
                        str(item.get("note") or ""),
                    ),
                )

            self._conn.execute(
                "UPDATE procurement_requests SET updated_at = ? WHERE id = ?",
                (now, request_id),
            )
            self._conn.commit()

        return self.get_vendor_quote(quote_id)

    def list_vendor_quotes(self, request_id: int) -> list[dict[str, Any]]:
        with self._lock:
            request_row = self._conn.execute(
                "SELECT id FROM procurement_requests WHERE id = ?",
                (request_id,),
            ).fetchone()
            if request_row is None:
                raise ValueError("Procurement request not found")

            rows = self._conn.execute(
                """
                SELECT
                    id,
                    request_id,
                    vendor_name,
                    vendor_rating,
                    delivery_days,
                    warranty_months,
                    compliance_score,
                    status,
                    created_at
                FROM procurement_vendor_quotes
                WHERE request_id = ?
                ORDER BY id ASC
                """,
                (request_id,),
            ).fetchall()

        quotes = [dict(row) for row in rows]
        quote_item_map = self._list_quote_items_for_quote_ids([int(row["id"]) for row in quotes])
        normalized: list[dict[str, Any]] = []
        for row in quotes:
            quote = self._row_to_quote_header(row)
            quote["items"] = quote_item_map.get(int(row["id"]), [])
            normalized.append(quote)
        return normalized

    def get_vendor_quote(self, quote_id: int) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT
                    id,
                    request_id,
                    vendor_name,
                    vendor_rating,
                    delivery_days,
                    warranty_months,
                    compliance_score,
                    status,
                    created_at
                FROM procurement_vendor_quotes
                WHERE id = ?
                """,
                (quote_id,),
            ).fetchone()
            if row is None:
                raise ValueError("Vendor quote not found")

            item_rows = self._conn.execute(
                """
                SELECT
                    id,
                    quote_id,
                    request_item_id,
                    unit_price,
                    available_quantity,
                    quality_score,
                    brand,
                    model,
                    note
                FROM procurement_quote_items
                WHERE quote_id = ?
                ORDER BY request_item_id ASC
                """,
                (quote_id,),
            ).fetchall()

        quote = self._row_to_quote_header(dict(row))
        quote["items"] = [self._row_to_quote_item(dict(item_row)) for item_row in item_rows]
        return quote

    def list_quote_candidates(self, request_id: int) -> list[dict[str, Any]]:
        with self._lock:
            request_row = self._conn.execute(
                "SELECT id FROM procurement_requests WHERE id = ?",
                (request_id,),
            ).fetchone()
            if request_row is None:
                raise ValueError("Procurement request not found")

            rows = self._conn.execute(
                """
                SELECT
                    i.id AS request_item_id,
                    i.item_name,
                    i.specification,
                    i.quantity AS required_quantity,
                    i.min_quality_score,
                    i.max_unit_price,
                    i.required_by_date,
                    i.must_comply_tender,
                    q.id AS quote_id,
                    q.vendor_name,
                    q.vendor_rating,
                    q.delivery_days,
                    q.warranty_months,
                    q.compliance_score,
                    qi.id AS quote_item_id,
                    qi.unit_price,
                    qi.available_quantity,
                    qi.quality_score,
                    qi.brand,
                    qi.model,
                    qi.note
                FROM procurement_request_items i
                JOIN procurement_vendor_quotes q ON q.request_id = i.request_id
                JOIN procurement_quote_items qi
                    ON qi.quote_id = q.id
                   AND qi.request_item_id = i.id
                WHERE i.request_id = ?
                ORDER BY i.id ASC, q.id ASC
                """,
                (request_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_purchase_orders(
        self,
        *,
        request_id: int,
        currency: str,
        orders: list[dict[str, Any]],
        mark_as_ordered: bool = True,
    ) -> list[dict[str, Any]]:
        now = int(time.time())
        with self._lock:
            request_row = self._conn.execute(
                "SELECT id FROM procurement_requests WHERE id = ?",
                (request_id,),
            ).fetchone()
            if request_row is None:
                raise ValueError("Procurement request not found")

            for order in orders:
                cursor = self._conn.execute(
                    """
                    INSERT INTO procurement_purchase_orders(
                        request_id,
                        vendor_name,
                        currency,
                        total_amount,
                        status,
                        created_at,
                        approved_at
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        request_id,
                        str(order["vendor_name"]),
                        currency,
                        float(order["total_amount"]),
                        str(order["status"]),
                        now,
                        order.get("approved_at"),
                    ),
                )
                purchase_order_id = new_row_id(cursor)
                for line in order["lines"]:
                    self._conn.execute(
                        """
                        INSERT INTO procurement_purchase_order_lines(
                            purchase_order_id,
                            request_item_id,
                            item_name,
                            quantity,
                            unit_price,
                            line_total
                        )
                        VALUES(?, ?, ?, ?, ?, ?)
                        """,
                        (
                            purchase_order_id,
                            line.get("request_item_id"),
                            str(line["item_name"]),
                            int(line["quantity"]),
                            float(line["unit_price"]),
                            float(line["line_total"]),
                        ),
                    )

            if mark_as_ordered:
                self._conn.execute(
                    """
                    UPDATE procurement_requests
                    SET status = 'ordered', updated_at = ?
                    WHERE id = ?
                    """,
                    (now, request_id),
                )
            else:
                self._conn.execute(
                    "UPDATE procurement_requests SET updated_at = ? WHERE id = ?",
                    (now, request_id),
                )

            self._conn.commit()

        return self.list_purchase_orders(request_id)

    def list_purchase_orders(self, request_id: int) -> list[dict[str, Any]]:
        with self._lock:
            request_row = self._conn.execute(
                "SELECT id FROM procurement_requests WHERE id = ?",
                (request_id,),
            ).fetchone()
            if request_row is None:
                raise ValueError("Procurement request not found")

            order_rows = self._conn.execute(
                """
                SELECT
                    id,
                    request_id,
                    vendor_name,
                    currency,
                    total_amount,
                    status,
                    created_at,
                    approved_at
                FROM procurement_purchase_orders
                WHERE request_id = ?
                ORDER BY id ASC
                """,
                (request_id,),
            ).fetchall()

            line_rows = self._conn.execute(
                """
                SELECT
                    id,
                    purchase_order_id,
                    request_item_id,
                    item_name,
                    quantity,
                    unit_price,
                    line_total
                FROM procurement_purchase_order_lines
                WHERE purchase_order_id IN (
                    SELECT id FROM procurement_purchase_orders WHERE request_id = ?
                )
                ORDER BY purchase_order_id ASC, id ASC
                """,
                (request_id,),
            ).fetchall()

        lines_by_po: dict[int, list[dict[str, Any]]] = {}
        for row in line_rows:
            po_id = int(row["purchase_order_id"])
            lines_by_po.setdefault(po_id, []).append(
                {
                    "id": int(row["id"]),
                    "request_item_id": _to_nullable_int(row["request_item_id"]),
                    "item_name": str(row["item_name"]),
                    "quantity": int(row["quantity"]),
                    "unit_price": float(row["unit_price"]),
                    "line_total": float(row["line_total"]),
                }
            )

        output: list[dict[str, Any]] = []
        for row in order_rows:
            po_id = int(row["id"])
            output.append(
                {
                    "id": po_id,
                    "request_id": int(row["request_id"]),
                    "vendor_name": str(row["vendor_name"]),
                    "currency": str(row["currency"]),
                    "total_amount": float(row["total_amount"]),
                    "status": str(row["status"]),
                    "created_at": int(row["created_at"]),
                    "approved_at": _to_nullable_int(row["approved_at"]),
                    "lines": lines_by_po.get(po_id, []),
                }
            )
        return output

    def _list_items_for_request_ids(self, request_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
        if not request_ids:
            return {}

        item_map: dict[int, list[dict[str, Any]]] = {}
        with self._lock:
            for request_id in request_ids:
                rows = self._conn.execute(
                    """
                    SELECT
                        id,
                        request_id,
                        item_name,
                        specification,
                        quantity,
                        min_quality_score,
                        max_unit_price,
                        required_by_date,
                        must_comply_tender
                    FROM procurement_request_items
                    WHERE request_id = ?
                    ORDER BY id ASC
                    """,
                    (request_id,),
                ).fetchall()
                for row in rows:
                    row_request_id = int(row["request_id"])
                    item_map.setdefault(row_request_id, []).append(self._row_to_request_item(dict(row)))
        return item_map

    def _list_quote_items_for_quote_ids(self, quote_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
        if not quote_ids:
            return {}

        item_map: dict[int, list[dict[str, Any]]] = {}
        with self._lock:
            for quote_id in quote_ids:
                rows = self._conn.execute(
                    """
                    SELECT
                        id,
                        quote_id,
                        request_item_id,
                        unit_price,
                        available_quantity,
                        quality_score,
                        brand,
                        model,
                        note
                    FROM procurement_quote_items
                    WHERE quote_id = ?
                    ORDER BY request_item_id ASC
                    """,
                    (quote_id,),
                ).fetchall()
                for row in rows:
                    row_quote_id = int(row["quote_id"])
                    item_map.setdefault(row_quote_id, []).append(self._row_to_quote_item(dict(row)))
        return item_map

    @staticmethod
    def _row_to_request_header(row: dict[str, Any]) -> dict[str, Any]:
        tender_requirements = _parse_json_list(row.get("tender_requirements"))
        return {
            "id": int(row["id"]),
            "company_name": str(row["company_name"]),
            "title": str(row["title"]),
            "strategy": str(row["strategy"]),
            "budget_limit": _to_nullable_float(row.get("budget_limit")),
            "currency": str(row["currency"]),
            "tender_reference": row.get("tender_reference"),
            "tender_requirements": tender_requirements,
            "status": str(row["status"]),
            "created_at": int(row["created_at"]),
            "updated_at": int(row["updated_at"]),
        }

    @staticmethod
    def _row_to_request_item(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": int(row["id"]),
            "request_id": int(row["request_id"]),
            "item_name": str(row["item_name"]),
            "specification": str(row.get("specification") or ""),
            "quantity": int(row["quantity"]),
            "min_quality_score": float(row.get("min_quality_score") or 0),
            "max_unit_price": _to_nullable_float(row.get("max_unit_price")),
            "required_by_date": row.get("required_by_date"),
            "must_comply_tender": bool(int(row.get("must_comply_tender") or 0)),
        }

    @staticmethod
    def _row_to_quote_header(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": int(row["id"]),
            "request_id": int(row["request_id"]),
            "vendor_name": str(row["vendor_name"]),
            "vendor_rating": float(row["vendor_rating"]),
            "delivery_days": int(row["delivery_days"]),
            "warranty_months": int(row["warranty_months"]),
            "compliance_score": float(row["compliance_score"]),
            "status": str(row["status"]),
            "created_at": int(row["created_at"]),
        }

    @staticmethod
    def _row_to_quote_item(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": int(row["id"]),
            "quote_id": int(row["quote_id"]),
            "request_item_id": int(row["request_item_id"]),
            "unit_price": float(row["unit_price"]),
            "available_quantity": int(row["available_quantity"]),
            "quality_score": float(row["quality_score"]),
            "brand": str(row.get("brand") or ""),
            "model": str(row.get("model") or ""),
            "note": str(row.get("note") or ""),
        }


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
        text = str(item).strip()
        if text:
            output.append(text)
    return output


def _to_nullable_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_nullable_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
