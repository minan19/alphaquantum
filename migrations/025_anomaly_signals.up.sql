-- A2: Cross-Company Anomaly Detection
--
-- Schema: tespit edilen her anomali sinyalini persist eder.
-- Frontend dashboard widget'ı + review queue bu tabloyu okur.
--
-- Tasarım kararları:
--   * holding_id ile scope — multi-tenant izolasyon
--   * confidence_pct + severity → frontend filter
--   * baseline_json + payload_json → her sinyal kendi açıklamasını taşır
--   * status (open/confirmed/dismissed) → human-in-loop feedback
--   * signature_hash UNIQUE → aynı anomali iki kez kayıtlanmaz (idempotency)

CREATE TABLE IF NOT EXISTS anomaly_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    holding_id INTEGER,                               -- nullable: tek şirket senaryosu
    signal_type TEXT NOT NULL,                        -- intercompany_leakage | volume_spike | duplicate_payment | velocity_anomaly
    severity TEXT NOT NULL CHECK (severity IN ('critical', 'high', 'medium', 'low')),
    confidence_pct REAL NOT NULL CHECK (confidence_pct >= 0 AND confidence_pct <= 100),
    modified_z REAL NOT NULL,
    title TEXT NOT NULL,                              -- TR kısa başlık
    description TEXT NOT NULL,                        -- TR detay (LLM gerekçe burada)
    baseline_json TEXT NOT NULL DEFAULT '{}',         -- BaselineStats serialize
    payload_json TEXT NOT NULL DEFAULT '{}',          -- detector'a özgü detay (counterparty, companies, amounts)
    signature_hash TEXT NOT NULL UNIQUE,              -- (signal_type + key fields) → dedup
    detected_at INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'confirmed', 'dismissed')),
    reviewed_by TEXT,
    reviewed_at INTEGER,
    review_note TEXT
);

CREATE INDEX IF NOT EXISTS idx_anomaly_signals_holding_status
    ON anomaly_signals(holding_id, status, detected_at DESC);

CREATE INDEX IF NOT EXISTS idx_anomaly_signals_severity
    ON anomaly_signals(severity, detected_at DESC)
    WHERE status = 'open';

CREATE INDEX IF NOT EXISTS idx_anomaly_signals_type
    ON anomaly_signals(signal_type, detected_at DESC);
