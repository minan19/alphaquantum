-- G+4 rollback: audit hash chain kolonları geri al.

DROP INDEX IF EXISTS idx_audit_logs_id_hash;

ALTER TABLE audit_logs DROP COLUMN prev_hash;
ALTER TABLE audit_logs DROP COLUMN entry_hash;
