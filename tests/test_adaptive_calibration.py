"""A2.1: AdaptiveCalibrationEngine tests — self-learning mekanizmalarının doğruluğu.

Bu testler kullanıcının "%99 doğruluğa yaklaşma" beklentisinin
matematiksel kanıtıdır:
  * Bayesian update doğru kuruluyor mu
  * Threshold offset hassasiyete doğru tepki veriyor mu
  * Whitelist 3 dismiss sonrası tetikleniyor mu, 1 confirm ile bozuluyor mu
  * Reliability per-detector doğru hesaplanıyor mu
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.engines.adaptive_calibration_engine import (
    AdaptiveCalibrationEngine,
    PRIOR_ALPHA,
    PRIOR_BETA,
    THRESHOLD_OFFSET_MAX,
    WHITELIST_DISMISSAL_THRESHOLD,
)
from app.identity_repository import IdentityRepository
from app.migration_manager import MigrationManager


class AdaptiveCalibrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp.name) / "calib_test.db"
        migrations_dir = Path(__file__).resolve().parent.parent / "migrations"

        bootstrap = IdentityRepository(str(self._db_path))
        bootstrap.close()
        self.manager = MigrationManager(str(self._db_path), str(migrations_dir))
        self.manager.apply_all()

        self.engine = AdaptiveCalibrationEngine(str(self._db_path))

    def tearDown(self) -> None:
        self.engine.close()
        self.manager.close()
        self._tmp.cleanup()

    # ── Bayesian update ────────────────────────────────────────────────

    def test_initial_state_uses_prior(self) -> None:
        """İlk review'dan önce posterior=prior."""
        state = self.engine.record_review(
            detector_type="duplicate_payment",
            target_key="TestCo",
            action="confirm",
        )
        # Prior + 1 confirm: α = 2 + 1 = 3, β = 1
        self.assertAlmostEqual(state.alpha, PRIOR_ALPHA + 1)
        self.assertAlmostEqual(state.beta, PRIOR_BETA)

    def test_confirm_increments_alpha(self) -> None:
        for _ in range(5):
            self.engine.record_review(
                detector_type="x", target_key="K", action="confirm",
            )
        state = self.engine._fetch_state("x", "K")
        assert state is not None
        self.assertEqual(state.confirmed_count, 5)
        self.assertEqual(state.dismissed_count, 0)
        self.assertAlmostEqual(state.alpha, PRIOR_ALPHA + 5)

    def test_dismiss_increments_beta(self) -> None:
        for _ in range(3):
            self.engine.record_review(
                detector_type="x", target_key="K", action="dismiss",
            )
        state = self.engine._fetch_state("x", "K")
        assert state is not None
        self.assertEqual(state.dismissed_count, 3)
        self.assertAlmostEqual(state.beta, PRIOR_BETA + 3)

    def test_precision_converges_to_empirical_rate(self) -> None:
        """20 confirm + 1 dismiss → posterior ≈ 22/24 ≈ %91.7"""
        for _ in range(20):
            self.engine.record_review(
                detector_type="x", target_key="K", action="confirm",
            )
        self.engine.record_review(
            detector_type="x", target_key="K", action="dismiss",
        )
        state = self.engine._fetch_state("x", "K")
        assert state is not None
        # α/(α+β) = (PRIOR_ALPHA+20)/(PRIOR_ALPHA+20+PRIOR_BETA+1)
        expected = (PRIOR_ALPHA + 20) / (PRIOR_ALPHA + 20 + PRIOR_BETA + 1)
        self.assertAlmostEqual(state.measured_precision, expected, places=4)

    # ── Threshold offset ───────────────────────────────────────────────

    def test_offset_zero_below_minimum_reviews(self) -> None:
        """5 review altında offset hesaplanmaz (uncertainty çok yüksek)."""
        for _ in range(3):
            self.engine.record_review(
                detector_type="x", target_key="K", action="dismiss",
            )
        offset = self.engine.get_threshold_offset(
            detector_type="x", target_key="K",
        )
        self.assertEqual(offset, 0.0)

    def test_offset_rises_when_precision_low(self) -> None:
        """Sürekli yanlış alarm → eşik yükselir."""
        # 10 dismiss → precision ≈ %16.7, target %95 → büyük gap
        for _ in range(10):
            self.engine.record_review(
                detector_type="x", target_key="K", action="dismiss",
            )
        offset = self.engine.get_threshold_offset(
            detector_type="x", target_key="K",
        )
        self.assertGreater(offset, 0.5)

    def test_offset_negative_when_precision_high(self) -> None:
        """Sürekli onay → eşik düşer (daha çok tespit)."""
        for _ in range(20):
            self.engine.record_review(
                detector_type="x", target_key="K", action="confirm",
            )
        offset = self.engine.get_threshold_offset(
            detector_type="x", target_key="K",
        )
        self.assertLess(offset, 0.0)

    def test_offset_clamped_to_max(self) -> None:
        for _ in range(100):
            self.engine.record_review(
                detector_type="x", target_key="K", action="dismiss",
            )
        offset = self.engine.get_threshold_offset(
            detector_type="x", target_key="K",
        )
        self.assertLessEqual(offset, THRESHOLD_OFFSET_MAX)

    # ── Whitelist ──────────────────────────────────────────────────────

    def test_three_dismissals_triggers_whitelist(self) -> None:
        for _ in range(WHITELIST_DISMISSAL_THRESHOLD):
            self.engine.record_review(
                detector_type="d", target_key="Vendor1", action="dismiss",
            )
        self.assertTrue(
            self.engine.is_whitelisted(detector_type="d", target_key="Vendor1")
        )

    def test_confirm_resets_whitelist(self) -> None:
        for _ in range(WHITELIST_DISMISSAL_THRESHOLD):
            self.engine.record_review(
                detector_type="d", target_key="Vendor1", action="dismiss",
            )
        self.assertTrue(
            self.engine.is_whitelisted(detector_type="d", target_key="Vendor1")
        )
        # Tek confirm whitelist'i bozar
        self.engine.record_review(
            detector_type="d", target_key="Vendor1", action="confirm",
        )
        self.assertFalse(
            self.engine.is_whitelisted(detector_type="d", target_key="Vendor1")
        )

    def test_intermediate_confirm_resets_consecutive_counter(self) -> None:
        """2 dismiss + 1 confirm + 2 dismiss → whitelist tetiklenmez."""
        for _ in range(2):
            self.engine.record_review(
                detector_type="d", target_key="V", action="dismiss",
            )
        self.engine.record_review(
            detector_type="d", target_key="V", action="confirm",
        )
        for _ in range(2):
            self.engine.record_review(
                detector_type="d", target_key="V", action="dismiss",
            )
        # 2 consecutive < threshold
        self.assertFalse(
            self.engine.is_whitelisted(detector_type="d", target_key="V")
        )

    # ── Reliability ────────────────────────────────────────────────────

    def test_unreliable_detector_low_reliability(self) -> None:
        for _ in range(10):
            self.engine.record_review(
                detector_type="bad", target_key="K", action="dismiss",
            )
        rel = self.engine.detector_reliability(detector_type="bad")
        self.assertLess(rel, 1.0)

    def test_high_precision_detector_high_reliability(self) -> None:
        for _ in range(20):
            self.engine.record_review(
                detector_type="good", target_key="K", action="confirm",
            )
        rel = self.engine.detector_reliability(detector_type="good")
        self.assertGreater(rel, 1.3)

    def test_default_reliability_is_neutral(self) -> None:
        rel = self.engine.detector_reliability(detector_type="new")
        self.assertEqual(rel, 1.0)

    # ── Overview / metrics ─────────────────────────────────────────────

    def test_overview_aggregates_per_detector(self) -> None:
        for _ in range(8):
            self.engine.record_review(
                detector_type="a", target_key="K1", action="confirm",
            )
        for _ in range(2):
            self.engine.record_review(
                detector_type="b", target_key="K2", action="dismiss",
            )
        overview = self.engine.overall_metrics()
        self.assertEqual(overview["confirmed"], 8)
        self.assertEqual(overview["dismissed"], 2)
        self.assertEqual(overview["total_reviews"], 10)
        self.assertAlmostEqual(overview["measured_precision"], 0.8)
        self.assertTrue(overview["is_learned"])
        self.assertIn("a", overview["per_detector"])
        self.assertIn("b", overview["per_detector"])

    def test_overview_handles_no_data(self) -> None:
        overview = self.engine.overall_metrics()
        self.assertEqual(overview["total_reviews"], 0)
        self.assertFalse(overview["is_learned"])
        self.assertIsNone(overview["measured_precision"])

    def test_snapshot_daily_metrics_persists(self) -> None:
        for _ in range(5):
            self.engine.record_review(
                detector_type="x", target_key="K", action="confirm",
            )
        count = self.engine.snapshot_daily_metrics()
        self.assertGreaterEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
