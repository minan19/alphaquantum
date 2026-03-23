import unittest
import tempfile
from pathlib import Path

from app.repository import CompanyRepository, default_companies


class RepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._temp_dir.name) / "alpha_quantum_test.db"
        self.repo = CompanyRepository(str(self._db_path), default_companies())

    def tearDown(self) -> None:
        self.repo.close()
        self._temp_dir.cleanup()

    def test_list_companies_returns_deep_copy(self) -> None:
        listed = self.repo.list_companies()
        listed[0].name = "Mutated Outside"
        listed[0].inventory[0].quantity = 9999

        listed_again = self.repo.list_companies()
        self.assertEqual(listed_again[0].name, "ABC Holding")
        self.assertNotEqual(listed_again[0].inventory[0].quantity, 9999)

    def test_update_random_never_makes_negative_quantity(self) -> None:
        for _ in range(100):
            companies = self.repo.update_random()
            for company in companies:
                for item in company.inventory:
                    self.assertGreaterEqual(item.quantity, 0)

    def test_data_persists_across_repository_instances(self) -> None:
        updated = self.repo.update_random()
        updated_balance = updated[0].balance

        self.repo.close()
        self.repo = CompanyRepository(str(self._db_path), default_companies())
        persisted = self.repo.list_companies()

        self.assertEqual(len(persisted), 1)
        self.assertEqual(persisted[0].name, "ABC Holding")
        self.assertEqual(persisted[0].balance, updated_balance)


if __name__ == "__main__":
    unittest.main()
