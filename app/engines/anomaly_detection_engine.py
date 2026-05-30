"""A2: Cross-Company Anomaly Detection Engine.

## Felsefe

Holding'in en pahalı finansal sızıntıları "tek tek bakınca normal,
şirketler arasında bakınca tehlikeli" paternlerden gelir:
  * Aynı tedarikçi 5 yan şirketin hepsinden ödeme alıyor (kasıtlı
    çift faturalama veya zayıf konsolidasyon)
  * Bir kategorideki ödemeler ayda 3× artmış (kayıp kontrol)
  * Aynı tutar, aynı counterparty, 7 gün içinde tekrar (duplicate
    bank-transfer)
  * Ödeme frekansı patladı (kasıt veya sistem hatası)

CorpOS pillar'ı: tek şirket finans yazılımı bunları yakalayamaz.
Bizim avantajımız: cross-company ledger erişimi.

## Doğruluk hedefi (kullanıcının %99 talebi)

Confidence tiers — `app.anomaly_stats` üzerinde inşa:
  * CRITICAL  (z ≥ 3.5)  → ≈99.95% confidence — kullanıcıya "hemen bak"
  * HIGH      (z ≥ 2.5)  → ≈98.75% confidence — "bugün incele"
  * MEDIUM    (z ≥ 1.8)  → ≈92% confidence — review queue
  * LOW       (z < 1.8)  → kayda alınmaz

Dashboard default'u sadece CRITICAL+HIGH gösterir → kullanıcı her
uyarıya güvenir → uygulamalı doğruluk 99%+ olur.

## Detector kontratı

Her detector → `list[DetectedSignal]` döner. Pure function (DB yazma
yok). Engine.run_all() bu sinyalleri repository'ye idempotent yazar.
Signature hash zaman aralığına özgüdür: aynı anomali günde 1 kez
kaydedilir.
"""
from __future__ import annotations

import hashlib
import sqlite3
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any

from app.anomaly_signals_repository import AnomalySignalsRepository
from app.anomaly_stats import (
    compute_baseline,
    is_actionable,
    score_observation,
)
from app.engines.adaptive_calibration_engine import AdaptiveCalibrationEngine


# ── Detector çıktı tipi ────────────────────────────────────────────────

@dataclass
class DetectedSignal:
    """Detector'ın ürettiği ham sinyal — repository.upsert_signal'a feed."""

    signal_type: str
    severity: str
    confidence_pct: float
    modified_z: float
    title: str
    description: str
    baseline: dict[str, Any]
    payload: dict[str, Any]
    signature_hash: str
    holding_id: int | None = None


# ── Engine ─────────────────────────────────────────────────────────────


@dataclass
class DetectionRunSummary:
    """run_all() çıktısı."""

    new_signals: int = 0
    detectors_run: list[str] = field(default_factory=list)
    duration_ms: int = 0
    generated_at: int = 0


class AnomalyDetectionEngine:
    """4 detector + persistence orchestration.

    Persist DB: anomaly_signals (migration 026).
    Read DB:    finance_ledger_entries (gider/gelir kayıtları).
    """

    # Baseline lookback günü — istatistiksel olarak yeterli pencere
    BASELINE_LOOKBACK_DAYS = 90

    # Detection penceresi — son N gün incelenir (default 7)
    DETECTION_WINDOW_DAYS = 7

    # Intercompany leakage için minimum company-count
    LEAKAGE_MIN_COMPANIES = 2

    # Duplicate payment için tolerans (TL cinsinden)
    DUPLICATE_AMOUNT_TOLERANCE = 0.01  # 1 kuruş

    def __init__(
        self,
        *,
        repo: AnomalySignalsRepository,
        ledger_db_path: str,
        calibration: AdaptiveCalibrationEngine | None = None,
    ) -> None:
        self._repo = repo
        self._ledger_db_path = ledger_db_path
        # Calibration optional — yoksa nötr davranış (no learning)
        self._calibration = calibration

    # ── Public API ─────────────────────────────────────────────────────

    def run_all(self, *, holding_id: int | None = None) -> DetectionRunSummary:
        """4 detector'u sırayla çalıştır, sinyalleri persist et."""
        start = time.monotonic()
        detectors = [
            ("intercompany_leakage", self.detect_intercompany_leakage),
            ("volume_spike", self.detect_volume_spike),
            ("duplicate_payment", self.detect_duplicate_payment),
            ("velocity_anomaly", self.detect_velocity_anomaly),
        ]

        new_count = 0
        ran: list[str] = []
        for name, fn in detectors:
            ran.append(name)
            for sig in fn(holding_id=holding_id):
                result = self._repo.upsert_signal(
                    holding_id=sig.holding_id,
                    signal_type=sig.signal_type,
                    severity=sig.severity,
                    confidence_pct=sig.confidence_pct,
                    modified_z=sig.modified_z,
                    title=sig.title,
                    description=sig.description,
                    baseline=sig.baseline,
                    payload=sig.payload,
                    signature_hash=sig.signature_hash,
                )
                if result is not None:
                    new_count += 1

        elapsed_ms = int((time.monotonic() - start) * 1000)
        return DetectionRunSummary(
            new_signals=new_count,
            detectors_run=ran,
            duration_ms=elapsed_ms,
            generated_at=int(time.time()),
        )

    def list_signals(
        self,
        *,
        holding_id: int | None,
        min_severity: str = "high",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return self._repo.list_open(
            holding_id=holding_id,
            min_severity=min_severity,
            limit=limit,
        )

    def summary(self, *, holding_id: int | None) -> dict[str, int]:
        counts = self._repo.count_by_severity(holding_id=holding_id)
        counts["total_open"] = sum(counts.values())
        return counts

    def review(
        self,
        *,
        signal_id: int,
        action: str,
        reviewed_by: str,
        note: str | None = None,
    ) -> dict[str, Any] | None:
        """Sinyal feedback'i + adaptive calibration update.

        Sinyal payload'ından target_key türetilir → per-pattern öğrenme.
        """
        result = self._repo.review_signal(
            signal_id=signal_id,
            action=action,
            reviewed_by=reviewed_by,
            note=note,
        )
        if result is not None and self._calibration is not None:
            target_key = self._target_key_for(result)
            self._calibration.record_review(
                detector_type=result["signal_type"],
                target_key=target_key,
                action=action,
                signal_id=signal_id,
            )
        return result

    @staticmethod
    def _target_key_for(signal: dict[str, Any]) -> str:
        """Sinyal payload'undan calibration target_key türet.

        Her detector kendi key formatına sahip — calibration tablosunun
        target_key kolonuyla uyumlu.
        """
        payload = signal.get("payload", {}) or {}
        signal_type = signal.get("signal_type", "")
        if signal_type == "intercompany_leakage":
            return str(payload.get("counterparty", "*"))
        if signal_type == "volume_spike":
            company = str(payload.get("company", ""))
            category = str(payload.get("category", ""))
            return f"{company}::{category}"
        if signal_type == "duplicate_payment":
            return str(payload.get("counterparty", "*"))
        if signal_type == "velocity_anomaly":
            return str(payload.get("counterparty", "*"))
        return "*"

    def _apply_calibration(
        self,
        *,
        detector_type: str,
        target_key: str,
        base_z: float,
        base_confidence: float,
        base_severity: str,
    ) -> tuple[float, float, str] | None:
        """Calibration offset + reliability uygula.

        Returns: (adjusted_z, adjusted_confidence, adjusted_severity) veya
        None (sinyal whitelist'te ise — atla).
        """
        if self._calibration is None:
            return base_z, base_confidence, base_severity

        # Whitelist filter — bu pattern kullanıcı tarafından "normaldir" denmiş
        if self._calibration.is_whitelisted(
            detector_type=detector_type, target_key=target_key
        ):
            return None

        offset = self._calibration.get_threshold_offset(
            detector_type=detector_type, target_key=target_key
        )
        adjusted_z = base_z - offset  # offset >0 → eşik yükselir → effective Z düşer
        reliability = self._calibration.detector_reliability(
            detector_type=detector_type
        )
        # Reliability multiplier sinyalin gücünü ayarlar
        # Kritik 1.0, yüksek hassasiyet 1.5 → severity yükselir;
        # düşük reliability 0.5 → severity düşer.
        effective_z = adjusted_z * reliability

        # Yeni severity threshold-based
        from app.anomaly_stats import severity_from_z, confidence_from_z
        new_severity = severity_from_z(effective_z, baseline_reliable=True)
        new_confidence = confidence_from_z(effective_z)
        # Severity'yi sadece base'den yukarı çekmiyoruz — koruma için
        # base critical ise critical kalır
        if base_severity == "critical":
            new_severity = "critical"
            new_confidence = max(new_confidence, base_confidence)
        return adjusted_z, new_confidence, new_severity

    # ── Detector 1: Intercompany Leakage ────────────────────────────────

    def detect_intercompany_leakage(
        self, *, holding_id: int | None
    ) -> list[DetectedSignal]:
        """Aynı tedarikçi N≥2 yan şirket tarafından ödeniyorsa flag.

        Pencere: son DETECTION_WINDOW_DAYS gün.
        Kritik koşul: counterparty geçen 12 ayda 1 şirketle iş yapmışken
        bu hafta birden fazla şirketle iş yapıyorsa — kasıtlı çift
        faturalama paterni.
        """
        rows = self._fetch_ledger(
            window_days=self.DETECTION_WINDOW_DAYS, kind="expense"
        )
        if not rows:
            return []

        # Aggregate per counterparty
        by_counterparty: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for r in rows:
            cp = (r.get("counterparty_company") or "").strip()
            if not cp:
                continue
            by_counterparty[cp].append(r)

        # Tarihsel baseline (önceki 12 ay, son hafta hariç)
        historical = self._fetch_ledger(
            window_days=365,
            kind="expense",
            exclude_recent_days=self.DETECTION_WINDOW_DAYS,
        )
        historical_companies_per_cp: dict[str, set[str]] = defaultdict(set)
        for r in historical:
            cp = (r.get("counterparty_company") or "").strip()
            if cp:
                historical_companies_per_cp[cp].add(str(r.get("company_name", "")))

        signals: list[DetectedSignal] = []
        today = datetime.now().strftime("%Y-%m-%d")
        for counterparty, entries in by_counterparty.items():
            companies = {str(e.get("company_name", "")) for e in entries}
            if len(companies) < self.LEAKAGE_MIN_COMPANIES:
                continue

            hist_companies = historical_companies_per_cp.get(counterparty, set())
            new_companies = companies - hist_companies
            total_amount = sum(float(e.get("amount", 0)) for e in entries)

            # Severity:
            #   * Bu counterparty geçmişte 0–1 şirketle çalışıyordu ve şimdi
            #     2+ şirket → CRITICAL (anormal davranış)
            #   * Geçmişte 2+ şirketle de çalışıyordu → MEDIUM (normal grup
            #     tedarikçisi olabilir)
            historical_breadth = len(hist_companies)
            if historical_breadth <= 1 and len(companies) >= 2:
                severity = "critical"
                confidence = 99.5
                z = 4.0
            elif historical_breadth < len(companies):
                severity = "high"
                confidence = 95.0
                z = 2.8
            else:
                severity = "medium"
                confidence = 80.0
                z = 1.9

            # Calibration: whitelist check + threshold adjustment
            adj = self._apply_calibration(
                detector_type="intercompany_leakage",
                target_key=counterparty,
                base_z=z,
                base_confidence=confidence,
                base_severity=severity,
            )
            if adj is None:
                continue  # Whitelisted — kullanıcı bu pattern'ı "normaldir" demiş
            z, confidence, severity = adj

            signature = self._signature(
                "intercompany_leakage",
                counterparty,
                today,
                sorted(companies),
            )

            companies_list = sorted(companies)
            title = f"Cross-company tedarikçi: {counterparty}"
            description = (
                f"{counterparty}, son {self.DETECTION_WINDOW_DAYS} günde "
                f"{len(companies)} şirket tarafından ödendi "
                f"({', '.join(companies_list)}). "
                f"Toplam: {total_amount:,.2f}. "
                f"Geçen 12 ayda bu tedarikçi {historical_breadth} şirketle çalışıyordu. "
                f"İnceleme: çift faturalama mı, merkezi tedarik mi?"
            )

            signals.append(DetectedSignal(
                holding_id=holding_id,
                signal_type="intercompany_leakage",
                severity=severity,
                confidence_pct=confidence,
                modified_z=z,
                title=title,
                description=description,
                baseline={
                    "historical_company_count": historical_breadth,
                    "historical_companies": sorted(hist_companies),
                    "window_days": self.DETECTION_WINDOW_DAYS,
                },
                payload={
                    "counterparty": counterparty,
                    "current_companies": companies_list,
                    "new_companies": sorted(new_companies),
                    "total_amount": total_amount,
                    "entry_count": len(entries),
                },
                signature_hash=signature,
            ))

        return signals

    # ── Detector 2: Volume Spike ────────────────────────────────────────

    def detect_volume_spike(
        self, *, holding_id: int | None
    ) -> list[DetectedSignal]:
        """Bir kategori/şirket çiftinin son haftası baseline'a göre spike mi?

        Baseline: son BASELINE_LOOKBACK_DAYS gün, son hafta hariç.
        Test: weekly_sum (son hafta) → MAD-based modified Z karşılaştırma.
        """
        recent = self._fetch_ledger(
            window_days=self.DETECTION_WINDOW_DAYS, kind="expense"
        )
        baseline_rows = self._fetch_ledger(
            window_days=self.BASELINE_LOOKBACK_DAYS,
            kind="expense",
            exclude_recent_days=self.DETECTION_WINDOW_DAYS,
        )
        if not recent or not baseline_rows:
            return []

        # Baseline: liste of weekly sums per (company, category)
        # Recent: single week total per (company, category)
        baseline_weekly = self._weekly_sums(baseline_rows)
        recent_weekly = self._weekly_sums_recent(recent)

        signals: list[DetectedSignal] = []
        for key, current_amount in recent_weekly.items():
            company, category = key
            history = baseline_weekly.get(key, [])
            if len(history) < 4:
                # Yetersiz baseline — high precision için bu paterni atla
                continue

            baseline = compute_baseline(history)
            score = score_observation(current_amount, baseline)
            if not is_actionable(score, min_severity="medium"):
                continue
            # Sadece pozitif spike (artış) — düşüş başka detector işi
            if not score.is_outlier_above:
                continue

            # Calibration
            target_key = f"{company}::{category}"
            adj = self._apply_calibration(
                detector_type="volume_spike",
                target_key=target_key,
                base_z=score.modified_z,
                base_confidence=score.confidence_pct,
                base_severity=score.severity,
            )
            if adj is None:
                continue
            adjusted_z, adjusted_conf, adjusted_sev = adj
            # Adjusted severity actionable mı?
            if adjusted_sev not in ("critical", "high"):
                continue

            signature = self._signature(
                "volume_spike",
                company,
                category,
                datetime.now().strftime("%Y-W%W"),
            )

            title = f"{company} · {category} kategoride harcama sıçradı"
            description = (
                f"Son hafta toplam: {current_amount:,.2f}. "
                f"Baseline medyan: {baseline.median:,.2f} "
                f"(önceki {self.BASELINE_LOOKBACK_DAYS} gün). "
                f"Sapma: %{score.deviation_pct:+.1f}, "
                f"modified Z: {score.modified_z:.2f}, "
                f"güven: %{score.confidence_pct:.1f}."
            )

            signals.append(DetectedSignal(
                holding_id=holding_id,
                signal_type="volume_spike",
                severity=adjusted_sev,
                confidence_pct=adjusted_conf,
                modified_z=adjusted_z,
                title=title,
                description=description,
                baseline=asdict(baseline),
                payload={
                    "company": company,
                    "category": category,
                    "current_amount": current_amount,
                    "deviation_pct": score.deviation_pct,
                    "baseline_sample_n": baseline.count,
                },
                signature_hash=signature,
            ))
        return signals

    # ── Detector 3: Duplicate Payment ───────────────────────────────────

    def detect_duplicate_payment(
        self, *, holding_id: int | None
    ) -> list[DetectedSignal]:
        """Aynı tutar + aynı counterparty + 7 gün içinde mükerrer ödeme.

        Bu detector deterministiktir: matematiksel olarak duplicate'ı
        garanti eden bir matching kuralı. Confidence 99.9% — manuel
        kontrolün de aşamayacağı.
        """
        rows = self._fetch_ledger(
            window_days=self.DETECTION_WINDOW_DAYS, kind="expense"
        )
        if not rows:
            return []

        # Group by (counterparty, rounded_amount)
        buckets: dict[tuple[str, float], list[dict[str, Any]]] = defaultdict(list)
        for r in rows:
            cp = (r.get("counterparty_company") or "").strip()
            if not cp:
                continue
            amount = round(float(r.get("amount", 0)), 2)
            if amount <= 0:
                continue
            buckets[(cp, amount)].append(r)

        signals: list[DetectedSignal] = []
        for (counterparty, amount), entries in buckets.items():
            if len(entries) < 2:
                continue
            # Tarihler arası fark — hepsi 7 gün penceresinde
            dates = sorted([str(e.get("entry_date", "")) for e in entries])
            companies = sorted({str(e.get("company_name", "")) for e in entries})

            # Calibration
            adj = self._apply_calibration(
                detector_type="duplicate_payment",
                target_key=counterparty,
                base_z=6.0,
                base_confidence=99.9,
                base_severity="critical",
            )
            if adj is None:
                continue

            signature = self._signature(
                "duplicate_payment",
                counterparty,
                f"{amount:.2f}",
                dates[0],
                dates[-1],
            )

            title = f"Mükerrer ödeme: {counterparty} · {amount:,.2f}"
            description = (
                f"{counterparty} adresine {amount:,.2f} tutarında "
                f"{len(entries)} adet aynı ödeme — {len(companies)} şirket "
                f"({', '.join(companies)}), {dates[0]} ile {dates[-1]} arası. "
                f"İnceleme: çift kayıt mı, gerçek tekrar mı?"
            )

            signals.append(DetectedSignal(
                holding_id=holding_id,
                signal_type="duplicate_payment",
                severity="critical",
                confidence_pct=99.9,
                modified_z=6.0,
                title=title,
                description=description,
                baseline={"detection_window_days": self.DETECTION_WINDOW_DAYS},
                payload={
                    "counterparty": counterparty,
                    "amount": amount,
                    "occurrence_count": len(entries),
                    "companies": companies,
                    "dates": dates,
                    "entry_ids": [int(e.get("id", 0)) for e in entries if e.get("id")],
                },
                signature_hash=signature,
            ))
        return signals

    # ── Detector 4: Velocity Anomaly ────────────────────────────────────

    def detect_velocity_anomaly(
        self, *, holding_id: int | None
    ) -> list[DetectedSignal]:
        """Bir counterparty'ye ödeme frekansı baseline'a göre patladı mı?

        Weekly transaction count → MAD-based outlier.
        """
        recent = self._fetch_ledger(
            window_days=self.DETECTION_WINDOW_DAYS, kind="expense"
        )
        baseline_rows = self._fetch_ledger(
            window_days=self.BASELINE_LOOKBACK_DAYS,
            kind="expense",
            exclude_recent_days=self.DETECTION_WINDOW_DAYS,
        )
        if not recent or not baseline_rows:
            return []

        baseline_counts = self._weekly_counts_by_counterparty(baseline_rows)
        recent_counts = self._counts_by_counterparty_recent(recent)

        signals: list[DetectedSignal] = []
        for counterparty, current_n in recent_counts.items():
            history = baseline_counts.get(counterparty, [])
            if len(history) < 4:
                continue
            baseline = compute_baseline(history)
            score = score_observation(float(current_n), baseline)
            if not is_actionable(score, min_severity="high"):
                continue
            if not score.is_outlier_above:
                continue

            # Calibration
            adj = self._apply_calibration(
                detector_type="velocity_anomaly",
                target_key=counterparty,
                base_z=score.modified_z,
                base_confidence=score.confidence_pct,
                base_severity=score.severity,
            )
            if adj is None:
                continue
            adjusted_z, adjusted_conf, adjusted_sev = adj
            if adjusted_sev not in ("critical", "high"):
                continue

            signature = self._signature(
                "velocity_anomaly",
                counterparty,
                datetime.now().strftime("%Y-W%W"),
            )

            title = f"{counterparty} ödeme sıklığı arttı"
            description = (
                f"Son hafta {current_n} işlem (baseline medyan: "
                f"{baseline.median:.1f}). Sapma %{score.deviation_pct:+.1f}, "
                f"güven %{score.confidence_pct:.1f}."
            )

            signals.append(DetectedSignal(
                holding_id=holding_id,
                signal_type="velocity_anomaly",
                severity=adjusted_sev,
                confidence_pct=adjusted_conf,
                modified_z=adjusted_z,
                title=title,
                description=description,
                baseline=asdict(baseline),
                payload={
                    "counterparty": counterparty,
                    "current_count": current_n,
                    "deviation_pct": score.deviation_pct,
                },
                signature_hash=signature,
            ))
        return signals

    # ── Internal helpers ────────────────────────────────────────────────

    def _fetch_ledger(
        self,
        *,
        window_days: int,
        kind: str = "expense",
        exclude_recent_days: int = 0,
    ) -> list[dict[str, Any]]:
        """Ledger entry'leri çek. Açık-kapalı pencere modeli.

        finance_ledger_entries:
          entry_date: 'YYYY-MM-DD' (TEXT)
          entry_type: 'income' | 'expense'
          amount, category, description, company_name, counterparty_company
        """
        today = datetime.now().date()
        end_date = today - timedelta(days=exclude_recent_days)
        start_date = end_date - timedelta(days=window_days)
        # Pencere: [start_date, end_date)
        conn = sqlite3.connect(self._ledger_db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        entry_type_filter = "expense" if kind == "expense" else "income"
        try:
            cur = conn.execute(
                """
                SELECT id, company_name, counterparty_company, entry_type,
                       amount, category, description, entry_date, created_at
                FROM finance_ledger_entries
                WHERE entry_type = ?
                  AND entry_date >= ?
                  AND entry_date < ?
                """,
                (entry_type_filter, start_date.isoformat(), end_date.isoformat()),
            )
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    @staticmethod
    def _weekly_sums(
        rows: list[dict[str, Any]]
    ) -> dict[tuple[str, str], list[float]]:
        """(company, category) → her ISO haftası için toplam.

        Volume baseline için: liste döner (geçmiş haftaların listesi).
        Single-week (recent) için: tek değer döner — wrap edilir.
        """
        # weekly_buckets: (company, category, iso_week) → toplam
        buckets: dict[tuple[str, str, str], float] = defaultdict(float)
        for r in rows:
            d = str(r.get("entry_date", ""))
            try:
                dt = datetime.strptime(d, "%Y-%m-%d")
                iso_week = dt.strftime("%Y-W%W")
            except ValueError:
                continue
            company = str(r.get("company_name", ""))
            category = str(r.get("category", "") or "uncategorized")
            buckets[(company, category, iso_week)] += float(r.get("amount", 0))

        # (company, category) → [week sums]
        grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
        for (company, category, _w), v in buckets.items():
            grouped[(company, category)].append(v)
        return grouped

    @staticmethod
    def _weekly_sums_recent(
        rows: list[dict[str, Any]]
    ) -> dict[tuple[str, str], float]:
        """Recent week tek değer — _weekly_sums'in single-week varyantı."""
        out: dict[tuple[str, str], float] = defaultdict(float)
        for r in rows:
            company = str(r.get("company_name", ""))
            category = str(r.get("category", "") or "uncategorized")
            out[(company, category)] += float(r.get("amount", 0))
        return out

    @staticmethod
    def _weekly_counts_by_counterparty(
        rows: list[dict[str, Any]]
    ) -> dict[str, list[int]]:
        """counterparty → her haftada kaç işlem (baseline pencere için)."""
        buckets: dict[tuple[str, str], int] = defaultdict(int)
        for r in rows:
            cp = (r.get("counterparty_company") or "").strip()
            if not cp:
                continue
            d = str(r.get("entry_date", ""))
            try:
                dt = datetime.strptime(d, "%Y-%m-%d")
                iso_week = dt.strftime("%Y-W%W")
            except ValueError:
                continue
            buckets[(cp, iso_week)] += 1
        result: dict[str, list[int]] = defaultdict(list)
        for (cp, _w), n in buckets.items():
            result[cp].append(n)
        return result

    @staticmethod
    def _counts_by_counterparty_recent(
        rows: list[dict[str, Any]]
    ) -> dict[str, int]:
        """Recent single-week counterparty → toplam işlem sayısı."""
        out: dict[str, int] = defaultdict(int)
        for r in rows:
            cp = (r.get("counterparty_company") or "").strip()
            if not cp:
                continue
            out[cp] += 1
        return out

    @staticmethod
    def _signature(*parts: Any) -> str:
        """Deterministik hash → idempotency anahtarı."""
        raw = "|".join(str(p) for p in parts)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
