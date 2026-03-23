import unittest

from app.models import Company, InventoryItem
from app.services import AnalysisService, DashboardService


class AnalysisServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = AnalysisService()

    def test_analyze_company_high_risk(self) -> None:
        company = Company(
            name="Risk Corp",
            balance=-1000,
            inventory=[
                InventoryItem(name="Kablo", quantity=0, min_level=10),
                InventoryItem(name="Trafo", quantity=1, min_level=10),
            ],
        )

        result = self.service.analyze_company(company)

        self.assertEqual(result.company, "Risk Corp")
        self.assertEqual(result.status, "Riskli")
        self.assertGreaterEqual(result.risk_score, 70)
        self.assertEqual(result.trend, "Dusus")
        self.assertGreaterEqual(len(result.critical_stock), 2)

    def test_analyze_company_low_risk(self) -> None:
        company = Company(
            name="Stable Corp",
            balance=120_000,
            inventory=[
                InventoryItem(name="Kablo", quantity=15, min_level=10),
                InventoryItem(name="Trafo", quantity=20, min_level=5),
            ],
        )

        result = self.service.analyze_company(company)

        self.assertEqual(result.status, "Saglikli")
        self.assertEqual(result.risk_score, 0)
        self.assertEqual(result.trend, "Yukselis")
        self.assertEqual(result.action, "Yatirim yapilabilir")


class DashboardServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.analysis_service = AnalysisService()
        self.dashboard_service = DashboardService()

    def test_build_summary_includes_risk_companies(self) -> None:
        companies = [
            Company(
                name="Risk Corp",
                balance=-1_000,
                inventory=[InventoryItem(name="Kablo", quantity=0, min_level=5)],
            ),
            Company(
                name="Safe Corp",
                balance=30_000,
                inventory=[InventoryItem(name="Trafo", quantity=10, min_level=5)],
            ),
        ]

        analyses = self.analysis_service.analyze_all(companies)
        summary = self.dashboard_service.build_summary(companies, analyses)

        self.assertEqual(summary.total_companies, 2)
        self.assertEqual(summary.risk_companies, 1)
        self.assertGreaterEqual(summary.critical_items, 1)

    def test_build_insights_returns_ranked_items(self) -> None:
        companies = [
            Company(
                name="Risk Corp",
                balance=-5_000,
                inventory=[InventoryItem(name="Kablo", quantity=0, min_level=15)],
            ),
            Company(
                name="Safe Corp",
                balance=50_000,
                inventory=[InventoryItem(name="Trafo", quantity=12, min_level=5)],
            ),
        ]

        analyses = self.analysis_service.analyze_all(companies)
        insights = self.dashboard_service.build_insights(analyses)

        self.assertGreaterEqual(len(insights), 2)
        self.assertEqual(insights[0].company, "Risk Corp")
        self.assertIn(insights[0].severity, {"HIGH", "MEDIUM", "LOW"})


if __name__ == "__main__":
    unittest.main()
