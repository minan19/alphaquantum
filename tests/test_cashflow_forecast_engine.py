"""A3: CashflowForecastEngine integration tests.

Sentetik ledger entries seed → engine.forecast() çağır → output sözleşmesi
+ cache + feedback round-trip doğrula.
"""
from __future__ import annotations

import math
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from app.cashflow_forecast_repository import CashflowForecastRepository
from app.engines.cashflow_forecast_engine import CashflowForecastEngine
from app.identity_repository import IdentityRepository
from app.migration_manager import MigrationManager


def _ymd(d: datetime) -> str:
    return d.strftime("%Y-%m-%d")


class CashflowForecastEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp.name) / "forecast_test.db"
        migrations_dir = Path(__file__).resolve().parent.parent / "migrations"

        bootstrap = IdentityRepository(str(self._db_path))
        bootstrap.close()
        self.manager = MigrationManager(str(self._db_path), str(migrations_dir))
        self.manager.apply_all()

        self.repo = CashflowForecastRepository(str(self._db_path))
        self.engine = CashflowForecastEngine(
            repo=self.repo, ledger_db_path=str(self._db_path),
        )

    def tearDown(self) -> None:
        self.repo.close()
        self.manager.close()
        self._tmp.cleanup()

    # ── Seed helpers ────────────────────────────────────────────────────

    def _insert(
        self,
        *,
        company: str = "AcmeCo",
        amount: float,
        entry_type: str,
        entry_date: datetime,
        category: str = "general",
    ) -> None:
        conn = sqlite3.connect(str(self._db_path))
        try:
            conn.execute(
                """
                INSERT INTO finance_ledger_entries
                  (company_name, entry_type, amount, category, description,
                   entry_date, created_at, intercompany_flag)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    company, entry_type, amount, category, "seed",
                    _ymd(entry_date), int(entry_date.timestamp()),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def _seed_stable_history(
        self,
        *,
        company: str = "AcmeCo",
        days: int = 60,
        base_income: float = 5000,
        base_expense: float = 3000,
        weekly_amplitude: float = 500,
    ) -> None:
        """Trend + weekly seasonality ledger seed."""
        today = datetime.now()
        for d in range(days):
            offset_date = today - timedelta(days=d)
            seasonal = weekly_amplitude * math.sin(2 * math.pi * d / 7)
            self._insert(
                company=company,
                amount=base_income + seasonal,
                entry_type="income",
                entry_date=offset_date,
            )
            self._insert(
                company=company,
                amount=base_expense,
                entry_type="expense",
                entry_date=offset_date,
            )

    # ── Tests: empty / insufficient ────────────────────────────────────

    def test_forecast_unreliable_with_no_history(self) -> None:
        result = self.engine.forecast(user_id="u1", horizon_days=30)
        self.assertFalse(result["is_reliable"])
        self.assertEqual(result["points"], [])
        self.assertEqual(result.get("unreliable_reason"), "insufficient_history")

    def test_forecast_unreliable_with_few_days(self) -> None:
        today = datetime.now()
        for d in range(5):
            self._insert(
                amount=1000, entry_type="income",
                entry_date=today - timedelta(days=d),
            )
        result = self.engine.forecast(user_id="u2", horizon_days=30)
        self.assertFalse(result["is_reliable"])

    # ── Tests: forecast happy path ─────────────────────────────────────

    def test_forecast_returns_horizon_points(self) -> None:
        self._seed_stable_history(days=90)
        result = self.engine.forecast(user_id="u3", horizon_days=30)
        self.assertEqual(len(result["points"]), 30)
        self.assertTrue(result["is_reliable"])

    def test_forecast_points_have_ci_bands(self) -> None:
        self._seed_stable_history(days=90)
        result = self.engine.forecast(user_id="u4", horizon_days=14)
        for p in result["points"]:
            self.assertLessEqual(p["ci95_low"], p["ci80_low"])
            self.assertLessEqual(p["ci80_low"], p["point_estimate"])
            self.assertLessEqual(p["point_estimate"], p["ci80_high"])
            self.assertLessEqual(p["ci80_high"], p["ci95_high"])

    def test_forecast_model_metadata_returned(self) -> None:
        self._seed_stable_history(days=90)
        result = self.engine.forecast(user_id="u5", horizon_days=30)
        self.assertIsNotNone(result["model"])
        self.assertGreaterEqual(result["model"]["alpha"], 0)
        self.assertLessEqual(result["model"]["alpha"], 1)
        self.assertEqual(result["model"]["period_days"], 7)

    # ── Tests: cache ────────────────────────────────────────────────────

    def test_second_call_returns_cached(self) -> None:
        self._seed_stable_history(days=90)
        first = self.engine.forecast(user_id="cacheU", horizon_days=30)
        second = self.engine.forecast(user_id="cacheU", horizon_days=30)
        self.assertFalse(first["cached"])
        self.assertTrue(second["cached"])

    def test_force_refresh_bypasses_cache(self) -> None:
        self._seed_stable_history(days=90)
        self.engine.forecast(user_id="forceU", horizon_days=30)
        refreshed = self.engine.forecast(
            user_id="forceU", horizon_days=30, force_refresh=True,
        )
        self.assertFalse(refreshed["cached"])

    # ── Tests: feedback loop ────────────────────────────────────────────

    def test_misleading_feedback_invalidates_cache(self) -> None:
        self._seed_stable_history(days=90)
        # İlk forecast — accuracy entry de yazılır
        result = self.engine.forecast(user_id="fbU", horizon_days=30)
        # Accuracy snapshot kullanılarak feedback ver
        today = datetime.now().strftime("%Y-%m-%d")
        ok = self.engine.record_feedback(
            user_id="fbU", snapshot_date=today, feedback="misleading",
        )
        self.assertTrue(ok)
        # Bir sonraki çağrı cache miss olmalı
        next_result = self.engine.forecast(user_id="fbU", horizon_days=30)
        self.assertFalse(next_result["cached"])
        _ = result  # used

    def test_accurate_feedback_records(self) -> None:
        self._seed_stable_history(days=90)
        self.engine.forecast(user_id="okU", horizon_days=30)
        today = datetime.now().strftime("%Y-%m-%d")
        ok = self.engine.record_feedback(
            user_id="okU", snapshot_date=today, feedback="accurate",
        )
        self.assertTrue(ok)
        history = self.engine.accuracy_history(user_id="okU")
        self.assertGreaterEqual(len(history), 1)
        self.assertEqual(history[0]["user_feedback"], "accurate")

    def test_invalid_feedback_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.engine.record_feedback(
                user_id="x", snapshot_date="2026-01-01", feedback="garbage",
            )

    # ── Tests: scope filtering ──────────────────────────────────────────

    def test_scope_company_filter_isolates_data(self) -> None:
        today = datetime.now()
        for d in range(30):
            self._insert(
                company="AcmeCo", amount=10000, entry_type="income",
                entry_date=today - timedelta(days=d),
            )
            self._insert(
                company="LojiCo", amount=500, entry_type="income",
                entry_date=today - timedelta(days=d),
            )
        global_result = self.engine.forecast(user_id="scope1", horizon_days=14, scope_key="*")
        acme_result = self.engine.forecast(user_id="scope1", horizon_days=14, scope_key="AcmeCo")
        # AcmeCo'nun forecast'i global'den küçük olmalı (sadece bir şirket)
        global_avg = sum(p["point_estimate"] for p in global_result["points"]) / 14
        acme_avg = sum(p["point_estimate"] for p in acme_result["points"]) / 14
        # Global > Acme (Acme + Loji toplam, Acme tek başına)
        # Acme 10000, Loji 500 → global avg ≈ 10500, Acme avg ≈ 10000
        self.assertGreater(global_avg, acme_avg)

    # ── Tests: invalid input ────────────────────────────────────────────

    def test_horizon_zero_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.engine.forecast(user_id="z", horizon_days=0)

    def test_horizon_too_large_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.engine.forecast(user_id="z", horizon_days=500)


if __name__ == "__main__":
    unittest.main()
