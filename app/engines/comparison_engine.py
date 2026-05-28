from __future__ import annotations

from app.models import Company, CompanyComparisonResponse, CompanyFinanceSnapshot


class ComparisonEngine:
    """Aggregate per-company finance KPIs into a side-by-side comparison."""

    @staticmethod
    def build_comparison(
        *,
        companies: list[Company],
        cashflows: dict[str, object],
        budget_reports: dict[str, object],
        year: int | None,
        lookback_days: int,
    ) -> CompanyComparisonResponse:
        snapshots: list[CompanyFinanceSnapshot] = []

        for company in companies:
            cashflow = cashflows.get(company.name)
            budget_report = budget_reports.get(company.name)

            if cashflow is None:
                total_income_30d = 0.0
                total_expense_30d = 0.0
                net_cashflow_30d = 0.0
                health_status = "NO_DATA"
            else:
                total_income_30d = cashflow.total_income
                total_expense_30d = cashflow.total_expense
                net_cashflow_30d = cashflow.net_cashflow
                if company.balance < 0:
                    health_status = "RISK"
                elif company.balance >= 50_000 and net_cashflow_30d >= 0:
                    health_status = "HEALTHY"
                else:
                    health_status = "WATCH"

            net_budget = None
            net_actual = None
            net_variance = None
            budget_vs_actual_year = None

            if budget_report is not None:
                net_budget = getattr(budget_report, "net_budget", None)
                net_actual = getattr(budget_report, "net_actual", None)
                net_variance = getattr(budget_report, "net_variance", None)
                budget_vs_actual_year = year

            snapshots.append(
                CompanyFinanceSnapshot(
                    company=company.name,
                    balance=company.balance,
                    total_income_30d=total_income_30d,
                    total_expense_30d=total_expense_30d,
                    net_cashflow_30d=net_cashflow_30d,
                    budget_vs_actual_year=budget_vs_actual_year,
                    net_budget=net_budget,
                    net_actual=net_actual,
                    net_variance=net_variance,
                    health_status=health_status,
                    rank=0,  # placeholder, assigned after sorting
                )
            )

        snapshots.sort(key=lambda s: s.net_cashflow_30d, reverse=True)

        for i, snapshot in enumerate(snapshots, start=1):
            snapshot.rank = i

        top_performer = snapshots[0].company if snapshots else None
        bottom_performer = snapshots[-1].company if len(snapshots) > 1 else None

        return CompanyComparisonResponse(
            year=year,
            lookback_days=lookback_days,
            snapshots=snapshots,
            total_companies=len(snapshots),
            top_performer=top_performer,
            bottom_performer=bottom_performer,
        )
