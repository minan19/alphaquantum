-- A4: AI Invoice OCR job tracking
--
-- Tek tablo: kullanıcının fiş/fatura fotoğrafı yükleme akışı + Claude
-- Vision API ile extract sonuçlarını saklar.

CREATE TABLE IF NOT EXISTS ocr_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    source_filename TEXT,
    source_size_bytes INTEGER NOT NULL DEFAULT 0,
    mime_type TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'extracted', 'confirmed', 'failed', 'cancelled')),
    -- Extract sonucu — Claude Vision çıktısı
    extract_json TEXT NOT NULL DEFAULT '{}',
    confidence_pct REAL NOT NULL DEFAULT 0,
    -- Otomatik kategorize edilen ledger entry id (confirm sonrası)
    ledger_entry_id INTEGER,
    error_message TEXT,
    created_at INTEGER NOT NULL,
    extracted_at INTEGER,
    confirmed_at INTEGER
);

CREATE INDEX IF NOT EXISTS idx_ocr_jobs_user_time
    ON ocr_jobs(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ocr_jobs_status
    ON ocr_jobs(status, created_at DESC);
