"""G1.3: IntercompanyTransferEngine tests — 4-eyes + atomic + state machine.

Karma sektörlü holding senaryosu:
  - Atlas Holding: İnşaat + Lojistik + Gıda
  - Mehmet (CFO) talep eder, Ayşe (Finans Müdürü) onaylar.
  - 4-eyes: Mehmet kendi talebini onaylayamaz.
  - Atomic: approve → 2 ledger entry oluşur, status=completed.
  - Reject path: status=rejected, ledger entry YOK.
"""
import tempfile
import unittest
from pathlib import Path

from app.engines.consolidation_engine import ConsolidationEngine
from app.engines.intercompany_transfer_engine import IntercompanyTransferEngine
from app.finance_repository import FinanceRepository
from app.holding_repository import HoldingRepository
from app.identity_repository import IdentityRepository
from app.intercompany_transfer_repository import IntercompanyTransferRepository
from app.migration_manager import MigrationManager
from app.models import IntercompanyTransferRequestCreate
from app.repository import CompanyRepository, default_companies


INSAAT = "Atlas İnşaat A.Ş."
LOJISTIK = "Atlas Lojistik A.Ş."
GIDA = "Atlas Gıda A.Ş."

MEHMET = "cfo@atlas.tr"      # requester
AYSE = "finance@atlas.tr"     # approver (4-eyes)
HASAN = "audit@atlas.tr"      # 3. user


class IntercompanyTransferEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._temp_dir.name) / "ic_transfer_test.db"
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
        self.transfer_repo = IntercompanyTransferRepository(str(self._db_path))

        # Holding + 3 şirket
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

        self.engine = IntercompanyTransferEngine(
            transfer_repo=self.transfer_repo,
            holding_repo=self.holding_repo,
        )
        # Konsolidasyon engine: atomic write sonrası elimination balance check için
        self.consolidation = ConsolidationEngine(
            finance_repo=self.finance_repo,
            holding_repo=self.holding_repo,
        )

    def tearDown(self) -> None:
        self.transfer_repo.close()
        self.finance_repo.close()
        self.holding_repo.close()
        self.company_repo.close()
        self.manager.close()
        self._temp_dir.cleanup()

    def _make_payload(
        self,
        amount: float = 100_000,
        from_company: str = INSAAT,
        to_company: str = LOJISTIK,
    ) -> IntercompanyTransferRequestCreate:
        return IntercompanyTransferRequestCreate(
            from_company=from_company,
            to_company=to_company,
            amount=amount,
            currency="TRY",
            description="Q4 kaynak desteği",
        )

    # ── REQUEST PATH ───────────────────────────────────────────────────

    def test_request_transfer_creates_pending(self) -> None:
        result = self.engine.request_transfer(
            holding_id=self.holding_id,
            payload=self._make_payload(),
            requested_by=MEHMET,
        )
        self.assertEqual(result.approval_status, "pending")
        self.assertEqual(result.requested_by, MEHMET)
        self.assertIsNone(result.approved_by)
        self.assertIsNone(result.ledger_entry_from_id)
        self.assertEqual(result.from_company, INSAAT)
        self.assertEqual(result.to_company, LOJISTIK)
        self.assertEqual(result.amount, 100_000.0)

    def test_request_with_invalid_holding_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.engine.request_transfer(
                holding_id=99999,
                payload=self._make_payload(),
                requested_by=MEHMET,
            )

    def test_request_self_transfer_blocked(self) -> None:
        payload = self._make_payload(from_company=INSAAT, to_company=INSAAT)
        with self.assertRaises(ValueError) as ctx:
            self.engine.request_transfer(
                holding_id=self.holding_id,
                payload=payload,
                requested_by=MEHMET,
            )
        self.assertIn("self-transfer", str(ctx.exception).lower())

    def test_cross_currency_requires_both_fields(self) -> None:
        # Sadece target_amount, fx_rate yok → reject
        payload = IntercompanyTransferRequestCreate(
            from_company=INSAAT,
            to_company=LOJISTIK,
            amount=1000,
            currency="EUR",
            target_amount=35_000,
            # fx_rate yok
        )
        with self.assertRaises(ValueError):
            self.engine.request_transfer(
                holding_id=self.holding_id,
                payload=payload,
                requested_by=MEHMET,
            )

    # ── APPROVE PATH (4-EYES + ATOMIC) ─────────────────────────────────

    def test_approve_creates_atomic_ledger_entries(self) -> None:
        transfer = self.engine.request_transfer(
            holding_id=self.holding_id,
            payload=self._make_payload(amount=500_000),
            requested_by=MEHMET,
        )
        # Pre-approve: ledger boş
        ledger_pre = self.finance_repo.list_ledger_entries(
            company_name=None, start_date="2020-01-01",
            end_date="2030-12-31", limit=100,
        )
        self.assertEqual(len(ledger_pre), 0)

        # Onayla (Ayşe, 4-eyes OK)
        approved = self.engine.approve(
            transfer_id=transfer.id,
            approver_user_id=AYSE,
        )

        # State: completed (yarı state "approved" geçişti)
        self.assertEqual(approved.approval_status, "completed")
        self.assertEqual(approved.approved_by, AYSE)
        self.assertIsNotNone(approved.approved_at)
        self.assertIsNotNone(approved.completed_at)
        self.assertIsNotNone(approved.ledger_entry_from_id)
        self.assertIsNotNone(approved.ledger_entry_to_id)

        # Ledger: 2 entry
        ledger_post = self.finance_repo.list_ledger_entries(
            company_name=None, start_date="2020-01-01",
            end_date="2030-12-31", limit=100,
        )
        self.assertEqual(len(ledger_post), 2)

        # Kontrol: from = expense, to = income
        # list_ledger_entries dict döner, key 'company_name'
        by_company = {e["company_name"]: e for e in ledger_post}
        self.assertEqual(by_company[INSAAT]["entry_type"], "expense")
        self.assertEqual(by_company[INSAAT]["amount"], 500_000)
        self.assertEqual(by_company[LOJISTIK]["entry_type"], "income")
        self.assertEqual(by_company[LOJISTIK]["amount"], 500_000)

    def test_4_eyes_violation_rejected(self) -> None:
        """Mehmet kendi talebini onaylayamaz."""
        transfer = self.engine.request_transfer(
            holding_id=self.holding_id,
            payload=self._make_payload(),
            requested_by=MEHMET,
        )
        with self.assertRaises(ValueError) as ctx:
            self.engine.approve(
                transfer_id=transfer.id,
                approver_user_id=MEHMET,  # SAME as requester
            )
        self.assertIn("4-eyes", str(ctx.exception))

    def test_double_approve_blocked(self) -> None:
        transfer = self.engine.request_transfer(
            holding_id=self.holding_id,
            payload=self._make_payload(),
            requested_by=MEHMET,
        )
        self.engine.approve(transfer_id=transfer.id, approver_user_id=AYSE)
        # Tekrar approve denenirse status=completed → reject
        with self.assertRaises(ValueError):
            self.engine.approve(transfer_id=transfer.id, approver_user_id=HASAN)

    def test_approve_nonexistent_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.engine.approve(transfer_id=99999, approver_user_id=AYSE)

    def test_approved_transfer_balances_in_consolidation(self) -> None:
        """Atomic write garantisi: konsolide P&L'de is_balanced=True olmalı."""
        transfer = self.engine.request_transfer(
            holding_id=self.holding_id,
            payload=self._make_payload(amount=75_000),
            requested_by=MEHMET,
        )
        self.engine.approve(transfer_id=transfer.id, approver_user_id=AYSE)

        pl = self.consolidation.consolidated_pl(
            holding_id=self.holding_id,
            start_date="2020-01-01",
            end_date="2030-12-31",
        )
        # Atomic write garantisi
        self.assertTrue(pl.elimination.is_balanced)
        self.assertEqual(pl.elimination.total_intercompany_income, 75_000)
        self.assertEqual(pl.elimination.total_intercompany_expense, 75_000)
        # Konsolide net = 0 (sadece grup içi transfer, dış işlem yok)
        self.assertEqual(pl.consolidated_net, 0.0)

    # ── REJECT PATH ────────────────────────────────────────────────────

    def test_reject_marks_status_without_ledger(self) -> None:
        transfer = self.engine.request_transfer(
            holding_id=self.holding_id,
            payload=self._make_payload(),
            requested_by=MEHMET,
        )
        rejected = self.engine.reject(
            transfer_id=transfer.id,
            approver_user_id=AYSE,
            reject_reason="Risk komitesi onayı gerekli",
        )
        self.assertEqual(rejected.approval_status, "rejected")
        self.assertEqual(rejected.approved_by, AYSE)
        self.assertEqual(rejected.reject_reason, "Risk komitesi onayı gerekli")
        # Ledger boş kalmalı
        ledger = self.finance_repo.list_ledger_entries(
            company_name=None, start_date="2020-01-01",
            end_date="2030-12-31", limit=100,
        )
        self.assertEqual(len(ledger), 0)

    def test_reject_4_eyes_violation(self) -> None:
        transfer = self.engine.request_transfer(
            holding_id=self.holding_id,
            payload=self._make_payload(),
            requested_by=MEHMET,
        )
        with self.assertRaises(ValueError):
            self.engine.reject(
                transfer_id=transfer.id,
                approver_user_id=MEHMET,  # self-reject yasak
                reject_reason="x",
            )

    def test_reject_after_approve_blocked(self) -> None:
        transfer = self.engine.request_transfer(
            holding_id=self.holding_id,
            payload=self._make_payload(),
            requested_by=MEHMET,
        )
        self.engine.approve(transfer_id=transfer.id, approver_user_id=AYSE)
        with self.assertRaises(ValueError):
            self.engine.reject(
                transfer_id=transfer.id,
                approver_user_id=HASAN,
                reject_reason="too late",
            )

    # ── LIST + READ ────────────────────────────────────────────────────

    def test_list_pending_returns_only_pending(self) -> None:
        # 1 pending, 1 approved, 1 rejected
        t1 = self.engine.request_transfer(
            holding_id=self.holding_id,
            payload=self._make_payload(amount=10_000),
            requested_by=MEHMET,
        )
        t2 = self.engine.request_transfer(
            holding_id=self.holding_id,
            payload=self._make_payload(amount=20_000),
            requested_by=MEHMET,
        )
        t3 = self.engine.request_transfer(
            holding_id=self.holding_id,
            payload=self._make_payload(amount=30_000),
            requested_by=MEHMET,
        )
        self.engine.approve(transfer_id=t2.id, approver_user_id=AYSE)
        self.engine.reject(
            transfer_id=t3.id, approver_user_id=AYSE, reject_reason="no"
        )

        pending = self.engine.list_pending(holding_id=self.holding_id)
        self.assertEqual(pending.total, 1)
        self.assertEqual(pending.transfers[0].id, t1.id)

    def test_get_transfer_round_trip(self) -> None:
        created = self.engine.request_transfer(
            holding_id=self.holding_id,
            payload=self._make_payload(),
            requested_by=MEHMET,
        )
        fetched = self.engine.get_transfer(created.id)
        self.assertEqual(fetched.id, created.id)
        self.assertEqual(fetched.requested_by, MEHMET)

    def test_get_nonexistent_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.engine.get_transfer(99999)


if __name__ == "__main__":
    unittest.main()
