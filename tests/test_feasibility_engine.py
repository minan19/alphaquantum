import tempfile
import unittest
from pathlib import Path

from app.engines.feasibility_engine import FeasibilityEngine
from app.feasibility_repository import FeasibilityRepository
from app.identity_repository import IdentityRepository
from app.migration_manager import MigrationManager
from app.models import FeasibilityReportRequest


class FeasibilityEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._temp_dir.name) / "feasibility_test.db"

        identity_repo = IdentityRepository(str(self._db_path))
        identity_repo.close()

        migrations_dir = Path(__file__).resolve().parent.parent / "migrations"
        self.migrations = MigrationManager(str(self._db_path), str(migrations_dir))
        self.migrations.apply_all()

        self.repo = FeasibilityRepository(str(self._db_path))
        self.engine = FeasibilityEngine(self.repo)

    def tearDown(self) -> None:
        self.repo.close()
        self.migrations.close()
        self._temp_dir.cleanup()

    def test_generate_persist_list_and_get(self) -> None:
        created = self.engine.generate(
            FeasibilityReportRequest(
                project_name="Logistics Hub Automation",
                sector="Logistics",
                geography="TR",
                objective=(
                    "Establish an automated logistics hub to improve throughput, reduce handling "
                    "costs, and improve service-level compliance."
                ),
                currency="TRY",
                initial_investment=45_000_000,
                annual_opex=7_500_000,
                annual_revenue_base=16_000_000,
                project_lifetime_years=10,
                implementation_months=8,
                discount_rate=0.15,
                tax_rate=0.2,
                inflation_rate=0.14,
                revenue_growth_base=0.09,
                revenue_growth_upside=0.16,
                revenue_growth_downside=-0.04,
                opex_growth_base=0.1,
                capacity_utilization=0.74,
                financing_debt_ratio=0.5,
                regulatory_requirements=["Occupational safety certification"],
                constraints=["Skilled labor availability"],
                additional_notes="Pilot rollout in first two regions.",
            )
        )

        self.assertGreater(created.id, 0)
        self.assertEqual(created.project_name, "Logistics Hub Automation")
        self.assertEqual(created.report.project_name, "Logistics Hub Automation")
        self.assertEqual(len(created.report.scenarios), 3)
        self.assertEqual(len(created.report.sensitivity_analysis), 6)
        self.assertGreaterEqual(len(created.report.coverage), 10)
        self.assertIn(created.report.recommendation, {"GO", "CONDITIONAL_GO", "NO_GO"})
        self.assertIn("# Feasibility Report", created.report.report_markdown)

        listed = self.engine.list_reports(limit=20)
        self.assertGreaterEqual(listed.total, 1)
        self.assertEqual(listed.items[0].id, created.id)
        self.assertEqual(listed.items[0].project_name, "Logistics Hub Automation")

        fetched = self.engine.get_report(created.id)
        self.assertEqual(fetched.id, created.id)
        self.assertEqual(fetched.report.project_name, created.report.project_name)
        self.assertEqual(fetched.report.financial_metrics.npv, created.report.financial_metrics.npv)

    def test_get_missing_report_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            self.engine.get_report(999999)


if __name__ == "__main__":
    unittest.main()
