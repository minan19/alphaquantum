import tempfile
import unittest
from pathlib import Path

from app.engines.holding_engine import HoldingEngine
from app.holding_repository import HoldingRepository
from app.models import (
    HoldingBulkOnboardRequest,
    HoldingCompanyOnboardInput,
    HoldingCreateRequest,
    HoldingOnboardRequest,
)
from app.repository import CompanyRepository, default_companies


class HoldingEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._temp_dir.name) / "holding_engine_test.db"
        self.company_repo = CompanyRepository(str(self._db_path), default_companies())
        self.holding_repo = HoldingRepository(str(self._db_path))
        self.engine = HoldingEngine(self.holding_repo, self.company_repo)

    def tearDown(self) -> None:
        self.holding_repo.close()
        self.company_repo.close()
        self._temp_dir.cleanup()

    def test_bulk_onboard_creates_holding_and_registers_companies(self) -> None:
        response = self.engine.onboard_bulk(
            HoldingBulkOnboardRequest(
                holding=HoldingCreateRequest(
                    name="Atlas Holding",
                    code="ATLAS",
                    description="Global portfolio holding",
                ),
                onboarding=HoldingOnboardRequest(
                    auto_register_companies=True,
                    companies=[
                        HoldingCompanyOnboardInput(
                            company_name="Atlas Energy",
                            sector="Energy",
                            country="TR",
                            data_quality_score=92,
                            integration_completeness_score=91,
                            security_compliance_score=90,
                            process_standardization_score=88,
                            master_data_health_score=90,
                            team_readiness_score=87,
                        ),
                        HoldingCompanyOnboardInput(
                            company_name="Atlas Retail",
                            sector="Retail",
                            country="TR",
                            data_quality_score=50,
                            integration_completeness_score=45,
                            security_compliance_score=40,
                            process_standardization_score=48,
                            master_data_health_score=42,
                            team_readiness_score=46,
                        ),
                    ],
                ),
            )
        )
        self.assertEqual(response.holding.name, "Atlas Holding")
        self.assertEqual(response.onboarding.total_companies, 2)
        self.assertEqual(response.onboarding.go_count, 1)
        self.assertEqual(response.onboarding.block_count, 1)
        self.assertTrue(self.company_repo.has_company("Atlas Energy"))
        self.assertTrue(self.company_repo.has_company("Atlas Retail"))

    def test_onboard_without_auto_register_keeps_external_company_unregistered(self) -> None:
        holding = self.engine.create_holding(
            HoldingCreateRequest(
                name="Scope Holding",
                code="SCOPE",
            )
        )
        response = self.engine.onboard_companies(
            holding.id,
            HoldingOnboardRequest(
                auto_register_companies=False,
                companies=[
                    HoldingCompanyOnboardInput(
                        company_name="External Co",
                        sector="Technology",
                        country="US",
                    )
                ],
            ),
        )
        self.assertEqual(response.total_companies, 1)
        self.assertFalse(response.items[0].registered_in_platform)
        self.assertFalse(self.company_repo.has_company("External Co"))


if __name__ == "__main__":
    unittest.main()
