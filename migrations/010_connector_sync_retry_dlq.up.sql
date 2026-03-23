ALTER TABLE integration_sync_jobs
    ADD COLUMN last_error_code TEXT;

ALTER TABLE integration_sync_jobs
    ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE integration_sync_jobs
    ADD COLUMN max_attempts INTEGER NOT NULL DEFAULT 3;

ALTER TABLE integration_sync_jobs
    ADD COLUMN next_retry_at INTEGER;

ALTER TABLE integration_sync_jobs
    ADD COLUMN dead_lettered_at INTEGER;

CREATE INDEX IF NOT EXISTS idx_integration_sync_jobs_retry_due
    ON integration_sync_jobs(status, next_retry_at);
