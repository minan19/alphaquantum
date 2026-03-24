from __future__ import annotations

from datetime import date, timedelta

from app.finance_repository import FinanceRepository
from app.models import (
    Company,
    FinanceBudgetCreateRequest,
    FinanceBudgetListResponse,
    FinanceBudgetRead,
    FinanceBudgetVsActualItem,
    FinanceBudgetVsActualResponse,
    FinanceCashflowResponse,
    FinanceForecastResponse,
    FinanceLedgerEntryCreateRequest,
    FinanceLedgerEntryRead,
    FinanceLedgerResponse,
    FinanceOverviewResponse,
    FinanceRecurringEntryCreateRequest,
    FinanceRecurringEntryRead,
    FinanceRecurringGenerateResponse,
    FinanceRecurringListResponse,
)


class FinanceEngine:
    def __init__(self, repo: FinanceRepository | None = None) -> None:
        self._repo = repo

    @staticmethod
    def build_overview(companies: list[Company]) -> FinanceOverviewResponse:
        if not companies:
            return FinanceOverviewResponse(
                total_balance=0,
                average_balance=0,
                negative_balance_companies=0,
                highest_balance_company=None,
                lowest_balance_company=None,
                health_status="NO_DATA",
            )

        total_balance = sum(company.balance for company in companies)
        negative_balance_companies = sum(1 for company in companies if company.balance < 0)
        average_balance = total_balance / len(companies)

        max_company = max(companies, key=lambda company: company.balance)
        min_company = min(companies, key=lambda company: company.balance)

        health_status = "HEALTHY"
        if total_balance < 0 or negative_balance_companies > 0:
            health_status = "RISK"
        elif total_balance < 50_000:
            health_status = "WATCH"

        return FinanceOverviewResponse(
            total_balance=total_balance,
            average_balance=average_balance,
            negative_balance_companies=negative_balance_companies,
            highest_balance_company=max_company.name,
            lowest_balance_company=min_company.name,
            health_status=health_status,
        )

    def create_ledger_entry(
        self,
        *,
        payload: FinanceLedgerEntryCreateRequest,
    ) -> FinanceLedgerEntryRead:
        repo = self._require_repo()
        entry_date = payload.entry_date or repo.today()

        row = repo.create_ledger_entry(
            company_name=payload.company,
            entry_type=payload.entry_type,
            amount=payload.amount,
            category=payload.category,
            description=payload.description,
            entry_date=entry_date,
        )
        return self._to_ledger_read(row)

    def list_ledger_entries(
        self,
        *,
        company: str | None,
        start_date: str | None,
        end_date: str | None,
        limit: int,
    ) -> FinanceLedgerResponse:
        repo = self._require_repo()
        today = date.today()

        end = self._parse_or_default_date(end_date, today)
        start = self._parse_or_default_date(start_date, today - timedelta(days=30))
        if start > end:
            raise ValueError("start_date cannot be greater than end_date")

        rows = repo.list_ledger_entries(
            company_name=company,
            start_date=start.isoformat(),
            end_date=end.isoformat(),
            limit=limit,
        )
        entries = [self._to_ledger_read(row) for row in rows]
        return FinanceLedgerResponse(total=len(entries), entries=entries)

    def build_cashflow(
        self,
        *,
        company: str | None,
        lookback_days: int,
    ) -> FinanceCashflowResponse:
        if lookback_days < 1:
            raise ValueError("lookback_days must be >= 1")

        today = date.today()
        start = today - timedelta(days=lookback_days - 1)
        ledger = self.list_ledger_entries(
            company=company,
            start_date=start.isoformat(),
            end_date=today.isoformat(),
            limit=10_000,
        )

        total_income = 0.0
        total_expense = 0.0
        for entry in ledger.entries:
            if entry.entry_type == "income":
                total_income += entry.amount
            else:
                total_expense += entry.amount

        net = total_income - total_expense
        average_daily_net = net / lookback_days

        return FinanceCashflowResponse(
            company=company,
            lookback_days=lookback_days,
            total_income=round(total_income, 2),
            total_expense=round(total_expense, 2),
            net_cashflow=round(net, 2),
            average_daily_net=round(average_daily_net, 2),
            transaction_count=ledger.total,
        )

    def forecast_cashflow(
        self,
        *,
        companies: list[Company],
        company: str | None,
        lookback_days: int,
        horizon_days: int,
    ) -> FinanceForecastResponse:
        if horizon_days < 1:
            raise ValueError("horizon_days must be >= 1")

        cashflow = self.build_cashflow(company=company, lookback_days=lookback_days)
        baseline_balance = self._balance_for_company_scope(companies, company)
        projected_net = cashflow.average_daily_net * horizon_days
        projected_balance = baseline_balance + projected_net

        confidence = min(
            0.95,
            max(0.3, cashflow.transaction_count / max(lookback_days * 2, 1)),
        )

        return FinanceForecastResponse(
            company=company,
            lookback_days=lookback_days,
            horizon_days=horizon_days,
            baseline_balance=round(baseline_balance, 2),
            projected_net_cashflow=round(projected_net, 2),
            projected_balance=round(projected_balance, 2),
            confidence=round(confidence, 2),
            model="moving_average_daily_net",
        )

    @staticmethod
    def _parse_or_default_date(raw: str | None, default_value: date) -> date:
        if raw is None:
            return default_value

        try:
            return date.fromisoformat(raw)
        except ValueError as exc:
            raise ValueError("Date must be YYYY-MM-DD") from exc

    @staticmethod
    def _to_ledger_read(row: dict) -> FinanceLedgerEntryRead:
        return FinanceLedgerEntryRead(
            id=int(row["id"]),
            company=str(row["company_name"]),
            entry_type=str(row["entry_type"]),
            amount=float(row["amount"]),
            category=str(row["category"]),
            description=str(row.get("description") or ""),
            entry_date=str(row["entry_date"]),
            created_at=int(row["created_at"]),
        )

    @staticmethod
    def _balance_for_company_scope(companies: list[Company], company: str | None) -> float:
        if company is None:
            return float(sum(row.balance for row in companies))

        for row in companies:
            if row.name == company:
                return float(row.balance)
        return 0.0

    # ── Recurring entries ──────────────────────────────────────────────────────

    def create_recurring_entry(
        self,
        *,
        payload: FinanceRecurringEntryCreateRequest,
    ) -> FinanceRecurringEntryRead:
        repo = self._require_repo()
        row = repo.create_recurring_entry(
            company_name=payload.company,
            entry_type=payload.entry_type,
            amount=payload.amount,
            category=payload.category,
            description=payload.description,
            frequency=payload.frequency,
            start_date=payload.start_date,
            end_date=payload.end_date,
        )
        return self._to_recurring_read(row)

    def list_recurring_entries(
        self,
        *,
        company: str | None,
        active_only: bool = True,
    ) -> FinanceRecurringListResponse:
        repo = self._require_repo()
        rows = repo.list_recurring_entries(company_name=company, active_only=active_only)
        entries = [self._to_recurring_read(row) for row in rows]
        return FinanceRecurringListResponse(total=len(entries), entries=entries)

    def generate_due_entries(self, *, as_of_date: str | None = None) -> FinanceRecurringGenerateResponse:
        """Generate ledger entries for all due recurring entries."""
        repo = self._require_repo()
        today = date.today()
        target = as_of_date or today.isoformat()

        due = repo.get_due_recurring_entries(target)
        generated_ids: list[int] = []

        for recurring in due:
            frequency = str(recurring["frequency"])
            last_date_str: str | None = recurring.get("last_generated_date")  # type: ignore[assignment]
            start_date_str = str(recurring["start_date"])

            # Determine the next date to generate from
            if last_date_str:
                next_gen_date = self._next_occurrence(last_date_str, frequency)
            else:
                next_gen_date = date.fromisoformat(start_date_str)

            target_date = date.fromisoformat(target)

            while next_gen_date <= target_date:
                entry_date_str = next_gen_date.isoformat()
                row = repo.create_ledger_entry(
                    company_name=str(recurring["company_name"]),
                    entry_type=str(recurring["entry_type"]),
                    amount=float(recurring["amount"]),
                    category=str(recurring["category"]),
                    description=str(recurring.get("description") or ""),
                    entry_date=entry_date_str,
                )
                generated_ids.append(int(row["id"]))
                repo.update_recurring_last_generated(int(recurring["id"]), entry_date_str)
                next_gen_date = self._next_occurrence(entry_date_str, frequency)

        return FinanceRecurringGenerateResponse(
            generated_count=len(generated_ids),
            ledger_entry_ids=generated_ids,
            message=f"Generated {len(generated_ids)} ledger entries from {len(due)} recurring templates",
        )

    @staticmethod
    def _next_occurrence(from_date_str: str, frequency: str) -> date:
        from_date = date.fromisoformat(from_date_str)
        if frequency == "weekly":
            return from_date + timedelta(weeks=1)
        if frequency == "monthly":
            import calendar
            # Advance one month
            month = from_date.month + 1
            year = from_date.year + (month - 1) // 12
            month = ((month - 1) % 12) + 1
            last_day = calendar.monthrange(year, month)[1]
            return date(year, month, min(from_date.day, last_day))
        if frequency == "quarterly":
            month = from_date.month + 3
            year = from_date.year + (month - 1) // 12
            month = ((month - 1) % 12) + 1
            import calendar
            last_day = calendar.monthrange(year, month)[1]
            return date(year, month, min(from_date.day, last_day))
        if frequency == "yearly":
            import calendar
            year = from_date.year + 1
            last_day = calendar.monthrange(year, from_date.month)[1]
            return date(year, from_date.month, min(from_date.day, last_day))
        raise ValueError(f"Unknown frequency: {frequency}")

    @staticmethod
    def _to_recurring_read(row: dict) -> FinanceRecurringEntryRead:
        return FinanceRecurringEntryRead(
            id=int(row["id"]),
            company=str(row["company_name"]),
            entry_type=str(row["entry_type"]),
            amount=float(row["amount"]),
            category=str(row["category"]),
            description=str(row.get("description") or ""),
            frequency=str(row["frequency"]),
            start_date=str(row["start_date"]),
            end_date=row.get("end_date"),
            last_generated_date=row.get("last_generated_date"),
            is_active=bool(row["is_active"]),
            created_at=int(row["created_at"]),
        )

    # ── Budgets ────────────────────────────────────────────────────────────────

    def create_budget(self, *, payload: FinanceBudgetCreateRequest) -> FinanceBudgetRead:
        repo = self._require_repo()
        row = repo.upsert_budget(
            company_name=payload.company,
            year=payload.year,
            month=payload.month,
            category=payload.category,
            entry_type=payload.entry_type,
            budget_amount=payload.budget_amount,
        )
        return self._to_budget_read(row)

    def list_budgets(
        self,
        *,
        company: str | None,
        year: int | None,
        month: int | None,
    ) -> FinanceBudgetListResponse:
        repo = self._require_repo()
        rows = repo.list_budgets(company_name=company, year=year, month=month)
        budgets = [self._to_budget_read(row) for row in rows]
        return FinanceBudgetListResponse(total=len(budgets), budgets=budgets)

    def budget_vs_actual(
        self,
        *,
        company: str | None,
        year: int,
        month: int | None,
    ) -> FinanceBudgetVsActualResponse:
        repo = self._require_repo()
        budgets = repo.list_budgets(company_name=company, year=year, month=month)
        actuals = repo.get_actuals_by_category(company_name=company, year=year, month=month)

        # Build actuals lookup
        actuals_map: dict[tuple[str, str], float] = {}
        for a in actuals:
            key = (str(a["category"]), str(a["entry_type"]))
            actuals_map[key] = float(a["actual_amount"])

        items: list[FinanceBudgetVsActualItem] = []
        total_budget_income = 0.0
        total_budget_expense = 0.0
        total_actual_income = 0.0
        total_actual_expense = 0.0

        for b in budgets:
            cat = str(b["category"])
            etype = str(b["entry_type"])
            budget_amt = float(b["budget_amount"])
            actual_amt = actuals_map.get((cat, etype), 0.0)
            variance = actual_amt - budget_amt
            variance_pct = (variance / budget_amt * 100) if budget_amt else 0.0

            if etype == "income":
                status = "ON_TRACK" if actual_amt >= budget_amt else "UNDER"
                total_budget_income += budget_amt
                total_actual_income += actual_amt
            else:
                status = "ON_TRACK" if actual_amt <= budget_amt else "OVER"
                total_budget_expense += budget_amt
                total_actual_expense += actual_amt

            items.append(
                FinanceBudgetVsActualItem(
                    category=cat,
                    entry_type=etype,
                    budget_amount=round(budget_amt, 2),
                    actual_amount=round(actual_amt, 2),
                    variance=round(variance, 2),
                    variance_pct=round(variance_pct, 2),
                    status=status,
                )
            )

        net_budget = total_budget_income - total_budget_expense
        net_actual = total_actual_income - total_actual_expense

        return FinanceBudgetVsActualResponse(
            company=company,
            year=year,
            month=month,
            items=items,
            total_budget_income=round(total_budget_income, 2),
            total_budget_expense=round(total_budget_expense, 2),
            total_actual_income=round(total_actual_income, 2),
            total_actual_expense=round(total_actual_expense, 2),
            net_budget=round(net_budget, 2),
            net_actual=round(net_actual, 2),
            net_variance=round(net_actual - net_budget, 2),
        )

    @staticmethod
    def _to_budget_read(row: dict) -> FinanceBudgetRead:
        return FinanceBudgetRead(
            id=int(row["id"]),
            company=str(row["company_name"]),
            year=int(row["year"]),
            month=row.get("month"),
            category=str(row["category"]),
            entry_type=str(row["entry_type"]),
            budget_amount=float(row["budget_amount"]),
            created_at=int(row["created_at"]),
        )

    def _require_repo(self) -> FinanceRepository:
        if self._repo is None:
            raise RuntimeError("Finance repository is not configured")
        return self._repo
