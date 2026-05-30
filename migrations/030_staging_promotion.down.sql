-- I2: Staging promotion log rollback
DROP INDEX IF EXISTS idx_staging_promotion_target;
DROP INDEX IF EXISTS idx_staging_promotion_user_time;
DROP TABLE IF EXISTS staging_promotion_log;
