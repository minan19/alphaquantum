import unittest

from app.engines import CompanyEngine, FinanceEngine, InventoryEngine
from app.models import Company, InventoryItem


class CompanyEngineTests(unittest.TestCase):
    def test_build_overview(self) -> None:
        companies = [
            Company(
                name="Risk Corp",
                balance=-100,
                inventory=[
                    InventoryItem(name="Kablo", quantity=0, min_level=10),
                    InventoryItem(name="Trafo", quantity=1, min_level=10),
                ],
            ),
            Company(
                name="Stable Corp",
                balance=50_000,
                inventory=[InventoryItem(name="Sigorta", quantity=30, min_level=10)],
            ),
        ]

        result = CompanyEngine.build_overview(companies)

        self.assertEqual(result.total_companies, 2)
        self.assertEqual(result.companies[0].name, "Risk Corp")
        self.assertEqual(result.companies[0].risk_level, "HIGH")


class InventoryEngineTests(unittest.TestCase):
    def test_list_critical(self) -> None:
        companies = [
            Company(
                name="Ops Corp",
                balance=10_000,
                inventory=[
                    InventoryItem(name="Kablo", quantity=0, min_level=10),
                    InventoryItem(name="Trafo", quantity=20, min_level=5),
                ],
            )
        ]

        result = InventoryEngine.list_critical(companies)

        self.assertEqual(result.total_critical_items, 1)
        self.assertEqual(result.items[0].item_name, "Kablo")
        self.assertEqual(result.items[0].severity, "HIGH")


class FinanceEngineTests(unittest.TestCase):
    def test_build_overview(self) -> None:
        companies = [
            Company(
                name="A",
                balance=30_000,
                inventory=[],
            ),
            Company(
                name="B",
                balance=-5_000,
                inventory=[],
            ),
        ]

        result = FinanceEngine.build_overview(companies)

        self.assertEqual(result.total_balance, 25_000)
        self.assertEqual(result.negative_balance_companies, 1)
        self.assertEqual(result.health_status, "RISK")


if __name__ == "__main__":
    unittest.main()
