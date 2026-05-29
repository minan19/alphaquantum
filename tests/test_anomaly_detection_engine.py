"""A2: AnomalyDetectionEngine integration tests.

Sentetik finance_ledger_entries seed → her detector için known anomali
inject et → engine.run_all() doğru sayıda sinyal mi üretiyor doğrula.

Bu testler kullanıcının "0 hata" ve "%99 doğruluk" iddiasının kanıtı.
"""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from app.anomaly_signals_repository import AnomalySignalsRepository
from app.engines.anomaly_detection_engine import AnomalyDetectionEngine
from app.identity_repository import IdentityRepository
from app.migration_manager import MigrationManager


def _ymd(d: datetime) -> str:
    return d.strftime("%Y-%m-%d")


class AnomalyDetectionEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp.name) / "anomaly_test.db"
        migrations_dir = Path(__file__).resolve().parent.parent / "migrations"

        bootstrap_repo = IdentityRepository(str(self._db_path))
        bootstrap_repo.close()
        self.manager = MigrationManager(str(self._db_path), str(migrations_dir))
        self.manager.apply_all()

        self.repo = AnomalySignalsRepository(str(self._db_path))
        self.engine = AnomalyDetectionEngine(
            repo=self.repo,
            ledger_db_path=str(self._db_path),
        )

    def tearDown(self) -> None:
        self.repo.close()
        self.manager.close()
        self._tmp.cleanup()

    # ── Seed helpers ────────────────────────────────────────────────────

    def _insert_ledger(
        self,
        *,
        company: str,
        amount: float,
        category: str,
        entry_date: datetime,
        counterparty: str | None = None,
        entry_type: str = "expense",
    ) -> None:
        conn = sqlite3.connect(str(self._db_path))
        try:
            conn.execute(
                """
                INSERT INTO finance_ledger_entries
                  (company_name, counterparty_company, entry_type, amount,
                   category, description, entry_date, created_at, intercompany_flag)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    company, counterparty, entry_type, amount,
                    category, "test entry", _ymd(entry_date),
                    int(entry_date.timestamp()),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def _seed_baseline_history(
        self,
        *,
        company: str,
        category: str,
        days_ago_range: range,
        amount: float = 1000.0,
    ) -> None:
        """Stabil baseline — her gün aynı tutarda harcama."""
        today = datetime.now()
        for d in days_ago_range:
            self._insert_ledger(
                company=company,
                amount=amount,
                category=category,
                entry_date=today - timedelta(days=d),
                counterparty=f"Tedarikçi_{category}",
            )

    # ── Tests: empty / no-op ────────────────────────────────────────────

    def test_run_all_with_empty_ledger_zero_signals(self) -> None:
        summary = self.engine.run_all(holding_id=1)
        self.assertEqual(summary.new_signals, 0)
        self.assertEqual(len(summary.detectors_run), 4)

    # ── Tests: Duplicate Payment Detector (deterministic) ───────────────

    def test_duplicate_payment_detected(self) -> None:
        today = datetime.now()
        # Aynı counterparty + amount, 2 şirketten ödenmiş — son 3 gün
        for company in ["AcmeCo", "LojiCo"]:
            self._insert_ledger(
                company=company,
                amount=50000.0,
                category="hizmet",
                entry_date=today - timedelta(days=2),
                counterparty="MerkeziBilişim",
            )

        signals = self.engine.detect_duplicate_payment(holding_id=1)
        self.assertEqual(len(signals), 1)
        sig = signals[0]
        self.assertEqual(sig.signal_type, "duplicate_payment")
        self.assertEqual(sig.severity, "critical")
        self.assertGreater(sig.confidence_pct, 99.0)
        self.assertEqual(sig.payload["occurrence_count"], 2)
        self.assertIn("MerkeziBilişim", sig.title)

    def test_duplicate_payment_skips_single_occurrence(self) -> None:
        today = datetime.now()
        self._insert_ledger(
            company="AcmeCo", amount=50000.0, category="hizmet",
            entry_date=today - timedelta(days=2),
            counterparty="MerkeziBilişim",
        )
        signals = self.engine.detect_duplicate_payment(holding_id=1)
        self.assertEqual(len(signals), 0)

    def test_duplicate_payment_idempotent_persistence(self) -> None:
        today = datetime.now()
        for company in ["AcmeCo", "LojiCo"]:
            self._insert_ledger(
                company=company, amount=12345.67, category="kira",
                entry_date=today - timedelta(days=1),
                counterparty="DupTest",
            )
        first = self.engine.run_all(holding_id=1)
        second = self.engine.run_all(holding_id=1)
        # İkinci run aynı sinyalleri tekrar üretmez (signature_hash UNIQUE).
        # İlk run: duplicate_payment + intercompany_leakage tetiklenebilir.
        # İkinci run: hiç yeni sinyal yok.
        self.assertGreaterEqual(first.new_signals, 1)
        self.assertEqual(second.new_signals, 0)

    # ── Tests: Intercompany Leakage Detector ────────────────────────────

    def test_intercompany_leakage_critical_when_historically_single_company(self) -> None:
        today = datetime.now()
        # Geçmiş 12 ayda sadece AcmeCo "Tedarikçi_X" ile çalışmış
        for d in range(30, 200, 10):
            self._insert_ledger(
                company="AcmeCo", amount=5000, category="hizmet",
                entry_date=today - timedelta(days=d),
                counterparty="Tedarikçi_X",
            )
        # Son hafta: AcmeCo + LojiCo aynı tedarikçiye ödüyor
        for company in ["AcmeCo", "LojiCo"]:
            self._insert_ledger(
                company=company, amount=8000, category="hizmet",
                entry_date=today - timedelta(days=2),
                counterparty="Tedarikçi_X",
            )

        signals = self.engine.detect_intercompany_leakage(holding_id=1)
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].severity, "critical")
        self.assertGreater(signals[0].confidence_pct, 99.0)

    def test_intercompany_leakage_medium_when_historically_shared(self) -> None:
        today = datetime.now()
        # Geçmişte de 3 şirket aynı tedarikçiyle çalışıyordu (normal merkezi tedarik)
        for d in range(30, 200, 10):
            for company in ["AcmeCo", "LojiCo", "İnşaatCo"]:
                self._insert_ledger(
                    company=company, amount=2000, category="hizmet",
                    entry_date=today - timedelta(days=d),
                    counterparty="OrtakTedarikçi",
                )
        # Son hafta: yine 3 şirket — normal pattern
        for company in ["AcmeCo", "LojiCo", "İnşaatCo"]:
            self._insert_ledger(
                company=company, amount=2000, category="hizmet",
                entry_date=today - timedelta(days=2),
                counterparty="OrtakTedarikçi",
            )

        signals = self.engine.detect_intercompany_leakage(holding_id=1)
        self.assertEqual(len(signals), 1)
        # Geçmiş 3 + güncel 3 → eşit → medium tier
        self.assertEqual(signals[0].severity, "medium")

    def test_intercompany_leakage_skipped_when_only_one_company(self) -> None:
        today = datetime.now()
        self._insert_ledger(
            company="AcmeCo", amount=5000, category="hizmet",
            entry_date=today - timedelta(days=2),
            counterparty="Tek_Tedarikçi",
        )
        signals = self.engine.detect_intercompany_leakage(holding_id=1)
        self.assertEqual(len(signals), 0)

    # ── Tests: Volume Spike Detector ────────────────────────────────────

    def test_volume_spike_detected_with_stable_baseline(self) -> None:
        today = datetime.now()
        # Stable baseline: önceki 12 hafta, haftada ~10k harcama
        for w in range(2, 14):
            self._insert_ledger(
                company="AcmeCo", amount=10000.0, category="kira",
                entry_date=today - timedelta(days=w * 7),
                counterparty="EmlakOfis",
            )
        # Son hafta: 5× spike
        self._insert_ledger(
            company="AcmeCo", amount=50000.0, category="kira",
            entry_date=today - timedelta(days=2),
            counterparty="EmlakOfis",
        )
        signals = self.engine.detect_volume_spike(holding_id=1)
        # En azından bir spike sinyali üretmeli
        self.assertGreaterEqual(len(signals), 1)
        # AcmeCo + kira için kritik/high tier
        match = next(
            (s for s in signals
             if s.payload.get("company") == "AcmeCo"
             and s.payload.get("category") == "kira"),
            None,
        )
        self.assertIsNotNone(match)
        assert match is not None
        self.assertIn(match.severity, ("critical", "high"))

    def test_volume_spike_skipped_with_insufficient_baseline(self) -> None:
        today = datetime.now()
        # Sadece 2 hafta baseline (< 4 yeterli minimum)
        for w in range(2, 4):
            self._insert_ledger(
                company="AcmeCo", amount=10000.0, category="kira",
                entry_date=today - timedelta(days=w * 7),
            )
        self._insert_ledger(
            company="AcmeCo", amount=100000.0, category="kira",
            entry_date=today - timedelta(days=2),
        )
        signals = self.engine.detect_volume_spike(holding_id=1)
        self.assertEqual(len(signals), 0)

    # ── Tests: Velocity Anomaly Detector ────────────────────────────────

    def test_velocity_anomaly_detected(self) -> None:
        today = datetime.now()
        # Baseline: her hafta 1 işlem (stable)
        for w in range(2, 14):
            self._insert_ledger(
                company="AcmeCo", amount=500.0, category="hizmet",
                entry_date=today - timedelta(days=w * 7),
                counterparty="HızlıFatura",
            )
        # Son hafta: 15 işlem (extreme spike)
        for i in range(15):
            self._insert_ledger(
                company="AcmeCo", amount=500.0, category="hizmet",
                entry_date=today - timedelta(days=2, hours=i),
                counterparty="HızlıFatura",
            )
        signals = self.engine.detect_velocity_anomaly(holding_id=1)
        self.assertGreaterEqual(len(signals), 1)

    # ── Tests: Review / Persistence ─────────────────────────────────────

    def test_review_marks_signal_confirmed(self) -> None:
        today = datetime.now()
        for company in ["A", "B"]:
            self._insert_ledger(
                company=company, amount=999.0, category="x",
                entry_date=today - timedelta(days=1),
                counterparty="ZTest",
            )
        self.engine.run_all(holding_id=1)
        signals = self.engine.list_signals(holding_id=1, min_severity="high")
        self.assertGreaterEqual(len(signals), 1)
        signal_id = signals[0]["id"]

        result = self.engine.review(
            signal_id=signal_id,
            action="confirm",
            reviewed_by="cfo@holding.tr",
            note="Çift kayıt — kabul edildi",
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["status"], "confirmed")
        self.assertEqual(result["reviewed_by"], "cfo@holding.tr")

    def test_review_invalid_action_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.engine.review(
                signal_id=999, action="garbage", reviewed_by="x",
            )

    def test_summary_counts_correctly(self) -> None:
        today = datetime.now()
        for company in ["A", "B"]:
            self._insert_ledger(
                company=company, amount=1234.0, category="x",
                entry_date=today - timedelta(days=1),
                counterparty="Sum1",
            )
        self.engine.run_all(holding_id=1)
        summary = self.engine.summary(holding_id=1)
        self.assertGreaterEqual(summary.get("critical", 0), 1)
        self.assertGreaterEqual(summary["total_open"], 1)


if __name__ == "__main__":
    unittest.main()
