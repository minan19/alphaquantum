import tempfile
import time
import unittest
from pathlib import Path

from app.connector_adapters import ConnectorAdapterRegistry
from app.connector_repository import ConnectorRepository
from app.connector_sync_worker import ConnectorSyncWorker
from app.engines.connector_engine import ConnectorEngine
from app.models import ConnectorCreateRequest, ConnectorSyncJobCreateRequest


class ConnectorSyncWorkerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._temp_dir.name) / "connector_worker_test.db"
        self.repo = ConnectorRepository(str(self._db_path))
        self.engine = ConnectorEngine(self.repo)
        self.worker = ConnectorSyncWorker(
            engine=self.engine,
            adapters=ConnectorAdapterRegistry(),
            poll_interval_seconds=1,
            retry_backoff_seconds=5,
            max_retries=3,
        )

    def tearDown(self) -> None:
        self.worker.stop()
        self.repo.close()
        self._temp_dir.cleanup()

    def test_worker_processes_successful_sync_job(self) -> None:
        connector = self.engine.create_connector(
            ConnectorCreateRequest(
                company_name="Worker Co",
                connector_type="finance_erp",
                provider="WorkerERP",
                auth_mode="oauth2",
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
        self.engine.create_sync_job(
            connector.id,
            ConnectorSyncJobCreateRequest(
                trigger_mode="manual",
                criticality="standard",
                max_attempts=3,
            ),
            requested_by="tester",
        )
        processed = self.worker.run_once()
        self.assertTrue(processed)

        jobs = self.engine.list_sync_jobs(connector_id=connector.id, status="success", limit=10)
        self.assertEqual(jobs.total, 1)
        self.assertEqual(jobs.items[0].status, "success")
        self.assertEqual(jobs.items[0].attempt_count, 1)

    def test_worker_retries_and_moves_job_to_dead_letter(self) -> None:
        connector = self.engine.create_connector(
            ConnectorCreateRequest(
                company_name="Worker Retry Co",
                connector_type="inventory",
                provider="WorkerInventory",
                auth_mode="api_key",
                config={"fail_until_attempt": 10},
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
        created = self.engine.create_sync_job(
            connector.id,
            ConnectorSyncJobCreateRequest(
                trigger_mode="manual",
                criticality="high",
                max_attempts=3,
            ),
            requested_by="tester",
        )
        self.assertEqual(created.max_attempts, 3)

        for _ in range(2):
            processed = self.worker.run_once()
            self.assertTrue(processed)
            # Make retry due immediately for deterministic test runtime.
            with self.repo._lock:  # type: ignore[attr-defined]
                self.repo._conn.execute(  # type: ignore[attr-defined]
                    "UPDATE integration_sync_jobs SET next_retry_at = ? WHERE id = ?",
                    (int(time.time()) - 1, created.id),
                )
                self.repo._conn.commit()  # type: ignore[attr-defined]

        processed = self.worker.run_once()
        self.assertTrue(processed)

        dead_letter = self.engine.list_sync_jobs(
            connector_id=connector.id,
            status="dead_letter",
            limit=10,
        )
        self.assertEqual(dead_letter.total, 1)
        row = dead_letter.items[0]
        self.assertEqual(row.status, "dead_letter")
        self.assertEqual(row.attempt_count, 3)
        self.assertIsNotNone(row.dead_lettered_at)
        self.assertEqual(row.error_code, "TRANSIENT_PROVIDER_ERROR")

    def test_leader_lock_allows_single_worker(self) -> None:
        connector = self.engine.create_connector(
            ConnectorCreateRequest(
                company_name="Worker Leader Co",
                connector_type="finance_erp",
                provider="WorkerLeaderERP",
                auth_mode="oauth2",
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
        for _ in range(2):
            self.engine.create_sync_job(
                connector.id,
                ConnectorSyncJobCreateRequest(
                    trigger_mode="manual",
                    criticality="standard",
                    max_attempts=3,
                ),
                requested_by="tester",
            )

        worker_b = ConnectorSyncWorker(
            engine=self.engine,
            adapters=ConnectorAdapterRegistry(),
            poll_interval_seconds=1,
            retry_backoff_seconds=5,
            max_retries=3,
            leader_lock_enabled=True,
            lease_seconds=30,
            heartbeat_seconds=5,
            worker_name="connector-sync-worker",
        )
        try:
            processed_a = self.worker.run_once()
            self.assertTrue(processed_a)
            self.assertTrue(self.worker.is_leader())

            processed_b_while_locked = worker_b.run_once()
            self.assertFalse(processed_b_while_locked)
            self.assertFalse(worker_b.is_leader())

            queued_jobs = self.engine.list_sync_jobs(
                connector_id=connector.id,
                status="queued",
                limit=10,
            )
            self.assertEqual(queued_jobs.total, 1)

            self.worker.stop()
            processed_b_after_release = worker_b.run_once()
            self.assertTrue(processed_b_after_release)
            self.assertTrue(worker_b.is_leader())
        finally:
            worker_b.stop()


if __name__ == "__main__":
    unittest.main()
