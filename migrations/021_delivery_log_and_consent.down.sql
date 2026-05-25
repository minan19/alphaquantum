-- SQLite supports DROP COLUMN since 3.35.0 (2021), which we assume.
ALTER TABLE customers DROP COLUMN consent_updated_at;
ALTER TABLE customers DROP COLUMN whatsapp_consent;
ALTER TABLE customers DROP COLUMN sms_consent;
ALTER TABLE customers DROP COLUMN email_consent;

DROP INDEX IF EXISTS idx_delivery_log_status;
DROP INDEX IF EXISTS idx_delivery_log_notification;
DROP INDEX IF EXISTS idx_delivery_log_company;
DROP TABLE IF EXISTS delivery_log;
