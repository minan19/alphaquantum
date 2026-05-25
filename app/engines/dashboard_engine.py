from __future__ import annotations

from datetime import datetime

from app.models import (
    DashboardLiveSignalsResponse,
    DashboardSignalItem,
    FinanceCashflowResponse,
    FinanceOverviewResponse,
)


class DashboardEngine:
    """Aggregates live signals from multiple sources into a single dashboard response."""

    def build_signals(
        self,
        *,
        company_scope: str | None,
        finance_overview: FinanceOverviewResponse | None,
        cashflow: FinanceCashflowResponse | None,
        low_stock_count: int,
        procurement_active_count: int,
        feasibility_pending_count: int,
        market_signal_count: int,
        # S-335 — operational signals
        overdue_task_count: int = 0,
        unread_critical_notification_count: int = 0,
    ) -> DashboardLiveSignalsResponse:
        signals: list[DashboardSignalItem] = []

        # Finance health signal
        if finance_overview is not None:
            health = finance_overview.health_status
            if health == "HEALTHY":
                health_status = "OK"
            elif health == "WATCH":
                health_status = "WARN"
            else:
                health_status = "ALERT"
            signals.append(
                DashboardSignalItem(
                    source="finance",
                    label="Finance Health",
                    value=health,
                    unit="",
                    status=health_status,
                    detail="",
                )
            )

            # Finance balance signal
            balance = finance_overview.total_balance
            balance_status = "OK" if balance >= 0 else "ALERT"
            signals.append(
                DashboardSignalItem(
                    source="finance",
                    label="Total Balance",
                    value=balance,
                    unit="USD",
                    status=balance_status,
                    detail="",
                )
            )
        else:
            signals.append(
                DashboardSignalItem(
                    source="finance",
                    label="Finance Health",
                    value=None,
                    unit="",
                    status="ALERT",
                    detail="No finance data available",
                )
            )
            signals.append(
                DashboardSignalItem(
                    source="finance",
                    label="Total Balance",
                    value=None,
                    unit="USD",
                    status="ALERT",
                    detail="No finance data available",
                )
            )

        # Net cashflow 30d signal
        if cashflow is not None:
            net_cf = cashflow.net_cashflow
            cf_status = "OK" if net_cf >= 0 else "WARN"
            signals.append(
                DashboardSignalItem(
                    source="finance",
                    label="Net Cashflow 30d",
                    value=net_cf,
                    unit="USD",
                    status=cf_status,
                    detail="",
                )
            )
        else:
            signals.append(
                DashboardSignalItem(
                    source="finance",
                    label="Net Cashflow 30d",
                    value=None,
                    unit="USD",
                    status="WARN",
                    detail="Cashflow data unavailable",
                )
            )

        # Inventory alerts signal
        signals.append(
            DashboardSignalItem(
                source="inventory",
                label="Inventory Alerts",
                value=low_stock_count,
                unit="companies",
                status="ALERT" if low_stock_count > 0 else "OK",
                detail="",
            )
        )

        # Procurement pipeline signal
        signals.append(
            DashboardSignalItem(
                source="procurement",
                label="Procurement Pipeline",
                value=procurement_active_count,
                unit="items",
                status="OK",
                detail="",
            )
        )

        # Feasibility pipeline signal
        signals.append(
            DashboardSignalItem(
                source="feasibility",
                label="Feasibility Pipeline",
                value=feasibility_pending_count,
                unit="reports",
                status="OK",
                detail="",
            )
        )

        # Market data signal
        signals.append(
            DashboardSignalItem(
                source="market",
                label="Market Data",
                value=market_signal_count,
                unit="symbols cached",
                status="OK" if market_signal_count > 0 else "WARN",
                detail="",
            )
        )

        # S-335 — Task overdue signal (operasyonel uyarı)
        signals.append(
            DashboardSignalItem(
                source="tasks",
                label="Overdue Tasks",
                value=overdue_task_count,
                unit="tasks",
                status=(
                    "ALERT" if overdue_task_count > 5
                    else "WARN" if overdue_task_count > 0
                    else "OK"
                ),
                detail="",
            )
        )

        # S-335 — Unread critical notifications signal (S-334 motoruna bağlı)
        signals.append(
            DashboardSignalItem(
                source="notifications",
                label="Critical Notifications",
                value=unread_critical_notification_count,
                unit="unread",
                status=(
                    "ALERT" if unread_critical_notification_count > 0
                    else "OK"
                ),
                detail="",
            )
        )

        alert_count = sum(1 for s in signals if s.status == "ALERT")
        warn_count = sum(1 for s in signals if s.status == "WARN")

        return DashboardLiveSignalsResponse(
            generated_at=datetime.utcnow().isoformat() + "Z",
            company_scope=company_scope,
            signals=signals,
            alert_count=alert_count,
            warn_count=warn_count,
        )
