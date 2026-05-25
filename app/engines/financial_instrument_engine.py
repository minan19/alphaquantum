from __future__ import annotations

from typing import Any

from app.financial_instrument_repository import FinancialInstrumentRepository
from app.models import (
    FinancialInstrumentCreateRequest,
    FinancialInstrumentListResponse,
    FinancialInstrumentRead,
    FinancialInstrumentStatusUpdateRequest,
    FinancialInstrumentSummaryResponse,
)


class FinancialInstrumentEngine:
    """S-342 — Promissory note / cheque / bond business logic."""

    def __init__(self, repo: FinancialInstrumentRepository) -> None:
        self._repo = repo

    # ── CRUD ────────────────────────────────────────────────────────────────

    def create(
        self, *, payload: FinancialInstrumentCreateRequest
    ) -> FinancialInstrumentRead:
        row = self._repo.create(
            company_name=payload.company,
            kind=payload.kind,
            amount=payload.amount,
            currency=payload.currency,
            issue_date=payload.issue_date,
            due_date=payload.due_date,
            customer_id=payload.customer_id,
            instrument_number=payload.instrument_number,
            payer_name=payload.payer_name,
            bank_name=payload.bank_name,
            notes=payload.notes,
        )
        return self._to_read(row)

    def get(self, instrument_id: int) -> FinancialInstrumentRead | None:
        row = self._repo.get(instrument_id)
        return self._to_read(row) if row else None

    def list_instruments(
        self,
        *,
        company: str | None,
        kind: str | None = None,
        status: str | None = None,
        customer_id: int | None = None,
        limit: int = 200,
    ) -> FinancialInstrumentListResponse:
        rows = self._repo.list_instruments(
            company_name=company,
            kind=kind,
            status=status,
            customer_id=customer_id,
            limit=limit,
        )
        items = [self._to_read(r) for r in rows]
        return FinancialInstrumentListResponse(total=len(items), instruments=items)

    def update_status(
        self,
        instrument_id: int,
        *,
        payload: FinancialInstrumentStatusUpdateRequest,
    ) -> FinancialInstrumentRead | None:
        row = self._repo.update_status(
            instrument_id,
            new_status=payload.status,
            cleared_date=payload.cleared_date,
        )
        return self._to_read(row) if row else None

    def summary(
        self, *, company: str | None
    ) -> FinancialInstrumentSummaryResponse:
        raw = self._repo.summary(company_name=company)
        by_status = raw.get("by_status", {})

        def _count(status: str) -> int:
            return int(by_status.get(status, {}).get("count", 0))

        def _amount(status: str) -> float:
            return float(by_status.get(status, {}).get("total_amount", 0.0))

        return FinancialInstrumentSummaryResponse(
            company=company,
            total_count=sum(_count(s) for s in ("pending", "cleared", "bounced", "cancelled")),
            pending_count=_count("pending"),
            cleared_count=_count("cleared"),
            bounced_count=_count("bounced"),
            cancelled_count=_count("cancelled"),
            pending_amount=round(_amount("pending"), 2),
            cleared_amount=round(_amount("cleared"), 2),
            bounced_amount=round(_amount("bounced"), 2),
            overdue_pending_count=int(raw.get("overdue_pending_count", 0)),
            overdue_pending_amount=round(float(raw.get("overdue_pending_amount", 0.0)), 2),
            by_kind_pending={
                k: int(v.get("count", 0))
                for k, v in raw.get("by_kind_pending", {}).items()
            },
        )

    # ── Converter ───────────────────────────────────────────────────────────

    @staticmethod
    def _to_read(row: dict[str, Any]) -> FinancialInstrumentRead:
        return FinancialInstrumentRead(
            id=int(row["id"]),
            company=str(row["company_name"]),
            customer_id=row.get("customer_id"),
            kind=str(row["kind"]),
            instrument_number=str(row.get("instrument_number") or ""),
            amount=float(row["amount"]),
            currency=str(row.get("currency") or "TRY"),
            issue_date=str(row["issue_date"]),
            due_date=str(row["due_date"]),
            payer_name=str(row.get("payer_name") or ""),
            bank_name=str(row.get("bank_name") or ""),
            status=str(row["status"]),
            cleared_date=row.get("cleared_date"),
            notes=str(row.get("notes") or ""),
            created_at=int(row["created_at"]),
            updated_at=int(row["updated_at"]),
        )
