"""A3: CashflowForecastRepository — model params + cache + accuracy storage."""
from __future__ import annotations

import json
import sqlite3
import time
from threading import Lock
from typing import Any


class CashflowForecastRepository:
    """Per-(user, scope) model persistence + cache."""

    CACHE_TTL_SECONDS = 6 * 3600  # 6 saat — günde 4× yenilenir

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

    # ── Model parametreleri ────────────────────────────────────────────

    def get_model(
        self, *, user_id: str, scope_key: str = "*"
    ) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT alpha, beta, gamma, period_days,
                       last_trained_at, last_mape, train_history_days
                FROM cashflow_forecast_models
                WHERE user_id = ? AND scope_key = ?
                """,
                (user_id, scope_key),
            ).fetchone()
        return dict(row) if row else None

    def upsert_model(
        self,
        *,
        user_id: str,
        scope_key: str,
        alpha: float,
        beta: float,
        gamma: float,
        period_days: int,
        mape: float | None,
        train_history_days: int,
    ) -> None:
        now = int(time.time())
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO cashflow_forecast_models
                    (user_id, scope_key, alpha, beta, gamma, period_days,
                     last_trained_at, last_mape, train_history_days)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, scope_key) DO UPDATE SET
                    alpha = excluded.alpha,
                    beta = excluded.beta,
                    gamma = excluded.gamma,
                    period_days = excluded.period_days,
                    last_trained_at = excluded.last_trained_at,
                    last_mape = excluded.last_mape,
                    train_history_days = excluded.train_history_days
                """,
                (
                    user_id, scope_key, alpha, beta, gamma, period_days,
                    now, mape, train_history_days,
                ),
            )
            self._conn.commit()

    # ── Forecast cache ─────────────────────────────────────────────────

    def get_cache(
        self, *, user_id: str, scope_key: str, horizon_days: int
    ) -> dict[str, Any] | None:
        now = int(time.time())
        with self._lock:
            row = self._conn.execute(
                """
                SELECT forecast_json, generated_at, expires_at
                FROM cashflow_forecast_cache
                WHERE user_id = ? AND scope_key = ? AND horizon_days = ?
                  AND expires_at > ?
                """,
                (user_id, scope_key, horizon_days, now),
            ).fetchone()
        if not row:
            return None
        try:
            return {
                "forecast": json.loads(row["forecast_json"]),
                "generated_at": int(row["generated_at"]),
                "expires_at": int(row["expires_at"]),
            }
        except (json.JSONDecodeError, TypeError):
            return None

    def put_cache(
        self,
        *,
        user_id: str,
        scope_key: str,
        horizon_days: int,
        forecast_json: str,
    ) -> None:
        now = int(time.time())
        expires = now + self.CACHE_TTL_SECONDS
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO cashflow_forecast_cache
                    (user_id, scope_key, horizon_days, forecast_json,
                     generated_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, scope_key, horizon_days) DO UPDATE SET
                    forecast_json = excluded.forecast_json,
                    generated_at = excluded.generated_at,
                    expires_at = excluded.expires_at
                """,
                (
                    user_id, scope_key, horizon_days, forecast_json,
                    now, expires,
                ),
            )
            self._conn.commit()

    def invalidate_cache(self, *, user_id: str, scope_key: str = "*") -> int:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM cashflow_forecast_cache WHERE user_id = ? AND scope_key = ?",
                (user_id, scope_key),
            )
            self._conn.commit()
        return int(cur.rowcount or 0)

    # ── Accuracy tracking ──────────────────────────────────────────────

    def upsert_accuracy(
        self,
        *,
        user_id: str,
        scope_key: str,
        snapshot_date: str,
        mape: float,
        rmse: float,
        test_size: int,
    ) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO cashflow_forecast_accuracy
                    (user_id, scope_key, snapshot_date, mape, rmse, test_size)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, scope_key, snapshot_date) DO UPDATE SET
                    mape = excluded.mape,
                    rmse = excluded.rmse,
                    test_size = excluded.test_size
                """,
                (user_id, scope_key, snapshot_date, mape, rmse, test_size),
            )
            self._conn.commit()

    def record_user_feedback(
        self,
        *,
        user_id: str,
        scope_key: str,
        snapshot_date: str,
        feedback: str,
    ) -> bool:
        """User: 'accurate' | 'misleading'. Engine bunu Bayesian update için kullanır."""
        if feedback not in ("accurate", "misleading"):
            raise ValueError(f"Geçersiz feedback: {feedback}")
        now = int(time.time())
        with self._lock:
            cur = self._conn.execute(
                """
                UPDATE cashflow_forecast_accuracy
                SET user_feedback = ?, user_feedback_at = ?
                WHERE user_id = ? AND scope_key = ? AND snapshot_date = ?
                """,
                (feedback, now, user_id, scope_key, snapshot_date),
            )
            self._conn.commit()
        return cur.rowcount > 0

    def list_accuracy_history(
        self, *, user_id: str, scope_key: str = "*", limit: int = 30
    ) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT snapshot_date, mape, rmse, test_size,
                       user_feedback, user_feedback_at
                FROM cashflow_forecast_accuracy
                WHERE user_id = ? AND scope_key = ?
                ORDER BY snapshot_date DESC
                LIMIT ?
                """,
                (user_id, scope_key, limit),
            ).fetchall()
        return [dict(r) for r in rows]
