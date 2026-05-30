-- A2.1: Adaptive Calibration — anomaly detection'ın kendini öğrenmesi
--
-- 3 tablo:
--   * anomaly_detector_calibration   — per-target Bayesian stats
--   * anomaly_pattern_whitelist      — kullanıcı "bu normaldir" demiş paternler
--   * anomaly_detector_metrics_daily — günlük precision snapshot (trend için)
--
-- Tasarım ilkesi: tüm güncellemeler atomik, her sinyal kararı için
-- repository tek query ile current state alır.

-- 1) Per-(detector, target_key) Bayesian calibration state
CREATE TABLE IF NOT EXISTS anomaly_detector_calibration (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    detector_type TEXT NOT NULL,
    -- target_key formatı: detector'a göre değişir
    --   intercompany_leakage: counterparty
    --   volume_spike:         "company::category"
    --   duplicate_payment:    counterparty
    --   velocity_anomaly:     counterparty
    -- '*' wildcard'ı global (per-detector) demektir
    target_key TEXT NOT NULL DEFAULT '*',
    alpha REAL NOT NULL DEFAULT 2.0,    -- Beta prior alpha (hafif iyimser)
    beta REAL NOT NULL DEFAULT 1.0,     -- Beta prior beta
    confirmed_count INTEGER NOT NULL DEFAULT 0,
    dismissed_count INTEGER NOT NULL DEFAULT 0,
    threshold_offset REAL NOT NULL DEFAULT 0.0,   -- Z-score'a eklenen düzeltme
    last_reviewed_at INTEGER,
    updated_at INTEGER NOT NULL,
    UNIQUE (detector_type, target_key)
);

CREATE INDEX IF NOT EXISTS idx_anomaly_calibration_detector
    ON anomaly_detector_calibration(detector_type);

-- 2) Whitelist: kullanıcının "bu pattern normaldir" dediği kombinasyonlar
CREATE TABLE IF NOT EXISTS anomaly_pattern_whitelist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    detector_type TEXT NOT NULL,
    target_key TEXT NOT NULL,
    consecutive_dismissals INTEGER NOT NULL DEFAULT 0,
    whitelisted INTEGER NOT NULL DEFAULT 0,    -- 1 = aktif whitelist
    last_dismissed_at INTEGER,
    last_confirmed_at INTEGER,
    updated_at INTEGER NOT NULL,
    UNIQUE (detector_type, target_key)
);

CREATE INDEX IF NOT EXISTS idx_anomaly_whitelist_active
    ON anomaly_pattern_whitelist(detector_type, target_key)
    WHERE whitelisted = 1;

-- 3) Günlük metric snapshot — "doğruluk trend grafiği" için
CREATE TABLE IF NOT EXISTS anomaly_detector_metrics_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    detector_type TEXT NOT NULL,
    snapshot_date TEXT NOT NULL,    -- YYYY-MM-DD
    precision_pct REAL NOT NULL,    -- alpha / (alpha + beta) * 100
    total_signals INTEGER NOT NULL,
    confirmed INTEGER NOT NULL DEFAULT 0,
    dismissed INTEGER NOT NULL DEFAULT 0,
    pending INTEGER NOT NULL DEFAULT 0,
    UNIQUE (detector_type, snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_anomaly_metrics_date
    ON anomaly_detector_metrics_daily(snapshot_date DESC);
