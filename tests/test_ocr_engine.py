"""A4: OCR Engine tests."""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.engines.ocr_engine import OcrEngine
from app.identity_repository import IdentityRepository
from app.migration_manager import MigrationManager
from app.ocr_service import OfflineOcrService


# 1x1 px JPG (smallest valid)
TINY_JPG = bytes.fromhex(
    "ffd8ffe000104a46494600010100000100010000ffdb004300080606070605080707"
    "07090908"
) + b"\x00" * 100 + bytes.fromhex("ffd9")


class OcrEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp.name) / "ocr_test.db"
        migrations_dir = Path(__file__).resolve().parent.parent / "migrations"

        bootstrap = IdentityRepository(str(self._db_path))
        bootstrap.close()
        self.manager = MigrationManager(str(self._db_path), str(migrations_dir))
        self.manager.apply_all()

        self.engine = OcrEngine(
            database_path=str(self._db_path),
            ocr_service=OfflineOcrService(),
        )

    def tearDown(self) -> None:
        self.manager.close()
        self._tmp.cleanup()

    def _count(self, table: str, where: str = "") -> int:
        conn = sqlite3.connect(str(self._db_path))
        try:
            sql = f"SELECT COUNT(*) FROM {table}"
            if where:
                sql += f" WHERE {where}"
            return int(conn.execute(sql).fetchone()[0])
        finally:
            conn.close()

    # ── Process (upload + extract) ─────────────────────────────────────

    def test_process_creates_extracted_job(self) -> None:
        view = self.engine.process(
            user_id="ahmet",
            image_bytes=TINY_JPG,
            mime_type="image/jpeg",
            filename="fis.jpg",
        )
        self.assertEqual(view.status, "extracted")
        self.assertGreater(view.confidence_pct, 0)
        self.assertEqual(view.user_id, "ahmet")
        self.assertGreater(view.extract.get("total_amount", 0), 0)

    def test_process_empty_image_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.engine.process(
                user_id="x", image_bytes=b"", mime_type="image/jpeg",
            )

    def test_process_invalid_mime_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.engine.process(
                user_id="x", image_bytes=TINY_JPG, mime_type="application/pdf",
            )

    def test_process_oversize_raises(self) -> None:
        big = b"\x00" * (11 * 1024 * 1024)
        with self.assertRaises(ValueError):
            self.engine.process(
                user_id="x", image_bytes=big, mime_type="image/jpeg",
            )

    def test_process_deterministic_offline(self) -> None:
        """Same bytes → same extract (OfflineOcr is deterministic)."""
        view1 = self.engine.process(
            user_id="u1", image_bytes=TINY_JPG, mime_type="image/jpeg",
        )
        view2 = self.engine.process(
            user_id="u2", image_bytes=TINY_JPG, mime_type="image/jpeg",
        )
        self.assertEqual(
            view1.extract["total_amount"], view2.extract["total_amount"]
        )

    # ── Confirm (create ledger entry) ──────────────────────────────────

    def test_confirm_creates_ledger_entry(self) -> None:
        view = self.engine.process(
            user_id="ahmet", image_bytes=TINY_JPG, mime_type="image/jpeg",
        )
        before = self._count("finance_ledger_entries")
        confirmed = self.engine.confirm(
            user_id="ahmet", job_id=view.id, company_name="AcmeCo",
        )
        self.assertEqual(confirmed.status, "confirmed")
        self.assertIsNotNone(confirmed.ledger_entry_id)
        self.assertEqual(self._count("finance_ledger_entries"), before + 1)

    def test_confirm_overrides_take_effect(self) -> None:
        view = self.engine.process(
            user_id="ahmet", image_bytes=TINY_JPG, mime_type="image/jpeg",
        )
        original_amount = float(view.extract["total_amount"])
        confirmed = self.engine.confirm(
            user_id="ahmet", job_id=view.id, company_name="AcmeCo",
            overrides={"total_amount": 99999.99},
        )
        # Ledger entry should reflect the override
        conn = sqlite3.connect(str(self._db_path))
        try:
            row = conn.execute(
                "SELECT amount FROM finance_ledger_entries WHERE id = ?",
                (confirmed.ledger_entry_id,),
            ).fetchone()
        finally:
            conn.close()
        self.assertAlmostEqual(row[0], 99999.99)
        # Original extract preserved
        self.assertAlmostEqual(view.extract["total_amount"], original_amount)

    def test_confirm_wrong_user_raises_permission(self) -> None:
        view = self.engine.process(
            user_id="owner", image_bytes=TINY_JPG, mime_type="image/jpeg",
        )
        with self.assertRaises(PermissionError):
            self.engine.confirm(
                user_id="hacker", job_id=view.id, company_name="X",
            )

    def test_confirm_non_extracted_raises(self) -> None:
        view = self.engine.process(
            user_id="u", image_bytes=TINY_JPG, mime_type="image/jpeg",
        )
        self.engine.confirm(
            user_id="u", job_id=view.id, company_name="X",
        )
        # Second confirm fails (status is now 'confirmed')
        with self.assertRaises(ValueError):
            self.engine.confirm(
                user_id="u", job_id=view.id, company_name="X",
            )

    def test_confirm_outgoing_creates_income_entry(self) -> None:
        view = self.engine.process(
            user_id="u", image_bytes=TINY_JPG, mime_type="image/jpeg",
        )
        confirmed = self.engine.confirm(
            user_id="u", job_id=view.id, company_name="X",
            overrides={"direction": "outgoing"},
        )
        conn = sqlite3.connect(str(self._db_path))
        try:
            row = conn.execute(
                "SELECT entry_type FROM finance_ledger_entries WHERE id = ?",
                (confirmed.ledger_entry_id,),
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual(row[0], "income")

    # ── List / get ─────────────────────────────────────────────────────

    def test_list_jobs_user_scoped(self) -> None:
        self.engine.process(
            user_id="alice", image_bytes=TINY_JPG, mime_type="image/jpeg",
        )
        self.engine.process(
            user_id="bob", image_bytes=TINY_JPG, mime_type="image/jpeg",
        )
        alice_jobs = self.engine.list_jobs(user_id="alice")
        bob_jobs = self.engine.list_jobs(user_id="bob")
        self.assertEqual(len(alice_jobs), 1)
        self.assertEqual(len(bob_jobs), 1)

    def test_get_job_other_user_returns_none(self) -> None:
        view = self.engine.process(
            user_id="charlie", image_bytes=TINY_JPG, mime_type="image/jpeg",
        )
        leaked = self.engine.get_job(user_id="dave", job_id=view.id)
        self.assertIsNone(leaked)


class OfflineOcrServiceTests(unittest.TestCase):
    def test_offline_service_returns_deterministic_results(self) -> None:
        svc = OfflineOcrService()
        r1 = svc.extract_invoice(image_bytes=TINY_JPG)
        r2 = svc.extract_invoice(image_bytes=TINY_JPG)
        self.assertEqual(r1.total_amount, r2.total_amount)
        self.assertEqual(r1.category, r2.category)
        self.assertEqual(r1.vendor_name, r2.vendor_name)

    def test_offline_service_different_images_different_results(self) -> None:
        svc = OfflineOcrService()
        r1 = svc.extract_invoice(image_bytes=TINY_JPG)
        r2 = svc.extract_invoice(image_bytes=TINY_JPG + b"x")
        # Different bytes → different deterministic output
        self.assertNotEqual(r1.total_amount, r2.total_amount)


if __name__ == "__main__":
    unittest.main()
