"""T1: TreasuryEngine tests."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.engines.treasury_engine import TreasuryEngine
from app.identity_repository import IdentityRepository
from app.migration_manager import MigrationManager


FX_TEST = {"TRY": 1.0, "USD": 30.0, "EUR": 33.0}


class TreasuryEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp.name) / "treasury_test.db"
        migrations_dir = Path(__file__).resolve().parent.parent / "migrations"

        bootstrap = IdentityRepository(str(self._db_path))
        bootstrap.close()
        self.manager = MigrationManager(str(self._db_path), str(migrations_dir))
        self.manager.apply_all()

        self.engine = TreasuryEngine(
            database_path=str(self._db_path), fx_rates=FX_TEST,
        )

    def tearDown(self) -> None:
        self.manager.close()
        self._tmp.cleanup()

    # ── add_account ────────────────────────────────────────────────────

    def test_add_account_basic(self) -> None:
        view = self.engine.add_account(
            user_id="u1", company_name="AcmeCo",
            bank_name="Garanti BBVA", iban="TR330006100519786457841326",
            current_balance=50000,
        )
        self.assertGreater(view.id, 0)
        self.assertEqual(view.bank_name, "Garanti BBVA")
        self.assertAlmostEqual(view.current_balance, 50000)

    def test_add_account_invalid_currency_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.engine.add_account(
                user_id="u1", company_name="X", bank_name="Y",
                iban="TR000", currency="XYZW",
            )

    def test_add_account_invalid_type_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.engine.add_account(
                user_id="u1", company_name="X", bank_name="Y",
                iban="TR000", account_type="garbage",
            )

    def test_add_account_no_identifier_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.engine.add_account(
                user_id="u1", company_name="X", bank_name="Y",
            )

    def test_iban_cleaned_no_spaces(self) -> None:
        view = self.engine.add_account(
            user_id="u1", company_name="X", bank_name="Y",
            iban="TR33 0006 1005 1978 6457 8413 26",
        )
        assert view.iban is not None
        self.assertNotIn(" ", view.iban)

    def test_duplicate_iban_raises(self) -> None:
        self.engine.add_account(
            user_id="u1", company_name="A", bank_name="B",
            iban="TR330006100519786457841326",
        )
        with self.assertRaises(ValueError):
            self.engine.add_account(
                user_id="u1", company_name="C", bank_name="D",
                iban="TR330006100519786457841326",
            )

    # ── update_balance ─────────────────────────────────────────────────

    def test_update_balance_creates_snapshot(self) -> None:
        view = self.engine.add_account(
            user_id="u1", company_name="X", bank_name="Y",
            iban="TR000111", current_balance=10000,
        )
        updated = self.engine.update_balance(
            user_id="u1", account_id=view.id, new_balance=12500,
        )
        self.assertAlmostEqual(updated.current_balance, 12500)
        history = self.engine.history(
            user_id="u1", account_id=view.id,
        )
        self.assertEqual(len(history), 1)

    def test_update_balance_wrong_user_raises(self) -> None:
        view = self.engine.add_account(
            user_id="owner", company_name="X", bank_name="Y",
            iban="TR222",
        )
        with self.assertRaises(PermissionError):
            self.engine.update_balance(
                user_id="hacker", account_id=view.id, new_balance=1,
            )

    # ── summary ────────────────────────────────────────────────────────

    def test_summary_aggregates_currencies(self) -> None:
        self.engine.add_account(
            user_id="u1", company_name="A", bank_name="Garanti",
            iban="TR1A", currency="TRY", current_balance=50000,
        )
        self.engine.add_account(
            user_id="u1", company_name="A", bank_name="Garanti",
            iban="TR1B", currency="USD", current_balance=1000,
        )
        self.engine.add_account(
            user_id="u1", company_name="B", bank_name="İş Bankası",
            iban="TR1C", currency="EUR", current_balance=2000,
        )
        summary = self.engine.summary(user_id="u1")
        # 50000 TRY + 1000*30 USD + 2000*33 EUR = 50000 + 30000 + 66000 = 146000
        self.assertAlmostEqual(summary.total_in_try, 146000, places=0)
        self.assertEqual(summary.account_count, 3)
        self.assertEqual(summary.by_currency["TRY"], 50000)
        self.assertEqual(summary.by_currency["USD"], 1000)
        self.assertEqual(len(summary.by_bank), 2)

    def test_summary_empty_for_no_accounts(self) -> None:
        summary = self.engine.summary(user_id="empty_user")
        self.assertEqual(summary.total_in_try, 0)
        self.assertEqual(summary.account_count, 0)

    # ── CSV import ─────────────────────────────────────────────────────

    def test_csv_import_basic(self) -> None:
        view = self.engine.add_account(
            user_id="u1", company_name="X", bank_name="Y",
            iban="TR_CSV1",
        )
        csv_content = (
            "date,balance\n"
            "2026-05-01,10000\n"
            "2026-05-02,15000\n"
            "2026-05-03,12500\n"
        )
        result = self.engine.import_csv(
            user_id="u1", account_id=view.id, csv_content=csv_content,
        )
        self.assertEqual(result["inserted"], 3)
        # Current balance should reflect latest date (2026-05-03)
        updated = self.engine.get_account(user_id="u1", account_id=view.id)
        assert updated is not None
        self.assertAlmostEqual(updated.current_balance, 12500)

    def test_csv_import_tr_amount_format(self) -> None:
        view = self.engine.add_account(
            user_id="u1", company_name="X", bank_name="Y", iban="TR_CSV2",
        )
        # TR format: 1.234,56 (semicolon delimiter)
        csv_content = (
            "tarih;bakiye\n"
            "01.05.2026;1.234,56\n"
            "02.05.2026;2.345,67\n"
        )
        result = self.engine.import_csv(
            user_id="u1", account_id=view.id, csv_content=csv_content,
        )
        self.assertEqual(result["inserted"], 2)
        updated = self.engine.get_account(user_id="u1", account_id=view.id)
        assert updated is not None
        self.assertAlmostEqual(updated.current_balance, 2345.67, places=2)

    def test_csv_import_idempotent_same_date_updates(self) -> None:
        view = self.engine.add_account(
            user_id="u1", company_name="X", bank_name="Y", iban="TR_CSV3",
        )
        self.engine.import_csv(
            user_id="u1", account_id=view.id,
            csv_content="date,balance\n2026-05-01,1000\n",
        )
        result = self.engine.import_csv(
            user_id="u1", account_id=view.id,
            csv_content="date,balance\n2026-05-01,9999\n",
        )
        self.assertEqual(result["updated"], 1)
        self.assertEqual(result["inserted"], 0)

    def test_csv_import_invalid_user_raises(self) -> None:
        view = self.engine.add_account(
            user_id="owner", company_name="X", bank_name="Y", iban="TR_CSV4",
        )
        with self.assertRaises(ValueError):
            self.engine.import_csv(
                user_id="hacker", account_id=view.id,
                csv_content="date,balance\n2026-05-01,1000\n",
            )

    def test_csv_import_garbage_raises(self) -> None:
        view = self.engine.add_account(
            user_id="u1", company_name="X", bank_name="Y", iban="TR_CSV5",
        )
        with self.assertRaises(ValueError):
            self.engine.import_csv(
                user_id="u1", account_id=view.id,
                csv_content="bla bla bla\nno valid rows here",
            )

    # ── List + history ─────────────────────────────────────────────────

    def test_list_accounts_user_scoped(self) -> None:
        self.engine.add_account(
            user_id="alice", company_name="X", bank_name="Y", iban="TR_A",
        )
        self.engine.add_account(
            user_id="bob", company_name="X", bank_name="Y", iban="TR_B",
        )
        alice_list = self.engine.list_accounts(user_id="alice")
        bob_list = self.engine.list_accounts(user_id="bob")
        self.assertEqual(len(alice_list), 1)
        self.assertEqual(len(bob_list), 1)

    def test_history_includes_initial_snapshot(self) -> None:
        view = self.engine.add_account(
            user_id="u1", company_name="X", bank_name="Y", iban="TR_HIST",
            current_balance=5000,
        )
        history = self.engine.history(
            user_id="u1", account_id=view.id,
        )
        # Initial snapshot from add_account (balance>0)
        self.assertEqual(len(history), 1)
        self.assertAlmostEqual(history[0]["balance"], 5000)


if __name__ == "__main__":
    unittest.main()
