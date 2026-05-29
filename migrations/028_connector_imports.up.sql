-- I1: Logo Tiger Connector — import job tracking + field mapping memory
--
-- 3 tablo:
--   * connector_import_jobs    — her import için audit + status
--   * connector_field_mappings — kullanıcının "şu Logo kolonu şu alana"
--                                eşlemesini öğretmesi
--   * connector_import_errors  — başarısız satır detayı (debug + UX)

CREATE TABLE IF NOT EXISTS connector_import_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    connector_type TEXT NOT NULL,        -- 'logo_tiger' | 'mikro' | ...
    mode TEXT NOT NULL,                  -- 'xml' | 'excel' | 'web_service'
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'parsing', 'preview', 'committing', 'completed', 'failed', 'cancelled')),
    source_filename TEXT,
    source_size_bytes INTEGER,
    record_summary_json TEXT NOT NULL DEFAULT '{}',  -- {customers: N, invoices: M, ...}
    preview_json TEXT,                   -- ilk 10 satırın preview'i
    error_message TEXT,
    started_at INTEGER NOT NULL,
    finished_at INTEGER,
    committed_at INTEGER
);

CREATE INDEX IF NOT EXISTS idx_connector_jobs_user_status
    ON connector_import_jobs(user_id, status, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_connector_jobs_type
    ON connector_import_jobs(connector_type, started_at DESC);

CREATE TABLE IF NOT EXISTS connector_field_mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    connector_type TEXT NOT NULL,
    record_type TEXT NOT NULL,           -- 'customer' | 'invoice' | ...
    source_field TEXT NOT NULL,          -- 'CARI_KODU'
    target_field TEXT NOT NULL,          -- 'customer_code'
    transform_hint TEXT,                 -- 'uppercase' | 'trim' | 'iban_clean' | NULL
    updated_at INTEGER NOT NULL,
    UNIQUE (user_id, connector_type, record_type, source_field)
);

CREATE TABLE IF NOT EXISTS connector_import_errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    row_index INTEGER NOT NULL,
    record_type TEXT NOT NULL,
    error_code TEXT NOT NULL,            -- 'missing_field' | 'invalid_format' | 'duplicate' | ...
    error_message TEXT NOT NULL,
    raw_payload TEXT,                    -- problemli satır kaydı
    FOREIGN KEY (job_id) REFERENCES connector_import_jobs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_connector_errors_job
    ON connector_import_errors(job_id, row_index);
