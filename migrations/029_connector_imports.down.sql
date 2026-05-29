-- I1: Connector imports rollback
DROP INDEX IF EXISTS idx_connector_errors_job;
DROP TABLE IF EXISTS connector_import_errors;
DROP TABLE IF EXISTS connector_field_mappings;
DROP INDEX IF EXISTS idx_connector_jobs_type;
DROP INDEX IF EXISTS idx_connector_jobs_user_status;
DROP TABLE IF EXISTS connector_import_jobs;
