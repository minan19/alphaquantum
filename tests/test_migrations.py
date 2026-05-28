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
        self.assertEqual(applied, list(range(1, 23)))

        status = self.manager.status()
        self.assertEqual(len(status), 22)
        for i in range(22):
            self.assertTrue(status[i]["applied"])

        # Migration 22 touches critical tables (users) — force=True required
        rolled_back = self.manager.rollback(steps=1, force=True)
        self.assertEqual(rolled_back, [22])

        status_after = self.manager.status()
        for i in range(21):
            self.assertTrue(status_after[i]["applied"])
        self.assertFalse(status_after[21]["applied"])

        reapplied = self.manager.apply_all()
        self.assertEqual(reapplied, [22])


if __name__ == "__main__":
    unittest.main()
