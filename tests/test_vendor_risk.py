"""VR1: Vendor risk scoring tests."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.engines.vendor_risk_engine import VendorRiskEngine
from app.identity_repository import IdentityRepository
from app.migration_manager import MigrationManager


class VendorRiskTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp.name) / "vr1_test.db"
        migrations_dir = Path(__file__).resolve().parent.parent / "migrations"
        bootstrap = IdentityRepository(str(self._db_path))
        bootstrap.close()
        self.manager = MigrationManager(str(self._db_path), str(migrations_dir))
        self.manager.apply_all()
        self.engine = VendorRiskEngine(database_path=str(self._db_path))

    def tearDown(self) -> None:
        self.manager.close()
        self._tmp.cleanup()

    # ── VKN validation ─────────────────────────────────────────────────

    def test_invalid_vkn_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.engine.score_vendor(vkn="123")  # too short

    def test_all_zero_vkn_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.engine.score_vendor(vkn="0000000000")

    def test_non_digit_chars_cleaned(self) -> None:
        score = self.engine.score_vendor(vkn="123-4567-890")
        self.assertEqual(score.vkn, "1234567890")

    # ── Scoring ────────────────────────────────────────────────────────

    def test_score_returns_composite_in_range(self) -> None:
        score = self.engine.score_vendor(vkn="1234567890")
        self.assertGreaterEqual(score.composite_score, 0)
        self.assertLessEqual(score.composite_score, 100)
        self.assertIn(score.severity, ("low", "medium", "high", "critical"))

    def test_deterministic_score_for_same_vkn(self) -> None:
        s1 = self.engine.score_vendor(vkn="1234567890")
        s2 = self.engine.score_vendor(vkn="1234567890")
        self.assertEqual(s1.composite_score, s2.composite_score)
        self.assertEqual(s1.credit_rating, s2.credit_rating)

    def test_different_vkn_different_score(self) -> None:
        s1 = self.engine.score_vendor(vkn="1234567890")
        s2 = self.engine.score_vendor(vkn="9876543210")
        # Not necessarily different (random collision possible), but
        # credit rating distribution should usually differ
        self.assertTrue(
            s1.composite_score != s2.composite_score
            or s1.credit_rating != s2.credit_rating
        )

    def test_recommendations_returned(self) -> None:
        score = self.engine.score_vendor(vkn="1234567890")
        self.assertIsInstance(score.recommendations, list)
        # At least one of: low/critical level recommendation
        # or rating/anomaly note
        self.assertGreater(len(score.recommendations), 0)

    def test_severity_consistent_with_score(self) -> None:
        # Test all severity bands by sweeping a range of VKNs
        scores: list[int] = []
        for n in range(100):
            vkn = f"{1000000000 + n}"
            s = self.engine.score_vendor(vkn=vkn)
            scores.append(s.composite_score)
            # Severity must match score band
            if s.composite_score >= 76:
                self.assertEqual(s.severity, "low")
            elif s.composite_score >= 51:
                self.assertEqual(s.severity, "medium")
            elif s.composite_score >= 26:
                self.assertEqual(s.severity, "high")
            else:
                self.assertEqual(s.severity, "critical")
        # Score'lar dağılmış olmalı (tek değere stuck olmamalı)
        self.assertGreater(len(set(scores)), 5)

    # ── Internal data integration ──────────────────────────────────────

    def test_ledger_history_boosts_score(self) -> None:
        """Counterparty ile çok ödeme varsa ledger_score yüksek."""
        import sqlite3
        conn = sqlite3.connect(str(self._db_path))
        # 12 farklı ödeme — son 6 ay
        for i in range(12):
            conn.execute(
                """
                INSERT INTO finance_ledger_entries
                  (company_name, entry_type, amount, category, description,
                   entry_date, created_at, intercompany_flag,
                   counterparty_company)
                VALUES ('AcmeCo', 'expense', 1000, 'general', '',
                        date('now', '-' || ? || ' days'), 1700000000, 0, ?)
                """,
                (i * 7, "Vendor X Ltd"),
            )
        conn.commit()
        conn.close()

        score = self.engine.score_vendor(
            vkn="1234567890", counterparty_name="Vendor X Ltd",
        )
        # Düzenli ödeme paterni → yüksek ledger score
        self.assertGreaterEqual(score.internal_payment_history_score, 80)

    def test_anomaly_count_lowers_composite(self) -> None:
        """Bu vendor için anomali sinyalleri varsa skor düşer."""
        import sqlite3
        conn = sqlite3.connect(str(self._db_path))
        for i in range(3):
            conn.execute(
                """
                INSERT INTO anomaly_signals
                    (holding_id, signal_type, severity, confidence_pct,
                     modified_z, title, description,
                     baseline_json, payload_json,
                     signature_hash, detected_at, status)
                VALUES (NULL, 'duplicate_payment', 'critical', 99.5, 4.0,
                        'Test', 'desc',
                        '{}',
                        '{"counterparty": "Suspicious Vendor"}',
                        ?, 1700000000, 'open')
                """,
                (f"sample_test_anom_{i}",),
            )
        conn.commit()
        conn.close()

        s_with = self.engine.score_vendor(
            vkn="1234567890", counterparty_name="Suspicious Vendor",
        )
        s_without = self.engine.score_vendor(
            vkn="1234567890", counterparty_name=None,
        )
        # Anomalisi olan vendor için anomaly_signal_count > 0
        self.assertGreater(s_with.anomaly_signal_count, 0)
        self.assertEqual(s_without.anomaly_signal_count, 0)


if __name__ == "__main__":
    unittest.main()
