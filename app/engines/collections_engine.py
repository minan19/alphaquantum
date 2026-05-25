from __future__ import annotations

from datetime import date

from app.invoice_repository import InvoiceRepository
from app.models import (
    AgingBucket,
    CashflowProjectionBucket,
    CashflowProjectionResponse,
    InvoiceCreateRequest,
    InvoiceRead,
    InvoiceListResponse,
    InvoicePaymentRequest,
    ReceivablesAgingResponse,
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

        # S-331 — aging breakdown
        aging = self._build_aging(company=company)

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
            aging=aging,
        )

    def _build_aging(self, *, company: str | None) -> ReceivablesAgingResponse:
        rows = self._repo.aging_analysis(company_name=company)
        buckets: dict[str, AgingBucket] = {}
        for r in rows:
            buckets[r["bucket"]] = AgingBucket(
                count=int(r["cnt"]),
                outstanding=round(float(r["outstanding"]), 2),
            )
        total_count = sum(b.count for b in buckets.values())
        total_outstanding = round(sum(b.outstanding for b in buckets.values()), 2)
        return ReceivablesAgingResponse(
            days_1_30=buckets.get("1_30", AgingBucket()),
            days_31_60=buckets.get("31_60", AgingBucket()),
            days_61_90=buckets.get("61_90", AgingBucket()),
            days_90_plus=buckets.get("90_plus", AgingBucket()),
            total_overdue_count=total_count,
            total_overdue_outstanding=total_outstanding,
        )

    def cashflow_projection(
        self,
        *,
        company: str | None,
        recurring_rows: list[dict] | None = None,
    ) -> CashflowProjectionResponse:
        """S-332 — 30/60/90-day forward cashflow projection.

        Combines:
        - Pending/partial invoice due dates  → expected income per bucket
        - Active recurring expenses           → estimated outflow per bucket
        """
        self._repo.mark_overdue(company_name=company)
        invoice_rows = self._repo.upcoming_cashflow(company_name=company, horizon_days=90)

        # Build income buckets from invoices
        income: dict[str, tuple[float, int]] = {}  # bucket -> (amount, count)
        for r in invoice_rows:
            b = r["bucket"]
            prev_amt, prev_cnt = income.get(b, (0.0, 0))
            income[b] = (prev_amt + float(r["expected"]), prev_cnt + int(r["cnt"]))

        # Build expense buckets from recurring entries (prorate to 30-day windows)
        expense: dict[str, float] = {"0_30": 0.0, "31_60": 0.0, "61_90": 0.0}
        for rec in (recurring_rows or []):
            if not rec.get("is_active", True):
                continue
            if rec.get("entry_type") != "expense":
                continue
            monthly = self._monthly_amount(float(rec["amount"]), rec["frequency"])
            for key in expense:
                expense[key] += monthly

        bucket_labels = [("0_30", "0–30 gün"), ("31_60", "31–60 gün"), ("61_90", "61–90 gün")]
        buckets: list[CashflowProjectionBucket] = []
        total_income = 0.0
        total_expense = 0.0

        for key, label in bucket_labels:
            inc_amt, inc_cnt = income.get(key, (0.0, 0))
            exp_amt = round(expense.get(key, 0.0), 2)
            inc_amt = round(inc_amt, 2)
            net = round(inc_amt - exp_amt, 2)
            buckets.append(CashflowProjectionBucket(
                label=label,
                expected_income=inc_amt,
                expected_expense=exp_amt,
                net=net,
                invoice_count=inc_cnt,
            ))
            total_income += inc_amt
            total_expense += exp_amt

        return CashflowProjectionResponse(
            company=company,
            as_of_date=date.today().isoformat(),
            buckets=buckets,
            total_expected_income=round(total_income, 2),
            total_expected_expense=round(total_expense, 2),
            total_net=round(total_income - total_expense, 2),
        )

    @staticmethod
    def _monthly_amount(amount: float, frequency: str) -> float:
        """Convert a recurring entry amount to its approximate 30-day equivalent."""
        return {
            "weekly": amount * (30 / 7),
            "monthly": amount,
            "quarterly": amount / 3,
            "yearly": amount / 12,
        }.get(frequency, amount)

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
