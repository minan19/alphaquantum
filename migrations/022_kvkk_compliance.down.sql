-- SQLite 3.35+ DROP COLUMN gerektirir
ALTER TABLE users DROP COLUMN anonymized_at;
ALTER TABLE users DROP COLUMN last_data_access_at;
ALTER TABLE users DROP COLUMN last_data_export_at;
ALTER TABLE users DROP COLUMN kvkk_consent_version;
ALTER TABLE users DROP COLUMN kvkk_consent_at;

DROP INDEX IF EXISTS idx_si_reported;
DROP INDEX IF EXISTS idx_si_user;
DROP INDEX IF EXISTS idx_si_status;
DROP INDEX IF EXISTS idx_si_severity;
DROP TABLE IF EXISTS security_incidents;

DROP INDEX IF EXISTS idx_adr_requested;
DROP INDEX IF EXISTS idx_adr_status;
DROP INDEX IF EXISTS idx_adr_user;
DROP TABLE IF EXISTS account_deletion_requests;
