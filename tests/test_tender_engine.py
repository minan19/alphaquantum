import unittest

from app.engines.tender_engine import TenderEngine
from app.models import TenderGenerationRequest


class TenderEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = TenderEngine()

    def test_build_dossier_returns_compliance_and_sections(self) -> None:
        payload = TenderGenerationRequest(
            institution_name="Sample Public Institution",
            tender_title="Network Infrastructure Tender",
            tender_reference="2026/12345",
            company_name="Alpha Quantum A.S.",
            administrative_spec=(
                "Bidder must provide tax clearance certificate. "
                "Signature circular is mandatory. "
                "Required documents shall be submitted before deadline."
            ),
            technical_spec=(
                "Technical response matrix is mandatory. "
                "Vendor shall provide minimum 24 months support. "
                "Compliance document must include architecture details."
            ),
            additional_requirements=["Temporary bid bond is mandatory for this lot."],
            use_kik_baseline=True,
        )

        report = self.engine.build_dossier(payload)
        self.assertEqual(report.institution_name, "Sample Public Institution")
        self.assertGreaterEqual(len(report.compliance_matrix), 3)
        self.assertGreaterEqual(len(report.control_checklist), len(report.compliance_matrix))
        self.assertGreaterEqual(len(report.traceability_matrix), 1)
        self.assertGreaterEqual(report.validation_summary.total_controls, 1)
        self.assertIn(report.validation_summary.release_recommendation, {"READY", "READY_WITH_CONDITIONS", "NOT_READY"})
        self.assertGreaterEqual(len(report.dossier_sections), 4)
        self.assertGreaterEqual(len(report.attachment_checklist), 4)
        self.assertIn("legal", report.legal_notice.lower())
        self.assertIn("Tender Dossier Draft", report.dossier_markdown)


if __name__ == "__main__":
    unittest.main()
