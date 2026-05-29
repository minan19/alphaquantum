"""OBS1: SampleDataEngine integration tests."""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.engines.sample_data_engine import SampleDataEngine
from app.identity_repository import IdentityRepository
from app.migration_manager import MigrationManager


class SampleDataEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp.name) / "sample_test.db"
        migrations_dir = Path(__file__).resolve().parent.parent / "migrations"

        bootstrap = IdentityRepository(str(self._db_path))
        bootstrap.close()
        self.manager = MigrationManager(str(self._db_path), str(migrations_dir))
        self.manager.apply_all()

        self.engine = SampleDataEngine(database_path=str(self._db_path))

    def tearDown(self) -> None:
        self.manager.close()
        self._tmp.cleanup()

    def _count(self, table: str, where: str = "") -> int:
        conn = sqlite3.connect(str(self._db_path))
        try:
            sql = f"SELECT COUNT(*) FROM {table}"
            if where:
                sql += f" WHERE {where}"
            return int(conn.execute(sql).fetchone()[0])
        finally:
            conn.close()

    # ── Status ─────────────────────────────────────────────────────────

    def test_has_sample_data_false_initially(self) -> None:
        self.assertFalse(self.engine.has_sample_data(user_id="u1"))

    def test_has_sample_data_true_after_seed(self) -> None:
        self.engine.seed(user_id="u1")
        self.assertTrue(self.engine.has_sample_data(user_id="u1"))

    # ── Seed ──────────────────────────────────────────────────────────

    def test_seed_creates_all_record_types(self) -> None:
        result = self.engine.seed(user_id="u1")
        self.assertEqual(result.customers_created, 8)
        self.assertEqual(result.invoices_created, 12)
        self.assertGreater(result.ledger_entries_created, 0)
        self.assertEqual(result.anomaly_signals_created, 2)
        self.assertFalse(result.already_seeded)

    def test_seed_ledger_creates_90_days_data(self) -> None:
        self.engine.seed(user_id="u1")
        # 90 gün × 2 entry (income + expense) = 180
        ledger_n = self._count(
            "finance_ledger_entries", "category = 'sample_seed'",
        )
        self.assertEqual(ledger_n, 180)

    def test_seed_idempotent_second_call_skips(self) -> None:
        first = self.engine.seed(user_id="u1")
        second = self.engine.seed(user_id="u1")
        self.assertFalse(first.already_seeded)
        self.assertTrue(second.already_seeded)
        self.assertEqual(second.customers_created, 0)

    def test_seed_creates_marked_customers(self) -> None:
        """Sample customers tags JSON'da '_sample_seed' içerir."""
        self.engine.seed(user_id="u1")
        marked = self._count(
            "customers", "tags LIKE '%_sample_seed%'",
        )
        self.assertEqual(marked, 8)

    def test_seed_creates_anomaly_signals_marked(self) -> None:
        self.engine.seed(user_id="u1")
        anomalies = self._count(
            "anomaly_signals", "signature_hash LIKE 'sample_%'",
        )
        self.assertEqual(anomalies, 2)

    # ── Clear ─────────────────────────────────────────────────────────

    def test_clear_removes_only_sample_data(self) -> None:
        # Önce sample seed
        self.engine.seed(user_id="u1")
        # Sonra gerçek bir customer ekle
        conn = sqlite3.connect(str(self._db_path))
        conn.execute(
            """
            INSERT INTO customers
              (company_name, full_name, email, phone, sector,
               tags, notes, is_active, created_at, updated_at)
            VALUES ('Real Co', 'Real Customer', '', '', 'general',
                    '[]', 'Real customer notes', 1, 1700000000, 1700000000)
            """,
        )
        conn.commit()
        conn.close()

        before_customers = self._count("customers")
        result = self.engine.clear(user_id="u1")
        self.assertEqual(result["customers_deleted"], 8)
        # Gerçek customer korunmuş olmalı
        self.assertEqual(
            self._count("customers"), before_customers - 8,
        )
        # Real Co hala duruyor
        self.assertEqual(self._count("customers", "company_name = 'Real Co'"), 1)
        self.assertFalse(self.engine.has_sample_data(user_id="u1"))

    def test_clear_idempotent_when_no_sample(self) -> None:
        result = self.engine.clear(user_id="u1")
        self.assertEqual(result["customers_deleted"], 0)
        self.assertEqual(result["invoices_deleted"], 0)

    def test_seed_then_clear_then_seed_works(self) -> None:
        self.engine.seed(user_id="u1")
        self.engine.clear(user_id="u1")
        result = self.engine.seed(user_id="u1")
        self.assertFalse(result.already_seeded)
        self.assertEqual(result.customers_created, 8)


if __name__ == "__main__":
    unittest.main()
