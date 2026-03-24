-- Ensure audit_logs exists (idempotent – no-op if AuditRepository already created it)
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT,
    username TEXT,
    role TEXT,
    method TEXT NOT NULL DEFAULT '',
    path TEXT NOT NULL DEFAULT '',
    status_code INTEGER NOT NULL DEFAULT 0,
    ip_address TEXT,
    user_agent TEXT,
    duration_ms REAL NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL DEFAULT 0
);

ALTER TABLE audit_logs ADD COLUMN event_type TEXT;
ALTER TABLE audit_logs ADD COLUMN event_detail TEXT;

CREATE INDEX IF NOT EXISTS idx_audit_logs_event_type
    ON audit_logs(event_type);
