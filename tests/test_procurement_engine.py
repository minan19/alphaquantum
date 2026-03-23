import tempfile
import unittest
from pathlib import Path

from app.engines.procurement_engine import ProcurementEngine
from app.engines.tender_engine import TenderEngine
from app.identity_repository import IdentityRepository
from app.migration_manager import MigrationManager
from app.models import (
    ProcurementAutoOrderRequest,
    ProcurementRequestCreateRequest,
    ProcurementRequestItemCreateRequest,
    ProcurementTenderPlanRequest,
    ProcurementVendorQuoteCreateRequest,
    ProcurementQuoteItemCreateRequest,
    TenderGenerationRequest,
)
from app.procurement_repository import ProcurementRepository


class ProcurementEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._temp_dir.name) / "procurement_test.db"

        identity_repo = IdentityRepository(str(self._db_path))
        identity_repo.close()

        migrations_dir = Path(__file__).resolve().parent.parent / "migrations"
        self.migrations = MigrationManager(str(self._db_path), str(migrations_dir))
        self.migrations.apply_all()

        self.repo = ProcurementRepository(str(self._db_path))
        self.engine = ProcurementEngine(self.repo, TenderEngine())

    def tearDown(self) -> None:
        self.repo.close()
        self.migrations.close()
        self._temp_dir.cleanup()

    def test_create_quote_evaluate_and_auto_order(self) -> None:
        request = self.engine.create_request(
            ProcurementRequestCreateRequest(
                company="Alpha Quantum A.S.",
                title="Datacenter Network Refresh",
                strategy="balanced",
                budget_limit=1000,
                currency="TRY",
                items=[
                    ProcurementRequestItemCreateRequest(
                        item_name="Network Switch",
                        specification="Layer3 managed switch",
                        quantity=10,
                        min_quality_score=70,
                        max_unit_price=20,
                        must_comply_tender=True,
                    )
                ],
            )
        )
        self.assertEqual(request.status, "open")
        self.assertEqual(len(request.items), 1)

        request_item_id = request.items[0].id
        self.engine.submit_quote(
            ProcurementVendorQuoteCreateRequest(
                request_id=request.id,
                vendor_name="VendorA",
                vendor_rating=90,
                delivery_days=4,
                warranty_months=36,
                compliance_score=95,
                quote_items=[
                    ProcurementQuoteItemCreateRequest(
                        request_item_id=request_item_id,
                        unit_price=11,
                        available_quantity=10,
                        quality_score=95,
                    )
                ],
            )
        )
        self.engine.submit_quote(
            ProcurementVendorQuoteCreateRequest(
                request_id=request.id,
                vendor_name="VendorB",
                vendor_rating=45,
                delivery_days=7,
                warranty_months=12,
                compliance_score=72,
                quote_items=[
                    ProcurementQuoteItemCreateRequest(
                        request_item_id=request_item_id,
                        unit_price=10,
                        available_quantity=10,
                        quality_score=60,
                    )
                ],
            )
        )

        evaluation = self.engine.evaluate_request(request.id)
        self.assertEqual(evaluation.unresolved_items, 0)
        self.assertEqual(evaluation.resolved_items, 1)
        self.assertEqual(evaluation.recommendations[0].selected_vendor, "VendorA")

        batch = self.engine.create_auto_purchase_orders(
            request.id,
            ProcurementAutoOrderRequest(auto_approve=True),
        )
        self.assertEqual(batch.total_orders, 1)
        self.assertEqual(batch.orders[0].status, "approved")
        self.assertGreater(batch.total_amount, 0)

    def test_create_request_from_tender_extracts_items(self) -> None:
        plan = self.engine.create_request_from_tender(
            ProcurementTenderPlanRequest(
                tender=TenderGenerationRequest(
                    institution_name="Sample Institution",
                    tender_title="Campus Security Upgrade",
                    company_name="Alpha Quantum A.S.",
                    administrative_spec=(
                        "Bidder must provide required documents and submit all declarations."
                    ),
                    technical_spec=(
                        "Vendor shall supply camera and network switch devices. "
                        "Installation service and software license shall be included."
                    ),
                    additional_requirements=["UPS power units are mandatory."],
                ),
                strategy="tender_compliance",
                default_quantity=2,
                max_items=10,
            )
        )
        self.assertGreaterEqual(plan.extracted_item_count, 2)
        self.assertTrue(plan.procurement_request.items[0].must_comply_tender)
        self.assertEqual(plan.procurement_request.strategy, "tender_compliance")


if __name__ == "__main__":
    unittest.main()
