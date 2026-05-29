-- A2: Anomaly signals rollback — tablo + index drop
DROP INDEX IF EXISTS idx_anomaly_signals_type;
DROP INDEX IF EXISTS idx_anomaly_signals_severity;
DROP INDEX IF EXISTS idx_anomaly_signals_holding_status;
DROP TABLE IF EXISTS anomaly_signals;
