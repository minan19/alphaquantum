-- G1.1 rollback: intercompany_transfers tablosu + ledger kolonları geri al
--
-- SQLite ALTER TABLE DROP COLUMN'u 3.35+ ile destekler (Python sqlite3
-- 3.10+ → SQLite 3.37+). Eğer ortam eski olursa table-recreate fallback
-- gerekir — bu migration system'in zaten desteklediği bir senaryo.

DROP INDEX IF EXISTS idx_intercompany_transfers_pending;
DROP INDEX IF EXISTS idx_intercompany_transfers_companies;
DROP INDEX IF EXISTS idx_intercompany_transfers_holding_status;

DROP TABLE IF EXISTS intercompany_transfers;

DROP INDEX IF EXISTS idx_finance_ledger_counterparty;
DROP INDEX IF EXISTS idx_finance_ledger_intercompany;

ALTER TABLE finance_ledger_entries DROP COLUMN intercompany_flag;
ALTER TABLE finance_ledger_entries DROP COLUMN transfer_id;
ALTER TABLE finance_ledger_entries DROP COLUMN counterparty_company;
