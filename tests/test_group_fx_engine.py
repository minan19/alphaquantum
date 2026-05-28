"""G1.4: GroupFXEngine tests — holding-wide multi-currency net pozisyon.

Senaryo: Atlas Holding (İnşaat + Lojistik + Gıda).
  - İnşaat: EUR ihracat alacağı (long EUR)
  - Gıda: USD ithalat alacağı (long USD ama bu örnekte kısa simüle)
  - Lojistik: TRY operations only
  - + intercompany USD transfer
"""
import tempfile
import unittest
from pathlib import Path

from app.currency_converter import CurrencyConverter
from app.engines.group_fx_engine import GroupFXEngine
from app.engines.intercompany_transfer_engine import IntercompanyTransferEngine
from app.holding_repository import HoldingRepository
from app.identity_repository import IdentityRepository
from app.intercompany_transfer_repository import IntercompanyTransferRepository
from app.invoice_repository import InvoiceRepository
from app.migration_manager import MigrationManager
from app.models import IntercompanyTransferRequestCreate
from app.repository import CompanyRepository, default_companies


INSAAT = "Atlas İnşaat A.Ş."
LOJISTIK = "Atlas Lojistik A.Ş."
GIDA = "Atlas Gıda A.Ş."

# Sabit FX rates (deterministic test)
FIXED_RATES = {"USD": 32.0, "EUR": 35.0, "GBP": 41.0}


class GroupFXEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._temp_dir.name) / "fx_test.db"
        migrations_dir = Path(__file__).resolve().parent.parent / "migrations"

        bootstrap_repo = IdentityRepository(str(self._db_path))
        bootstrap_repo.close()
        self.manager = MigrationManager(str(self._db_path), str(migrations_dir))
        self.manager.apply_all()

        self.company_repo = CompanyRepository(
            str(self._db_path), default_companies()
        )
        self.holding_repo = HoldingRepository(str(self._db_path))
        self.invoice_repo = InvoiceRepository(str(self._db_path))
        self.transfer_repo = IntercompanyTransferRepository(str(self._db_path))

        # Holding + companies
        holding_row = self.holding_repo.create_holding(
            name="Atlas Holding",
            code="ATLAS",
            description="FX test holding",
            status="active",
        )
        self.holding_id = int(holding_row["id"])
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

        # Deterministic FX converter
        converter = CurrencyConverter(rates=FIXED_RATES)
        self.engine = GroupFXEngine(
            holding_repo=self.holding_repo,
            invoice_repo=self.invoice_repo,
            transfer_repo=self.transfer_repo,
            fx_converter=converter,
        )
        # IC engine for atomic transfers
        self.ic_engine = IntercompanyTransferEngine(
            transfer_repo=self.transfer_repo,
            holding_repo=self.holding_repo,
        )

    def tearDown(self) -> None:
        self.transfer_repo.close()
        self.invoice_repo.close()
        self.holding_repo.close()
        self.company_repo.close()
        self.manager.close()
        self._temp_dir.cleanup()

    # ── Tests ──────────────────────────────────────────────────────────

    def test_empty_holding_returns_zero_exposure(self) -> None:
        result = self.engine.group_fx_position(holding_id=self.holding_id)
        self.assertEqual(result.holding_id, self.holding_id)
        self.assertEqual(result.exposures, [])
        self.assertEqual(result.total_long_try, 0.0)
        self.assertEqual(result.total_short_try, 0.0)
        self.assertEqual(result.net_exposure_try, 0.0)
        self.assertEqual(result.risk_level, "balanced")
        # 3 sensitivity senaryosu hep var
        self.assertEqual(len(result.sensitivity_scenarios), 3)

    def test_eur_receivable_creates_long_position(self) -> None:
        # İnşaat'ın €100K EUR alacağı (export)
        self.invoice_repo.create_invoice(
            company_name=INSAAT,
            title="Almanya inşaat ihracatı",
            amount=100_000,
            currency="EUR",
            issue_date="2026-01-15",
            due_date="2026-06-15",
        )
        result = self.engine.group_fx_position(holding_id=self.holding_id)
        self.assertEqual(len(result.exposures), 1)
        eur = result.exposures[0]
        self.assertEqual(eur.currency, "EUR")
        self.assertEqual(eur.receivable_open, 100_000.0)
        self.assertEqual(eur.net_position_fx, 100_000.0)
        self.assertEqual(eur.position_type, "long")
        # TRY karşılığı: 100K × 35 = 3.5M
        self.assertEqual(eur.net_position_try, 3_500_000.0)

    def test_multi_currency_holding(self) -> None:
        # EUR long (3.5M TL)
        self.invoice_repo.create_invoice(
            company_name=INSAAT, title="EUR ihracat", amount=100_000,
            currency="EUR", issue_date="2026-01-15", due_date="2026-06-15",
        )
        # USD long (1.6M TL)
        self.invoice_repo.create_invoice(
            company_name=GIDA, title="USD ihracat", amount=50_000,
            currency="USD", issue_date="2026-01-15", due_date="2026-06-15",
        )
        # GBP long (820K TL)
        self.invoice_repo.create_invoice(
            company_name=LOJISTIK, title="GBP kargo", amount=20_000,
            currency="GBP", issue_date="2026-01-15", due_date="2026-06-15",
        )
        result = self.engine.group_fx_position(holding_id=self.holding_id)
        self.assertEqual(len(result.exposures), 3)
        # Sort: |net_try| desc → EUR (3.5M), USD (1.6M), GBP (820K)
        self.assertEqual(result.exposures[0].currency, "EUR")
        self.assertEqual(result.exposures[1].currency, "USD")
        self.assertEqual(result.exposures[2].currency, "GBP")
        # Total long = 3.5M + 1.6M + 820K
        self.assertEqual(result.total_long_try, 5_920_000.0)
        self.assertEqual(result.total_short_try, 0.0)
        self.assertEqual(result.net_exposure_try, 5_920_000.0)

    def test_overdue_invoices_tracked_separately(self) -> None:
        # Overdue: due_date 2025-01-01, as_of_date 2026-06-15
        self.invoice_repo.create_invoice(
            company_name=INSAAT, title="Gecikmiş",
            amount=200_000, currency="EUR",
            issue_date="2024-12-01", due_date="2025-01-01",
        )
        # Open (not overdue): due 2027
        self.invoice_repo.create_invoice(
            company_name=INSAAT, title="Vadeli",
            amount=100_000, currency="EUR",
            issue_date="2026-01-15", due_date="2027-01-15",
        )
        result = self.engine.group_fx_position(
            holding_id=self.holding_id, as_of_date="2026-06-15"
        )
        eur = result.exposures[0]
        self.assertEqual(eur.receivable_open, 300_000.0)
        self.assertEqual(eur.receivable_overdue, 200_000.0)

    def test_sensitivity_scenarios_compute(self) -> None:
        # EUR long 100K (3.5M TL)
        self.invoice_repo.create_invoice(
            company_name=INSAAT, title="EUR", amount=100_000,
            currency="EUR", issue_date="2026-01-15", due_date="2026-06-15",
        )
        result = self.engine.group_fx_position(holding_id=self.holding_id)
        # %5 devaluation → 3.5M × 0.05 = 175K gain
        s5 = next(s for s in result.sensitivity_scenarios if s.devaluation_pct == 0.05)
        self.assertEqual(s5.total_impact_try, 175_000.0)
        # %10 → 350K
        s10 = next(s for s in result.sensitivity_scenarios if s.devaluation_pct == 0.10)
        self.assertEqual(s10.total_impact_try, 350_000.0)
        # %20 → 700K
        s20 = next(s for s in result.sensitivity_scenarios if s.devaluation_pct == 0.20)
        self.assertEqual(s20.total_impact_try, 700_000.0)

    def test_risk_level_balanced_when_no_concentration(self) -> None:
        # Sıfır exposure → balanced
        result = self.engine.group_fx_position(holding_id=self.holding_id)
        self.assertEqual(result.risk_level, "balanced")

    def test_risk_level_critical_when_concentrated(self) -> None:
        # Tek yön çok büyük
        self.invoice_repo.create_invoice(
            company_name=INSAAT, title="Big EUR", amount=1_000_000,
            currency="EUR", issue_date="2026-01-15", due_date="2026-06-15",
        )
        result = self.engine.group_fx_position(holding_id=self.holding_id)
        self.assertEqual(result.risk_level, "critical")  # tek yön = max concentration

    def test_intercompany_completed_transfer_aggregates(self) -> None:
        # USD intercompany transfer (atomic G1.3 engine ile)
        payload = IntercompanyTransferRequestCreate(
            from_company=INSAAT, to_company=LOJISTIK,
            amount=10_000, currency="USD",
            description="USD transfer",
        )
        transfer = self.ic_engine.request_transfer(
            holding_id=self.holding_id,
            payload=payload,
            requested_by="cfo@atlas.tr",
        )
        # 4-eyes approve
        self.ic_engine.approve(
            transfer_id=transfer.id,
            approver_user_id="finance@atlas.tr",
        )

        result = self.engine.group_fx_position(holding_id=self.holding_id)
        # USD exposure'u var
        usd_exposures = [e for e in result.exposures if e.currency == "USD"]
        self.assertEqual(len(usd_exposures), 1)
        usd = usd_exposures[0]
        self.assertEqual(usd.intercompany_inflow, 10_000.0)
        self.assertEqual(usd.intercompany_outflow, 10_000.0)
        # Net = inflow - outflow = 0 (holding-wide, intercompany kapanır)
        self.assertEqual(usd.net_position_fx, 0.0)
        self.assertEqual(usd.position_type, "flat")

    def test_holding_not_found_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.engine.group_fx_position(holding_id=99999)

    def test_recommendations_present(self) -> None:
        self.invoice_repo.create_invoice(
            company_name=INSAAT, title="EUR", amount=100_000,
            currency="EUR", issue_date="2026-01-15", due_date="2026-06-15",
        )
        result = self.engine.group_fx_position(holding_id=self.holding_id)
        # En az bir genel öneri + bir EUR-spesifik
        self.assertGreater(len(result.recommendations), 0)
        # critical risk level → "KRİTİK" öneri
        self.assertTrue(
            any("KRİTİK" in r or "konsantrasyon" in r for r in result.recommendations)
        )


if __name__ == "__main__":
    unittest.main()
