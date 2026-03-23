DROP INDEX IF EXISTS idx_integration_sync_jobs_retry_due;

CREATE TABLE IF NOT EXISTS integration_sync_jobs_rollback_010 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    connector_id INTEGER NOT NULL,
    trigger_mode TEXT NOT NULL,
    priority_score REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    requested_by TEXT,
    request_payload_json TEXT NOT NULL DEFAULT '{}',
    result_summary TEXT NOT NULL DEFAULT '',
    error_message TEXT,
    requested_at INTEGER NOT NULL,
    started_at INTEGER,
    finished_at INTEGER,
    FOREIGN KEY(connector_id) REFERENCES integration_connectors(id) ON DELETE CASCADE
);

INSERT INTO integration_sync_jobs_rollback_010(
    id,
    connector_id,
    trigger_mode,
    priority_score,
    status,
    requested_by,
    request_payload_json,
    result_summary,
    error_message,
    requested_at,
    started_at,
    finished_at
)
SELECT
    id,
    connector_id,
    trigger_mode,
    priority_score,
    status,
    requested_by,
    request_payload_json,
    result_summary,
    error_message,
    requested_at,
    started_at,
    finished_at
FROM integration_sync_jobs;

DROP TABLE integration_sync_jobs;

ALTER TABLE integration_sync_jobs_rollback_010 RENAME TO integration_sync_jobs;

CREATE INDEX IF NOT EXISTS idx_integration_sync_jobs_status_priority
    ON integration_sync_jobs(status, priority_score DESC, requested_at ASC);

CREATE INDEX IF NOT EXISTS idx_integration_sync_jobs_connector_id
    ON integration_sync_jobs(connector_id);
