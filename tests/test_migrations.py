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
        self.assertEqual(applied, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14])

        status = self.manager.status()
        self.assertEqual(len(status), 14)
        for i in range(14):
            self.assertTrue(status[i]["applied"])

        rolled_back = self.manager.rollback(steps=1)
        self.assertEqual(rolled_back, [14])

        status_after = self.manager.status()
        for i in range(13):
            self.assertTrue(status_after[i]["applied"])
        self.assertFalse(status_after[13]["applied"])

        reapplied = self.manager.apply_all()
        self.assertEqual(reapplied, [14])


if __name__ == "__main__":
    unittest.main()
