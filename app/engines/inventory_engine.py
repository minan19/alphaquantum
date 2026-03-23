from __future__ import annotations

from app.models import Company, InventoryCriticalItem, InventoryEngineResponse


class InventoryEngine:
    @staticmethod
    def list_critical(companies: list[Company]) -> InventoryEngineResponse:
        critical_rows: list[InventoryCriticalItem] = []

        for company in companies:
            for item in company.inventory:
                if item.quantity > item.min_level:
                    continue

                gap = max(item.min_level - item.quantity, 0)
                severity = "LOW"
                if gap >= 10:
                    severity = "HIGH"
                elif gap >= 3:
                    severity = "MEDIUM"

                critical_rows.append(
                    InventoryCriticalItem(
                        company=company.name,
                        item_name=item.name,
                        quantity=item.quantity,
                        min_level=item.min_level,
                        gap=gap,
                        severity=severity,
                    )
                )

        critical_rows.sort(key=lambda row: (row.gap, row.company), reverse=True)
        return InventoryEngineResponse(
            total_critical_items=len(critical_rows),
            items=critical_rows,
        )
