"""SP1: Scenario Planning Engine — A3 forecast üzerine "what-if" sensitivity.

## Felsefe — Causal/Pigment paradigm

A3 baseline forecast üretir. SP1: kullanıcı "ya gelir %20 düşerse?"
"ya USD %15 yükselirse?" gibi senaryolar tanımlar, her senaryonun
ileriye dönük etkisi hesaplanır.

## Senaryo türleri

  * revenue_shock     — Gelirler ±X% değişirse (uniform tüm horizon)
  * expense_shock     — Giderler ±X% değişirse
  * fx_shock          — USD/EUR ±X% kayma (FX-sensitive ledger hareketleri)
  * delayed_collection — Tahsilat süresi +X gün uzarsa
  * lump_sum          — Tek seferlik gelir/gider ekleme
  * combined          — Yukarıdakilerden birden fazlası

## Monte Carlo simulation

Adjustment'ları forecast point'larına uygular, N=500 iterasyon
ile residual sampling üzerine. Out: percentile bantlar (p10/p50/p90).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field


VALID_SCENARIO_TYPES = frozenset({
    "revenue_shock", "expense_shock", "fx_shock",
    "delayed_collection", "lump_sum", "combined",
})


@dataclass(frozen=True)
class ScenarioAdjustment:
    """Tek bir senaryo adjustment'i."""

    type: str                # VALID_SCENARIO_TYPES
    pct_change: float = 0    # ±X% (revenue/expense/fx için)
    day_offset: int = 0      # delay için gün, lump_sum için tarih
    amount: float = 0        # lump_sum için tutar (+ gelir, - gider)
    category_filter: str | None = None  # sadece bu kategori etkilenir


@dataclass
class ScenarioResult:
    """Senaryo uygulanmış forecast."""

    horizon_days: int
    baseline_points: list[float] = field(default_factory=list)
    adjusted_points: list[float] = field(default_factory=list)
    p10_points: list[float] = field(default_factory=list)
    p90_points: list[float] = field(default_factory=list)
    cumulative_baseline: float = 0
    cumulative_adjusted: float = 0
    delta: float = 0          # adjusted - baseline (toplam)
    delta_pct: float = 0      # % değişim


class ScenarioPlanningEngine:
    """A3 forecast üzerinde what-if analysis."""

    BOOTSTRAP_N = 500

    def apply_scenario(
        self,
        *,
        baseline_forecast: list[float],
        adjustments: list[ScenarioAdjustment],
        residuals: list[float] | None = None,
        rng: random.Random | None = None,
    ) -> ScenarioResult:
        """Baseline forecast + adjustment list → uygulanmış forecast.

        residuals: bootstrap CI için A3 model.residuals; yoksa CI=zero.
        """
        if not baseline_forecast:
            raise ValueError("Boş baseline forecast")
        for adj in adjustments:
            if adj.type not in VALID_SCENARIO_TYPES:
                raise ValueError(f"Geçersiz adjustment tipi: {adj.type!r}")

        horizon = len(baseline_forecast)
        adjusted = list(baseline_forecast)

        for adj in adjustments:
            adjusted = self._apply_single(adjusted, adj, horizon)

        rng_ = rng or random.Random(42)
        residuals = list(residuals or [0.0])

        # Monte Carlo: her adjusted point'a residual sample ekle
        samples: list[list[float]] = []
        for _ in range(self.BOOTSTRAP_N):
            sample_path: list[float] = []
            cumulative_noise = 0.0
            for h in range(horizon):
                cumulative_noise += rng_.choice(residuals)
                sample_path.append(adjusted[h] + cumulative_noise)
            samples.append(sample_path)

        # Per-step p10/p90
        p10: list[float] = []
        p90: list[float] = []
        for h in range(horizon):
            values_at_h = sorted(s[h] for s in samples)
            p10.append(self._percentile(values_at_h, 10))
            p90.append(self._percentile(values_at_h, 90))

        baseline_sum = sum(baseline_forecast)
        adjusted_sum = sum(adjusted)
        delta = adjusted_sum - baseline_sum
        delta_pct = (delta / baseline_sum * 100) if baseline_sum != 0 else 0

        return ScenarioResult(
            horizon_days=horizon,
            baseline_points=list(baseline_forecast),
            adjusted_points=adjusted,
            p10_points=p10,
            p90_points=p90,
            cumulative_baseline=round(baseline_sum, 2),
            cumulative_adjusted=round(adjusted_sum, 2),
            delta=round(delta, 2),
            delta_pct=round(delta_pct, 2),
        )

    # ── Internals ──────────────────────────────────────────────────────

    def _apply_single(
        self,
        points: list[float],
        adj: ScenarioAdjustment,
        horizon: int,
    ) -> list[float]:
        out = list(points)
        factor = 1 + (adj.pct_change / 100)

        if adj.type == "revenue_shock":
            # Sadece pozitif noktalar revenue sayılır
            out = [p * factor if p > 0 else p for p in out]
        elif adj.type == "expense_shock":
            # Sadece negatif noktalar expense (negatif net flow)
            out = [p * factor if p < 0 else p for p in out]
        elif adj.type == "fx_shock":
            # FX shock tüm noktaları uniform etkiler
            out = [p * factor for p in out]
        elif adj.type == "delayed_collection":
            # day_offset günü kadar shift et (en az 1, en çok horizon)
            shift = max(0, min(adj.day_offset, horizon - 1))
            if shift > 0:
                # İlk 'shift' gün 0, kalan zaman gerçek değerler
                out = [0.0] * shift + out[:horizon - shift]
        elif adj.type == "lump_sum":
            # Tek bir güne tutar ekle
            idx = max(0, min(adj.day_offset, horizon - 1))
            out[idx] = out[idx] + adj.amount
        elif adj.type == "combined":
            # No-op: combined senaryolar birden fazla
            # ScenarioAdjustment ile çağrılır
            pass
        return out

    @staticmethod
    def _percentile(sorted_values: list[float], pct: float) -> float:
        if not sorted_values:
            return 0.0
        if len(sorted_values) == 1:
            return sorted_values[0]
        import math
        k = (len(sorted_values) - 1) * (pct / 100.0)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return sorted_values[int(k)]
        d0 = sorted_values[int(f)] * (c - k)
        d1 = sorted_values[int(c)] * (k - f)
        return d0 + d1
