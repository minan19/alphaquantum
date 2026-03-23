from __future__ import annotations

from datetime import date, timedelta

from app.finance_repository import FinanceRepository
from app.models import (
    Company,
    FinanceCashflowResponse,
    FinanceForecastResponse,
    FinanceLedgerEntryCreateRequest,
    FinanceLedgerEntryRead,
    FinanceLedgerResponse,
    FinanceOverviewResponse,
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

    def _require_repo(self) -> FinanceRepository:
        if self._repo is None:
            raise RuntimeError("Finance repository is not configured")
        return self._repo
