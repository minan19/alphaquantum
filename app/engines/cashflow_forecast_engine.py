"""A3: CashflowForecastEngine — adaptive Holt-Winters orkestrasyonu.

## Akış

1. Tarihsel ledger çek (son N gün, daily net flow)
2. Cache hit ise döndür (6h TTL)
3. Yoksa: model parametreleri DB'den oku (yoksa grid_search ile bul + persist)
4. Holt-Winters fit + horizon forecast + bootstrap CI
5. Backtest MAPE'i kaydet → accuracy history
6. Cache'e yaz, response döndür

## Adaptive layer

Kullanıcı "forecast doğru çıktı / yanılttı" feedback verirse:
  * 'accurate' → mevcut (α, β, γ) kalır
  * 'misleading' → bir sonraki çağrıda yeniden grid_search tetiklenir
                   ve last_mape geçici olarak yükseltilir (zorlama re-train)

A2.1 calibration ile aynı paradigma: sistem kullanıcıya özel hassaslaşır.

## LLM narrative (opsiyonel)

AIService varsa, forecast özetinin Türkçe gerekçe metni eklenir
("Önümüzdeki 30g ~245k net pozitif: %60 Mart paterni, %30 son trend...").
G+1 entegrasyonu — yoksa narrative=None.
"""
from __future__ import annotations

import json
import sqlite3
import time
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any

from app.cashflow_forecast_repository import CashflowForecastRepository
from app.forecasting_stats import (
    MIN_HISTORY_DAYS,
    TARGET_MAPE,
    ForecastResult,
    backtest,
    fit_holt_winters,
    forecast_with_ci,
    grid_search_parameters,
)


# ── Sabitler ───────────────────────────────────────────────────────────

DEFAULT_HORIZONS = (30, 60, 90)
LOOKBACK_DAYS = 180          # ~6 ay tarihsel; Holt-Winters için yeterli
WEEKLY_PERIOD = 7
GRID_SEARCH_TEST_SIZE = 14   # 2 hafta validation

# Adaptive: bu kadar gün geçince model yeniden train edilir
MODEL_STALE_DAYS = 7


class CashflowForecastEngine:
    """Adaptive cash flow forecasting."""

    def __init__(
        self,
        *,
        repo: CashflowForecastRepository,
        ledger_db_path: str,
    ) -> None:
        self._repo = repo
        self._ledger_db_path = ledger_db_path

    # ── Public API ─────────────────────────────────────────────────────

    def forecast(
        self,
        *,
        user_id: str,
        horizon_days: int = 30,
        scope_key: str = "*",
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """Kullanıcıya net nakit akışı tahmini döner.

        Output sözleşmesi (frontend tüketimi):
            {
              "horizon_days": int,
              "points": [{day_offset, point_estimate, ci80_low/high, ci95_low/high}],
              "history_used": int,
              "mape": float | None,
              "rmse": float | None,
              "is_reliable": bool,
              "model": {alpha, beta, gamma, period_days, last_trained_at},
              "generated_at": int,
              "cached": bool
            }
        """
        if horizon_days not in DEFAULT_HORIZONS and not (1 <= horizon_days <= 180):
            raise ValueError(f"Geçersiz horizon: {horizon_days}")

        # Cache check
        if not force_refresh:
            cached = self._repo.get_cache(
                user_id=user_id, scope_key=scope_key, horizon_days=horizon_days,
            )
            if cached is not None:
                payload: dict[str, Any] = cached["forecast"]
                payload["cached"] = True
                payload["generated_at"] = cached["generated_at"]
                return payload

        # Tarihsel veri çek
        series = self._fetch_daily_net_flow(user_id=user_id, scope_key=scope_key)
        # All-zero pad'ler "veri yok" demektir — gerçek hareketleri say
        non_zero_days = sum(1 for v in series if v != 0)
        if len(series) < MIN_HISTORY_DAYS or non_zero_days < MIN_HISTORY_DAYS:
            return self._unreliable_response(
                horizon_days=horizon_days,
                history_used=non_zero_days,
                reason="insufficient_history",
            )

        # Model parametreleri — cache'ten oku ya da grid search
        model_params = self._repo.get_model(user_id=user_id, scope_key=scope_key)
        needs_retrain = model_params is None or self._is_stale(model_params)

        if needs_retrain:
            alpha, beta, gamma, train_mape = grid_search_parameters(
                series, period=WEEKLY_PERIOD, test_size=GRID_SEARCH_TEST_SIZE,
            )
            self._repo.upsert_model(
                user_id=user_id, scope_key=scope_key,
                alpha=alpha, beta=beta, gamma=gamma,
                period_days=WEEKLY_PERIOD,
                mape=train_mape if train_mape != float("inf") else None,
                train_history_days=len(series),
            )
        else:
            assert model_params is not None  # narrowed by needs_retrain
            alpha = float(model_params["alpha"])
            beta = float(model_params["beta"])
            gamma = float(model_params["gamma"])
            train_mape = (
                float(model_params["last_mape"])
                if model_params.get("last_mape") is not None
                else float("inf")
            )

        # Fit + forecast
        model = fit_holt_winters(
            series, period=WEEKLY_PERIOD,
            alpha=alpha, beta=beta, gamma=gamma,
        )
        points = forecast_with_ci(
            model, horizon=horizon_days, history_n=len(series),
        )

        # Out-of-sample backtest — son 14 günü test seti olarak değerlendir
        bt = backtest(
            series, period=WEEKLY_PERIOD, test_size=min(14, len(series) // 4),
            alpha=alpha, beta=beta, gamma=gamma,
        )
        if bt.mape != float("inf"):
            today = datetime.now().strftime("%Y-%m-%d")
            self._repo.upsert_accuracy(
                user_id=user_id, scope_key=scope_key,
                snapshot_date=today, mape=bt.mape, rmse=bt.rmse,
                test_size=bt.test_size,
            )

        # Reliable mi?
        is_reliable = (
            len(series) >= MIN_HISTORY_DAYS * 2
            and bt.mape != float("inf")
            and bt.mape < TARGET_MAPE * 2  # esnek; %30 altı kabul
        )

        result = ForecastResult(
            horizon_days=horizon_days,
            points=points,
            model_components=model,
            mape=bt.mape if bt.mape != float("inf") else None,
            rmse=bt.rmse if bt.rmse != float("inf") else None,
            history_used=len(series),
            is_reliable=is_reliable,
        )
        payload = self._serialize_result(result, alpha, beta, gamma)
        payload["cached"] = False
        # Persist cache
        self._repo.put_cache(
            user_id=user_id, scope_key=scope_key,
            horizon_days=horizon_days,
            forecast_json=json.dumps(payload, ensure_ascii=False, default=str),
        )
        return payload

    def record_feedback(
        self,
        *,
        user_id: str,
        snapshot_date: str,
        feedback: str,
        scope_key: str = "*",
    ) -> bool:
        """User: 'accurate' | 'misleading'. Misleading → cache + model invalidate."""
        ok = self._repo.record_user_feedback(
            user_id=user_id, scope_key=scope_key,
            snapshot_date=snapshot_date, feedback=feedback,
        )
        if ok and feedback == "misleading":
            # Force re-train at next call
            model = self._repo.get_model(user_id=user_id, scope_key=scope_key)
            if model is not None:
                # MAPE'yi sun'i yükselt → _is_stale true olur, retrain tetiklenir
                self._repo.upsert_model(
                    user_id=user_id, scope_key=scope_key,
                    alpha=float(model["alpha"]),
                    beta=float(model["beta"]),
                    gamma=float(model["gamma"]),
                    period_days=int(model["period_days"]),
                    mape=99.0,
                    train_history_days=int(model["train_history_days"]),
                )
            self._repo.invalidate_cache(user_id=user_id, scope_key=scope_key)
        return ok

    def accuracy_history(
        self, *, user_id: str, scope_key: str = "*", limit: int = 30,
    ) -> list[dict[str, Any]]:
        return self._repo.list_accuracy_history(
            user_id=user_id, scope_key=scope_key, limit=limit,
        )

    # ── Internals ──────────────────────────────────────────────────────

    @staticmethod
    def _is_stale(model_params: dict[str, Any]) -> bool:
        """Model 7 günden eskiyse veya MAPE > 25% ise re-train gerekli."""
        last_trained = int(model_params.get("last_trained_at", 0))
        age_days = (int(time.time()) - last_trained) / 86400
        mape = model_params.get("last_mape")
        return (
            age_days > MODEL_STALE_DAYS
            or (mape is not None and float(mape) > 25.0)
        )

    def _fetch_daily_net_flow(
        self, *, user_id: str, scope_key: str
    ) -> list[float]:
        """Son LOOKBACK_DAYS gün için günlük net (income - expense) flow.

        scope_key '*': tüm şirketler.
        scope_key 'AcmeCo': bir şirket.
        scope_key 'AcmeCo::sales': şirket + kategori.

        Note: kullanıcı bazlı multi-tenant scope için identity/permission
        katmanı router seviyesinde uygular; engine ham ledger okur.
        """
        today = datetime.now().date()
        start_date = today - timedelta(days=LOOKBACK_DAYS)
        end_date = today

        company_filter, category_filter = self._parse_scope(scope_key)

        sql = """
            SELECT entry_date, entry_type, SUM(amount) AS total
            FROM finance_ledger_entries
            WHERE entry_date >= ? AND entry_date < ?
        """
        params: list[Any] = [start_date.isoformat(), end_date.isoformat()]
        if company_filter:
            sql += " AND company_name = ?"
            params.append(company_filter)
        if category_filter:
            sql += " AND category = ?"
            params.append(category_filter)
        sql += " GROUP BY entry_date, entry_type ORDER BY entry_date ASC"

        conn = sqlite3.connect(self._ledger_db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(sql, tuple(params)).fetchall()
        finally:
            conn.close()

        # Günlük net flow hesabı
        daily: dict[str, float] = defaultdict(float)
        for r in rows:
            sign = 1.0 if r["entry_type"] == "income" else -1.0
            daily[str(r["entry_date"])] += sign * float(r["total"])

        # Eksik günleri 0 ile doldur — sürekli zaman serisi
        series: list[float] = []
        d = start_date
        while d < end_date:
            series.append(daily.get(d.isoformat(), 0.0))
            d += timedelta(days=1)
        return series

    @staticmethod
    def _parse_scope(scope_key: str) -> tuple[str | None, str | None]:
        if scope_key == "*":
            return None, None
        if "::" in scope_key:
            parts = scope_key.split("::", 1)
            return parts[0] or None, parts[1] or None
        return scope_key, None

    @staticmethod
    def _serialize_result(
        result: ForecastResult,
        alpha: float,
        beta: float,
        gamma: float,
    ) -> dict[str, Any]:
        return {
            "horizon_days": result.horizon_days,
            "points": [asdict(p) for p in result.points],
            "history_used": result.history_used,
            "mape": result.mape,
            "rmse": result.rmse,
            "is_reliable": result.is_reliable,
            "model": {
                "alpha": alpha,
                "beta": beta,
                "gamma": gamma,
                "period_days": result.model_components.period,
                "level": result.model_components.level,
                "trend": result.model_components.trend,
            },
            "generated_at": int(time.time()),
        }

    @staticmethod
    def _unreliable_response(
        *, horizon_days: int, history_used: int, reason: str,
    ) -> dict[str, Any]:
        return {
            "horizon_days": horizon_days,
            "points": [],
            "history_used": history_used,
            "mape": None,
            "rmse": None,
            "is_reliable": False,
            "model": None,
            "generated_at": int(time.time()),
            "cached": False,
            "unreliable_reason": reason,
        }
