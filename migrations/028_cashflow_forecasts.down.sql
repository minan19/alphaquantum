-- A3: Cashflow forecasts rollback
DROP INDEX IF EXISTS idx_cashflow_accuracy_user_date;
DROP TABLE IF EXISTS cashflow_forecast_accuracy;
DROP INDEX IF EXISTS idx_cashflow_cache_expiry;
DROP TABLE IF EXISTS cashflow_forecast_cache;
DROP INDEX IF EXISTS idx_cashflow_models_user;
DROP TABLE IF EXISTS cashflow_forecast_models;
