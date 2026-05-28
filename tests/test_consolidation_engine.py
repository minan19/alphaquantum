"""G1.2: ConsolidationEngine — intercompany eliminasyonlu konsolide P&L tests.

Karma sektörlü holding senaryosu:
  - Atlas Holding'in 3 alt şirketi: İnşaat, Lojistik, Gıda
  - İnşaat → dış satış (proje) ve Lojistik'e nakliye için ödeme
  - Lojistik → dış satış (kargo) ve İnşaat'tan gelen ödeme + Gıda'ya nakliye
  - Gıda → dış satış (hammadde) ve Lojistik'e nakliye ödemesi

Beklenen: gross_total her şirketin her şeyini sayar (büyük rakam).
consolidated_* sadece dış işlemleri sayar (gerçek grup ciro/gider).
elimination_amount intercompany toplamı (income + expense) = grup içi sirkülasyon.
"""
import tempfile
import time
import unittest
from pathlib import Path

from app.engines.consolidation_engine import ConsolidationEngine
from app.finance_repository import FinanceRepository
from app.holding_repository import HoldingRepository
from app.identity_repository import IdentityRepository
from app.migration_manager import MigrationManager
from app.repository import CompanyRepository, default_companies


# Karma sektör senaryosu için sabitler (Türkiye holding örneği)
INSAAT = "Atlas İnşaat A.Ş."
LOJISTIK = "Atlas Lojistik A.Ş."
GIDA = "Atlas Gıda A.Ş."


class ConsolidationEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._temp_dir.name) / "consolidation_test.db"
        migrations_dir = Path(__file__).resolve().parent.parent / "migrations"

        # Bootstrap: identity (roles/users) → migrations
        bootstrap_repo = IdentityRepository(str(self._db_path))
        bootstrap_repo.close()
        self.manager = MigrationManager(str(self._db_path), str(migrations_dir))
        self.manager.apply_all()

        # Repositories
        self.company_repo = CompanyRepository(
            str(self._db_path), default_companies()
        )
        self.holding_repo = HoldingRepository(str(self._db_path))
        self.finance_repo = FinanceRepository(str(self._db_path))

        # Test holding + companies
        self.holding_row = self.holding_repo.create_holding(
            name="Atlas Holding",
            code="ATLAS",
            description="Karma sektörlü test holding",
            status="active",
        )
        self.holding_id = int(self.holding_row["id"])

        for company in (INSAAT, LOJISTIK, GIDA):
            self.holding_repo.upsert_holding_company(
                holding_id=self.holding_id,
                company_name=company,
                sector="mixed",
                country="TR",
                registered_in_platform=True,
                data_quality_score=80,
                integration_completeness_score=80,
                security_compliance_score=80,
                process_standardization_score=80,
                master_data_health_score=80,
                team_readiness_score=80,
                onboarding_readiness_score=80,
                onboarding_status="GO",
                recommendation="proceed",
                notes="",
            )

        self.engine = ConsolidationEngine(
            finance_repo=self.finance_repo,
            holding_repo=self.holding_repo,
        )

    def tearDown(self) -> None:
        self.finance_repo.close()
        self.holding_repo.close()
        self.company_repo.close()
        self.manager.close()
        self._temp_dir.cleanup()

    # ── Helpers ────────────────────────────────────────────────────────

    def _insert_ledger(
        self,
        *,
        company: str,
        entry_type: str,
        amount: float,
        intercompany: bool,
        counterparty: str | None = None,
        transfer_id: int | None = None,
        entry_date: str = "2026-03-15",
    ) -> int:
        """Direct insert (atomic transfer engine henüz yok — G1.3'te)."""
        with self.finance_repo._lock:
            cur = self.finance_repo._conn.execute(
                """
                INSERT INTO finance_ledger_entries
                    (company_name, entry_type, amount, category, description,
                     entry_date, created_at,
                     counterparty_company, transfer_id, intercompany_flag)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    company, entry_type, amount, "test", "test entry",
                    entry_date, int(time.time()),
                    counterparty, transfer_id, 1 if intercompany else 0,
                ),
            )
            self.finance_repo._conn.commit()
            assert cur.lastrowid is not None
            return int(cur.lastrowid)

    # ── Tests ──────────────────────────────────────────────────────────

    def test_empty_holding_returns_zeros(self) -> None:
        result = self.engine.consolidated_pl(
            holding_id=self.holding_id,
            start_date="2026-01-01",
            end_date="2026-12-31",
        )
        self.assertEqual(result.holding_id, self.holding_id)
        self.assertEqual(result.holding_name, "Atlas Holding")
        self.assertEqual(result.gross_total_income, 0.0)
        self.assertEqual(result.consolidated_net, 0.0)
        self.assertEqual(len(result.lines), 3)  # all 3 companies present, zero
        self.assertTrue(result.elimination.is_balanced)  # 0 == 0 trivially
        self.assertEqual(result.health_status, "watch")  # 0 < 100K

    def test_only_external_income_no_elimination(self) -> None:
        # Üç şirket, sadece dış satışlar — eliminasyon olmamalı
        self._insert_ledger(company=INSAAT, entry_type="income", amount=500_000, intercompany=False)
        self._insert_ledger(company=LOJISTIK, entry_type="income", amount=300_000, intercompany=False)
        self._insert_ledger(company=GIDA, entry_type="income", amount=200_000, intercompany=False)

        result = self.engine.consolidated_pl(
            holding_id=self.holding_id,
            start_date="2026-01-01",
            end_date="2026-12-31",
        )
        self.assertEqual(result.gross_total_income, 1_000_000.0)
        self.assertEqual(result.consolidated_income, 1_000_000.0)
        self.assertEqual(result.elimination.elimination_amount, 0.0)
        self.assertEqual(result.health_status, "strong")  # ≥ 1M

    def test_intercompany_transfer_eliminated(self) -> None:
        """Karma holding senaryosu: İnşaat lojistiğe ₺100K nakliye ücreti ödüyor.

        Gerçek hayatta atomic G1.3 engine yazar; testte manuel simüle.
        Beklenen: gross büyük, consolidated küçük; eliminasyon doğru.
        """
        # Dış satışlar
        self._insert_ledger(company=INSAAT, entry_type="income", amount=800_000, intercompany=False)
        self._insert_ledger(company=LOJISTIK, entry_type="income", amount=400_000, intercompany=False)
        self._insert_ledger(company=GIDA, entry_type="income", amount=300_000, intercompany=False)

        # Dış giderler
        self._insert_ledger(company=INSAAT, entry_type="expense", amount=200_000, intercompany=False)
        self._insert_ledger(company=LOJISTIK, entry_type="expense", amount=100_000, intercompany=False)
        self._insert_ledger(company=GIDA, entry_type="expense", amount=80_000, intercompany=False)

        # Intercompany: İnşaat ödüyor (expense), Lojistik alıyor (income)
        # (G1.3 atomic write bunu garanti edecek — şimdilik manuel simüle)
        self._insert_ledger(
            company=INSAAT, entry_type="expense", amount=100_000,
            intercompany=True, counterparty=LOJISTIK, transfer_id=999,
        )
        self._insert_ledger(
            company=LOJISTIK, entry_type="income", amount=100_000,
            intercompany=True, counterparty=INSAAT, transfer_id=999,
        )

        # Intercompany 2: Gıda ödüyor, Lojistik alıyor
        self._insert_ledger(
            company=GIDA, entry_type="expense", amount=50_000,
            intercompany=True, counterparty=LOJISTIK, transfer_id=1000,
        )
        self._insert_ledger(
            company=LOJISTIK, entry_type="income", amount=50_000,
            intercompany=True, counterparty=GIDA, transfer_id=1000,
        )

        result = self.engine.consolidated_pl(
            holding_id=self.holding_id,
            start_date="2026-01-01",
            end_date="2026-12-31",
        )

        # Gross (eliminasyon öncesi)
        # income: 800K + 400K + 300K + 100K (IC) + 50K (IC) = 1,650K
        # expense: 200K + 100K + 80K + 100K (IC) + 50K (IC) = 530K
        self.assertEqual(result.gross_total_income, 1_650_000.0)
        self.assertEqual(result.gross_total_expense, 530_000.0)
        self.assertEqual(result.gross_net, 1_120_000.0)

        # Consolidated (eliminasyon sonrası — gerçek dış işlemler)
        # income: 800K + 400K + 300K = 1,500K
        # expense: 200K + 100K + 80K = 380K
        self.assertEqual(result.consolidated_income, 1_500_000.0)
        self.assertEqual(result.consolidated_expense, 380_000.0)
        self.assertEqual(result.consolidated_net, 1_120_000.0)

        # Eliminasyon detayı
        # Intercompany income (Lojistik alıyor): 100K + 50K = 150K
        # Intercompany expense (İnşaat + Gıda ödüyor): 100K + 50K = 150K
        self.assertEqual(result.elimination.total_intercompany_income, 150_000.0)
        self.assertEqual(result.elimination.total_intercompany_expense, 150_000.0)
        self.assertEqual(result.elimination.elimination_amount, 300_000.0)
        self.assertTrue(result.elimination.is_balanced)
        self.assertEqual(result.health_status, "strong")

    def test_imbalanced_intercompany_detected(self) -> None:
        """Eğer atomic write bozulmuşsa (legacy/manuel entry), is_balanced=False."""
        # Tek taraflı intercompany — atomic değil (BUG durumu)
        self._insert_ledger(
            company=INSAAT, entry_type="expense", amount=100_000,
            intercompany=True, counterparty=LOJISTIK, transfer_id=500,
        )
        # Lojistik income girilmedi → imbalance

        result = self.engine.consolidated_pl(
            holding_id=self.holding_id,
            start_date="2026-01-01",
            end_date="2026-12-31",
        )
        self.assertEqual(result.elimination.total_intercompany_income, 0.0)
        self.assertEqual(result.elimination.total_intercompany_expense, 100_000.0)
        self.assertFalse(result.elimination.is_balanced)  # 100K mismatch detected

    def test_per_company_breakdown_sorted_by_gross_income(self) -> None:
        self._insert_ledger(company=INSAAT, entry_type="income", amount=100, intercompany=False)
        self._insert_ledger(company=LOJISTIK, entry_type="income", amount=500, intercompany=False)
        self._insert_ledger(company=GIDA, entry_type="income", amount=300, intercompany=False)

        result = self.engine.consolidated_pl(
            holding_id=self.holding_id,
            start_date="2026-01-01",
            end_date="2026-12-31",
        )
        self.assertEqual([l.company for l in result.lines], [LOJISTIK, GIDA, INSAAT])

    def test_holding_not_found_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.engine.consolidated_pl(
                holding_id=99999,
                start_date="2026-01-01",
                end_date="2026-12-31",
            )

    def test_invalid_date_range_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.engine.consolidated_pl(
                holding_id=self.holding_id,
                start_date="2026-12-31",
                end_date="2026-01-01",
            )

    def test_health_status_classification(self) -> None:
        # Negatif net = risk
        self._insert_ledger(company=INSAAT, entry_type="expense", amount=500, intercompany=False)
        result = self.engine.consolidated_pl(
            holding_id=self.holding_id,
            start_date="2026-01-01",
            end_date="2026-12-31",
        )
        self.assertEqual(result.health_status, "risk")

    def test_date_range_filters_correctly(self) -> None:
        self._insert_ledger(
            company=INSAAT, entry_type="income", amount=100_000,
            intercompany=False, entry_date="2025-12-15",
        )
        self._insert_ledger(
            company=INSAAT, entry_type="income", amount=200_000,
            intercompany=False, entry_date="2026-06-15",
        )
        result_q1 = self.engine.consolidated_pl(
            holding_id=self.holding_id,
            start_date="2026-01-01",
            end_date="2026-12-31",
        )
        self.assertEqual(result_q1.consolidated_income, 200_000.0)


if __name__ == "__main__":
    unittest.main()
