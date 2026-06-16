-- M4.1 DOWN — company_id kolonu + companies tablosu kaldırılır.
--
-- VERİ KAYBI YOK: company_name kolonu ve verileri yerinde kalır.
-- Sadece M4.1 expand'le eklenen yapılar geri alınır.

-- 1) İndexleri düşür.
DROP INDEX IF EXISTS idx_finance_ledger_entries_company_id;
DROP INDEX IF EXISTS idx_procurement_requests_company_id;
DROP INDEX IF EXISTS idx_international_projects_company_id;
DROP INDEX IF EXISTS idx_holding_companies_company_id;
DROP INDEX IF EXISTS idx_integration_connectors_company_id;
DROP INDEX IF EXISTS idx_finance_recurring_entries_company_id;
DROP INDEX IF EXISTS idx_finance_budgets_company_id;
DROP INDEX IF EXISTS idx_scheduled_reports_company_id;
DROP INDEX IF EXISTS idx_customers_company_id;
DROP INDEX IF EXISTS idx_proposals_company_id;
DROP INDEX IF EXISTS idx_tasks_company_id;
DROP INDEX IF EXISTS idx_invoices_company_id;
DROP INDEX IF EXISTS idx_notifications_company_id;
DROP INDEX IF EXISTS idx_financial_instruments_company_id;
DROP INDEX IF EXISTS idx_delivery_log_company_id;
DROP INDEX IF EXISTS idx_treasury_accounts_company_id;

-- 2) company_id kolonlarını düşür (SQLite 3.35+ ALTER TABLE DROP COLUMN).
ALTER TABLE finance_ledger_entries    DROP COLUMN company_id;
ALTER TABLE procurement_requests      DROP COLUMN company_id;
ALTER TABLE international_projects    DROP COLUMN company_id;
ALTER TABLE holding_companies         DROP COLUMN company_id;
ALTER TABLE integration_connectors    DROP COLUMN company_id;
ALTER TABLE finance_recurring_entries DROP COLUMN company_id;
ALTER TABLE finance_budgets           DROP COLUMN company_id;
ALTER TABLE scheduled_reports         DROP COLUMN company_id;
ALTER TABLE customers                 DROP COLUMN company_id;
ALTER TABLE proposals                 DROP COLUMN company_id;
ALTER TABLE tasks                     DROP COLUMN company_id;
ALTER TABLE invoices                  DROP COLUMN company_id;
ALTER TABLE notifications             DROP COLUMN company_id;
ALTER TABLE financial_instruments     DROP COLUMN company_id;
ALTER TABLE delivery_log              DROP COLUMN company_id;
ALTER TABLE treasury_accounts         DROP COLUMN company_id;

-- 3) `companies` tablosunu DROP ETMİYORUZ — uygulama (`app/repository.py`)
--    zaten bu tabloyu canonical olarak kullanıyor ve `inventory` tablosu
--    FK ile bağlı. Backfill'le eklenen ek isimler zararsız (dangling olur,
--    M4.1 tekrar uygulanırsa INSERT OR IGNORE üzerine yazmaz). Veri kaybı YOK.
