from __future__ import annotations

from typing import Any

from collections import defaultdict
from datetime import datetime, timezone
import re
import time

from app.engines.tender_engine import TenderEngine
from app.models import (
    ProcurementAutoOrderRequest,
    ProcurementCandidateOption,
    ProcurementEvaluationResponse,
    ProcurementItemRecommendation,
    ProcurementPurchaseOrderBatchResponse,
    ProcurementPurchaseOrderLineRead,
    ProcurementPurchaseOrderRead,
    ProcurementQuoteItemRead,
    ProcurementRequestCreateRequest,
    ProcurementRequestItemCreateRequest,
    ProcurementRequestItemRead,
    ProcurementRequestListResponse,
    ProcurementRequestRead,
    ProcurementTenderPlanRequest,
    ProcurementTenderPlanResponse,
    ProcurementVendorQuoteCreateRequest,
    ProcurementVendorQuoteListResponse,
    ProcurementVendorQuoteRead,
)
from app.procurement_repository import ProcurementRepository

_SCORE_WEIGHTS: dict[str, dict[str, float]] = {
    "balanced": {
        "price": 0.30,
        "quality": 0.25,
        "delivery": 0.15,
        "compliance": 0.15,
        "vendor": 0.10,
        "availability": 0.05,
    },
    "lowest_cost": {
        "price": 0.55,
        "quality": 0.15,
        "delivery": 0.10,
        "compliance": 0.10,
        "vendor": 0.05,
        "availability": 0.05,
    },
    "highest_quality": {
        "price": 0.10,
        "quality": 0.50,
        "delivery": 0.10,
        "compliance": 0.15,
        "vendor": 0.10,
        "availability": 0.05,
    },
    "fastest_delivery": {
        "price": 0.20,
        "quality": 0.10,
        "delivery": 0.45,
        "compliance": 0.10,
        "vendor": 0.10,
        "availability": 0.05,
    },
    "tender_compliance": {
        "price": 0.15,
        "quality": 0.20,
        "delivery": 0.10,
        "compliance": 0.40,
        "vendor": 0.10,
        "availability": 0.05,
    },
}
_SUPPLY_HINTS = (
    "supply",
    "provide",
    "procure",
    "deliver",
    "temin",
    "teslim",
    "sunul",
    "kurulum",
    "installation",
    "malzeme",
    "ekipman",
    "equipment",
    "license",
    "lisans",
)
_ITEM_MAP = (
    ("switch", "Network Switch"),
    ("router", "Router"),
    ("server", "Server"),
    ("storage", "Storage Unit"),
    ("firewall", "Firewall"),
    ("ups", "UPS"),
    ("kablo", "Kablo"),
    ("cable", "Cable"),
    ("trafo", "Trafo"),
    ("transformer", "Transformer"),
    ("kamera", "Camera System"),
    ("camera", "Camera System"),
    ("license", "Software License"),
    ("lisans", "Software License"),
    ("software", "Software License"),
    ("yazilim", "Software License"),
    ("hizmet", "Professional Service"),
    ("service", "Professional Service"),
)
_RE_MULTI_SPACE = re.compile(r"\s+")


class ProcurementEngine:
    def __init__(
        self,
        repo: ProcurementRepository,
        tender_engine: TenderEngine | None = None,
    ) -> None:
        self._repo = repo
        self._tender_engine = tender_engine or TenderEngine()

    def create_request(self, payload: ProcurementRequestCreateRequest) -> ProcurementRequestRead:
        created = self._repo.create_request(
            company_name=payload.company,
            title=payload.title,
            strategy=payload.strategy,
            budget_limit=payload.budget_limit,
            currency=payload.currency.upper(),
            tender_reference=payload.tender_reference,
            tender_requirements=[_compact_text(item) for item in payload.tender_requirements if _compact_text(item)],
            items=[item.model_dump() for item in payload.items],
        )
        return _to_request_read(created)

    def list_requests(self, *, status: str | None = None, limit: int = 100) -> ProcurementRequestListResponse:
        rows = self._repo.list_requests(status=status, limit=limit)
        return ProcurementRequestListResponse(
            total=len(rows),
            items=[_to_request_read(row) for row in rows],
        )

    def get_request(self, request_id: int) -> ProcurementRequestRead:
        row = self._repo.get_request(request_id)
        return _to_request_read(row)

    def submit_quote(self, payload: ProcurementVendorQuoteCreateRequest) -> ProcurementVendorQuoteRead:
        row = self._repo.create_vendor_quote(
            request_id=payload.request_id,
            vendor_name=payload.vendor_name,
            vendor_rating=payload.vendor_rating,
            delivery_days=payload.delivery_days,
            warranty_months=payload.warranty_months,
            compliance_score=payload.compliance_score,
            status=payload.status,
            quote_items=[item.model_dump() for item in payload.quote_items],
        )
        return _to_vendor_quote_read(row)

    def list_quotes(self, request_id: int) -> ProcurementVendorQuoteListResponse:
        rows = self._repo.list_vendor_quotes(request_id)
        return ProcurementVendorQuoteListResponse(
            request_id=request_id,
            total=len(rows),
            items=[_to_vendor_quote_read(row) for row in rows],
        )

    def evaluate_request(
        self,
        request_id: int,
        *,
        strategy_override: str | None = None,
    ) -> ProcurementEvaluationResponse:
        request = self._repo.get_request(request_id)
        strategy = strategy_override or str(request["strategy"])
        weights = _SCORE_WEIGHTS.get(strategy)
        if weights is None:
            raise ValueError("Unsupported procurement strategy")

        candidates = self._repo.list_quote_candidates(request_id)
        candidates_by_item: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in candidates:
            candidates_by_item[int(row["request_item_id"])].append(row)

        recommendations: list[ProcurementItemRecommendation] = []
        selected_scores: list[float] = []
        estimated_total_cost = 0.0

        for item in request["items"]:
            item_id = int(item["id"])
            item_candidates = candidates_by_item.get(item_id, [])
            if not item_candidates:
                recommendations.append(
                    ProcurementItemRecommendation(
                        request_item_id=item_id,
                        item_name=str(item["item_name"]),
                        required_quantity=int(item["quantity"]),
                        status="unresolved",
                        reasoning="No vendor quote submitted for this item.",
                        alternatives=[],
                    )
                )
                continue

            min_price = min(float(row["unit_price"]) for row in item_candidates)
            delivery_values = [max(0, int(row["delivery_days"])) for row in item_candidates]
            min_delivery = min(delivery_values) if delivery_values else 0
            required_qty = int(item["quantity"])
            min_quality = float(item.get("min_quality_score") or 0)
            max_unit_price = item.get("max_unit_price")
            must_comply_tender = bool(item.get("must_comply_tender"))

            option_rows: list[ProcurementCandidateOption] = []
            for row in item_candidates:
                unit_price = float(row["unit_price"])
                quality_score = _clamp_score(float(row["quality_score"]))
                compliance_score = _clamp_score(float(row["compliance_score"]))
                vendor_rating = _clamp_score(float(row["vendor_rating"]))
                available_qty = int(row["available_quantity"])
                delivery_days = max(0, int(row["delivery_days"]))
                availability_ratio = min(available_qty / required_qty, 1.0) if required_qty > 0 else 1.0

                price_score = _clamp_score((min_price / unit_price) * 100 if unit_price > 0 else 0)
                delivery_ref = max(min_delivery, 1)
                delivery_base = max(delivery_days, 1)
                delivery_score = _clamp_score((delivery_ref / delivery_base) * 100)
                availability_score = _clamp_score(availability_ratio * 100)
                weighted_score = (
                    price_score * weights["price"]
                    + quality_score * weights["quality"]
                    + delivery_score * weights["delivery"]
                    + compliance_score * weights["compliance"]
                    + vendor_rating * weights["vendor"]
                    + availability_score * weights["availability"]
                )
                weighted_score = round(_clamp_score(weighted_score), 2)

                feasibility_notes: list[str] = []
                if available_qty < required_qty:
                    feasibility_notes.append("available_quantity_below_required")
                if quality_score < min_quality:
                    feasibility_notes.append("quality_below_minimum")
                if max_unit_price is not None and unit_price > float(max_unit_price):
                    feasibility_notes.append("unit_price_above_limit")
                if must_comply_tender and compliance_score < 70:
                    feasibility_notes.append("tender_compliance_below_threshold")

                option_rows.append(
                    ProcurementCandidateOption(
                        quote_item_id=int(row["quote_item_id"]),
                        quote_id=int(row["quote_id"]),
                        vendor_name=str(row["vendor_name"]),
                        unit_price=unit_price,
                        available_quantity=available_qty,
                        quality_score=quality_score,
                        delivery_days=delivery_days,
                        compliance_score=compliance_score,
                        vendor_rating=vendor_rating,
                        weighted_score=weighted_score,
                        feasible=(len(feasibility_notes) == 0),
                        feasibility_notes=feasibility_notes,
                    )
                )

            option_rows.sort(
                key=lambda opt: (
                    1 if opt.feasible else 0,
                    opt.weighted_score,
                    -opt.unit_price,
                ),
                reverse=True,
            )

            selected = next((opt for opt in option_rows if opt.feasible), None)
            if selected is None:
                recommendations.append(
                    ProcurementItemRecommendation(
                        request_item_id=item_id,
                        item_name=str(item["item_name"]),
                        required_quantity=required_qty,
                        status="unresolved",
                        reasoning="All received quotes violate quality/compliance/price or quantity constraints.",
                        alternatives=option_rows,
                    )
                )
                continue

            expected_total = round(required_qty * selected.unit_price, 2)
            estimated_total_cost += expected_total
            selected_scores.append(selected.weighted_score)
            recommendations.append(
                ProcurementItemRecommendation(
                    request_item_id=item_id,
                    item_name=str(item["item_name"]),
                    required_quantity=required_qty,
                    status="recommended",
                    selected_quote_item_id=selected.quote_item_id,
                    selected_vendor=selected.vendor_name,
                    selected_unit_price=selected.unit_price,
                    expected_total=expected_total,
                    weighted_score=selected.weighted_score,
                    reasoning=(
                        f"Selected {selected.vendor_name} based on highest feasible weighted score "
                        f"({selected.weighted_score:.2f}) for strategy '{strategy}'."
                    ),
                    alternatives=option_rows,
                )
            )

        total_required_items = len(request["items"])
        resolved_items = sum(1 for item in recommendations if item.status == "recommended")
        unresolved_items = max(0, total_required_items - resolved_items)
        budget_limit = request.get("budget_limit")
        within_budget = budget_limit is None or estimated_total_cost <= float(budget_limit)
        average_weighted_score = round(sum(selected_scores) / len(selected_scores), 2) if selected_scores else 0.0

        decision_notes: list[str] = []
        if unresolved_items > 0:
            decision_notes.append(
                f"{unresolved_items} item(s) unresolved; collect additional RFQ offers or relax constraints."
            )
        if not within_budget and budget_limit is not None:
            decision_notes.append(
                f"Estimated total {estimated_total_cost:.2f} exceeds budget {float(budget_limit):.2f}."
            )
        if not decision_notes:
            decision_notes.append("Procurement plan is ready for approval and PO issuance.")

        return ProcurementEvaluationResponse(
            request_id=request_id,
            strategy=strategy,
            generated_at=datetime.now(timezone.utc).isoformat(),
            currency=str(request["currency"]),
            total_required_items=total_required_items,
            resolved_items=resolved_items,
            unresolved_items=unresolved_items,
            estimated_total_cost=round(estimated_total_cost, 2),
            budget_limit=float(budget_limit) if budget_limit is not None else None,
            within_budget=within_budget,
            average_weighted_score=average_weighted_score,
            recommendations=recommendations,
            decision_notes=decision_notes,
        )

    def create_auto_purchase_orders(
        self,
        request_id: int,
        payload: ProcurementAutoOrderRequest,
    ) -> ProcurementPurchaseOrderBatchResponse:
        evaluation = self.evaluate_request(
            request_id=request_id,
            strategy_override=payload.strategy_override,
        )
        if payload.require_full_coverage and evaluation.unresolved_items > 0:
            raise ValueError("Request has unresolved items; complete quote coverage before auto-order.")

        selected_recommendations = [
            item for item in evaluation.recommendations if item.status == "recommended" and item.selected_vendor
        ]
        if not selected_recommendations:
            raise ValueError("No recommended items found for purchase order generation.")

        lines_by_vendor: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in selected_recommendations:
            selected_vendor = item.selected_vendor
            selected_unit_price = item.selected_unit_price
            if selected_vendor is None or selected_unit_price is None:
                raise ValueError("Evaluation result contains incomplete recommendation fields.")
            line_total = round(item.required_quantity * selected_unit_price, 2)
            lines_by_vendor[selected_vendor].append(
                {
                    "request_item_id": item.request_item_id,
                    "item_name": item.item_name,
                    "quantity": item.required_quantity,
                    "unit_price": selected_unit_price,
                    "line_total": line_total,
                }
            )

        if len(lines_by_vendor) > payload.max_vendor_split:
            raise ValueError(
                f"Recommended plan requires {len(lines_by_vendor)} vendors, above max_vendor_split={payload.max_vendor_split}"
            )

        approved_at = int(time.time()) if payload.auto_approve else None
        status = "approved" if payload.auto_approve else "draft"
        order_rows: list[dict[str, Any]] = []
        for vendor_name, lines in lines_by_vendor.items():
            total_amount = round(sum(float(line["line_total"]) for line in lines), 2)
            order_rows.append(
                {
                    "vendor_name": vendor_name,
                    "status": status,
                    "approved_at": approved_at,
                    "total_amount": total_amount,
                    "lines": lines,
                }
            )

        created_orders = self._repo.create_purchase_orders(
            request_id=request_id,
            currency=evaluation.currency,
            orders=order_rows,
            mark_as_ordered=True,
        )
        total_amount = round(sum(float(order["total_amount"]) for order in created_orders), 2)
        notes = [
            f"Auto PO generated with strategy={evaluation.strategy}.",
            f"Vendor split: {len(created_orders)} order(s).",
        ]
        if evaluation.unresolved_items > 0:
            notes.append("Some items remain unresolved and were excluded from auto PO.")

        return ProcurementPurchaseOrderBatchResponse(
            request_id=request_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
            total_orders=len(created_orders),
            total_amount=total_amount,
            unresolved_items=evaluation.unresolved_items,
            currency=evaluation.currency,
            orders=[_to_purchase_order_read(row) for row in created_orders],
            notes=notes,
        )

    def list_purchase_orders(self, request_id: int) -> ProcurementPurchaseOrderBatchResponse:
        request = self._repo.get_request(request_id)
        orders = self._repo.list_purchase_orders(request_id)
        total_amount = round(sum(float(order["total_amount"]) for order in orders), 2)
        return ProcurementPurchaseOrderBatchResponse(
            request_id=request_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
            total_orders=len(orders),
            total_amount=total_amount,
            unresolved_items=0,
            currency=str(request["currency"]),
            orders=[_to_purchase_order_read(row) for row in orders],
            notes=[],
        )

    def create_request_from_tender(self, payload: ProcurementTenderPlanRequest) -> ProcurementTenderPlanResponse:
        dossier = self._tender_engine.build_dossier(payload.tender)
        tender_requirements = [item.requirement for item in dossier.compliance_matrix]
        extracted_items, extraction_notes = _extract_items_from_requirements(
            requirements=tender_requirements,
            default_quantity=payload.default_quantity,
            max_items=payload.max_items,
        )
        if not extracted_items:
            extracted_items = [
                ProcurementRequestItemCreateRequest(
                    item_name="General Tender Scope Package",
                    specification="Procurement team must map this package to detailed tender annexes.",
                    quantity=payload.default_quantity,
                    min_quality_score=70,
                    must_comply_tender=True,
                )
            ]
            extraction_notes.append("No explicit material token detected, fallback package item created.")

        request_payload = ProcurementRequestCreateRequest(
            company=payload.tender.company_name,
            title=f"{payload.tender.tender_title} - Procurement Plan",
            strategy=payload.strategy,
            budget_limit=payload.budget_limit,
            currency=payload.currency.upper(),
            tender_reference=payload.tender.tender_reference,
            tender_requirements=tender_requirements[:200],
            items=extracted_items,
        )
        created_request = self.create_request(request_payload)
        return ProcurementTenderPlanResponse(
            generated_at=datetime.now(timezone.utc).isoformat(),
            tender_reference=payload.tender.tender_reference,
            institution_name=payload.tender.institution_name,
            tender_title=payload.tender.tender_title,
            extracted_item_count=len(created_request.items),
            extraction_notes=extraction_notes,
            procurement_request=created_request,
        )


def _to_request_read(row: dict[str, Any]) -> ProcurementRequestRead:
    return ProcurementRequestRead(
        id=int(row["id"]),
        company=str(row["company_name"]),
        title=str(row["title"]),
        strategy=str(row["strategy"]),
        budget_limit=float(row["budget_limit"]) if row.get("budget_limit") is not None else None,
        currency=str(row["currency"]),
        tender_reference=row.get("tender_reference"),
        tender_requirements=[str(item) for item in row.get("tender_requirements", [])],
        status=str(row["status"]),
        created_at=int(row["created_at"]),
        updated_at=int(row["updated_at"]),
        items=[
            ProcurementRequestItemRead(
                id=int(item["id"]),
                request_id=int(item["request_id"]),
                item_name=str(item["item_name"]),
                specification=str(item.get("specification") or ""),
                quantity=int(item["quantity"]),
                min_quality_score=float(item.get("min_quality_score") or 0),
                max_unit_price=float(item["max_unit_price"]) if item.get("max_unit_price") is not None else None,
                required_by_date=item.get("required_by_date"),
                must_comply_tender=bool(item.get("must_comply_tender")),
            )
            for item in row.get("items", [])
        ],
    )


def _to_vendor_quote_read(row: dict[str, Any]) -> ProcurementVendorQuoteRead:
    return ProcurementVendorQuoteRead(
        id=int(row["id"]),
        request_id=int(row["request_id"]),
        vendor_name=str(row["vendor_name"]),
        vendor_rating=float(row["vendor_rating"]),
        delivery_days=int(row["delivery_days"]),
        warranty_months=int(row["warranty_months"]),
        compliance_score=float(row["compliance_score"]),
        status=str(row["status"]),
        created_at=int(row["created_at"]),
        items=[
            ProcurementQuoteItemRead(
                id=int(item["id"]),
                quote_id=int(item["quote_id"]),
                request_item_id=int(item["request_item_id"]),
                unit_price=float(item["unit_price"]),
                available_quantity=int(item["available_quantity"]),
                quality_score=float(item["quality_score"]),
                brand=str(item.get("brand") or ""),
                model=str(item.get("model") or ""),
                note=str(item.get("note") or ""),
            )
            for item in row.get("items", [])
        ],
    )


def _to_purchase_order_read(row: dict[str, Any]) -> ProcurementPurchaseOrderRead:
    return ProcurementPurchaseOrderRead(
        id=int(row["id"]),
        request_id=int(row["request_id"]),
        vendor_name=str(row["vendor_name"]),
        currency=str(row["currency"]),
        total_amount=float(row["total_amount"]),
        status=str(row["status"]),
        created_at=int(row["created_at"]),
        approved_at=int(row["approved_at"]) if row.get("approved_at") is not None else None,
        lines=[
            ProcurementPurchaseOrderLineRead(
                id=int(line["id"]),
                request_item_id=int(line["request_item_id"]) if line.get("request_item_id") is not None else None,
                item_name=str(line["item_name"]),
                quantity=int(line["quantity"]),
                unit_price=float(line["unit_price"]),
                line_total=float(line["line_total"]),
            )
            for line in row.get("lines", [])
        ],
    )


def _extract_items_from_requirements(
    *,
    requirements: list[str],
    default_quantity: int,
    max_items: int,
) -> tuple[list[ProcurementRequestItemCreateRequest], list[str]]:
    grouped_specs: dict[str, list[str]] = {}
    notes: list[str] = []
    for requirement in requirements:
        normalized = _compact_text(requirement)
        if not normalized:
            continue
        lowered = normalized.lower()
        matched = False
        for token, canonical in _ITEM_MAP:
            if token in lowered:
                grouped_specs.setdefault(canonical, []).append(normalized)
                matched = True
        if matched:
            continue

        if any(hint in lowered for hint in _SUPPLY_HINTS):
            summary = _summary_item_name(normalized)
            grouped_specs.setdefault(summary, []).append(normalized)

    items: list[ProcurementRequestItemCreateRequest] = []
    for item_name, specs in grouped_specs.items():
        spec_text = " | ".join(specs[:3])
        items.append(
            ProcurementRequestItemCreateRequest(
                item_name=item_name,
                specification=spec_text,
                quantity=default_quantity,
                min_quality_score=70,
                must_comply_tender=True,
            )
        )
        if len(items) >= max_items:
            notes.append(f"Item list truncated to max_items={max_items}.")
            break

    if items:
        notes.append(f"Extracted {len(items)} item(s) from tender requirements.")
    return items, notes


def _summary_item_name(requirement: str) -> str:
    words = [word for word in re.split(r"[^a-zA-Z0-9]+", requirement) if word]
    if not words:
        return "Tender Supply Item"
    head = " ".join(words[:5]).strip()
    if not head:
        return "Tender Supply Item"
    return _compact_text(head).title()


def _compact_text(text: str) -> str:
    return _RE_MULTI_SPACE.sub(" ", text).strip()


def _clamp_score(value: float) -> float:
    return max(0.0, min(value, 100.0))
