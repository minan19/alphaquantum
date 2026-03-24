-- SQLite does not support DROP COLUMN; recreate without event columns

CREATE TABLE audit_logs_v0 AS
    SELECT id, request_id, username, role, method, path,
           status_code, ip_address, user_agent, duration_ms, created_at
    FROM audit_logs;

DROP TABLE audit_logs;

ALTER TABLE audit_logs_v0 RENAME TO audit_logs;
