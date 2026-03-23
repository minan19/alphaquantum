import tempfile
import unittest
from pathlib import Path

from app.engines.feasibility_engine import FeasibilityEngine
from app.engines.international_operations_engine import InternationalOperationsEngine
from app.engines.procurement_engine import ProcurementEngine
from app.engines.strategic_ecosystem_engine import StrategicEcosystemEngine
from app.engines.tender_engine import TenderEngine
from app.feasibility_repository import FeasibilityRepository
from app.identity_repository import IdentityRepository
from app.international_repository import InternationalProjectRepository
from app.migration_manager import MigrationManager
from app.models import (
    EcosystemActivationRequest,
    EcosystemPortfolioActivationRequest,
    EcosystemPortfolioCompanyInput,
    EcosystemProcurementItem,
)
from app.procurement_repository import ProcurementRepository


class StrategicEcosystemEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._temp_dir.name) / "ecosystem_engine_test.db"

        identity_repo = IdentityRepository(str(self._db_path))
        identity_repo.close()

        migrations_dir = Path(__file__).resolve().parent.parent / "migrations"
        self.migrations = MigrationManager(str(self._db_path), str(migrations_dir))
        self.migrations.apply_all()

        self.feasibility_repo = FeasibilityRepository(str(self._db_path))
        self.international_repo = InternationalProjectRepository(str(self._db_path))
        self.procurement_repo = ProcurementRepository(str(self._db_path))

        self.engine = StrategicEcosystemEngine(
            FeasibilityEngine(self.feasibility_repo),
            InternationalOperationsEngine(self.international_repo),
            ProcurementEngine(self.procurement_repo, TenderEngine()),
        )

    def tearDown(self) -> None:
        self.feasibility_repo.close()
        self.international_repo.close()
        self.procurement_repo.close()
        self.migrations.close()
        self._temp_dir.cleanup()

    def test_activate_with_procurement_bootstrap(self) -> None:
        response = self.engine.activate(
            EcosystemActivationRequest(
                project_name="Integrated Expansion Program",
                company_name="Alpha Quantum A.S.",
                sector="Energy",
                geography="TR",
                objective=(
                    "Establish country-based operations with integrated procurement and international "
                    "execution governance."
                ),
                budget_total=20_000_000,
                currency="USD",
                base_country="TR",
                target_countries=["DE", "AE"],
                services=["management", "consulting", "import_export"],
                timeline_months=18,
                risk_appetite="medium",
                procurement_items=[
                    EcosystemProcurementItem(
                        item_name="Transformer",
                        quantity=4,
                        specification="Power transformer set",
                        min_quality_score=75,
                        max_unit_price=150000,
                        must_comply_tender=True,
                    ),
                    EcosystemProcurementItem(
                        item_name="Control Panel",
                        quantity=8,
                        specification="Industrial control panel",
                        min_quality_score=70,
                        max_unit_price=60000,
                    ),
                ],
            )
        )

        self.assertGreater(response.feasibility_report_id, 0)
        self.assertGreater(response.international_project_id, 0)
        self.assertIsNotNone(response.procurement_request_id)
        self.assertIn(response.recommendation, {"GO", "CONDITIONAL_GO", "NO_GO"})
        self.assertIn("feasibility", response.module_status)
        self.assertIn("international_operations", response.module_status)
        self.assertIn("procurement", response.module_status)
        self.assertGreaterEqual(len(response.action_plan), 4)
        self.assertIn("Feasibility Report", response.feasibility_report_markdown_preview)

    def test_activate_without_procurement_bootstrap(self) -> None:
        response = self.engine.activate(
            EcosystemActivationRequest(
                project_name="Consulting Expansion",
                company_name="Alpha Quantum A.S.",
                sector="Consulting",
                geography="EU",
                objective="Expand consulting capabilities in multiple target countries with governance controls.",
                budget_total=5_000_000,
                currency="USD",
                base_country="TR",
                target_countries=["GB", "DE"],
                services=["management", "consulting"],
                timeline_months=12,
                risk_appetite="low",
            )
        )
        self.assertGreater(response.feasibility_report_id, 0)
        self.assertGreater(response.international_project_id, 0)
        self.assertIsNone(response.procurement_request_id)

    def test_activate_portfolio_multi_and_holding_scope(self) -> None:
        multi = self.engine.activate_portfolio(
            EcosystemPortfolioActivationRequest(
                scope_mode="multi",
                project_name_prefix="Portfolio Program",
                base_country="TR",
                target_countries=["DE", "AE"],
                services=["management", "consulting", "import_export"],
                companies=[
                    EcosystemPortfolioCompanyInput(
                        company_name="Alpha Energy",
                        sector="Energy",
                        geography="TR",
                        objective="Expand energy service footprint in multiple countries with integrated controls.",
                        budget_total=8_000_000,
                    ),
                    EcosystemPortfolioCompanyInput(
                        company_name="Alpha Tech",
                        sector="Technology",
                        geography="EU",
                        objective="Scale technology deployment and advisory operations for export markets.",
                        budget_total=6_500_000,
                    ),
                ],
            )
        )
        self.assertEqual(multi.scope_mode, "multi")
        self.assertEqual(multi.total_companies, 2)
        self.assertEqual(multi.successful_companies, 2)
        self.assertEqual(multi.failed_companies, 0)
        self.assertIn(multi.portfolio_recommendation, {"GO", "CONDITIONAL_GO", "NO_GO"})
        self.assertGreaterEqual(len(multi.items), 2)

        holding = self.engine.activate_portfolio(
            EcosystemPortfolioActivationRequest(
                scope_mode="holding",
                holding_name="Alpha Holding",
                project_name_prefix="Holding Program",
                base_country="TR",
                target_countries=["DE", "US"],
                services=["management", "consulting"],
                companies=[],
                use_registered_companies_when_empty=True,
                default_sector="General",
                default_geography="Global",
                default_objective=(
                    "Run holding-wide integrated activation across all subsidiaries with common governance."
                ),
                default_budget_total=4_000_000,
            ),
            registered_company_names=["ABC Holding", "Subsidiary A", "Subsidiary B"],
        )
        self.assertEqual(holding.scope_mode, "holding")
        self.assertEqual(holding.holding_name, "Alpha Holding")
        self.assertEqual(holding.total_companies, 3)
        self.assertEqual(holding.successful_companies, 3)


if __name__ == "__main__":
    unittest.main()
