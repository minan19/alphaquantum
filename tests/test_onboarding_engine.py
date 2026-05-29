"""BZ1: OnboardingEngine tests — self-service aktivasyon."""
import tempfile
import unittest
from pathlib import Path

from app.engines.onboarding_engine import OnboardingEngine
from app.identity_repository import IdentityRepository
from app.invoice_repository import InvoiceRepository
from app.migration_manager import MigrationManager
from app.models import (
    OnboardingCompanyStep,
    OnboardingCompleteRequest,
    OnboardingConnectorStep,
    OnboardingFirstInvoiceStep,
)
from app.repository import CompanyRepository, default_companies


class OnboardingEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._temp_dir.name) / "onboarding_test.db"
        migrations_dir = Path(__file__).resolve().parent.parent / "migrations"

        bootstrap_repo = IdentityRepository(str(self._db_path))
        bootstrap_repo.close()
        self.manager = MigrationManager(str(self._db_path), str(migrations_dir))
        self.manager.apply_all()

        self.company_repo = CompanyRepository(
            str(self._db_path), default_companies()
        )
        self.invoice_repo = InvoiceRepository(str(self._db_path))
        self.engine = OnboardingEngine(
            company_repo=self.company_repo,
            invoice_repo=self.invoice_repo,
        )

    def tearDown(self) -> None:
        self.invoice_repo.close()
        self.company_repo.close()
        self.manager.close()
        self._temp_dir.cleanup()

    def _make_payload(
        self,
        *,
        company_name: str = "Test KOBİ A.Ş.",
        connector_type: str | None = "skip",
        customer_name: str = "Acme Ltd.",
    ) -> OnboardingCompleteRequest:
        return OnboardingCompleteRequest(
            company=OnboardingCompanyStep(
                name=company_name,
                sector="Tekstil",
                employee_count=15,
                initial_balance=100_000,
            ),
            connector=OnboardingConnectorStep(connector_type=connector_type),
            first_invoice=OnboardingFirstInvoiceStep(
                customer_name=customer_name,
                amount=25_000,
                currency="TRY",
                issue_date="2026-05-01",
                due_date="2026-06-01",
                description="Q2 ürün satış",
            ),
        )

    # ── COMPLETE ──────────────────────────────────────────────────────

    def test_complete_creates_company_and_invoice(self) -> None:
        result = self.engine.complete(
            user_id="ahmet@kobi.tr",
            payload=self._make_payload(),
        )
        self.assertTrue(result.success)
        self.assertEqual(result.company_name, "Test KOBİ A.Ş.")
        self.assertIsNotNone(result.invoice_id)
        self.assertFalse(result.connector_registered)  # skip
        self.assertGreater(result.completed_at, 0)
        self.assertIn("Hoş geldiniz", result.welcome_message)
        self.assertGreater(len(result.next_steps), 0)

    def test_complete_with_logo_tiger_connector_marked_registered(self) -> None:
        result = self.engine.complete(
            user_id="x",
            payload=self._make_payload(connector_type="logo_tiger"),
        )
        self.assertTrue(result.connector_registered)
        # Next steps başında connector kurulum yönlendirmesi
        self.assertTrue(
            any("logo_tiger" in s for s in result.next_steps),
        )

    def test_complete_with_unknown_connector_not_registered(self) -> None:
        result = self.engine.complete(
            user_id="x",
            payload=self._make_payload(connector_type="unknown_erp"),
        )
        self.assertFalse(result.connector_registered)

    def test_complete_idempotent_company_ensure(self) -> None:
        """Aynı şirket adıyla 2. submission → bozulmaz, yeni fatura eklenir."""
        first = self.engine.complete(
            user_id="a",
            payload=self._make_payload(company_name="Atlas Ltd"),
        )
        second = self.engine.complete(
            user_id="a",
            payload=self._make_payload(
                company_name="Atlas Ltd",
                customer_name="2. müşteri",
            ),
        )
        self.assertNotEqual(first.invoice_id, second.invoice_id)

    def test_complete_invalid_date_range_raises(self) -> None:
        payload = self._make_payload()
        # due_date < issue_date
        payload.first_invoice.issue_date = "2026-06-01"
        payload.first_invoice.due_date = "2026-05-01"
        with self.assertRaises(ValueError):
            self.engine.complete(user_id="x", payload=payload)

    def test_complete_empty_company_name_raises(self) -> None:
        payload = self._make_payload(company_name="   ")
        with self.assertRaises(ValueError):
            self.engine.complete(user_id="x", payload=payload)

    # ── STATUS ────────────────────────────────────────────────────────

    def test_status_default_companies_have_no_invoice(self) -> None:
        """Default seed companies var ama henüz fatura yok → is_onboarded=False."""
        result = self.engine.status(user_id="x")
        # default_companies() içeren company sayısı 1+ olabilir
        self.assertGreaterEqual(result.company_count, 0)
        self.assertEqual(result.invoice_count, 0)
        self.assertFalse(result.is_onboarded)

    def test_status_onboarded_after_complete(self) -> None:
        self.engine.complete(user_id="x", payload=self._make_payload())
        result = self.engine.status(user_id="x")
        self.assertTrue(result.is_onboarded)
        self.assertGreaterEqual(result.company_count, 1)
        self.assertGreaterEqual(result.invoice_count, 1)


if __name__ == "__main__":
    unittest.main()
