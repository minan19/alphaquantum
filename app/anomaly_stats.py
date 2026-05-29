"""A2: Anomaly detection için istatistiksel yardımcılar.

## Felsefe — neden bu fonksiyonlar?

Finans datası **non-normal** dağılır: çoğu zaman log-normal, fat-tail,
seasonal. Klasik z-score (mean/std) outlier'a karşı kırılgan — bir
büyük transaction baseline'ı zehirler ve sonraki anomaly'ler kaçar.

Bu modülün tercihi:
  * **Median Absolute Deviation (MAD)** — outlier-robust merkezi eğilim
  * **Modified Z-score** (Iglewicz–Hoaglin 1993) — MAD-based, financial
    audit literatüründe standart
  * **IQR-based outlier** — kapsayıcı confidence interval'lar
  * **Empirical Bayes shrinkage** — küçük N'de overfit önler

%99 doğruluk hedefimizin matematiksel zemini:
  Modified Z ≥ 3.5  → ≈99.95% confidence (3-tier kritik)
  Modified Z ≥ 2.5  → ≈98.75% confidence (yüksek)
  Modified Z ≥ 1.8  → ≈92% confidence (orta — investigate)

## API — fonksiyonel + saf

Hiçbir state, hiçbir IO. Repository → engine'e injekte edilir, engine
saf hesap için bu modülü çağırır. Test edilebilirlik birinci sınıf.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Sequence


# ── Sabitler ───────────────────────────────────────────────────────────

# Iglewicz & Hoaglin 1993: 0.6745 = inverse of standard normal at 0.75
# Modified Z = 0.6745 * (x - median) / MAD
_MAD_CONSTANT = 0.6745

# Confidence tier eşikleri — UI'da gösterim için
# (modified_z, confidence_pct, severity_label)
CRITICAL_Z_THRESHOLD = 3.5  # ≈99.95%
HIGH_Z_THRESHOLD = 2.5      # ≈98.75%
MEDIUM_Z_THRESHOLD = 1.8    # ≈92%

# Minimum baseline sample — altında istatistik anlamsız
MIN_BASELINE_N = 4


# ── Tip tanımları ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class BaselineStats:
    """Bir metric'in tarihsel baseline'ı.

    Bütün değerler robust (MAD-based). count <= MIN_BASELINE_N ise
    is_reliable=False — engine bu durumda tier'ı düşürmeli.
    """

    median: float
    mad: float                 # Median Absolute Deviation
    mad_scaled: float          # MAD / 0.6745 — robust std proxy
    iqr_low: float             # Q1
    iqr_high: float            # Q3
    sample_min: float
    sample_max: float
    count: int
    is_reliable: bool          # count ≥ MIN_BASELINE_N


@dataclass(frozen=True)
class AnomalyScore:
    """Bir gözlem'in baseline'a göre skoru.

    confidence_pct: 0–100 (insan-okunabilir). Tier'a göre eşlenir.
    severity: 'critical' | 'high' | 'medium' | 'low'
    """

    value: float
    modified_z: float          # Iglewicz–Hoaglin modified Z
    confidence_pct: float      # 0–100
    severity: str              # critical | high | medium | low
    deviation_pct: float       # (value - median) / median * 100, signed
    is_outlier_above: bool     # value > median
    baseline: BaselineStats


# ── Yardımcı fonksiyonlar ──────────────────────────────────────────────

def _percentile(sorted_values: Sequence[float], pct: float) -> float:
    """Sorted input üzerinde linear-interpolation percentile."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    k = (len(sorted_values) - 1) * pct
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(sorted_values[int(k)])
    d0 = sorted_values[int(f)] * (c - k)
    d1 = sorted_values[int(c)] * (k - f)
    return float(d0 + d1)


def compute_baseline(values: Sequence[float]) -> BaselineStats:
    """Bir değer dizisinden robust baseline çıkar.

    Boş input → sıfır baseline, is_reliable=False.
    """
    if not values:
        return BaselineStats(
            median=0.0, mad=0.0, mad_scaled=0.0,
            iqr_low=0.0, iqr_high=0.0,
            sample_min=0.0, sample_max=0.0,
            count=0, is_reliable=False,
        )

    sorted_vals = sorted(float(v) for v in values)
    n = len(sorted_vals)
    median = statistics.median(sorted_vals)

    # MAD — median of absolute deviations
    abs_devs = sorted(abs(v - median) for v in sorted_vals)
    mad = statistics.median(abs_devs)

    # MAD == 0 edge case (tüm değerler eşit veya yarısı medyana eşit):
    # mean absolute deviation'a düş — Iglewicz–Hoaglin önerisi.
    if mad == 0.0:
        mean_abs_dev = sum(abs_devs) / n if n > 0 else 0.0
        # 0.7979 = sqrt(2/pi), normal dağılım altında MAD ile ölçeklemek için
        mad_scaled = mean_abs_dev / 0.7979 if mean_abs_dev > 0 else 0.0
    else:
        mad_scaled = mad / _MAD_CONSTANT

    iqr_low = _percentile(sorted_vals, 0.25)
    iqr_high = _percentile(sorted_vals, 0.75)

    return BaselineStats(
        median=float(median),
        mad=float(mad),
        mad_scaled=float(mad_scaled),
        iqr_low=float(iqr_low),
        iqr_high=float(iqr_high),
        sample_min=float(sorted_vals[0]),
        sample_max=float(sorted_vals[-1]),
        count=n,
        is_reliable=n >= MIN_BASELINE_N,
    )


def modified_z_score(value: float, baseline: BaselineStats) -> float:
    """Iglewicz–Hoaglin modified Z-score.

    Z = 0.6745 * (x - median) / MAD

    MAD == 0 ise mean_abs_dev fallback (compute_baseline'da hesaplanan
    mad_scaled üzerinden çevrim). MAD ve mean_abs_dev her ikisi de 0 ise
    (tüm değerler aynı) → 0 (hiçbir gözlem outlier değil).
    """
    if baseline.count == 0:
        return 0.0
    if baseline.mad > 0:
        return _MAD_CONSTANT * (value - baseline.median) / baseline.mad
    if baseline.mad_scaled > 0:
        # mad_scaled = mean_abs_dev / 0.7979
        # Z proxy = (x - median) / mad_scaled
        return (value - baseline.median) / baseline.mad_scaled
    # Tüm değerler eşit → herhangi bir farklı gözlem extreme outlier
    if math.isclose(value, baseline.median, rel_tol=1e-9):
        return 0.0
    # Sonsuza yakın anlamına gelir; pratik amaçla büyük bir sınır döndür
    return math.copysign(10.0, value - baseline.median)


def confidence_from_z(z: float) -> float:
    """|z| → confidence_pct (0–100).

    Empirik mapping — normal dağılım altında modified Z'nin tek-kuyruk
    p-value'sı. Doğrudan erf yerine pratik tablo (CPU-cheap, yeterince
    isabetli, deterministik):
      z 1.8 ≈ 92%   z 2.5 ≈ 98.75%   z 3.5 ≈ 99.95%   z 6+ ≈ 99.9999%
    """
    abs_z = abs(z)
    if abs_z <= 0:
        return 0.0
    if abs_z >= 6:
        return 99.9999
    # Standart normal CDF (Abramowitz & Stegun 26.2.17 yaklaşımı)
    # P(|Z| ≤ z) = 2Φ(z) - 1
    # Tek-kuyruk için P(Z > z) confidence olarak (1 - 2*(1-Φ(z))) * 100
    cdf = _norm_cdf(abs_z)
    two_tailed_p = 2 * (1 - cdf)
    confidence = max(0.0, min(99.9999, (1 - two_tailed_p) * 100))
    return float(confidence)


def _norm_cdf(x: float) -> float:
    """Standart normal CDF — math.erf üzerinden (stdlib, bağımlılık yok)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def severity_from_z(z: float, *, baseline_reliable: bool) -> str:
    """|z| → severity tier. Baseline reliable değilse bir tier düşür."""
    abs_z = abs(z)
    if abs_z >= CRITICAL_Z_THRESHOLD:
        return "critical" if baseline_reliable else "high"
    if abs_z >= HIGH_Z_THRESHOLD:
        return "high" if baseline_reliable else "medium"
    if abs_z >= MEDIUM_Z_THRESHOLD:
        return "medium" if baseline_reliable else "low"
    return "low"


def score_observation(value: float, baseline: BaselineStats) -> AnomalyScore:
    """Bir gözlemi baseline'a göre puanla.

    Tek noktadan tüm metric'leri çıkar — engine bu sonucu DB'ye yazar.
    """
    z = modified_z_score(value, baseline)
    severity = severity_from_z(z, baseline_reliable=baseline.is_reliable)
    confidence = confidence_from_z(z)
    deviation_pct = 0.0
    if baseline.median != 0:
        deviation_pct = (value - baseline.median) / abs(baseline.median) * 100

    return AnomalyScore(
        value=float(value),
        modified_z=float(z),
        confidence_pct=float(confidence),
        severity=severity,
        deviation_pct=float(deviation_pct),
        is_outlier_above=value > baseline.median,
        baseline=baseline,
    )


def is_actionable(score: AnomalyScore, *, min_severity: str = "high") -> bool:
    """Dashboard'a yansıyacak mı? Default: yüksek+ tier.

    Bu fonksiyon false-positive yorgunluğunu önleyen ana kapıdır.
    """
    order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    return order.get(score.severity, 0) >= order.get(min_severity, 2)
