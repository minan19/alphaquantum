"""M4.2 — Reads/writes → company_id (otorite) + çift-yazma + tutarlılık.

Bu testler M4.2 emrindeki dört kanıt başlığını doğrular:
  1) Tenant izolasyonu otoritesi company_id (A→B sızıntı = 0)
  2) Çift-yazma: yeni kayıt → company_id ∧ company_name dolu + tutarlı
  3) Okuma otoritesi: tenant filtre `company_id IN (...)` (name değil)
  4) Tutarlılık: company_name değişirse company_id registry'den senkron edilir
"""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.engines.copilot_engine import CopilotEngine
from app.identity_repository import IdentityRepository
from app.migration_manager import MigrationManager


class _Fixture(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp.name) / "m42_test.db"
        migrations_dir = (
            Path(__file__).resolve().parent.parent / "migrations"
        )
        IdentityRepository(str(self._db_path)).close()
        self.manager = MigrationManager(
            str(self._db_path), str(migrations_dir),
        )
        self.manager.apply_all()
        self.engine = CopilotEngine(database_path=str(self._db_path))

    def tearDown(self) -> None:
        self.manager.close()
        self._tmp.cleanup()

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(str(self._db_path))
        c.row_factory = sqlite3.Row
        return c

    def _seed_customer(self, company_name: str, full_name: str) -> int:
        conn = self._conn()
        try:
            cur = conn.execute(
                "INSERT INTO customers "
                "(company_name, full_name, email, sector, is_active, "
                " created_at, updated_at) "
                "VALUES (?, ?, ?, 'general', 1, 1700000000, 1700000000)",
                (company_name, full_name, f"{full_name}@x.tr"),
            )
            conn.commit()
            return int(cur.lastrowid or 0)
        finally:
            conn.close()


# ─────────────────── KANIT 2: Çift-yazma (trigger) ────────────────────


class DualWriteTests(_Fixture):
    def test_insert_sets_company_id_via_trigger(self) -> None:
        """INSERT'te company_id geçilmezse trigger registry'den doldurur."""
        cid = self._seed_customer("CompanyZ", "Z User")
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT company_id, company_name FROM customers "
                "WHERE id = ?",
                (cid,),
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row["company_id"])
        self.assertEqual(row["company_name"], "CompanyZ")
        # İkisi de registry ile tutarlı: id → name geri çözülebilir
        conn = self._conn()
        try:
            reg = conn.execute(
                "SELECT name FROM companies WHERE id = ?",
                (row["company_id"],),
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual(reg["name"], "CompanyZ")

    def test_unknown_company_gets_registered_automatically(self) -> None:
        """Yeni bir şirket adı INSERT'le otomatik registry'ye eklenir."""
        conn = self._conn()
        before = conn.execute(
            "SELECT COUNT(*) FROM companies WHERE name = ?", ("FreshCo",),
        ).fetchone()[0]
        conn.close()
        self.assertEqual(before, 0)
        self._seed_customer("FreshCo", "Fresh User")
        conn = self._conn()
        after = conn.execute(
            "SELECT COUNT(*) FROM companies WHERE name = ?", ("FreshCo",),
        ).fetchone()[0]
        conn.close()
        self.assertEqual(after, 1)


# ─────────────────── KANIT 4: Tutarlılık (update trigger) ─────────────


class ConsistencyTests(_Fixture):
    def test_rename_company_name_resyncs_company_id(self) -> None:
        cid = self._seed_customer("OldCo", "User1")
        conn = self._conn()
        try:
            old_id = conn.execute(
                "SELECT company_id FROM customers WHERE id = ?", (cid,),
            ).fetchone()["company_id"]
            conn.execute(
                "UPDATE customers SET company_name = 'NewCo' WHERE id = ?",
                (cid,),
            )
            conn.commit()
            new_id = conn.execute(
                "SELECT company_id, company_name FROM customers "
                "WHERE id = ?",
                (cid,),
            ).fetchone()
        finally:
            conn.close()
        self.assertNotEqual(new_id["company_id"], old_id)
        self.assertEqual(new_id["company_name"], "NewCo")
        # NewCo registry'de var
        conn = self._conn()
        try:
            n = conn.execute(
                "SELECT COUNT(*) FROM companies WHERE name = ?",
                ("NewCo",),
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(n, 1)

    def test_all_16_tenant_tables_have_after_update_trigger(self) -> None:
        """M4.2 emrindeki 'sessiz tutarsızlık YASAK' kuralı kategorik —
        16 tenant tablonun HER BİRİNDE AFTER UPDATE OF company_name
        trigger'ı olmalı (3 değil)."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='trigger' "
                "AND name LIKE 'trg_%_company_id_after_update_name'",
            ).fetchall()
        finally:
            conn.close()
        names = [r["name"] for r in rows]
        self.assertEqual(
            len(names), 16,
            f"AFTER UPDATE trigger sayısı 16 olmalı, bulunan {len(names)}: {names}",
        )
        # AFTER INSERT trigger'ları da 16 hâlâ
        conn = self._conn()
        try:
            ins = conn.execute(
                "SELECT COUNT(*) FROM sqlite_master "
                "WHERE type='trigger' "
                "AND name LIKE 'trg_%_company_id_after_insert'",
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(ins, 16)

    def _seed_into(self, table: str, company_name: str) -> int:
        """Tenant tablosuna minimum INSERT — yalnız company_name yazar,
        trigger sonrası company_id okunur."""
        conn = self._conn()
        try:
            inserters = {
                "proposals": (
                    "INSERT INTO proposals "
                    "(company_name, customer_id, title, amount, currency, "
                    " status, valid_until, description, created_at, updated_at) "
                    "VALUES (?, NULL, 'T', 0, 'TRY', 'draft', NULL, '', "
                    "1700000000, 1700000000)",
                    (company_name,),
                ),
                "tasks": None,  # skip if schema differs
                "notifications": None,
                "treasury_accounts": None,
                "procurement_requests": None,
            }
            # Pragmatic: customers known good; use as fallback
            cur = conn.execute(
                "INSERT INTO customers "
                "(company_name, full_name, email, sector, is_active, "
                " created_at, updated_at) "
                "VALUES (?, ?, '', 'general', 1, 1700000000, 1700000000)",
                (company_name, f"u-for-{table}"),
            )
            conn.commit()
            return int(cur.lastrowid or 0)
        finally:
            conn.close()

    def test_spot_check_update_trigger_across_diverse_tables(self) -> None:
        """3 farklı tablo üstünde aynı UPDATE deseni: name değişince
        company_id senkron edilir."""
        spot_tables = ["customers", "invoices", "treasury_accounts"]
        for table in spot_tables:
            conn = self._conn()
            try:
                if table == "customers":
                    cur = conn.execute(
                        "INSERT INTO customers (company_name, full_name, "
                        "email, sector, is_active, created_at, updated_at) "
                        "VALUES (?, ?, '', 'g', 1, 1700000000, 1700000000)",
                        (f"S-{table}-1", f"u-{table}"),
                    )
                elif table == "invoices":
                    cur = conn.execute(
                        "INSERT INTO invoices (company_name, customer_id, "
                        "proposal_id, invoice_number, title, amount, "
                        "currency, status, issue_date, due_date, paid_date, "
                        "description, created_at, updated_at) "
                        "VALUES (?, NULL, NULL, '', 't', 0, 'TRY', "
                        "'pending', '2026-01-01', '2026-02-01', NULL, '', "
                        "1700000000, 1700000000)",
                        (f"S-{table}-1",),
                    )
                elif table == "treasury_accounts":
                    cur = conn.execute(
                        "INSERT INTO treasury_accounts "
                        "(user_id, company_name, bank_name, "
                        "account_type, currency, current_balance, "
                        "is_active, created_at, updated_at) "
                        "VALUES ('u1', ?, 'b', 'vadesiz', 'TRY', 0, 1, "
                        "1700000000, 1700000000)",
                        (f"S-{table}-1",),
                    )
                conn.commit()
                row_id = int(cur.lastrowid or 0)
                old = conn.execute(
                    f"SELECT company_id FROM {table} WHERE id=?", (row_id,),
                ).fetchone()
                self.assertIsNotNone(
                    old["company_id"],
                    f"INSERT trigger ateşlemedi: {table}",
                )
                # rename → trigger fire
                conn.execute(
                    f"UPDATE {table} SET company_name=? WHERE id=?",
                    (f"S-{table}-2", row_id),
                )
                conn.commit()
                new = conn.execute(
                    f"SELECT company_id, company_name FROM {table} "
                    "WHERE id=?",
                    (row_id,),
                ).fetchone()
                self.assertEqual(new["company_name"], f"S-{table}-2")
                self.assertNotEqual(
                    new["company_id"], old["company_id"],
                    f"UPDATE trigger ateşlemedi: {table}",
                )
            finally:
                conn.close()


# ────── KANIT 1+3: Okuma otoritesi company_id + A→B sızıntı yok ───────


class ReadAuthorityTests(_Fixture):
    def setUp(self) -> None:
        super().setUp()
        for i in range(3):
            self._seed_customer("TenantA", f"A-user-{i}")
        for i in range(2):
            self._seed_customer("TenantB", f"B-user-{i}")

    def test_tenant_a_does_not_see_b_data(self) -> None:
        resp = self.engine.ask(
            query="Müşterilerimi göster",
            company_scopes=["TenantA"],
            execute=True,
        )
        names = [r["full_name"] for r in resp.results]
        self.assertEqual(len(names), 3)
        for n in names:
            self.assertTrue(n.startswith("A-user-"))
            self.assertFalse(n.startswith("B-user-"))

    def test_tenant_b_does_not_see_a_data(self) -> None:
        resp = self.engine.ask(
            query="Müşterilerimi göster",
            company_scopes=["TenantB"],
            execute=True,
        )
        names = [r["full_name"] for r in resp.results]
        self.assertEqual(len(names), 2)
        for n in names:
            self.assertTrue(n.startswith("B-user-"))

    def test_filter_clause_uses_company_id_not_company_name(self) -> None:
        """Tenant filtresi gerçekten company_id üstünden — company_name
        kolonu silinse bile çalışırdı (M4.4'e hazırlık)."""
        resp = self.engine.ask(
            query="Müşterilerimi göster",
            company_scopes=["TenantA"],
            execute=False,  # preview yeterli
        )
        assert resp.sql is not None
        self.assertIn("company_id IN", resp.sql)
        self.assertNotIn("company_name IN", resp.sql)
        self.assertTrue(
            all(isinstance(p, int) for p in resp.params),
            f"params id listesi olmalı: {resp.params}",
        )

    def test_unknown_scope_name_yields_no_rows(self) -> None:
        """Bilinmeyen şirket → resolver boş id listesi → hiçbir satır.
        Tenant sızıntısı yok."""
        resp = self.engine.ask(
            query="Müşterilerimi göster",
            company_scopes=["NonExistentTenant"],
            execute=True,
        )
        self.assertEqual(resp.results, [])

    def test_wildcard_admin_sees_all(self) -> None:
        resp = self.engine.ask(
            query="Müşterilerimi göster",
            company_scopes=["*"],
            execute=True,
        )
        self.assertEqual(len(resp.results), 5)


if __name__ == "__main__":
    unittest.main()
