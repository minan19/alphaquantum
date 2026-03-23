import os
import unittest

from app.engines.institution_web_engine import InstitutionWebEngine
from app.models import InstitutionPageRequest, InstitutionReportRequest


class InstitutionWebEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_offline = os.getenv("AQ_WEB_OFFLINE")
        self.engine = InstitutionWebEngine()

    def tearDown(self) -> None:
        if self._original_offline is None:
            os.environ.pop("AQ_WEB_OFFLINE", None)
        else:
            os.environ["AQ_WEB_OFFLINE"] = self._original_offline

    def test_build_report_in_offline_mode(self) -> None:
        os.environ["AQ_WEB_OFFLINE"] = "true"

        payload = InstitutionReportRequest(
            pages=[
                InstitutionPageRequest(
                    url="https://www.worldbank.org",
                    focus_terms=["inflation", "rate"],
                ),
                InstitutionPageRequest(url="https://www.tcmb.gov.tr"),
            ],
            global_focus_terms=["budget", "growth"],
        )

        report = self.engine.build_report(payload)
        self.assertEqual(report.page_count, 2)
        self.assertEqual(len(report.pages), 2)
        self.assertTrue(report.executive_summary)

        first_page = report.pages[0]
        self.assertEqual(first_page.status, "ok")
        self.assertIn("worldbank.org", first_page.source_domain)
        self.assertGreaterEqual(len(first_page.extracted_table_rows), 1)
        self.assertGreaterEqual(len(first_page.matched_terms), 1)

    def test_private_host_is_rejected(self) -> None:
        os.environ["AQ_WEB_OFFLINE"] = "false"
        payload = InstitutionReportRequest(
            pages=[InstitutionPageRequest(url="http://localhost/internal-report")],
            global_focus_terms=["budget"],
        )

        report = self.engine.build_report(payload)
        self.assertEqual(report.page_count, 1)
        self.assertEqual(report.pages[0].status, "error")
        self.assertIn("Private or local hosts", report.pages[0].error or "")


if __name__ == "__main__":
    unittest.main()
