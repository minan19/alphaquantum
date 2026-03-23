import tempfile
import unittest
from pathlib import Path

from app.connector_repository import ConnectorRepository
from app.engines.connector_engine import ConnectorEngine
from app.models import (
    ConnectorCanonicalPreviewRequest,
    ConnectorCreateRequest,
    ConnectorSyncDispatchRequest,
    ConnectorSyncJobCreateRequest,
)


class ConnectorEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._temp_dir.name) / "connector_engine_test.db"
        self.repo = ConnectorRepository(str(self._db_path))
        self.engine = ConnectorEngine(self.repo)

    def tearDown(self) -> None:
        self.repo.close()
        self._temp_dir.cleanup()

    def test_create_connector_and_canonical_preview(self) -> None:
        connector = self.engine.create_connector(
            ConnectorCreateRequest(
                company_name="Atlas Co",
                connector_type="finance_erp",
                provider="ERP Hub",
                base_url="https://erp.example",
                auth_mode="oauth2",
                config={
                    "token_rotate_days": 30,
                    "ip_allowlist_enabled": True,
                    "mfa_enabled": True,
                    "retry_count": 3,
                    "timeout_seconds": 20,
                },
                mapping={
                    "id": "external_id",
                    "company": "company_name",
                    "type": "entry_type",
                    "amount": "amount",
                    "currency": "currency",
                    "date": "entry_date",
                },
            ),
            created_by="tester",
        )
        self.assertEqual(connector.company_name, "Atlas Co")
        self.assertGreaterEqual(connector.mapping_coverage_score, 95.0)
        self.assertGreaterEqual(connector.readiness_score, 80.0)
        self.assertEqual(connector.status, "active")

        preview = self.engine.preview_canonical_mapping(
            ConnectorCanonicalPreviewRequest(
                connector_type="finance_erp",
                mapping={"id": "external_id", "company": "company_name"},
                sample_payload={
                    "id": "txn-001",
                    "company": "Atlas Co",
                    "type": "income",
                    "amount": 1500,
                    "currency": "USD",
                    "date": "2026-03-22",
                },
            )
        )
        self.assertEqual(preview.target_entity, "finance_ledger_entry")
        self.assertIn("entry_type", preview.mapped_fields)
        self.assertGreaterEqual(preview.coverage_score, 80.0)

        with self.assertRaises(ValueError):
            self.engine.create_connector(
                ConnectorCreateRequest(
                    company_name="Atlas Co",
                    connector_type="finance_erp",
                    provider="ERP Hub",
                ),
                created_by="tester",
            )

    def test_sync_job_queue_and_dispatch_scope_filter(self) -> None:
        connector_a = self.engine.create_connector(
            ConnectorCreateRequest(
                company_name="Scope Co A",
                connector_type="inventory",
                provider="ProviderA",
                auth_mode="api_key",
                mapping={
                    "id": "external_id",
                    "company": "company_name",
                    "productcode": "sku",
                    "productname": "item_name",
                    "qty": "quantity",
                    "timestamp": "updated_at",
                },
            ),
            created_by="tester",
        )
        connector_b = self.engine.create_connector(
            ConnectorCreateRequest(
                company_name="Scope Co B",
                connector_type="inventory",
                provider="ProviderB",
                auth_mode="api_key",
                mapping={
                    "id": "external_id",
                    "company": "company_name",
                    "productcode": "sku",
                    "productname": "item_name",
                    "qty": "quantity",
                    "timestamp": "updated_at",
                },
            ),
            created_by="tester",
        )

        self.engine.create_sync_job(
            connector_a.id,
            ConnectorSyncJobCreateRequest(
                trigger_mode="scheduled",
                criticality="standard",
            ),
            requested_by="tester",
        )
        self.engine.create_sync_job(
            connector_b.id,
            ConnectorSyncJobCreateRequest(
                trigger_mode="manual",
                criticality="critical",
            ),
            requested_by="tester",
        )

        dispatch = self.engine.dispatch_next_sync_job(
            ConnectorSyncDispatchRequest(
                auto_complete=True,
                success=True,
                health_score=92,
            ),
            requested_by="tester",
            allowed_company_names=["Scope Co A"],
        )
        self.assertTrue(dispatch.claimed)
        assert dispatch.connector is not None
        assert dispatch.job is not None
        self.assertEqual(dispatch.connector.company_name, "Scope Co A")
        self.assertEqual(dispatch.job.status, "success")


if __name__ == "__main__":
    unittest.main()
