from __future__ import annotations

from app.models import Company, CompanyEngineResponse, CompanyOverviewItem


class CompanyEngine:
    @staticmethod
    def build_overview(companies: list[Company]) -> CompanyEngineResponse:
        items: list[CompanyOverviewItem] = []
        for company in companies:
            critical_count = sum(
                1
                for inventory_item in company.inventory
                if inventory_item.quantity <= inventory_item.min_level
            )
            risk_level = "LOW"
            if company.balance < 0 or critical_count >= 2:
                risk_level = "HIGH"
            elif critical_count >= 1:
                risk_level = "MEDIUM"

            items.append(
                CompanyOverviewItem(
                    name=company.name,
                    balance=company.balance,
                    inventory_items=len(company.inventory),
                    critical_items=critical_count,
                    risk_level=risk_level,
                )
            )

        risk_weight = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
        items.sort(
            key=lambda row: (
                -risk_weight.get(row.risk_level, 0),
                -row.critical_items,
                row.balance,
            )
        )
        return CompanyEngineResponse(total_companies=len(items), companies=items)
