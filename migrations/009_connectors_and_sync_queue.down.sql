DROP INDEX IF EXISTS idx_integration_sync_jobs_connector_id;
DROP INDEX IF EXISTS idx_integration_sync_jobs_status_priority;
DROP TABLE IF EXISTS integration_sync_jobs;

DROP INDEX IF EXISTS idx_integration_connectors_status;
DROP INDEX IF EXISTS idx_integration_connectors_company;
DROP TABLE IF EXISTS integration_connectors;
