"""VR1: Vendor Risk Scoring Engine.

## Felsefe

Türkiye B2B'de en pahalı hata: iflas etmek üzere olan tedarikçiye
büyük ön ödeme. SP/Ariba/Coupa paradigm + GİB/KKB mock skorlama
ile risk önceden tespit.

## Risk Skorlama Faktörleri

  * VKN format validation (gerçek 10 hane VKN modulo check)
  * Mock GİB query: mükellef aktif mi, vergi numarası faal mi
  * Mock KKB query: kredi notu (synthesized deterministic VKN'den)
  * Internal ledger history: 6 ay ödeme paterni
  * Anomaly history: bu tedarikçi için A2 sinyal var mı

## Skor

0-100 → low/medium/high/critical
  * 0-25  → critical (ödeme yapma!)
  * 26-50 → high
  * 51-75 → medium
  * 76-100 → low (güvenli)

## Mock sources

GİB ve KKB resmi API'lerine gerçek erişim için anlaşma gerekli;
bu sprint deterministic mock'larla skor üretir, API contract'ı
kurar. Production'da mock → real swap edilir.
"""
from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class VendorRiskScore:
    vkn: str
    composite_score: int       # 0-100
    severity: str              # low/medium/high/critical
    is_taxpayer_active: bool   # GİB mock
    credit_rating: str         # KKB mock: AAA-D
    internal_payment_history_score: int  # 0-100, son 6 ay ledger paterni
    anomaly_signal_count: int  # A2'den
    recommendations: list[str] = field(default_factory=list)


class VendorRiskEngine:
    """Vendor risk scoring + recommendations."""

    def __init__(self, *, database_path: str) -> None:
        self._database_path = database_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._database_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    # ── Public API ─────────────────────────────────────────────────────

    def score_vendor(
        self,
        *,
        vkn: str,
        counterparty_name: str | None = None,
    ) -> VendorRiskScore:
        """Tedarikçi risk skoru hesapla.

        Mock kaynaklardan (GİB/KKB) deterministic skor çıkarır + ledger
        history + anomaly history ile composite skor üretir.
        """
        clean_vkn = self._clean_vkn(vkn)
        if not self._validate_vkn(clean_vkn):
            raise ValueError(f"Geçersiz VKN: {vkn!r}")

        # 1. GİB mock query
        is_active = self._mock_gib_query(clean_vkn)

        # 2. KKB mock query — credit rating
        rating, rating_score = self._mock_kkb_query(clean_vkn)

        # 3. Internal: ledger payment history
        ledger_score = self._compute_ledger_score(
            counterparty_name=counterparty_name or "", vkn=clean_vkn,
        )

        # 4. Internal: anomaly signals
        anomaly_count = self._count_anomalies(counterparty_name or "")

        # Composite skor: weighted average
        # GİB 25%, KKB 35%, Ledger 25%, Anomaly 15%
        gib_w = 100 if is_active else 0
        anomaly_w = max(0, 100 - anomaly_count * 25)  # her 1 anomaly -25
        composite = int(
            gib_w * 0.25
            + rating_score * 0.35
            + ledger_score * 0.25
            + anomaly_w * 0.15
        )

        severity = self._severity_from_score(composite)
        recommendations = self._build_recommendations(
            composite=composite, is_active=is_active,
            rating=rating, ledger_score=ledger_score,
            anomaly_count=anomaly_count,
        )

        return VendorRiskScore(
            vkn=clean_vkn,
            composite_score=composite,
            severity=severity,
            is_taxpayer_active=is_active,
            credit_rating=rating,
            internal_payment_history_score=ledger_score,
            anomaly_signal_count=anomaly_count,
            recommendations=recommendations,
        )

    # ── VKN validation ─────────────────────────────────────────────────

    @staticmethod
    def _clean_vkn(raw: str) -> str:
        import re
        return re.sub(r"\D", "", raw or "")

    @staticmethod
    def _validate_vkn(vkn: str) -> bool:
        """VKN 10 hane + checksum validation.

        Türkiye VKN algoritma: son hane diğer 9 hanenin özel formülünden
        türetilen kontrol hanesi. Bu mock için sadece 10 hane + non-zero
        first check.
        """
        if len(vkn) != 10 or not vkn.isdigit():
            return False
        # İlk hane 0 olabilir; tamamı 0 olamaz (00000... geçersiz)
        if vkn == "0" * 10:
            return False
        return True

    # ── Mock external queries (deterministic) ──────────────────────────

    @staticmethod
    def _mock_gib_query(vkn: str) -> bool:
        """GİB mükellef aktif mi (deterministic mock).

        VKN'nin son hanesinin hash'inden türetilir. Production'da
        gerçek GİB Mükellef Sorgulama API'siyle değiştirilir.
        """
        h = hashlib.sha256(vkn.encode()).digest()
        # %85 aktif, %15 inactive (sentetik dağılım)
        return (h[0] % 100) < 85

    @staticmethod
    def _mock_kkb_query(vkn: str) -> tuple[str, int]:
        """KKB kredi notu (mock).

        Returns: (rating_string, score_0_to_100)
        """
        h = hashlib.sha256(vkn.encode()).digest()
        # Bucket'lara böl: AAA(90+), AA(80-89), A(70-79), BBB(60-69),
        # BB(50-59), B(40-49), CCC(30-39), CC(20-29), C(10-19), D(0-9)
        score = h[0] % 100
        if score >= 90:
            return "AAA", score
        if score >= 80:
            return "AA", score
        if score >= 70:
            return "A", score
        if score >= 60:
            return "BBB", score
        if score >= 50:
            return "BB", score
        if score >= 40:
            return "B", score
        if score >= 30:
            return "CCC", score
        if score >= 20:
            return "CC", score
        if score >= 10:
            return "C", score
        return "D", score

    # ── Internal data ─────────────────────────────────────────────────

    def _compute_ledger_score(
        self, *, counterparty_name: str, vkn: str,
    ) -> int:
        """Son 6 ay ödeme paterni: regular + zamanında → 100,
        düzensiz veya yok → 50, hiç → 75 (neutral)."""
        if not counterparty_name:
            return 75  # neutral
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT COUNT(*) AS n, COUNT(DISTINCT entry_date) AS uniq_days
                FROM finance_ledger_entries
                WHERE counterparty_company = ?
                  AND entry_date >= date('now', '-6 months')
                """,
                (counterparty_name,),
            ).fetchone()
        finally:
            conn.close()
        if not row or int(row["n"]) == 0:
            return 75
        n = int(row["n"])
        uniq_days = int(row["uniq_days"])
        # n high + uniq days yüksek → düzenli ödeme → yüksek skor
        if n >= 12 and uniq_days >= 6:
            return 100
        if n >= 6:
            return 80
        if n >= 3:
            return 65
        return 50

    def _count_anomalies(self, counterparty_name: str) -> int:
        if not counterparty_name:
            return 0
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT COUNT(*) AS n FROM anomaly_signals
                WHERE status = 'open'
                  AND payload_json LIKE ?
                """,
                (f"%{counterparty_name}%",),
            ).fetchone()
            return int(row["n"]) if row else 0
        finally:
            conn.close()

    # ── Severity + recommendations ─────────────────────────────────────

    @staticmethod
    def _severity_from_score(score: int) -> str:
        if score >= 76:
            return "low"
        if score >= 51:
            return "medium"
        if score >= 26:
            return "high"
        return "critical"

    @staticmethod
    def _build_recommendations(
        *,
        composite: int,
        is_active: bool,
        rating: str,
        ledger_score: int,
        anomaly_count: int,
    ) -> list[str]:
        recs: list[str] = []
        if not is_active:
            recs.append(
                "⚠️ GİB'de aktif mükellef değil — vergi numarasını doğrula"
            )
        if rating in ("D", "C", "CC", "CCC"):
            recs.append(
                f"🚨 KKB kredi notu düşük ({rating}) — ön ödeme tavsiye edilmez"
            )
        if ledger_score < 60:
            recs.append(
                "📉 Geçmiş ödeme paterni düzensiz — küçük partilerle başla"
            )
        if anomaly_count > 0:
            recs.append(
                f"🔍 {anomaly_count} aktif anomali sinyali var — incele"
            )
        if composite >= 76:
            recs.append("✅ Düşük risk — standart ödeme koşulları uygulanabilir")
        elif composite < 26:
            recs.append("⛔ Kritik risk — yeni iş ilişkisi başlatma")
        return recs
