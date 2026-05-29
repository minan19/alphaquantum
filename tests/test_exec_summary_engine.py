"""G+1: ExecSummaryEngine tests — offline LLM mode + integration.

Senaryo: Atlas Holding (G1 sprint test fixture) için exec summary üretilir.
LLM offline mode'da deterministic rule-based çıktı döner — CI'da Claude
API çağrısı yapılmaz (sıfır maliyet, sıfır flake).
"""
import os
import tempfile
import time
import unittest
from pathlib import Path

from app.engines.consolidation_engine import ConsolidationEngine
from app.engines.exec_summary_engine import ExecSummaryEngine
from app.engines.group_fx_engine import GroupFXEngine
from app.engines.intercompany_transfer_engine import IntercompanyTransferEngine
from app.finance_repository import FinanceRepository
from app.holding_repository import HoldingRepository
from app.identity_repository import IdentityRepository
from app.intercompany_transfer_repository import IntercompanyTransferRepository
from app.invoice_repository import InvoiceRepository
from app.llm_service import (
    OfflineLLMService,
    create_llm_service,
)
from app.migration_manager import MigrationManager
from app.models import ExecSummaryRequest, IntercompanyTransferRequestCreate
from app.repository import CompanyRepository, default_companies


INSAAT = "Atlas İnşaat A.Ş."
LOJISTIK = "Atlas Lojistik A.Ş."
GIDA = "Atlas Gıda A.Ş."


class OfflineLLMServiceTests(unittest.TestCase):
    """Pure unit tests — DB'siz, rule-based narrative üretimi."""

    def setUp(self) -> None:
        self.service = OfflineLLMService()

    def test_healthy_balanced_narrative(self) -> None:
        ctx = {
            "holding_name": "Atlas Holding",
            "period_start": "2026-01-01",
            "period_end": "2026-03-31",
            "consolidated_pl": {
                "consolidated_net": 1_500_000,
                "gross_total_income": 3_000_000,
                "health_status": "strong",
                "elimination": {"is_balanced": True},
            },
            "fx_position": {
                "net_exposure_try": 500_000,
                "risk_level": "balanced",
            },
            "pending_transfers_count": 0,
        }
        result = self.service.generate_exec_summary(context=ctx)
        self.assertIn("Atlas Holding", result)
        self.assertIn("2026-01-01", result)
        self.assertIn("güçlü", result)
        self.assertIn("dengeli", result)
        self.assertIn("Bekleyen intercompany transfer yok", result)

    def test_risk_state_narrative_includes_warning(self) -> None:
        ctx = {
            "holding_name": "X",
            "period_start": "2026-01-01",
            "period_end": "2026-03-31",
            "consolidated_pl": {
                "consolidated_net": -200_000,
                "gross_total_income": 100_000,
                "health_status": "risk",
                "elimination": {"is_balanced": True},
            },
            "fx_position": {
                "net_exposure_try": 2_000_000,
                "risk_level": "critical",
            },
            "pending_transfers_count": 5,
        }
        result = self.service.generate_exec_summary(context=ctx)
        self.assertIn("risk seviyesinde", result)
        self.assertIn("kritik", result)
        # 3 suggestion (risk + FX + pending birikti)
        self.assertIn("Negatif konsolide net", result)
        self.assertIn("hedging stratejisi", result)
        self.assertIn("4-eyes workflow", result)

    def test_imbalance_triggers_warning(self) -> None:
        ctx = {
            "holding_name": "Y",
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
            "consolidated_pl": {
                "consolidated_net": 0,
                "gross_total_income": 0,
                "health_status": "watch",
                "elimination": {"is_balanced": False},
            },
            "fx_position": {
                "net_exposure_try": 0,
                "risk_level": "balanced",
            },
            "pending_transfers_count": 0,
        }
        result = self.service.generate_exec_summary(context=ctx)
        self.assertIn("⚠️", result)
        self.assertIn("tutarsızlık", result)

    def test_deterministic_output(self) -> None:
        """Aynı context → aynı output (test güvenilirliği)."""
        ctx = {
            "holding_name": "Test",
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
            "consolidated_pl": {
                "consolidated_net": 100,
                "gross_total_income": 200,
                "health_status": "stable",
                "elimination": {"is_balanced": True},
            },
            "fx_position": {
                "net_exposure_try": 50,
                "risk_level": "balanced",
            },
            "pending_transfers_count": 0,
        }
        out1 = self.service.generate_exec_summary(context=ctx)
        out2 = self.service.generate_exec_summary(context=ctx)
        self.assertEqual(out1, out2)


class LLMServiceFactoryTests(unittest.TestCase):
    """Factory: env var'lara göre doğru service döner."""

    def setUp(self) -> None:
        # Save env state
        self._saved = {
            "AQ_LLM_OFFLINE": os.environ.get("AQ_LLM_OFFLINE"),
            "AQ_ANTHROPIC_API_KEY": os.environ.get("AQ_ANTHROPIC_API_KEY"),
        }

    def tearDown(self) -> None:
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_offline_flag_returns_offline_service(self) -> None:
        os.environ["AQ_LLM_OFFLINE"] = "true"
        os.environ.pop("AQ_ANTHROPIC_API_KEY", None)
        service = create_llm_service()
        self.assertIsInstance(service, OfflineLLMService)

    def test_no_api_key_returns_offline_service(self) -> None:
        os.environ.pop("AQ_LLM_OFFLINE", None)
        os.environ.pop("AQ_ANTHROPIC_API_KEY", None)
        service = create_llm_service()
        self.assertIsInstance(service, OfflineLLMService)


class ExecSummaryEngineIntegrationTests(unittest.TestCase):
    """ExecSummaryEngine + 3 engine + OfflineLLM tam akış."""

    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._temp_dir.name) / "exec_test.db"
        migrations_dir = Path(__file__).resolve().parent.parent / "migrations"

        bootstrap_repo = IdentityRepository(str(self._db_path))
        bootstrap_repo.close()
        self.manager = MigrationManager(str(self._db_path), str(migrations_dir))
        self.manager.apply_all()

        self.company_repo = CompanyRepository(
            str(self._db_path), default_companies()
        )
        self.holding_repo = HoldingRepository(str(self._db_path))
        self.finance_repo = FinanceRepository(str(self._db_path))
        self.invoice_repo = InvoiceRepository(str(self._db_path))
        self.transfer_repo = IntercompanyTransferRepository(str(self._db_path))

        # Atlas Holding
        holding_row = self.holding_repo.create_holding(
            name="Atlas Holding",
            code="ATLAS",
            description="Test",
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

        consolidation = ConsolidationEngine(
            finance_repo=self.finance_repo,
            holding_repo=self.holding_repo,
        )
        group_fx = GroupFXEngine(
            holding_repo=self.holding_repo,
            invoice_repo=self.invoice_repo,
            transfer_repo=self.transfer_repo,
        )
        ic_engine = IntercompanyTransferEngine(
            transfer_repo=self.transfer_repo,
            holding_repo=self.holding_repo,
        )
        self.exec_engine = ExecSummaryEngine(
            consolidation_engine=consolidation,
            group_fx_engine=group_fx,
            intercompany_engine=ic_engine,
            llm_service=OfflineLLMService(),
        )
        self.ic_engine = ic_engine

    def tearDown(self) -> None:
        self.transfer_repo.close()
        self.invoice_repo.close()
        self.finance_repo.close()
        self.holding_repo.close()
        self.company_repo.close()
        self.manager.close()
        self._temp_dir.cleanup()

    def _insert_ledger(
        self, *, company: str, entry_type: str, amount: float,
        intercompany: bool = False, counterparty: str | None = None,
        transfer_id: int | None = None,
    ) -> None:
        with self.finance_repo._lock:
            self.finance_repo._conn.execute(
                """
                INSERT INTO finance_ledger_entries
                    (company_name, entry_type, amount, category, description,
                     entry_date, created_at,
                     counterparty_company, transfer_id, intercompany_flag)
                VALUES (?, ?, ?, 'test', 'test', '2026-03-15', ?, ?, ?, ?)
                """,
                (
                    company, entry_type, amount, int(time.time()),
                    counterparty, transfer_id, 1 if intercompany else 0,
                ),
            )
            self.finance_repo._conn.commit()

    def test_generate_summary_empty_holding(self) -> None:
        """Boş holding → narrative + highlights üretir."""
        result = self.exec_engine.generate_summary(
            holding_id=self.holding_id,
            payload=ExecSummaryRequest(
                period_start="2026-01-01",
                period_end="2026-03-31",
            ),
        )
        self.assertEqual(result.holding_id, self.holding_id)
        self.assertEqual(result.holding_name, "Atlas Holding")
        self.assertEqual(result.period_start, "2026-01-01")
        self.assertEqual(result.period_end, "2026-03-31")
        self.assertGreater(len(result.narrative), 50)  # gerçek metin
        self.assertGreater(len(result.highlights), 0)
        self.assertIn("Atlas Holding", result.narrative)

    def test_generate_summary_with_data(self) -> None:
        """Income/expense + IC transfer + invoice ile gerçek senaryo."""
        # Dış satışlar
        self._insert_ledger(company=INSAAT, entry_type="income", amount=1_400_000)
        self._insert_ledger(company=LOJISTIK, entry_type="income", amount=720_000)
        # Dış giderler
        self._insert_ledger(company=INSAAT, entry_type="expense", amount=360_000)
        self._insert_ledger(company=GIDA, entry_type="expense", amount=165_000)

        # Pending transfer
        self.ic_engine.request_transfer(
            holding_id=self.holding_id,
            payload=IntercompanyTransferRequestCreate(
                from_company=LOJISTIK,
                to_company=GIDA,
                amount=50_000,
                currency="TRY",
                description="Q2 destek",
            ),
            requested_by="cfo@atlas.tr",
        )

        result = self.exec_engine.generate_summary(
            holding_id=self.holding_id,
            payload=ExecSummaryRequest(
                period_start="2026-01-01",
                period_end="2026-12-31",
            ),
        )
        # Rakamlar context'e geçti
        self.assertEqual(result.pending_transfers_count, 1)
        self.assertGreater(result.consolidated_net_try, 0)
        # Highlights yapısal
        self.assertTrue(any("Konsolide net" in h for h in result.highlights))
        self.assertTrue(any("FX net" in h for h in result.highlights))
        self.assertTrue(any("4-eyes" in h or "onay sırasında" in h for h in result.highlights))

    def test_generate_summary_invalid_date_range_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.exec_engine.generate_summary(
                holding_id=self.holding_id,
                payload=ExecSummaryRequest(
                    period_start="2026-12-31",
                    period_end="2026-01-01",
                ),
            )

    def test_generate_summary_holding_not_found_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.exec_engine.generate_summary(
                holding_id=99999,
                payload=ExecSummaryRequest(
                    period_start="2026-01-01",
                    period_end="2026-03-31",
                ),
            )

    def test_highlights_emoji_health_indicator(self) -> None:
        result = self.exec_engine.generate_summary(
            holding_id=self.holding_id,
            payload=ExecSummaryRequest(
                period_start="2026-01-01",
                period_end="2026-03-31",
            ),
        )
        # En az bir emoji-prefixed highlight olmalı
        emoji_codes = {"🟢", "🟡", "🟠", "🔴", "⚪"}
        has_emoji = any(any(e in h for e in emoji_codes) for h in result.highlights)
        self.assertTrue(has_emoji)


if __name__ == "__main__":
    unittest.main()
