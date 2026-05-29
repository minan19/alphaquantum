import tempfile
import unittest
from pathlib import Path

from app.identity_repository import IdentityRepository
from app.migration_manager import MigrationManager


class MigrationManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._temp_dir.name) / "migration_test.db"
        self._migrations_dir = Path(__file__).resolve().parent.parent / "migrations"

        # roles table must exist before permission migration due FK.
        bootstrap_repo = IdentityRepository(str(self._db_path))
        bootstrap_repo.close()

        self.manager = MigrationManager(str(self._db_path), str(self._migrations_dir))

    def tearDown(self) -> None:
        self.manager.close()
        self._temp_dir.cleanup()

    def test_apply_status_and_rollback(self) -> None:
        applied = self.manager.apply_all()
        self.assertEqual(applied, list(range(1, 25)))

        status = self.manager.status()
        self.assertEqual(len(status), 24)
        for i in range(24):
            self.assertTrue(status[i]["applied"])

        # Migration 24 (dashboard_layouts) safe to roll back — yeni tablo.
        rolled_back = self.manager.rollback(steps=1)
        self.assertEqual(rolled_back, [24])

        status_after = self.manager.status()
        for i in range(23):
            self.assertTrue(status_after[i]["applied"])
        self.assertFalse(status_after[23]["applied"])

        reapplied = self.manager.apply_all()
        self.assertEqual(reapplied, [24])

    def test_023_intercompany_schema_shape(self) -> None:
        """G1.1: intercompany migration adds the right columns + tables.

        Verifies Critical Finding #1 from the gap analysis is structurally
        resolved — schema can now physically express double-entry
        intercompany transfers.
        """
        self.manager.apply_all()

        # 1. finance_ledger_entries gained 3 columns
        cur = self.manager._conn.execute("PRAGMA table_info(finance_ledger_entries)")
        cols = {row["name"]: row for row in cur.fetchall()}
        self.assertIn("counterparty_company", cols)
        self.assertIn("transfer_id", cols)
        self.assertIn("intercompany_flag", cols)
        # intercompany_flag defaults to 0 (non-intercompany) — backward compatible
        self.assertEqual(cols["intercompany_flag"]["notnull"], 1)

        # 2. intercompany_transfers master table exists with expected columns
        cur = self.manager._conn.execute("PRAGMA table_info(intercompany_transfers)")
        tcols = {row["name"]: row for row in cur.fetchall()}
        for required in (
            "id", "holding_id", "from_company", "to_company",
            "amount", "currency", "requested_by", "requested_at",
            "approval_status", "approved_by", "approved_at",
            "completed_at", "ledger_entry_from_id", "ledger_entry_to_id",
            "fx_rate", "target_amount", "reject_reason",
        ):
            self.assertIn(required, tcols, f"missing column: {required}")

        # 3. CHECK constraint: from_company != to_company
        with self.assertRaises(Exception):
            self.manager._conn.execute(
                """
                INSERT INTO intercompany_transfers
                    (holding_id, from_company, to_company, amount, requested_by, requested_at)
                VALUES (1, 'AcmeCo', 'AcmeCo', 100.0, 'u1', 1700000000)
                """
            )

        # 4. CHECK constraint: amount > 0
        with self.assertRaises(Exception):
            self.manager._conn.execute(
                """
                INSERT INTO intercompany_transfers
                    (holding_id, from_company, to_company, amount, requested_by, requested_at)
                VALUES (1, 'A', 'B', 0, 'u1', 1700000000)
                """
            )

        # 5. CHECK constraint: approval_status enum
        with self.assertRaises(Exception):
            self.manager._conn.execute(
                """
                INSERT INTO intercompany_transfers
                    (holding_id, from_company, to_company, amount, requested_by, requested_at, approval_status)
                VALUES (1, 'A', 'B', 100, 'u1', 1700000000, 'INVALID_STATUS')
                """
            )

        # 6. Happy path: valid pending transfer inserts cleanly
        cur = self.manager._conn.execute(
            """
            INSERT INTO intercompany_transfers
                (holding_id, from_company, to_company, amount, currency,
                 description, requested_by, requested_at)
            VALUES (1, 'Inşaat A.Ş.', 'Lojistik A.Ş.', 50000.0, 'TRY',
                    'Q4 kaynak desteği', 'cfo@holding.tr', 1700000000)
            """
        )
        self.manager._conn.commit()
        self.assertIsNotNone(cur.lastrowid)

    def test_023_ledger_intercompany_flag_default(self) -> None:
        """Existing ledger inserts (legacy code) keep intercompany_flag = 0."""
        self.manager.apply_all()
        self.manager._conn.execute(
            """
            INSERT INTO finance_ledger_entries
                (company_name, entry_type, amount, category, description, entry_date, created_at)
            VALUES ('AcmeCo', 'income', 1000.0, 'sales', 'Q4 invoice', '2026-01-15', 1700000000)
            """
        )
        self.manager._conn.commit()
        row = self.manager._conn.execute(
            "SELECT intercompany_flag, transfer_id, counterparty_company "
            "FROM finance_ledger_entries WHERE company_name = 'AcmeCo'"
        ).fetchone()
        self.assertEqual(row["intercompany_flag"], 0)
        self.assertIsNone(row["transfer_id"])
        self.assertIsNone(row["counterparty_company"])


if __name__ == "__main__":
    unittest.main()
