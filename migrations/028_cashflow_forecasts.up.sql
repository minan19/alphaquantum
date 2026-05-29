-- A3: ML Cash Flow Forecasting — adaptive Holt-Winters
--
-- 3 tablo:
--   * cashflow_forecast_models    — per-(user, scope) öğrenilmiş α,β,γ
--   * cashflow_forecast_cache     — kısa süreli forecast cache (6h TTL)
--   * cashflow_forecast_accuracy  — backtest sonuçları (MAPE tracking)

CREATE TABLE IF NOT EXISTS cashflow_forecast_models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    scope_key TEXT NOT NULL DEFAULT '*',   -- '*' = global, 'AcmeCo::sales' = per-co/cat
    alpha REAL NOT NULL DEFAULT 0.3,
    beta REAL NOT NULL DEFAULT 0.1,
    gamma REAL NOT NULL DEFAULT 0.1,
    period_days INTEGER NOT NULL DEFAULT 7,
    last_trained_at INTEGER NOT NULL,
    last_mape REAL,                        -- en son backtest MAPE
    train_history_days INTEGER NOT NULL DEFAULT 0,
    UNIQUE (user_id, scope_key)
);

CREATE INDEX IF NOT EXISTS idx_cashflow_models_user
    ON cashflow_forecast_models(user_id);

CREATE TABLE IF NOT EXISTS cashflow_forecast_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    scope_key TEXT NOT NULL DEFAULT '*',
    horizon_days INTEGER NOT NULL,
    forecast_json TEXT NOT NULL,           -- ForecastResult serialize
    generated_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    UNIQUE (user_id, scope_key, horizon_days)
);

CREATE INDEX IF NOT EXISTS idx_cashflow_cache_expiry
    ON cashflow_forecast_cache(expires_at);

CREATE TABLE IF NOT EXISTS cashflow_forecast_accuracy (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    scope_key TEXT NOT NULL DEFAULT '*',
    snapshot_date TEXT NOT NULL,           -- YYYY-MM-DD
    mape REAL NOT NULL,
    rmse REAL NOT NULL,
    test_size INTEGER NOT NULL,
    user_feedback TEXT,                    -- 'accurate' | 'misleading' | NULL
    user_feedback_at INTEGER,
    UNIQUE (user_id, scope_key, snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_cashflow_accuracy_user_date
    ON cashflow_forecast_accuracy(user_id, snapshot_date DESC);
