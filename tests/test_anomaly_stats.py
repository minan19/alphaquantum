"""A2: anomaly_stats tests — istatistiksel doğruluk garantisi.

Confidence tier eşiklerinin gerçekten matematiksel doğru noktalara
düştüğünü doğrular. %99 doğruluk iddiamızın kökü buradan beslenir.
"""
from __future__ import annotations

import unittest

from app.anomaly_stats import (
    CRITICAL_Z_THRESHOLD,
    HIGH_Z_THRESHOLD,
    MEDIUM_Z_THRESHOLD,
    MIN_BASELINE_N,
    compute_baseline,
    confidence_from_z,
    is_actionable,
    modified_z_score,
    score_observation,
    severity_from_z,
)


class BaselineTests(unittest.TestCase):
    def test_empty_input_yields_zero_baseline(self) -> None:
        b = compute_baseline([])
        self.assertEqual(b.median, 0.0)
        self.assertEqual(b.mad, 0.0)
        self.assertFalse(b.is_reliable)
        self.assertEqual(b.count, 0)

    def test_small_sample_marked_unreliable(self) -> None:
        b = compute_baseline([10, 20, 30])  # 3 < MIN_BASELINE_N
        self.assertFalse(b.is_reliable)
        self.assertEqual(b.count, 3)

    def test_min_reliable_sample(self) -> None:
        b = compute_baseline([10, 20, 30, 40])
        self.assertTrue(b.is_reliable)
        self.assertEqual(b.count, MIN_BASELINE_N)

    def test_median_robust_to_outlier(self) -> None:
        """Robustness: bir 1000'lik outlier baseline'ı zehirlememeli."""
        b = compute_baseline([10, 11, 10, 12, 11, 1000])
        # Median ~10.5 — outlier'a rağmen
        self.assertLess(b.median, 50)
        # Sample max'ı yine de yakalıyor
        self.assertEqual(b.sample_max, 1000)

    def test_all_equal_values_mad_zero_fallback(self) -> None:
        """Tüm değerler eşit → MAD=0 ama mad_scaled de 0 olur."""
        b = compute_baseline([100, 100, 100, 100])
        self.assertEqual(b.mad, 0.0)
        self.assertEqual(b.mad_scaled, 0.0)


class ModifiedZTests(unittest.TestCase):
    def test_value_at_median_z_zero(self) -> None:
        b = compute_baseline([10, 20, 30, 40, 50])
        z = modified_z_score(b.median, b)
        self.assertAlmostEqual(z, 0.0)

    def test_extreme_outlier_high_z(self) -> None:
        # Stable baseline + 10× büyük gözlem
        b = compute_baseline([100, 102, 99, 101, 98, 100])
        z = modified_z_score(1000, b)
        self.assertGreater(abs(z), CRITICAL_Z_THRESHOLD)

    def test_mad_zero_with_extreme_outlier_returns_large_z(self) -> None:
        """MAD=0 fallback: aynı değerden çok farklı bir gözlem extreme z."""
        b = compute_baseline([100, 100, 100, 100])
        z = modified_z_score(500, b)
        self.assertGreaterEqual(abs(z), 6.0)


class ConfidenceTests(unittest.TestCase):
    def test_zero_z_zero_confidence(self) -> None:
        self.assertEqual(confidence_from_z(0), 0.0)

    def test_high_z_above_99(self) -> None:
        # Modified Z 3.5 → ≈99.95%
        self.assertGreater(confidence_from_z(3.5), 99.0)

    def test_critical_z_above_99_9(self) -> None:
        self.assertGreater(confidence_from_z(6), 99.99)

    def test_medium_z_above_90(self) -> None:
        # Modified Z 1.8 → ≈92%
        self.assertGreater(confidence_from_z(1.8), 90.0)

    def test_confidence_capped_at_999999(self) -> None:
        self.assertLessEqual(confidence_from_z(100), 99.9999)


class SeverityTests(unittest.TestCase):
    def test_critical_threshold(self) -> None:
        self.assertEqual(
            severity_from_z(CRITICAL_Z_THRESHOLD + 0.5, baseline_reliable=True),
            "critical",
        )

    def test_high_threshold(self) -> None:
        self.assertEqual(
            severity_from_z(HIGH_Z_THRESHOLD + 0.1, baseline_reliable=True),
            "high",
        )

    def test_medium_threshold(self) -> None:
        self.assertEqual(
            severity_from_z(MEDIUM_Z_THRESHOLD + 0.05, baseline_reliable=True),
            "medium",
        )

    def test_unreliable_baseline_demotes_tier(self) -> None:
        """Baseline güvenilmez → bir tier aşağı."""
        self.assertEqual(
            severity_from_z(CRITICAL_Z_THRESHOLD + 1.0, baseline_reliable=False),
            "high",
        )

    def test_below_threshold_low(self) -> None:
        self.assertEqual(severity_from_z(0.5, baseline_reliable=True), "low")


class ScoreObservationTests(unittest.TestCase):
    def test_full_score_critical_outlier(self) -> None:
        # Baseline ~100, ±2 noise → 10000 gözlemi extreme outlier
        b = compute_baseline([100, 102, 98, 101, 99, 100, 100, 102])
        s = score_observation(10000, b)
        self.assertEqual(s.severity, "critical")
        self.assertGreater(s.confidence_pct, 99.0)
        self.assertTrue(s.is_outlier_above)
        self.assertGreater(s.deviation_pct, 9000)  # ≈9900%

    def test_full_score_normal_observation(self) -> None:
        b = compute_baseline([100, 102, 98, 101, 99, 100])
        s = score_observation(100, b)
        self.assertEqual(s.severity, "low")
        self.assertLess(s.confidence_pct, 50)


class ActionableTests(unittest.TestCase):
    def test_critical_actionable(self) -> None:
        b = compute_baseline([100, 100, 100, 100, 100, 100])
        s = score_observation(5000, b)
        self.assertTrue(is_actionable(s, min_severity="high"))

    def test_medium_not_actionable_at_high_min(self) -> None:
        # Hafifçe yüksek
        b = compute_baseline([100, 105, 95, 100, 102, 98, 100])
        s = score_observation(115, b)
        # Severity'si medium ya da low olur — min "high" altında
        self.assertEqual(is_actionable(s, min_severity="high"), s.severity == "critical")

    def test_low_observation_filtered_out(self) -> None:
        b = compute_baseline([100, 105, 95, 100])
        s = score_observation(101, b)
        self.assertFalse(is_actionable(s, min_severity="medium"))


if __name__ == "__main__":
    unittest.main()
