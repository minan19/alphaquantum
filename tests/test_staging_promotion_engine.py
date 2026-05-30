"""I2: StagingPromotionEngine integration tests.

I1'in stage ettiği veriyi → gerçek CRM/Invoice/Ledger tablolarına
aktarımın doğruluk + idempotency + conflict resolution garantisi.
"""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.connector_import_repository import ConnectorImportRepository
from app.engines.connector_import_engine import ConnectorImportEngine
from app.engines.staging_promotion_engine import (
    CREATE_NEW,
    SKIP,
    UPDATE_EXISTING,
    StagingPromotionEngine,
)
from app.identity_repository import IdentityRepository
from app.migration_manager import MigrationManager


# Tek cari + tek fatura içeren minimal Logo XML
SIMPLE_LOGO_XML = """<?xml version="1.0" encoding="UTF-8"?>
<LOGOWORLD>
  <CARI>
    <CARI_KODU>CR100</CARI_KODU>
    <CARI_UNVAN>AcmeCo Ltd</CARI_UNVAN>
    <CARI_VKN>1234567890</CARI_VKN>
    <CARI_EMAIL>finans@acme.com</CARI_EMAIL>
    <CARI_TELEFON>02165551234</CARI_TELEFON>
    <CARI_TIPI>1</CARI_TIPI>
  </CARI>
  <FATURA>
    <FATURA_NO>F100</FATURA_NO>
    <FATURA_CARI_KODU>CR100</FATURA_CARI_KODU>
    <FATURA_TARIHI>2026-05-01</FATURA_TARIHI>
    <FATURA_VADE>2026-06-01</FATURA_VADE>
    <FATURA_NET>10000</FATURA_NET>
    <FATURA_KDV>1800</FATURA_KDV>
    <FATURA_BRUT>11800</FATURA_BRUT>
    <FATURA_TIPI>1</FATURA_TIPI>
  </FATURA>
</LOGOWORLD>
""".encode("utf-8")


class StagingPromotionEngineTests(unittest.TestCase):
    COMPANY = "HoldingMain"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp.name) / "promo_test.db"
        migrations_dir = Path(__file__).resolve().parent.parent / "migrations"

        bootstrap = IdentityRepository(str(self._db_path))
        bootstrap.close()
        self.manager = MigrationManager(str(self._db_path), str(migrations_dir))
        self.manager.apply_all()

        # Connector import engine — staging'i doldurmak için kullanılır
        self.import_repo = ConnectorImportRepository(str(self._db_path))
        self.import_engine = ConnectorImportEngine(
            repo=self.import_repo, ledger_db_path=str(self._db_path),
        )
        # Promotion engine
        self.promo = StagingPromotionEngine(database_path=str(self._db_path))

    def tearDown(self) -> None:
        self.import_repo.close()
        self.manager.close()
        self._tmp.cleanup()

    def _stage(self, *, user_id: str = "ahmet") -> None:
        job = self.import_engine.parse_and_preview(
            user_id=user_id, connector_type="logo_tiger",
            mode="xml", data=SIMPLE_LOGO_XML,
        )
        self.import_engine.commit_job(
            user_id=user_id, job_id=job["id"], raw_data=SIMPLE_LOGO_XML,
        )

    def _count(self, table: str, where: str = "") -> int:
        conn = sqlite3.connect(str(self._db_path))
        try:
            sql = f"SELECT COUNT(*) FROM {table}"
            if where:
                sql += f" WHERE {where}"
            row = conn.execute(sql).fetchone()
            return int(row[0])
        finally:
            conn.close()

    # ── list_staged ────────────────────────────────────────────────────

    def test_list_staged_returns_imported_records(self) -> None:
        self._stage()
        data = self.promo.list_staged(user_id="ahmet")
        self.assertEqual(data["customer_count"], 1)
        self.assertEqual(data["invoice_count"], 1)
        self.assertEqual(data["customers"][0]["payload"]["source_code"], "CR100")

    def test_list_staged_user_scoped(self) -> None:
        self._stage(user_id="alice")
        bob_data = self.promo.list_staged(user_id="bob")
        self.assertEqual(bob_data["customer_count"], 0)

    # ── preview_promotion ──────────────────────────────────────────────

    def test_preview_with_empty_target_all_new(self) -> None:
        self._stage()
        plan = self.promo.preview_promotion(
            user_id="ahmet", company_name=self.COMPANY,
        )
        self.assertEqual(plan.new_customers, 1)
        self.assertEqual(plan.new_invoices, 1)
        self.assertEqual(plan.conflict_customers, 0)
        self.assertEqual(plan.ledger_entries_to_create, 1)

    def test_preview_invalid_policy_raises(self) -> None:
        self._stage()
        with self.assertRaises(ValueError):
            self.promo.preview_promotion(
                user_id="ahmet", company_name=self.COMPANY, policy="garbage",
            )

    # ── promote happy path ─────────────────────────────────────────────

    def test_promote_creates_customer_invoice_ledger(self) -> None:
        self._stage()
        before_customers = self._count("customers")
        before_invoices = self._count("invoices")
        before_ledger = self._count("finance_ledger_entries")

        result = self.promo.promote(
            user_id="ahmet", company_name=self.COMPANY, policy=CREATE_NEW,
        )
        self.assertEqual(result.customers_created, 1)
        self.assertEqual(result.invoices_created, 1)
        self.assertEqual(result.ledger_entries_created, 1)
        self.assertEqual(self._count("customers"), before_customers + 1)
        self.assertEqual(self._count("invoices"), before_invoices + 1)
        self.assertEqual(self._count("finance_ledger_entries"), before_ledger + 1)

    def test_promote_outgoing_invoice_creates_income_entry(self) -> None:
        self._stage()
        self.promo.promote(
            user_id="ahmet", company_name=self.COMPANY, policy=CREATE_NEW,
        )
        # outgoing fatura → income ledger entry
        conn = sqlite3.connect(str(self._db_path))
        try:
            row = conn.execute(
                """
                SELECT entry_type, amount FROM finance_ledger_entries
                WHERE company_name = ? AND category = 'logo_import'
                """,
                (self.COMPANY,),
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row[0], "income")
        self.assertAlmostEqual(row[1], 11800.0)

    def test_promoted_customer_has_vkn_in_notes(self) -> None:
        self._stage()
        self.promo.promote(
            user_id="ahmet", company_name=self.COMPANY,
        )
        conn = sqlite3.connect(str(self._db_path))
        try:
            row = conn.execute(
                "SELECT notes FROM customers WHERE company_name = ?",
                (self.COMPANY,),
            ).fetchone()
        finally:
            conn.close()
        assert row is not None
        self.assertIn("VKN:1234567890", row[0])
        self.assertIn("LogoKod:CR100", row[0])

    # ── promote idempotency ────────────────────────────────────────────

    def test_second_promote_is_idempotent(self) -> None:
        self._stage()
        first = self.promo.promote(
            user_id="ahmet", company_name=self.COMPANY,
        )
        second = self.promo.promote(
            user_id="ahmet", company_name=self.COMPANY,
        )
        self.assertEqual(first.customers_created, 1)
        self.assertEqual(second.customers_created, 0)
        self.assertEqual(second.customers_skipped, 1)
        self.assertEqual(second.invoices_skipped, 1)
        # Sadece 1 ledger entry oluşmuş olmalı
        self.assertEqual(self._count("finance_ledger_entries"), 1)

    # ── promote conflict resolution ────────────────────────────────────

    def test_skip_policy_keeps_existing_customer(self) -> None:
        # Önce manuel bir customer ekle aynı VKN ile
        conn = sqlite3.connect(str(self._db_path))
        conn.execute(
            """
            INSERT INTO customers
              (company_name, full_name, email, phone, sector,
               tags, notes, is_active, created_at, updated_at)
            VALUES (?, 'Mevcut Customer', 'old@example.com', '', 'general',
                    '[]', 'VKN:1234567890', 1, 1700000000, 1700000000)
            """,
            (self.COMPANY,),
        )
        conn.commit()
        conn.close()

        self._stage()
        result = self.promo.promote(
            user_id="ahmet", company_name=self.COMPANY, policy=SKIP,
        )
        self.assertEqual(result.customers_created, 0)
        self.assertEqual(result.customers_skipped, 1)
        # Mevcut customer'ın ismi değişmemiş olmalı
        conn = sqlite3.connect(str(self._db_path))
        row = conn.execute(
            "SELECT full_name FROM customers WHERE company_name = ?",
            (self.COMPANY,),
        ).fetchone()
        conn.close()
        assert row is not None
        self.assertEqual(row[0], "Mevcut Customer")

    def test_update_existing_policy_overwrites_customer(self) -> None:
        # Önce manuel customer
        conn = sqlite3.connect(str(self._db_path))
        conn.execute(
            """
            INSERT INTO customers
              (company_name, full_name, email, phone, sector,
               tags, notes, is_active, created_at, updated_at)
            VALUES (?, 'Eski Isim', '', '', 'general',
                    '[]', 'VKN:1234567890', 1, 1700000000, 1700000000)
            """,
            (self.COMPANY,),
        )
        conn.commit()
        conn.close()

        self._stage()
        result = self.promo.promote(
            user_id="ahmet", company_name=self.COMPANY,
            policy=UPDATE_EXISTING,
        )
        self.assertEqual(result.customers_updated, 1)
        # İsim güncellenmiş olmalı
        conn = sqlite3.connect(str(self._db_path))
        row = conn.execute(
            "SELECT full_name, email FROM customers WHERE company_name = ?",
            (self.COMPANY,),
        ).fetchone()
        conn.close()
        assert row is not None
        self.assertEqual(row[0], "AcmeCo Ltd")
        self.assertEqual(row[1], "finans@acme.com")

    def test_create_new_policy_makes_duplicate_customer(self) -> None:
        # Aynı VKN'li customer var, create_new ile yeni satır oluşur
        conn = sqlite3.connect(str(self._db_path))
        conn.execute(
            """
            INSERT INTO customers
              (company_name, full_name, email, phone, sector,
               tags, notes, is_active, created_at, updated_at)
            VALUES (?, 'Mevcut', 'eski@example.com', '', 'general',
                    '[]', 'VKN:1234567890', 1, 1700000000, 1700000000)
            """,
            (self.COMPANY,),
        )
        conn.commit()
        conn.close()
        before = self._count("customers")

        self._stage()
        result = self.promo.promote(
            user_id="ahmet", company_name=self.COMPANY, policy=CREATE_NEW,
        )
        # create_new: var olan eşleşmesini görmesine rağmen yeni kayıt açar
        self.assertEqual(result.customers_created, 1)
        self.assertEqual(self._count("customers"), before + 1)


if __name__ == "__main__":
    unittest.main()
