-- T1: Treasury rollback
DROP INDEX IF EXISTS idx_treasury_history_date;
DROP TABLE IF EXISTS treasury_balance_history;
DROP INDEX IF EXISTS idx_treasury_accounts_company;
DROP INDEX IF EXISTS idx_treasury_accounts_user;
DROP TABLE IF EXISTS treasury_accounts;
