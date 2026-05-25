from __future__ import annotations

from datetime import date

from app.currency_converter import CurrencyConverter
from app.invoice_repository import InvoiceRepository
from app.models import (
    AgingBucket,
    CashflowProjectionBucket,
    CashflowProjectionResponse,
    CustomerRiskScoreResponse,
    FxCurrencyBucket,
    FxReceivablesSummaryResponse,
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

    def customer_risk_score(
        self,
        *,
        customer_id: int,
        customer_name: str,
        company: str,
    ) -> CustomerRiskScoreResponse:
        """S-333 — Compute a 0-100 payment-reliability score for a customer.

        Scoring (starting from 100, subtract penalties, clamp to [0,100]):
            On-time payment shortfall  →  up to -40   ((1 - on_time_ratio) * 40)
            Active overdue ratio       →  up to -25   (active_overdue / invoice_count * 25)
            Outstanding/billed ratio   →  up to -20   (outstanding / billed * 20)
            Average late days          →  up to -15   (min(avg_late_days / 4, 15))

        With no history: score = 50, risk_level = NO_HISTORY, confidence = LOW.
        """
        # mark any newly-overdue invoices first so counts are accurate
        self._repo.mark_overdue(company_name=company)

        stats = self._repo.customer_payment_stats(
            customer_id=customer_id, company_name=company
        )
        invoice_count = int(stats.get("invoice_count", 0) or 0)

        if invoice_count == 0:
            return CustomerRiskScoreResponse(
                customer_id=customer_id,
                customer_name=customer_name,
                company=company,
                score=50.0,
                risk_level="NO_HISTORY",
                confidence="LOW",
                factors=["Bu müşteri için kayıtlı fatura yok."],
            )

        paid_count = int(stats.get("paid_count", 0) or 0)
        on_time_count = int(stats.get("on_time_count", 0) or 0)
        late_paid_count = int(stats.get("late_paid_count", 0) or 0)
        active_overdue_count = int(stats.get("active_overdue_count", 0) or 0)
        avg_late_days = float(stats.get("avg_late_days", 0.0) or 0.0)
        total_billed = float(stats.get("total_billed", 0.0) or 0.0)
        total_outstanding = float(stats.get("total_outstanding", 0.0) or 0.0)

        # On-time ratio uses paid invoices as denominator (only meaningful when
        # we have closed history). If nothing paid yet, treat as fully on-time
        # to avoid double-penalizing through the outstanding factor below.
        if paid_count > 0:
            on_time_ratio = on_time_count / paid_count
        else:
            on_time_ratio = 1.0

        overdue_ratio = active_overdue_count / invoice_count
        outstanding_ratio = (
            total_outstanding / total_billed if total_billed > 0 else 0.0
        )

        # Penalty calculation
        penalty_ontime = (1.0 - on_time_ratio) * 40.0
        penalty_overdue = overdue_ratio * 25.0
        penalty_outstanding = outstanding_ratio * 20.0
        penalty_delay = min(avg_late_days / 4.0, 15.0) if avg_late_days > 0 else 0.0

        score = 100.0 - (
            penalty_ontime + penalty_overdue + penalty_outstanding + penalty_delay
        )
        score = max(0.0, min(100.0, score))

        # Risk level
        if score >= 75.0:
            risk_level = "LOW"
        elif score >= 40.0:
            risk_level = "MEDIUM"
        else:
            risk_level = "HIGH"

        # Confidence based on data volume
        if invoice_count >= 5:
            confidence = "HIGH"
        elif invoice_count >= 2:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

        # Human-readable factor explanations (Turkish)
        factors: list[str] = []
        if paid_count > 0:
            factors.append(
                f"Zamanında ödeme oranı: %{on_time_ratio * 100:.0f} "
                f"({on_time_count}/{paid_count})"
            )
        if late_paid_count > 0:
            factors.append(
                f"Ortalama gecikme: {avg_late_days:.1f} gün ({late_paid_count} faturada)"
            )
        if active_overdue_count > 0:
            factors.append(
                f"Aktif gecikmiş fatura: {active_overdue_count} adet"
            )
        if outstanding_ratio > 0:
            factors.append(
                f"Açık bakiye: {total_outstanding:.2f} / "
                f"{total_billed:.2f} (%{outstanding_ratio * 100:.0f})"
            )
        if not factors:
            factors.append("Tüm faturalar zamanında ve tam ödenmiş.")

        return CustomerRiskScoreResponse(
            customer_id=customer_id,
            customer_name=customer_name,
            company=company,
            score=round(score, 1),
            risk_level=risk_level,
            confidence=confidence,
            invoice_count=invoice_count,
            paid_count=paid_count,
            on_time_count=on_time_count,
            late_paid_count=late_paid_count,
            active_overdue_count=active_overdue_count,
            avg_late_days=round(avg_late_days, 2),
            total_billed=round(total_billed, 2),
            total_outstanding=round(total_outstanding, 2),
            on_time_ratio=round(on_time_ratio, 3),
            factors=factors,
        )

    def fx_aware_receivables_summary(
        self,
        *,
        company: str | None,
        converter: CurrencyConverter | None = None,
    ) -> FxReceivablesSummaryResponse:
        """S-341 — Outstanding receivables broken down by currency + normalized to TRY.

        Returns one bucket per currency that has any open receivables, plus
        a top-level TRY total and an `fx_exposure_pct` (share from non-TRY).
        Paid and cancelled invoices are excluded; partial payments contribute
        their remaining balance.
        """
        self._repo.mark_overdue(company_name=company)
        conv = converter or CurrencyConverter()

        invoices = self._repo.list_invoices(company_name=company, limit=10_000)

        # Accumulate per currency
        accum: dict[str, dict[str, float | int]] = {}
        for inv in invoices:
            if inv.get("status") in ("paid", "cancelled"):
                continue
            outstanding = float(inv.get("amount", 0.0)) - float(
                inv.get("paid_amount") or 0.0
            )
            if outstanding <= 0:
                continue
            ccy = str(inv.get("currency") or "TRY").upper()
            bucket = accum.setdefault(
                ccy,
                {"count": 0, "outstanding": 0.0},
            )
            bucket["count"] = int(bucket["count"]) + 1
            bucket["outstanding"] = float(bucket["outstanding"]) + outstanding

        # Convert and tally
        buckets: list[FxCurrencyBucket] = []
        total_try = 0.0
        for ccy, b in accum.items():
            rate = conv.rate(ccy)
            outstanding = round(float(b["outstanding"]), 2)
            outstanding_try = round(outstanding * rate, 2)
            buckets.append(
                FxCurrencyBucket(
                    currency=ccy,
                    count=int(b["count"]),
                    outstanding=outstanding,
                    outstanding_try=outstanding_try,
                    fx_rate=round(rate, 4),
                )
            )
            total_try += outstanding_try

        # Compute percentages — guard against zero division
        for bucket in buckets:
            bucket.pct_of_total = round(
                (bucket.outstanding_try / total_try * 100.0) if total_try > 0 else 0.0,
                1,
            )

        foreign_try = sum(b.outstanding_try for b in buckets if b.currency != "TRY")
        fx_exposure_pct = round(
            (foreign_try / total_try * 100.0) if total_try > 0 else 0.0, 1
        )

        # Stable sort: TRY first, then by TRY-converted outstanding descending
        buckets.sort(key=lambda b: (b.currency != "TRY", -b.outstanding_try))

        return FxReceivablesSummaryResponse(
            company=company,
            total_outstanding_try=round(total_try, 2),
            fx_exposure_pct=fx_exposure_pct,
            by_currency=buckets,
            as_of_date=date.today().isoformat(),
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
