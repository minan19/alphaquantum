"""AC1: Copilot engine + intent parser tests."""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.copilot_intent_parser import OfflineCopilotParser
from app.engines.copilot_engine import CopilotEngine
from app.identity_repository import IdentityRepository
from app.migration_manager import MigrationManager


class IntentParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = OfflineCopilotParser()

    def test_count_invoices_intent(self) -> None:
        intent = self.parser.parse("Geçen ay kaç fatura kestik?")
        self.assertEqual(intent.intent, "count_invoices")
        self.assertEqual(intent.time_window_days, 60)  # geçen ay
        self.assertEqual(intent.direction, "outgoing")  # kestik

    def test_sum_amount_intent(self) -> None:
        intent = self.parser.parse("Bu ay toplam ne kadar para girdi?")
        self.assertEqual(intent.intent, "sum_amount")
        self.assertEqual(intent.time_window_days, 30)

    def test_list_customers_intent(self) -> None:
        intent = self.parser.parse("Müşterilerimi göster")
        self.assertEqual(intent.intent, "list_customers")

    def test_list_anomalies_intent(self) -> None:
        intent = self.parser.parse("Aktif anomalileri listele")
        self.assertEqual(intent.intent, "list_anomalies")

    def test_balance_intent(self) -> None:
        intent = self.parser.parse("Bakiyem ne kadar?")
        self.assertEqual(intent.intent, "cashflow_balance")

    def test_entity_extraction_quoted(self) -> None:
        intent = self.parser.parse('"AcmeCo Ltd" için fatura kestik mi?')
        self.assertEqual(intent.entity_name, "AcmeCo Ltd")

    def test_unknown_intent(self) -> None:
        intent = self.parser.parse("Bugün hava nasıl?")
        self.assertEqual(intent.intent, "unknown")

    def test_empty_query(self) -> None:
        intent = self.parser.parse("")
        self.assertEqual(intent.intent, "unknown")


class CopilotEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp.name) / "copilot_test.db"
        migrations_dir = Path(__file__).resolve().parent.parent / "migrations"
        bootstrap = IdentityRepository(str(self._db_path))
        bootstrap.close()
        self.manager = MigrationManager(str(self._db_path), str(migrations_dir))
        self.manager.apply_all()
        self.engine = CopilotEngine(database_path=str(self._db_path))

    def tearDown(self) -> None:
        self.manager.close()
        self._tmp.cleanup()

    def _seed_ledger(self, *, income: float = 0, expense: float = 0) -> None:
        conn = sqlite3.connect(str(self._db_path))
        if income > 0:
            conn.execute(
                """
                INSERT INTO finance_ledger_entries
                  (company_name, entry_type, amount, category, description,
                   entry_date, created_at, intercompany_flag)
                VALUES ('AcmeCo', 'income', ?, 'general', '',
                        date('now'), 1700000000, 0)
                """,
                (income,),
            )
        if expense > 0:
            conn.execute(
                """
                INSERT INTO finance_ledger_entries
                  (company_name, entry_type, amount, category, description,
                   entry_date, created_at, intercompany_flag)
                VALUES ('AcmeCo', 'expense', ?, 'general', '',
                        date('now'), 1700000000, 0)
                """,
                (expense,),
            )
        conn.commit()
        conn.close()

    def test_balance_query_computes_correctly(self) -> None:
        self._seed_ledger(income=10000, expense=3500)
        response = self.engine.ask(query="Bakiyem ne kadar?")
        self.assertEqual(response.intent.intent, "cashflow_balance")
        self.assertEqual(len(response.results), 1)
        self.assertAlmostEqual(response.results[0]["balance"], 6500)

    def test_sum_amount_with_time_window(self) -> None:
        self._seed_ledger(income=5000)
        response = self.engine.ask(
            query="Bu ay toplam ne kadar girdi?",
        )
        self.assertEqual(response.intent.intent, "sum_amount")

    def test_count_invoices_empty(self) -> None:
        response = self.engine.ask(query="Kaç fatura kestik?")
        self.assertEqual(response.intent.intent, "count_invoices")
        self.assertEqual(response.results[0]["count"], 0)

    def test_unknown_returns_helpful_message(self) -> None:
        response = self.engine.ask(query="hava durumu")
        self.assertEqual(response.intent.intent, "unknown")
        self.assertIn("anlayamadım", response.summary_text)

    def test_explanation_includes_intent_info(self) -> None:
        response = self.engine.ask(
            query="Geçen ay AcmeCo için kaç fatura kestik?",
        )
        self.assertIn("count_invoices", response.explanation)
        self.assertIn("AcmeCo", response.explanation)

    def test_sql_template_used_in_response(self) -> None:
        response = self.engine.ask(query="Müşterilerimi göster")
        self.assertEqual(response.sql_template_used, "list_customers")

    def test_no_direct_sql_in_query_param(self) -> None:
        """Doğal dil sorgusunda SQL injection denemesi reddedilir."""
        response = self.engine.ask(
            query="; DROP TABLE invoices; --"
        )
        # Intent unknown veya safe template — SQL silinmedi
        # Verify with a count after
        conn = sqlite3.connect(str(self._db_path))
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE name = 'invoices'",
        ).fetchone()
        conn.close()
        self.assertIsNotNone(row, "invoices tablosu silinmemeli")
        self.assertIn(
            response.intent.intent,
            ("unknown", "list_invoices", "count_invoices"),
        )


if __name__ == "__main__":
    unittest.main()
