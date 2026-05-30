"""A3: Cash flow forecasting için istatistiksel temel.

## Felsefe

Türkiye KOBİ'sinin gerçek acısı: "yarın param yeter mi?". Bu soruyu
cevaplayan bir yazılım üretmek; basit ortalama değil, **trend + mevsim +
seviye** ayrımı yapan rejim-bilinçli forecast lazım.

## Algoritma — Holt-Winters Triple Exponential Smoothing

3 bileşen:
  * **Level (L)**     — anlık seviye (zero-order)
  * **Trend (T)**     — değişim hızı (first-order)
  * **Season (S)**    — periyodik dalgalanma (haftalık/aylık)

Update denklemleri (additive seasonality):
    L_t = α(y_t - S_{t-m}) + (1-α)(L_{t-1} + T_{t-1})
    T_t = β(L_t - L_{t-1})  + (1-β)T_{t-1}
    S_t = γ(y_t - L_t)       + (1-γ)S_{t-m}

Forecast h adım ileri:
    ŷ_{t+h} = L_t + h·T_t + S_{t+h-m}

α, β, γ ∈ [0,1] smoothing parametreleri — adaptive layer (A3.1) zaman
içinde kullanıcı feedback'inden öğrenecek.

## Confidence interval — bootstrap

Residual'ların ampirik dağılımı üzerinden N=1000 örnek alıp her horizon
için percentile-based band çıkarılır. Parametrik bir dağılım varsayımı
yok — finance datasının non-normal yapısına saygılı.

## Accuracy metric — MAPE + RMSE

  * MAPE (Mean Absolute Percentage Error) — kullanıcıya anlamlı
  * RMSE — outlier-sensitive, regression için standart

Hedef: MAPE < %15 → "iyi forecast" (Hyndman literatürü).

## Saf — zero IO

Bu modül yalnız hesap yapar. Repository/engine üzerinden çağrılır.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Sequence


# ── Sabitler ───────────────────────────────────────────────────────────

# Default smoothing parametreleri — Hyndman önerisi
DEFAULT_ALPHA = 0.3   # Level adaptiveness
DEFAULT_BETA = 0.1    # Trend adaptiveness
DEFAULT_GAMMA = 0.1   # Seasonality adaptiveness

# Confidence interval percentile'ları
CI_80_LOW = 10.0
CI_80_HIGH = 90.0
CI_95_LOW = 2.5
CI_95_HIGH = 97.5

# Bootstrap sample size
BOOTSTRAP_N = 1000

# Minimum tarihsel veri — altında forecast yapılmaz
MIN_HISTORY_DAYS = 14

# Hedef accuracy
TARGET_MAPE = 15.0


# ── Tip tanımları ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class HoltWintersComponents:
    """Eğitilmiş Holt-Winters modelinin son durumu."""

    level: float
    trend: float
    seasonal: list[float]    # son m değer (periyot uzunluğu)
    period: int              # mevsim periyodu (örn. 7 → haftalık)
    alpha: float
    beta: float
    gamma: float
    fitted_values: list[float]
    residuals: list[float]


@dataclass(frozen=True)
class ForecastPoint:
    """Tek bir gelecek günün tahmini + güven bantları."""

    day_offset: int           # 1, 2, ..., horizon
    point_estimate: float
    ci80_low: float
    ci80_high: float
    ci95_low: float
    ci95_high: float


@dataclass(frozen=True)
class ForecastResult:
    """Tam forecast çıktısı — engine bu objeyi cache'e yazar."""

    horizon_days: int
    points: list[ForecastPoint]
    model_components: HoltWintersComponents
    mape: float | None        # Validation set varsa
    rmse: float | None
    history_used: int         # Kaç gün tarihsel veri kullanıldı
    is_reliable: bool         # MIN_HISTORY_DAYS ≥ ve MAPE < TARGET_MAPE


# ── Holt-Winters fit ───────────────────────────────────────────────────

def fit_holt_winters(
    values: Sequence[float],
    *,
    period: int = 7,
    alpha: float = DEFAULT_ALPHA,
    beta: float = DEFAULT_BETA,
    gamma: float = DEFAULT_GAMMA,
) -> HoltWintersComponents:
    """Triple exponential smoothing fit.

    Args:
        values: Tarihsel günlük seri (en eski → en yeni).
        period: Mevsimsel periyot (haftalık=7, aylık≈30).
        alpha/beta/gamma: Smoothing parametreleri.

    Returns:
        Eğitilmiş model state'i + fitted + residual değerleri.

    Note: Period * 2 altında veri varsa initial seasonal'ı sıfırlar
    (zayıf forecast üretir; engine is_reliable=False işaretler).
    """
    if not values:
        raise ValueError("Boş veri ile fit yapılamaz")

    n = len(values)
    series = [float(v) for v in values]

    # Initial level: ilk period'un ortalaması
    if n >= period:
        initial_level = sum(series[:period]) / period
    else:
        initial_level = sum(series) / n

    # Initial trend: ilk iki period'un ortalama farkı bölü period
    if n >= 2 * period:
        first_avg = sum(series[:period]) / period
        second_avg = sum(series[period:2 * period]) / period
        initial_trend = (second_avg - first_avg) / period
    else:
        initial_trend = 0.0

    # Initial seasonality: ilk period'un level'a göre sapması
    if n >= period:
        seasonal: list[float] = [
            series[i] - initial_level for i in range(period)
        ]
    else:
        seasonal = [0.0] * period

    level = initial_level
    trend = initial_trend
    fitted: list[float] = []

    for t, y in enumerate(series):
        # Fitted (predicted) — bu nokta için tahmin
        s_idx = t % period
        prev_seasonal = seasonal[s_idx]
        f = level + trend + prev_seasonal
        fitted.append(f)

        # Update
        new_level = alpha * (y - prev_seasonal) + (1 - alpha) * (level + trend)
        new_trend = beta * (new_level - level) + (1 - beta) * trend
        new_seasonal = gamma * (y - new_level) + (1 - gamma) * prev_seasonal
        level = new_level
        trend = new_trend
        seasonal[s_idx] = new_seasonal

    residuals = [y - f for y, f in zip(series, fitted)]

    return HoltWintersComponents(
        level=level,
        trend=trend,
        seasonal=list(seasonal),
        period=period,
        alpha=alpha,
        beta=beta,
        gamma=gamma,
        fitted_values=fitted,
        residuals=residuals,
    )


# ── Forecast + confidence interval ─────────────────────────────────────

def forecast_with_ci(
    model: HoltWintersComponents,
    *,
    horizon: int,
    history_n: int,
    bootstrap_n: int = BOOTSTRAP_N,
    rng: random.Random | None = None,
) -> list[ForecastPoint]:
    """Horizon adım ileri tahmin + bootstrap güven bandları.

    Point estimate Holt-Winters formülünden, CI residual bootstrap'ından.
    Horizon büyüdükçe variance birikir → bandlar açılır.
    """
    if horizon <= 0:
        return []
    rng_ = rng or random.Random(42)  # deterministik default
    residuals = model.residuals or [0.0]

    points: list[ForecastPoint] = []
    for h in range(1, horizon + 1):
        s_idx = (history_n + h - 1) % model.period
        point = model.level + h * model.trend + model.seasonal[s_idx]

        # Bootstrap: h adım birikmiş sample
        samples: list[float] = []
        for _ in range(bootstrap_n):
            cumulative_noise = sum(
                rng_.choice(residuals) for _ in range(h)
            )
            samples.append(point + cumulative_noise)
        samples.sort()

        ci80_low = _percentile(samples, CI_80_LOW)
        ci80_high = _percentile(samples, CI_80_HIGH)
        ci95_low = _percentile(samples, CI_95_LOW)
        ci95_high = _percentile(samples, CI_95_HIGH)

        points.append(ForecastPoint(
            day_offset=h,
            point_estimate=float(point),
            ci80_low=float(ci80_low),
            ci80_high=float(ci80_high),
            ci95_low=float(ci95_low),
            ci95_high=float(ci95_high),
        ))
    return points


def _percentile(sorted_values: Sequence[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    k = (len(sorted_values) - 1) * (pct / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(sorted_values[int(k)])
    d0 = sorted_values[int(f)] * (c - k)
    d1 = sorted_values[int(c)] * (k - f)
    return float(d0 + d1)


# ── Accuracy metrics ───────────────────────────────────────────────────

def compute_mape(actual: Sequence[float], predicted: Sequence[float]) -> float:
    """Mean Absolute Percentage Error — kullanıcı için anlamlı.

    Sıfır actual değerleri için skip — bölüm sıfırı önler.
    """
    if not actual or len(actual) != len(predicted):
        return float("inf")
    errors: list[float] = []
    for a, p in zip(actual, predicted):
        if a == 0:
            continue
        errors.append(abs((a - p) / a) * 100)
    if not errors:
        return float("inf")
    return sum(errors) / len(errors)


def compute_rmse(actual: Sequence[float], predicted: Sequence[float]) -> float:
    """Root Mean Squared Error — outlier-sensitive."""
    if not actual or len(actual) != len(predicted):
        return float("inf")
    sq_errors = [(a - p) ** 2 for a, p in zip(actual, predicted)]
    return math.sqrt(sum(sq_errors) / len(sq_errors))


# ── Backtesting helper ─────────────────────────────────────────────────

@dataclass
class BacktestResult:
    """Train/test split sonucu."""

    mape: float
    rmse: float
    train_size: int
    test_size: int
    predictions: list[float] = field(default_factory=list)
    actuals: list[float] = field(default_factory=list)


def backtest(
    series: Sequence[float],
    *,
    period: int = 7,
    test_size: int = 7,
    alpha: float = DEFAULT_ALPHA,
    beta: float = DEFAULT_BETA,
    gamma: float = DEFAULT_GAMMA,
) -> BacktestResult:
    """Walk-forward backtest — son test_size günü tahmin et, gerçekle karşılaştır.

    Engine accuracy raporlaması bu fonksiyonu kullanır.
    """
    if len(series) < test_size + period:
        return BacktestResult(
            mape=float("inf"), rmse=float("inf"),
            train_size=max(0, len(series) - test_size),
            test_size=test_size,
        )
    train = list(series[:-test_size])
    test = list(series[-test_size:])
    model = fit_holt_winters(
        train, period=period, alpha=alpha, beta=beta, gamma=gamma,
    )
    points = forecast_with_ci(
        model, horizon=test_size, history_n=len(train), bootstrap_n=10,
    )
    predictions = [p.point_estimate for p in points]
    return BacktestResult(
        mape=compute_mape(test, predictions),
        rmse=compute_rmse(test, predictions),
        train_size=len(train),
        test_size=test_size,
        predictions=predictions,
        actuals=test,
    )


# ── Adaptive parameter tuning ──────────────────────────────────────────

def grid_search_parameters(
    series: Sequence[float],
    *,
    period: int = 7,
    test_size: int = 7,
) -> tuple[float, float, float, float]:
    """Coarse grid search — α, β, γ kombinasyonlarından en iyi MAPE.

    11×11×11 ≈ 1331 kombinasyon. Forecast başlangıcında bir kez çalışır,
    bulunan parametreler model state'e yazılır.

    Returns: (best_alpha, best_beta, best_gamma, best_mape)
    """
    grid = [0.05, 0.15, 0.25, 0.35, 0.5, 0.65]
    best: tuple[float, float, float, float] = (
        DEFAULT_ALPHA, DEFAULT_BETA, DEFAULT_GAMMA, float("inf"),
    )
    for a in grid:
        for b in grid:
            for g in grid:
                result = backtest(
                    series, period=period, test_size=test_size,
                    alpha=a, beta=b, gamma=g,
                )
                if result.mape < best[3]:
                    best = (a, b, g, result.mape)
    return best
