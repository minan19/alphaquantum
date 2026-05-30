"""A3: forecasting_stats — Holt-Winters matematik doğruluk testleri.

Sentetik seriler üzerinde:
  * Trend doğru yakalanıyor mu
  * Seasonality doğru yakalanıyor mu
  * Forecast hata payı kabul edilebilir mi (MAPE < %15 = iyi)
  * Confidence interval coverage mantıklı mı (CI95 ⊃ CI80 ⊃ point)
"""
from __future__ import annotations

import math
import random
import unittest

from app.forecasting_stats import (
    DEFAULT_ALPHA,
    DEFAULT_BETA,
    DEFAULT_GAMMA,
    backtest,
    compute_mape,
    compute_rmse,
    fit_holt_winters,
    forecast_with_ci,
    grid_search_parameters,
)


def _seasonal_series(n: int = 90, level: float = 1000, trend: float = 5,
                     amplitude: float = 200, period: int = 7,
                     noise: float = 0.0) -> list[float]:
    """Deterministik trend + seasonal seri."""
    rng = random.Random(42)
    return [
        level + trend * i + amplitude * math.sin(2 * math.pi * i / period)
        + (rng.gauss(0, noise) if noise > 0 else 0)
        for i in range(n)
    ]


class FitTests(unittest.TestCase):
    def test_fit_clean_series_low_residual(self) -> None:
        series = _seasonal_series(n=60, noise=0)
        model = fit_holt_winters(series, period=7)
        # Warmup'tan sonra residual'lar düşük olmalı
        late_residuals = model.residuals[14:]
        mean_abs_residual = sum(abs(r) for r in late_residuals) / len(late_residuals)
        # Level ~1000+trend → mean ~1100. Residual << level olmalı.
        self.assertLess(mean_abs_residual, 50)

    def test_fit_captures_trend(self) -> None:
        series = [1000 + 10 * i for i in range(30)]  # pure trend
        model = fit_holt_winters(series, period=7)
        # Trend ~10/gün
        self.assertGreater(model.trend, 5)
        self.assertLess(model.trend, 15)

    def test_fit_captures_seasonality(self) -> None:
        # Sade haftalık pattern, no trend, no level change
        series = [1000 + 100 * math.sin(2 * math.pi * i / 7) for i in range(28)]
        model = fit_holt_winters(series, period=7)
        # Seasonal vektörü ~ amplitude scale'inde olmalı (mutlak)
        max_seasonal = max(abs(s) for s in model.seasonal)
        self.assertGreater(max_seasonal, 50)

    def test_fit_empty_raises(self) -> None:
        with self.assertRaises(ValueError):
            fit_holt_winters([])


class ForecastTests(unittest.TestCase):
    def test_forecast_horizon_length(self) -> None:
        series = _seasonal_series(n=60, noise=5)
        model = fit_holt_winters(series, period=7)
        points = forecast_with_ci(model, horizon=14, history_n=60, bootstrap_n=50)
        self.assertEqual(len(points), 14)

    def test_ci_bands_strictly_ordered(self) -> None:
        """CI95 ⊃ CI80 ⊃ point (yaklaşık)."""
        series = _seasonal_series(n=60, noise=20)
        model = fit_holt_winters(series, period=7)
        points = forecast_with_ci(model, horizon=10, history_n=60, bootstrap_n=200)
        for p in points:
            self.assertLessEqual(p.ci95_low, p.ci80_low)
            self.assertLessEqual(p.ci80_low, p.point_estimate)
            self.assertLessEqual(p.point_estimate, p.ci80_high)
            self.assertLessEqual(p.ci80_high, p.ci95_high)

    def test_forecast_close_to_known_pattern(self) -> None:
        """Temiz veri üzerinde forecast %10'dan iyi olmalı."""
        series = _seasonal_series(n=90, trend=5, amplitude=100, noise=0)
        # Son 14 gün test, geri kalan train
        train, test = series[:-14], series[-14:]
        model = fit_holt_winters(train, period=7)
        points = forecast_with_ci(
            model, horizon=14, history_n=len(train), bootstrap_n=10,
        )
        predictions = [p.point_estimate for p in points]
        mape = compute_mape(test, predictions)
        self.assertLess(mape, 10.0)


class AccuracyMetricTests(unittest.TestCase):
    def test_mape_zero_for_perfect_prediction(self) -> None:
        self.assertEqual(compute_mape([100, 200, 300], [100, 200, 300]), 0)

    def test_mape_skips_zero_actuals(self) -> None:
        mape = compute_mape([0, 100], [50, 110])
        self.assertAlmostEqual(mape, 10.0)

    def test_rmse_zero_for_perfect_prediction(self) -> None:
        self.assertEqual(compute_rmse([100, 200], [100, 200]), 0)

    def test_mape_infinity_for_empty(self) -> None:
        self.assertEqual(compute_mape([], []), float("inf"))


class BacktestTests(unittest.TestCase):
    def test_backtest_clean_series_low_mape(self) -> None:
        series = _seasonal_series(n=90, noise=0)
        result = backtest(series, period=7, test_size=14)
        self.assertLess(result.mape, 15.0)

    def test_backtest_insufficient_data_infinity(self) -> None:
        result = backtest([100, 200], period=7, test_size=14)
        self.assertEqual(result.mape, float("inf"))

    def test_backtest_returns_predictions(self) -> None:
        series = _seasonal_series(n=60, noise=10)
        result = backtest(series, period=7, test_size=7)
        self.assertEqual(len(result.predictions), 7)
        self.assertEqual(len(result.actuals), 7)


class GridSearchTests(unittest.TestCase):
    def test_grid_search_returns_valid_params(self) -> None:
        series = _seasonal_series(n=90, noise=20)
        a, b, g, mape = grid_search_parameters(series, period=7, test_size=14)
        self.assertGreaterEqual(a, 0)
        self.assertLessEqual(a, 1)
        self.assertGreaterEqual(b, 0)
        self.assertLessEqual(b, 1)
        self.assertGreaterEqual(g, 0)
        self.assertLessEqual(g, 1)

    def test_grid_search_improves_over_default(self) -> None:
        """Grid search default'tan daha iyi olmalı (veya eşit)."""
        series = _seasonal_series(n=90, trend=20, amplitude=300, noise=15)
        default_bt = backtest(
            series, period=7, test_size=14,
            alpha=DEFAULT_ALPHA, beta=DEFAULT_BETA, gamma=DEFAULT_GAMMA,
        )
        _, _, _, grid_mape = grid_search_parameters(
            series, period=7, test_size=14,
        )
        self.assertLessEqual(grid_mape, default_bt.mape + 0.01)


if __name__ == "__main__":
    unittest.main()
