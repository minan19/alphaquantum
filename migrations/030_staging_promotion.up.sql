-- I2: Staging → CRM/Invoice/Ledger promotion log + idempotency
--
-- Logo'dan stage edilmiş kayıtlar gerçek tablolara aktarılırken bu log:
--   * signature_hash → produced_record_id eşlemesi → re-promote'ta skip
--   * conflict_resolution: hangi strateji kullanıldı (create_new/update/skip)
--   * promotion job audit trail

CREATE TABLE IF NOT EXISTS staging_promotion_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    record_type TEXT NOT NULL CHECK (record_type IN ('customer', 'invoice', 'ledger')),
    source_signature_hash TEXT NOT NULL,
    target_table TEXT NOT NULL,
    target_id INTEGER NOT NULL,
    conflict_resolution TEXT NOT NULL DEFAULT 'create_new'
        CHECK (conflict_resolution IN ('create_new', 'update_existing', 'skip')),
    promoted_at INTEGER NOT NULL,
    promoted_by TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE (user_id, source_signature_hash, record_type)
);

CREATE INDEX IF NOT EXISTS idx_staging_promotion_user_time
    ON staging_promotion_log(user_id, promoted_at DESC);

CREATE INDEX IF NOT EXISTS idx_staging_promotion_target
    ON staging_promotion_log(target_table, target_id);
