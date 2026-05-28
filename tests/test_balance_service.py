"""G1.5: BalanceService tests — ledger-derived authoritative balance."""
import tempfile
import time
import unittest
from pathlib import Path

from app.balance_service import BalanceService
from app.finance_repository import FinanceRepository
from app.identity_repository import IdentityRepository
from app.migration_manager import MigrationManager
from app.models import Company
from app.repository import CompanyRepository, default_companies


class BalanceServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._temp_dir.name) / "balance_test.db"
        migrations_dir = Path(__file__).resolve().parent.parent / "migrations"

        bootstrap_repo = IdentityRepository(str(self._db_path))
        bootstrap_repo.close()
        self.manager = MigrationManager(str(self._db_path), str(migrations_dir))
        self.manager.apply_all()

        self.company_repo = CompanyRepository(
            str(self._db_path), default_companies()
        )
        self.finance_repo = FinanceRepository(str(self._db_path))

        # Test şirketleri (custom baseline)
        self.company_repo.ensure_company("TestCo Alpha", initial_balance=100_000)
        self.company_repo.ensure_company("TestCo Beta", initial_balance=50_000)

        self.service = BalanceService(
            company_repo=self.company_repo,
            finance_repo=self.finance_repo,
        )

    def tearDown(self) -> None:
        self.finance_repo.close()
        self.company_repo.close()
        self.manager.close()
        self._temp_dir.cleanup()

    # ── Helpers ────────────────────────────────────────────────────────

    def _insert_ledger(
        self, *, company: str, entry_type: str, amount: float
    ) -> None:
        with self.finance_repo._lock:
            self.finance_repo._conn.execute(
                """
                INSERT INTO finance_ledger_entries
                    (company_name, entry_type, amount, category, description,
                     entry_date, created_at)
                VALUES (?, ?, ?, 'test', 'test', '2026-03-15', ?)
                """,
                (company, entry_type, amount, int(time.time())),
            )
            self.finance_repo._conn.commit()

    # ── Tests ──────────────────────────────────────────────────────────

    def test_compute_balance_baseline_only(self) -> None:
        """Hiç ledger entry yoksa baseline döner."""
        balance = self.service.compute_company_balance("TestCo Alpha")
        self.assertEqual(balance, 100_000.0)

    def test_compute_balance_with_income(self) -> None:
        """Baseline + income."""
        self._insert_ledger(
            company="TestCo Alpha", entry_type="income", amount=25_000
        )
        balance = self.service.compute_company_balance("TestCo Alpha")
        self.assertEqual(balance, 125_000.0)

    def test_compute_balance_with_expense(self) -> None:
        """Baseline - expense."""
        self._insert_ledger(
            company="TestCo Alpha", entry_type="expense", amount=30_000
        )
        balance = self.service.compute_company_balance("TestCo Alpha")
        self.assertEqual(balance, 70_000.0)

    def test_compute_balance_net_calculation(self) -> None:
        """Baseline + income - expense."""
        self._insert_ledger(
            company="TestCo Alpha", entry_type="income", amount=50_000
        )
        self._insert_ledger(
            company="TestCo Alpha", entry_type="expense", amount=15_000
        )
        balance = self.service.compute_company_balance("TestCo Alpha")
        self.assertEqual(balance, 135_000.0)

    def test_compute_balance_unknown_company(self) -> None:
        """Yok olan şirket → 0 (defensive)."""
        balance = self.service.compute_company_balance("NoSuch Co")
        self.assertEqual(balance, 0.0)

    def test_compute_companies_with_ledger_balance_aggregate(self) -> None:
        """Mevcut Engine API ile uyumlu: companies list update."""
        self._insert_ledger(
            company="TestCo Alpha", entry_type="income", amount=20_000
        )
        self._insert_ledger(
            company="TestCo Beta", entry_type="expense", amount=10_000
        )

        original = [
            Company(name="TestCo Alpha", balance=100_000),
            Company(name="TestCo Beta", balance=50_000),
        ]
        updated = self.service.compute_companies_with_ledger_balance(original)

        self.assertEqual(len(updated), 2)
        by_name = {c.name: c for c in updated}
        self.assertEqual(by_name["TestCo Alpha"].balance, 120_000.0)
        self.assertEqual(by_name["TestCo Beta"].balance, 40_000.0)

    def test_compute_companies_with_no_ledger_entries(self) -> None:
        """Ledger boş → baseline aynı kalır."""
        original = [
            Company(name="TestCo Alpha", balance=100_000),
        ]
        updated = self.service.compute_companies_with_ledger_balance(original)
        self.assertEqual(updated[0].balance, 100_000.0)

    def test_compute_companies_empty_list(self) -> None:
        """Empty list → empty list (no SQL)."""
        updated = self.service.compute_companies_with_ledger_balance([])
        self.assertEqual(updated, [])

    def test_immutability_original_unchanged(self) -> None:
        """Pydantic model_copy → original untouched."""
        self._insert_ledger(
            company="TestCo Alpha", entry_type="income", amount=50_000
        )
        original = [Company(name="TestCo Alpha", balance=100_000)]
        original_balance = original[0].balance

        self.service.compute_companies_with_ledger_balance(original)
        # Original değişmemeli
        self.assertEqual(original[0].balance, original_balance)


if __name__ == "__main__":
    unittest.main()
