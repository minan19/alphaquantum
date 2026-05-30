-- A2.1: Adaptive calibration rollback — 3 tablo drop
DROP INDEX IF EXISTS idx_anomaly_metrics_date;
DROP TABLE IF EXISTS anomaly_detector_metrics_daily;
DROP INDEX IF EXISTS idx_anomaly_whitelist_active;
DROP TABLE IF EXISTS anomaly_pattern_whitelist;
DROP INDEX IF EXISTS idx_anomaly_calibration_detector;
DROP TABLE IF EXISTS anomaly_detector_calibration;
