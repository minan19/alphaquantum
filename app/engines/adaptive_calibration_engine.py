"""A2.1: AdaptiveCalibrationEngine — anomaly detection'ın kendini öğrenmesi.

## Felsefe

Statik eşik = ilk gün maksimum doğruluk, sonra atrofiye uğrar.
Her şirketin pattern'i, mevsimi, tedarikçi tabanı farklı. Sistemin
kendi kendine kalibre olması zorunlu.

## Üç öğrenme mekanizması

1. **Per-target Bayesian update** — her (detector, counterparty) çifti
   kendi Beta(α, β) dağılımını tutar. Onayla → α+1, Yanlış → β+1.
   Posterior mean = α/(α+β) = ölçülmüş hassasiyet.

2. **Threshold offset** — hassasiyet target'tan (default %95) düşükse
   bir sonraki signal için Z eşiği +SCALE × (target − measured) kadar
   yükselir. Yüksekse düşer. Konverjans aralığı: [-1.0σ, +2.0σ].

3. **Pattern whitelist** — bir kombinasyon 3× peş peşe dismiss alırsa
   otomatik whitelist'e girer. Herhangi bir confirmation whitelist'i
   iptal eder ve counter sıfırlanır.

## Matematik

Beta-Bernoulli conjugate prior. Her detector, her target için:
    Prior:     Beta(α₀=2, β₀=1)  — hafif iyimser ("önce dene")
    Update:    α += I(confirm), β += I(dismiss)
    Mean:      μ = α / (α + β)
    Variance:  σ² = αβ / [(α+β)² (α+β+1)]

Düşük N: variance büyük → threshold_offset küçük, conservative ayar.
Yüksek N: variance küçük → offset güvenli, agresif ayar.

## Convergence guarantee

α + β ≥ 30 olduğunda offset stabilize olur (variance < 0.001).
Her detector 30 review sonrası "öğrenilmiş" sayılır.
"""
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from typing import Any


# ── Sabitler ───────────────────────────────────────────────────────────

TARGET_PRECISION = 0.95           # Hedef hassasiyet (%95)
THRESHOLD_OFFSET_SCALE = 2.0      # |target − measured| × SCALE → offset (σ)
THRESHOLD_OFFSET_MIN = -1.0       # Eşik bu kadar düşebilir
THRESHOLD_OFFSET_MAX = 2.0        # Eşik bu kadar yükselebilir
WHITELIST_DISMISSAL_THRESHOLD = 3 # Bu kadar peş peşe dismiss → whitelist
MIN_REVIEWS_FOR_TUNING = 5        # Bu kadar review altında offset tune edilmez
PRIOR_ALPHA = 2.0                 # Beta prior alpha (hafif iyimser)
PRIOR_BETA = 1.0                  # Beta prior beta

WILDCARD_TARGET = "*"             # Per-detector global key


@dataclass(frozen=True)
class CalibrationState:
    """Bir (detector, target) çifti için öğrenilmiş durum."""

    detector_type: str
    target_key: str
    alpha: float
    beta: float
    confirmed_count: int
    dismissed_count: int
    threshold_offset: float
    measured_precision: float    # α / (α+β)
    review_count: int            # confirmed + dismissed
    last_reviewed_at: int | None


class AdaptiveCalibrationEngine:
    """Self-tuning anomaly detection — Bayesian calibration."""

    def __init__(self, database_path: str) -> None:
        self._lock = Lock()
        self._conn = self._connect(database_path)

    @staticmethod
    def _connect(database_path: str) -> sqlite3.Connection:
        conn = sqlite3.connect(database_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def close(self) -> None:
        self._conn.close()

    # ── Public API: read state ─────────────────────────────────────────

    def get_threshold_offset(
        self, *, detector_type: str, target_key: str = WILDCARD_TARGET
    ) -> float:
        """Sinyal puanlanırken Z'ye eklenen düzeltme.

        Specific target önce kontrol edilir, yoksa global (wildcard).
        """
        state = self._fetch_state(detector_type, target_key)
        if state is None:
            global_state = self._fetch_state(detector_type, WILDCARD_TARGET)
            return global_state.threshold_offset if global_state else 0.0
        return state.threshold_offset

    def is_whitelisted(
        self, *, detector_type: str, target_key: str
    ) -> bool:
        """Bu pattern kullanıcı tarafından "normaldir" olarak işaretlendi mi?"""
        with self._lock:
            row = self._conn.execute(
                """
                SELECT whitelisted FROM anomaly_pattern_whitelist
                WHERE detector_type = ? AND target_key = ?
                """,
                (detector_type, target_key),
            ).fetchone()
        return bool(row and int(row["whitelisted"]) == 1)

    def detector_reliability(self, *, detector_type: str) -> float:
        """0.0 – 1.5 — sinyalin son severity'sini çarpan multiplier.

        Global (wildcard) state üzerinden hesaplanır. Yeni dedektör
        için 1.0 (nötr).
        """
        state = self._fetch_state(detector_type, WILDCARD_TARGET)
        if state is None or state.review_count < MIN_REVIEWS_FOR_TUNING:
            return 1.0
        # measured_precision 0–1; 1.0 = mükemmel
        # reliability: 0.5 + 1.0 × precision → [0.5, 1.5]
        return 0.5 + state.measured_precision

    def measured_precision(
        self, *, detector_type: str = WILDCARD_TARGET
    ) -> float | None:
        """Dedektör için ölçülmüş hassasiyet. None = yeterli veri yok."""
        with self._lock:
            if detector_type == WILDCARD_TARGET:
                # Aggregate across all detectors
                row = self._conn.execute(
                    """
                    SELECT SUM(confirmed_count) AS c, SUM(dismissed_count) AS d
                    FROM anomaly_detector_calibration
                    WHERE target_key = '*'
                    """
                ).fetchone()
            else:
                row = self._conn.execute(
                    """
                    SELECT SUM(confirmed_count) AS c, SUM(dismissed_count) AS d
                    FROM anomaly_detector_calibration
                    WHERE detector_type = ?
                    """,
                    (detector_type,),
                ).fetchone()
        if not row:
            return None
        c = int(row["c"] or 0)
        d = int(row["d"] or 0)
        total = c + d
        if total < MIN_REVIEWS_FOR_TUNING:
            return None
        return c / total if total else None

    # ── Public API: record reviews ─────────────────────────────────────

    def record_review(
        self,
        *,
        detector_type: str,
        target_key: str,
        action: str,
        signal_id: int | None = None,
    ) -> CalibrationState:
        """Kullanıcı feedback'i → Beta update + threshold tune + whitelist.

        action: 'confirm' | 'dismiss'
        target_key: signal payload'undan türetilir (counterparty, vs.)

        Bu metod iki state'i günceller:
          1. specific (detector, target) → fine-grained tuning
          2. global  (detector, '*')     → detector reliability
        """
        if action not in ("confirm", "dismiss"):
            raise ValueError(f"Geçersiz action: {action}")

        # Per-target update
        new_state = self._update_state(
            detector_type=detector_type,
            target_key=target_key,
            action=action,
        )
        # Global per-detector update (target_key='*')
        if target_key != WILDCARD_TARGET:
            self._update_state(
                detector_type=detector_type,
                target_key=WILDCARD_TARGET,
                action=action,
            )
        # Whitelist tracking
        self._update_whitelist(
            detector_type=detector_type,
            target_key=target_key,
            action=action,
        )
        return new_state

    # ── Public API: metrics ────────────────────────────────────────────

    def overall_metrics(self) -> dict[str, Any]:
        """Dashboard 'doğruluk KPI'sı için özet.

        Tüm dedektörlerin global (wildcard) state'i + en az 1 review almış
        per-detector breakdown.
        """
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT detector_type, alpha, beta,
                       confirmed_count, dismissed_count, threshold_offset
                FROM anomaly_detector_calibration
                WHERE target_key = ?
                """,
                (WILDCARD_TARGET,),
            ).fetchall()

        per_detector: dict[str, dict[str, Any]] = {}
        total_c = 0
        total_d = 0
        for row in rows:
            c = int(row["confirmed_count"])
            d = int(row["dismissed_count"])
            total_c += c
            total_d += d
            total = c + d
            precision = (c / total) if total > 0 else None
            per_detector[row["detector_type"]] = {
                "confirmed": c,
                "dismissed": d,
                "total_reviews": total,
                "measured_precision": precision,
                "threshold_offset": float(row["threshold_offset"]),
                "reliability": self.detector_reliability(
                    detector_type=row["detector_type"]
                ),
            }

        with self._lock:
            wl_row = self._conn.execute(
                """
                SELECT COUNT(*) AS n FROM anomaly_pattern_whitelist
                WHERE whitelisted = 1
                """
            ).fetchone()
        whitelisted = int(wl_row["n"] or 0) if wl_row else 0

        total_reviews = total_c + total_d
        overall_precision = (total_c / total_reviews) if total_reviews > 0 else None
        return {
            "measured_precision": overall_precision,
            "total_reviews": total_reviews,
            "confirmed": total_c,
            "dismissed": total_d,
            "whitelisted_patterns": whitelisted,
            "per_detector": per_detector,
            "is_learned": total_reviews >= MIN_REVIEWS_FOR_TUNING,
        }

    def snapshot_daily_metrics(self) -> int:
        """Bugünkü detector metric'lerini snapshot'a yaz. Trend grafiği için.

        Returns: snapshot edilen detector sayısı.
        """
        today = datetime.now().strftime("%Y-%m-%d")
        now = int(time.time())
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT detector_type, alpha, beta, confirmed_count, dismissed_count
                FROM anomaly_detector_calibration
                WHERE target_key = ?
                """,
                (WILDCARD_TARGET,),
            ).fetchall()

            count = 0
            for row in rows:
                c = int(row["confirmed_count"])
                d = int(row["dismissed_count"])
                total = c + d
                precision_pct = (c / total * 100) if total > 0 else 0.0
                self._conn.execute(
                    """
                    INSERT INTO anomaly_detector_metrics_daily
                        (detector_type, snapshot_date, precision_pct,
                         total_signals, confirmed, dismissed, pending)
                    VALUES (?, ?, ?, ?, ?, ?, 0)
                    ON CONFLICT(detector_type, snapshot_date) DO UPDATE SET
                        precision_pct = excluded.precision_pct,
                        total_signals = excluded.total_signals,
                        confirmed = excluded.confirmed,
                        dismissed = excluded.dismissed
                    """,
                    (row["detector_type"], today, precision_pct, total, c, d),
                )
                count += 1
            self._conn.commit()
            _ = now  # used for future "last snapshot at" field
            return count

    # ── Internal: state CRUD ───────────────────────────────────────────

    def _fetch_state(
        self, detector_type: str, target_key: str
    ) -> CalibrationState | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT detector_type, target_key, alpha, beta,
                       confirmed_count, dismissed_count, threshold_offset,
                       last_reviewed_at
                FROM anomaly_detector_calibration
                WHERE detector_type = ? AND target_key = ?
                """,
                (detector_type, target_key),
            ).fetchone()
        if not row:
            return None
        return self._row_to_state(row)

    def _update_state(
        self, *, detector_type: str, target_key: str, action: str
    ) -> CalibrationState:
        """Atomik Bayesian update + threshold recompute.

        Mevcut state yoksa prior'dan başlat.
        """
        now = int(time.time())
        delta_alpha = 1.0 if action == "confirm" else 0.0
        delta_beta = 1.0 if action == "dismiss" else 0.0
        delta_c = 1 if action == "confirm" else 0
        delta_d = 1 if action == "dismiss" else 0

        with self._lock:
            self._conn.execute(
                """
                INSERT INTO anomaly_detector_calibration (
                    detector_type, target_key, alpha, beta,
                    confirmed_count, dismissed_count,
                    threshold_offset, last_reviewed_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 0.0, ?, ?)
                ON CONFLICT(detector_type, target_key) DO UPDATE SET
                    alpha = alpha + ?,
                    beta = beta + ?,
                    confirmed_count = confirmed_count + ?,
                    dismissed_count = dismissed_count + ?,
                    last_reviewed_at = ?,
                    updated_at = ?
                """,
                (
                    detector_type, target_key,
                    PRIOR_ALPHA + delta_alpha, PRIOR_BETA + delta_beta,
                    delta_c, delta_d, now, now,
                    delta_alpha, delta_beta, delta_c, delta_d, now, now,
                ),
            )
            self._conn.commit()

        state = self._fetch_state(detector_type, target_key)
        assert state is not None  # just inserted
        # Threshold offset recompute
        new_offset = self._compute_threshold_offset(state)
        if abs(new_offset - state.threshold_offset) > 1e-6:
            with self._lock:
                self._conn.execute(
                    """
                    UPDATE anomaly_detector_calibration
                    SET threshold_offset = ?, updated_at = ?
                    WHERE detector_type = ? AND target_key = ?
                    """,
                    (new_offset, now, detector_type, target_key),
                )
                self._conn.commit()
            # Re-fetch
            refreshed = self._fetch_state(detector_type, target_key)
            assert refreshed is not None
            state = refreshed
        return state

    def _update_whitelist(
        self, *, detector_type: str, target_key: str, action: str
    ) -> None:
        """Peş peşe dismiss sayacı → eşiği geçerse whitelist."""
        if target_key == WILDCARD_TARGET:
            return  # global state için whitelist anlamsız
        now = int(time.time())
        with self._lock:
            row = self._conn.execute(
                """
                SELECT consecutive_dismissals, whitelisted
                FROM anomaly_pattern_whitelist
                WHERE detector_type = ? AND target_key = ?
                """,
                (detector_type, target_key),
            ).fetchone()

            if action == "dismiss":
                if row:
                    new_n = int(row["consecutive_dismissals"]) + 1
                    new_wl = 1 if new_n >= WHITELIST_DISMISSAL_THRESHOLD else int(row["whitelisted"])
                    self._conn.execute(
                        """
                        UPDATE anomaly_pattern_whitelist
                        SET consecutive_dismissals = ?,
                            whitelisted = ?,
                            last_dismissed_at = ?,
                            updated_at = ?
                        WHERE detector_type = ? AND target_key = ?
                        """,
                        (new_n, new_wl, now, now, detector_type, target_key),
                    )
                else:
                    initial_wl = 1 if WHITELIST_DISMISSAL_THRESHOLD == 1 else 0
                    self._conn.execute(
                        """
                        INSERT INTO anomaly_pattern_whitelist
                            (detector_type, target_key, consecutive_dismissals,
                             whitelisted, last_dismissed_at, updated_at)
                        VALUES (?, ?, 1, ?, ?, ?)
                        """,
                        (detector_type, target_key, initial_wl, now, now),
                    )
            else:  # confirm → reset counter, drop whitelist
                if row:
                    self._conn.execute(
                        """
                        UPDATE anomaly_pattern_whitelist
                        SET consecutive_dismissals = 0,
                            whitelisted = 0,
                            last_confirmed_at = ?,
                            updated_at = ?
                        WHERE detector_type = ? AND target_key = ?
                        """,
                        (now, now, detector_type, target_key),
                    )
                else:
                    self._conn.execute(
                        """
                        INSERT INTO anomaly_pattern_whitelist
                            (detector_type, target_key, consecutive_dismissals,
                             whitelisted, last_confirmed_at, updated_at)
                        VALUES (?, ?, 0, 0, ?, ?)
                        """,
                        (detector_type, target_key, now, now),
                    )
            self._conn.commit()

    @staticmethod
    def _compute_threshold_offset(state: CalibrationState) -> float:
        """measured_precision'a göre Z eşik offset hesapla.

        Düşük precision → offset yükselir (eşik daha katı, az false positive).
        Yüksek precision → offset düşer (eşik gevşer, daha çok tespit).
        """
        if state.review_count < MIN_REVIEWS_FOR_TUNING:
            return 0.0
        gap = TARGET_PRECISION - state.measured_precision
        offset = gap * THRESHOLD_OFFSET_SCALE
        return max(THRESHOLD_OFFSET_MIN, min(THRESHOLD_OFFSET_MAX, offset))

    @staticmethod
    def _row_to_state(row: sqlite3.Row) -> CalibrationState:
        c = int(row["confirmed_count"])
        d = int(row["dismissed_count"])
        total = c + d
        # measured_precision = α/(α+β) — empirical, hafif iyimser prior'la
        alpha = float(row["alpha"])
        beta = float(row["beta"])
        denom = alpha + beta
        precision = alpha / denom if denom > 0 else 0.0
        last_reviewed = row["last_reviewed_at"]
        return CalibrationState(
            detector_type=str(row["detector_type"]),
            target_key=str(row["target_key"]),
            alpha=alpha,
            beta=beta,
            confirmed_count=c,
            dismissed_count=d,
            threshold_offset=float(row["threshold_offset"]),
            measured_precision=precision,
            review_count=total,
            last_reviewed_at=int(last_reviewed) if last_reviewed is not None else None,
        )
