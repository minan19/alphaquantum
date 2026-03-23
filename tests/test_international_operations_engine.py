import tempfile
import unittest
from pathlib import Path

from app.engines.international_operations_engine import InternationalOperationsEngine
from app.identity_repository import IdentityRepository
from app.international_repository import InternationalProjectRepository
from app.migration_manager import MigrationManager
from app.models import InternationalProjectRequest


class InternationalOperationsEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._temp_dir.name) / "international_ops_test.db"

        identity_repo = IdentityRepository(str(self._db_path))
        identity_repo.close()

        migrations_dir = Path(__file__).resolve().parent.parent / "migrations"
        self.migrations = MigrationManager(str(self._db_path), str(migrations_dir))
        self.migrations.apply_all()

        self.repo = InternationalProjectRepository(str(self._db_path))
        self.engine = InternationalOperationsEngine(self.repo)

    def tearDown(self) -> None:
        self.repo.close()
        self.migrations.close()
        self._temp_dir.cleanup()

    def test_create_list_and_get_project(self) -> None:
        created = self.engine.create_project(
            InternationalProjectRequest(
                project_name="International Delivery Network",
                company_name="Alpha Quantum A.S.",
                base_country="TR",
                target_countries=["DE", "AE", "USA"],
                services=["management", "consulting", "import_export"],
                sectors=["energy", "telecom"],
                strategic_objectives=["Increase recurring revenue", "Expand country portfolio"],
                budget_total=15_000_000,
                currency="USD",
                timeline_months=16,
                risk_appetite="medium",
                local_partner_required=True,
                preferred_incoterms=["FOB", "CIF", "DAP"],
                trade_lanes=["TR->DE", "TR->AE", "TR->US"],
                notes="Use phased market entry with partner governance.",
            )
        )

        self.assertGreater(created.id, 0)
        self.assertEqual(created.base_country, "TR")
        self.assertEqual(len(created.report.country_profiles), 3)
        self.assertIn(created.report.recommendation, {"GO", "CONDITIONAL_GO", "NO_GO"})
        self.assertIn("# International Project Development Report", created.report.report_markdown)

        listed = self.engine.list_projects(limit=20)
        self.assertGreaterEqual(listed.total, 1)
        self.assertEqual(listed.items[0].id, created.id)
        self.assertEqual(listed.items[0].project_name, "International Delivery Network")

        fetched = self.engine.get_project(created.id)
        self.assertEqual(fetched.id, created.id)
        self.assertEqual(fetched.report.project_name, created.report.project_name)
        self.assertEqual(fetched.report.base_country, "TR")

    def test_get_missing_project_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            self.engine.get_project(999999)


if __name__ == "__main__":
    unittest.main()
