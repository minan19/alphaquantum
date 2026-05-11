from __future__ import annotations

from app.invoice_repository import InvoiceRepository
from app.models import (
    InvoiceCreateRequest,
    InvoiceRead,
    InvoiceListResponse,
    InvoicePaymentRequest,
    ReceivablesSummaryResponse,
)


class CollectionsEngine:
    def __init__(self, repo: InvoiceRepository) -> None:
        self._repo = repo

    def create_invoice(self, *, payload: InvoiceCreateRequest) -> InvoiceRead:
        row = self._repo.create_invoice(
            company_name=payload.company,
            title=payload.title,
            amount=payload.amount,
            issue_date=payload.issue_date,
            due_date=payload.due_date,
            customer_id=payload.customer_id,
            proposal_id=payload.proposal_id,
            invoice_number=payload.invoice_number,
            currency=payload.currency,
            description=payload.description,
        )
        return self._to_read(row)

    def get_invoice(self, invoice_id: int) -> InvoiceRead | None:
        row = self._repo.get_invoice(invoice_id)
        return self._to_read(row) if row else None

    def list_invoices(
        self,
        *,
        company: str | None,
        customer_id: int | None = None,
        status: str | None = None,
        overdue_only: bool = False,
        limit: int = 200,
    ) -> InvoiceListResponse:
        # Auto-mark overdue before listing
        self._repo.mark_overdue(company_name=company)
        rows = self._repo.list_invoices(
            company_name=company,
            customer_id=customer_id,
            status=status,
            overdue_only=overdue_only,
            limit=limit,
        )
        items = [self._to_read(r) for r in rows]
        return InvoiceListResponse(total=len(items), invoices=items)

    def record_payment(
        self, invoice_id: int, *, payload: InvoicePaymentRequest
    ) -> InvoiceRead | None:
        row = self._repo.record_payment(
            invoice_id,
            payment_amount=payload.payment_amount,
            paid_date=payload.paid_date,
        )
        return self._to_read(row) if row else None

    def receivables_summary(self, *, company: str | None) -> ReceivablesSummaryResponse:
        self._repo.mark_overdue(company_name=company)
        raw = self._repo.receivables_summary(company_name=company)

        def _get(key: str, field: str, default: float = 0.0) -> float:
            return float(raw.get(key, {}).get(field, default))

        pending_amount = _get("pending", "total_amount") - _get("pending", "total_paid")
        partial_remaining = _get("partial", "total_amount") - _get("partial", "total_paid")
        overdue_amount = _get("overdue", "total_amount") - _get("overdue", "total_paid")
        paid_amount = _get("paid", "total_paid")

        return ReceivablesSummaryResponse(
            company=company,
            pending_count=int(_get("pending", "count")),
            partial_count=int(_get("partial", "count")),
            overdue_count=int(_get("overdue", "count")),
            paid_count=int(_get("paid", "count")),
            pending_amount=round(pending_amount, 2),
            partial_remaining=round(partial_remaining, 2),
            overdue_amount=round(overdue_amount, 2),
            paid_amount_total=round(paid_amount, 2),
            total_outstanding=round(pending_amount + partial_remaining + overdue_amount, 2),
        )

    @staticmethod
    def _to_read(row: dict) -> InvoiceRead:
        return InvoiceRead(
            id=int(row["id"]),
            company=str(row["company_name"]),
            customer_id=row.get("customer_id"),
            proposal_id=row.get("proposal_id"),
            invoice_number=str(row.get("invoice_number") or ""),
            title=str(row["title"]),
            amount=float(row["amount"]),
            paid_amount=float(row.get("paid_amount") or 0),
            currency=str(row.get("currency") or "TRY"),
            status=str(row["status"]),
            issue_date=str(row["issue_date"]),
            due_date=str(row["due_date"]),
            paid_date=row.get("paid_date"),
            description=str(row.get("description") or ""),
            created_at=int(row["created_at"]),
            updated_at=int(row["updated_at"]),
        )
