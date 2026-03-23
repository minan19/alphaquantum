CREATE TABLE IF NOT EXISTS integration_worker_leases (
    worker_name TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    acquired_at INTEGER NOT NULL,
    heartbeat_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_integration_worker_leases_expires
    ON integration_worker_leases(expires_at);
