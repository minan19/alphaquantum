"""I1: ConnectorImportEngine integration tests."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.connector_import_repository import ConnectorImportRepository
from app.engines.connector_import_engine import ConnectorImportEngine
from app.identity_repository import IdentityRepository
from app.migration_manager import MigrationManager


SIMPLE_LOGO_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<LOGOWORLD>
  <CARI>
    <CARI_KODU>C100</CARI_KODU>
    <CARI_UNVAN>Test Cari A.S.</CARI_UNVAN>
    <CARI_VKN>1111111111</CARI_VKN>
    <CARI_TIPI>1</CARI_TIPI>
  </CARI>
  <FATURA>
    <FATURA_NO>F100</FATURA_NO>
    <FATURA_CARI_KODU>C100</FATURA_CARI_KODU>
    <FATURA_TARIHI>2026-05-01</FATURA_TARIHI>
    <FATURA_NET>1000</FATURA_NET>
    <FATURA_KDV>180</FATURA_KDV>
    <FATURA_BRUT>1180</FATURA_BRUT>
    <FATURA_TIPI>1</FATURA_TIPI>
  </FATURA>
</LOGOWORLD>
"""


class ConnectorImportEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp.name) / "import_test.db"
        migrations_dir = Path(__file__).resolve().parent.parent / "migrations"

        bootstrap = IdentityRepository(str(self._db_path))
        bootstrap.close()
        self.manager = MigrationManager(str(self._db_path), str(migrations_dir))
        self.manager.apply_all()

        self.repo = ConnectorImportRepository(str(self._db_path))
        self.engine = ConnectorImportEngine(
            repo=self.repo, ledger_db_path=str(self._db_path),
        )

    def tearDown(self) -> None:
        self.repo.close()
        self.manager.close()
        self._tmp.cleanup()

    # ── Preview ────────────────────────────────────────────────────────

    def test_parse_and_preview_creates_job_with_preview_status(self) -> None:
        job = self.engine.parse_and_preview(
            user_id="u1",
            connector_type="logo_tiger",
            mode="xml",
            data=SIMPLE_LOGO_XML,
            filename="logo.xml",
        )
        self.assertEqual(job["status"], "preview")
        self.assertEqual(job["summary"]["customers"], 1)
        self.assertEqual(job["summary"]["invoices"], 1)
        self.assertEqual(len(job["preview"]), 2)

    def test_unknown_connector_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.engine.parse_and_preview(
                user_id="u1", connector_type="garbage", mode="xml",
                data=b"<x/>",
            )

    def test_unsupported_mode_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.engine.parse_and_preview(
                user_id="u1", connector_type="logo_tiger", mode="invalid",
                data=b"<x/>",
            )

    # ── Commit ─────────────────────────────────────────────────────────

    def test_commit_persists_records(self) -> None:
        job = self.engine.parse_and_preview(
            user_id="u2", connector_type="logo_tiger", mode="xml",
            data=SIMPLE_LOGO_XML,
        )
        committed = self.engine.commit_job(
            user_id="u2", job_id=job["id"], raw_data=SIMPLE_LOGO_XML,
        )
        self.assertEqual(committed["status"], "completed")
        self.assertEqual(committed["summary"]["committed_customers"], 1)
        self.assertEqual(committed["summary"]["committed_invoices"], 1)

    def test_commit_idempotent_second_run_skips(self) -> None:
        """Aynı veri ikinci kez commit edildiğinde signature_hash UNIQUE
        constraint sayesinde sıfır yeni kayıt eklenir."""
        job1 = self.engine.parse_and_preview(
            user_id="u3", connector_type="logo_tiger", mode="xml",
            data=SIMPLE_LOGO_XML,
        )
        self.engine.commit_job(
            user_id="u3", job_id=job1["id"], raw_data=SIMPLE_LOGO_XML,
        )
        # Yeni preview + commit aynı verilerle
        job2 = self.engine.parse_and_preview(
            user_id="u3", connector_type="logo_tiger", mode="xml",
            data=SIMPLE_LOGO_XML,
        )
        committed = self.engine.commit_job(
            user_id="u3", job_id=job2["id"], raw_data=SIMPLE_LOGO_XML,
        )
        # İkinci commit'te yeni kayıt yok
        self.assertEqual(committed["summary"]["committed_customers"], 0)
        self.assertEqual(committed["summary"]["committed_invoices"], 0)

    def test_commit_wrong_user_raises(self) -> None:
        job = self.engine.parse_and_preview(
            user_id="owner", connector_type="logo_tiger", mode="xml",
            data=SIMPLE_LOGO_XML,
        )
        with self.assertRaises(PermissionError):
            self.engine.commit_job(
                user_id="hacker", job_id=job["id"], raw_data=SIMPLE_LOGO_XML,
            )

    def test_commit_non_preview_status_raises(self) -> None:
        job = self.engine.parse_and_preview(
            user_id="u4", connector_type="logo_tiger", mode="xml",
            data=SIMPLE_LOGO_XML,
        )
        self.engine.commit_job(
            user_id="u4", job_id=job["id"], raw_data=SIMPLE_LOGO_XML,
        )
        with self.assertRaises(ValueError):
            self.engine.commit_job(
                user_id="u4", job_id=job["id"], raw_data=SIMPLE_LOGO_XML,
            )

    # ── List / get / cancel ────────────────────────────────────────────

    def test_list_jobs_scoped_to_user(self) -> None:
        self.engine.parse_and_preview(
            user_id="alice", connector_type="logo_tiger", mode="xml",
            data=SIMPLE_LOGO_XML,
        )
        self.engine.parse_and_preview(
            user_id="bob", connector_type="logo_tiger", mode="xml",
            data=SIMPLE_LOGO_XML,
        )
        alice_jobs = self.engine.list_jobs(user_id="alice")
        bob_jobs = self.engine.list_jobs(user_id="bob")
        self.assertEqual(len(alice_jobs), 1)
        self.assertEqual(len(bob_jobs), 1)
        self.assertEqual(alice_jobs[0]["user_id"], "alice")
        self.assertEqual(bob_jobs[0]["user_id"], "bob")

    def test_get_job_other_user_returns_none(self) -> None:
        job = self.engine.parse_and_preview(
            user_id="charlie", connector_type="logo_tiger", mode="xml",
            data=SIMPLE_LOGO_XML,
        )
        leaked = self.engine.get_job(user_id="dave", job_id=job["id"])
        self.assertIsNone(leaked)

    def test_cancel_preview_job(self) -> None:
        job = self.engine.parse_and_preview(
            user_id="u5", connector_type="logo_tiger", mode="xml",
            data=SIMPLE_LOGO_XML,
        )
        ok = self.engine.cancel_job(user_id="u5", job_id=job["id"])
        self.assertTrue(ok)
        cancelled = self.engine.get_job(user_id="u5", job_id=job["id"])
        assert cancelled is not None
        self.assertEqual(cancelled["status"], "cancelled")


if __name__ == "__main__":
    unittest.main()
