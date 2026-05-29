"""SP1: ScenarioPlanningEngine tests."""
from __future__ import annotations

import random
import unittest

from app.engines.scenario_planning_engine import (
    ScenarioAdjustment,
    ScenarioPlanningEngine,
)


class ScenarioPlanningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = ScenarioPlanningEngine()
        # Pozitif net flow baseline (income > expense)
        self.baseline = [1000.0] * 30

    def test_revenue_shock_minus_20_reduces_total(self) -> None:
        result = self.engine.apply_scenario(
            baseline_forecast=self.baseline,
            adjustments=[
                ScenarioAdjustment(type="revenue_shock", pct_change=-20),
            ],
        )
        # -20% revenue × 30 days × 1000 = -6000
        self.assertAlmostEqual(result.delta, -6000.0, places=1)
        self.assertAlmostEqual(result.delta_pct, -20.0, places=1)

    def test_revenue_shock_plus_50_increases_total(self) -> None:
        result = self.engine.apply_scenario(
            baseline_forecast=self.baseline,
            adjustments=[
                ScenarioAdjustment(type="revenue_shock", pct_change=50),
            ],
        )
        self.assertAlmostEqual(result.delta_pct, 50.0, places=1)

    def test_expense_shock_only_affects_negative_points(self) -> None:
        # Negatif net flow baseline (expense > income)
        baseline = [-500.0] * 30
        result = self.engine.apply_scenario(
            baseline_forecast=baseline,
            adjustments=[
                ScenarioAdjustment(type="expense_shock", pct_change=20),
            ],
        )
        # 30 × -500 × 1.2 = -18000 (vs baseline -15000)
        self.assertAlmostEqual(result.cumulative_baseline, -15000)
        self.assertAlmostEqual(result.cumulative_adjusted, -18000)

    def test_fx_shock_uniform_all_points(self) -> None:
        mixed = [1000.0, -500.0, 800.0]
        result = self.engine.apply_scenario(
            baseline_forecast=mixed,
            adjustments=[
                ScenarioAdjustment(type="fx_shock", pct_change=10),
            ],
        )
        # All points multiplied by 1.10
        self.assertAlmostEqual(result.adjusted_points[0], 1100)
        self.assertAlmostEqual(result.adjusted_points[1], -550)
        self.assertAlmostEqual(result.adjusted_points[2], 880)

    def test_delayed_collection_shifts_points(self) -> None:
        baseline = [100, 200, 300, 400, 500]
        result = self.engine.apply_scenario(
            baseline_forecast=baseline,
            adjustments=[
                ScenarioAdjustment(type="delayed_collection", day_offset=2),
            ],
        )
        # First 2 days = 0, then original sequence shifted
        self.assertEqual(result.adjusted_points[0], 0)
        self.assertEqual(result.adjusted_points[1], 0)
        self.assertEqual(result.adjusted_points[2], 100)

    def test_lump_sum_adds_to_specific_day(self) -> None:
        baseline = [100.0] * 10
        result = self.engine.apply_scenario(
            baseline_forecast=baseline,
            adjustments=[
                ScenarioAdjustment(
                    type="lump_sum", day_offset=5, amount=50000,
                ),
            ],
        )
        self.assertEqual(result.adjusted_points[5], 100 + 50000)
        # Other days unchanged
        for i in range(10):
            if i != 5:
                self.assertEqual(result.adjusted_points[i], 100)

    def test_combined_adjustments_compose(self) -> None:
        baseline = [1000.0] * 10
        result = self.engine.apply_scenario(
            baseline_forecast=baseline,
            adjustments=[
                ScenarioAdjustment(type="revenue_shock", pct_change=-10),
                ScenarioAdjustment(
                    type="lump_sum", day_offset=5, amount=5000,
                ),
            ],
        )
        # -10% on pozitif points × 10 days = -1000
        # +5000 lump sum
        # baseline_sum = 10000, adjusted ≈ 9000 + 5000 = 14000
        self.assertAlmostEqual(result.cumulative_adjusted, 14000, places=0)

    def test_empty_baseline_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.engine.apply_scenario(
                baseline_forecast=[],
                adjustments=[
                    ScenarioAdjustment(type="revenue_shock", pct_change=10),
                ],
            )

    def test_invalid_adjustment_type_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.engine.apply_scenario(
                baseline_forecast=[100],
                adjustments=[
                    ScenarioAdjustment(type="garbage", pct_change=10),
                ],
            )

    def test_p10_p90_bands_have_expected_ordering(self) -> None:
        baseline = [1000.0] * 30
        result = self.engine.apply_scenario(
            baseline_forecast=baseline,
            adjustments=[
                ScenarioAdjustment(type="revenue_shock", pct_change=0),
            ],
            residuals=[100.0, -100.0, 50.0, -50.0, 0.0],
            rng=random.Random(42),
        )
        for h in range(30):
            self.assertLessEqual(result.p10_points[h], result.adjusted_points[h])
            self.assertGreaterEqual(result.p90_points[h], result.adjusted_points[h])


if __name__ == "__main__":
    unittest.main()
