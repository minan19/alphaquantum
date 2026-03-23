CREATE TABLE IF NOT EXISTS integration_connectors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name TEXT NOT NULL,
    connector_type TEXT NOT NULL,
    provider TEXT NOT NULL,
    base_url TEXT,
    auth_mode TEXT NOT NULL,
    config_json TEXT NOT NULL DEFAULT '{}',
    mapping_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'active',
    readiness_score REAL NOT NULL DEFAULT 0,
    mapping_coverage_score REAL NOT NULL DEFAULT 0,
    security_score REAL NOT NULL DEFAULT 0,
    created_by TEXT,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    last_sync_at INTEGER,
    UNIQUE(company_name, connector_type, provider)
);

CREATE INDEX IF NOT EXISTS idx_integration_connectors_company
    ON integration_connectors(company_name);

CREATE INDEX IF NOT EXISTS idx_integration_connectors_status
    ON integration_connectors(status);

CREATE TABLE IF NOT EXISTS integration_sync_jobs (
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

CREATE INDEX IF NOT EXISTS idx_integration_sync_jobs_status_priority
    ON integration_sync_jobs(status, priority_score DESC, requested_at ASC);

CREATE INDEX IF NOT EXISTS idx_integration_sync_jobs_connector_id
    ON integration_sync_jobs(connector_id);
