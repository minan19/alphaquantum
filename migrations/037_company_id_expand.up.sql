-- M4.1 EXPAND — companies registry + company_id FK kolonu (additif).
--
-- Bu migration kod davranışını DEĞİŞTİRMEZ. Yalnız:
--   1) Canonical `companies(id, name)` tablosunu oluşturur.
--   2) 16 tenant tablosundaki distinct company_name'leri companies'e backfill eder.
--   3) Her tenant tabloya `company_id INTEGER NULL REFERENCES companies(id)` ekler.
--   4) Her satırın company_id'sini company_name eşleşmesinden doldurur.
--   5) company_id için index açar (M4.2 read path'i için).
--
-- NOT NULL ve cascade M4.3'te eklenir (enforce fazı). company_name kolonu
-- yerinde — geri-dönülebilir, veri kaybı YOK.

-- 1) Canonical companies registry — mevcut tablo `app/repository.py`'de
--    `(id, name UNIQUE, balance REAL)` şemasıyla var. Yoksa IF NOT EXISTS
--    bu şemayı oluşturur; varsa no-op. Hiçbir kolonu değiştirmiyoruz —
--    pure additif (yan ekosistem `inventory` zaten companies'e FK).
CREATE TABLE IF NOT EXISTS companies (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name    TEXT NOT NULL UNIQUE,
    balance REAL NOT NULL DEFAULT 0
);

-- 2) Distinct company_name → companies backfill (idempotent, INSERT OR IGNORE).
INSERT OR IGNORE INTO companies (name, balance)
SELECT DISTINCT name, 0
FROM (
    SELECT company_name AS name FROM finance_ledger_entries
    UNION SELECT company_name FROM procurement_requests
    UNION SELECT company_name FROM international_projects
    UNION SELECT company_name FROM holding_companies
    UNION SELECT company_name FROM integration_connectors
    UNION SELECT company_name FROM finance_recurring_entries
    UNION SELECT company_name FROM finance_budgets
    UNION SELECT company_name FROM scheduled_reports
    UNION SELECT company_name FROM customers
    UNION SELECT company_name FROM proposals
    UNION SELECT company_name FROM tasks
    UNION SELECT company_name FROM invoices
    UNION SELECT company_name FROM notifications
    UNION SELECT company_name FROM financial_instruments
    UNION SELECT company_name FROM delivery_log
    UNION SELECT company_name FROM treasury_accounts
)
WHERE name IS NOT NULL AND name != '';

-- 3) company_id kolonu (FK, NULL — şimdilik zorunlu değil).
ALTER TABLE finance_ledger_entries    ADD COLUMN company_id INTEGER REFERENCES companies(id);
ALTER TABLE procurement_requests      ADD COLUMN company_id INTEGER REFERENCES companies(id);
ALTER TABLE international_projects    ADD COLUMN company_id INTEGER REFERENCES companies(id);
ALTER TABLE holding_companies         ADD COLUMN company_id INTEGER REFERENCES companies(id);
ALTER TABLE integration_connectors    ADD COLUMN company_id INTEGER REFERENCES companies(id);
ALTER TABLE finance_recurring_entries ADD COLUMN company_id INTEGER REFERENCES companies(id);
ALTER TABLE finance_budgets           ADD COLUMN company_id INTEGER REFERENCES companies(id);
ALTER TABLE scheduled_reports         ADD COLUMN company_id INTEGER REFERENCES companies(id);
ALTER TABLE customers                 ADD COLUMN company_id INTEGER REFERENCES companies(id);
ALTER TABLE proposals                 ADD COLUMN company_id INTEGER REFERENCES companies(id);
ALTER TABLE tasks                     ADD COLUMN company_id INTEGER REFERENCES companies(id);
ALTER TABLE invoices                  ADD COLUMN company_id INTEGER REFERENCES companies(id);
ALTER TABLE notifications             ADD COLUMN company_id INTEGER REFERENCES companies(id);
ALTER TABLE financial_instruments     ADD COLUMN company_id INTEGER REFERENCES companies(id);
ALTER TABLE delivery_log              ADD COLUMN company_id INTEGER REFERENCES companies(id);
ALTER TABLE treasury_accounts         ADD COLUMN company_id INTEGER REFERENCES companies(id);

-- 4) Backfill — her satırın company_name'i companies.id'ye yazılır.
UPDATE finance_ledger_entries    SET company_id = (SELECT id FROM companies WHERE name = finance_ledger_entries.company_name)    WHERE company_id IS NULL;
UPDATE procurement_requests      SET company_id = (SELECT id FROM companies WHERE name = procurement_requests.company_name)      WHERE company_id IS NULL;
UPDATE international_projects    SET company_id = (SELECT id FROM companies WHERE name = international_projects.company_name)    WHERE company_id IS NULL;
UPDATE holding_companies         SET company_id = (SELECT id FROM companies WHERE name = holding_companies.company_name)         WHERE company_id IS NULL;
UPDATE integration_connectors    SET company_id = (SELECT id FROM companies WHERE name = integration_connectors.company_name)    WHERE company_id IS NULL;
UPDATE finance_recurring_entries SET company_id = (SELECT id FROM companies WHERE name = finance_recurring_entries.company_name) WHERE company_id IS NULL;
UPDATE finance_budgets           SET company_id = (SELECT id FROM companies WHERE name = finance_budgets.company_name)           WHERE company_id IS NULL;
UPDATE scheduled_reports         SET company_id = (SELECT id FROM companies WHERE name = scheduled_reports.company_name)         WHERE company_id IS NULL;
UPDATE customers                 SET company_id = (SELECT id FROM companies WHERE name = customers.company_name)                 WHERE company_id IS NULL;
UPDATE proposals                 SET company_id = (SELECT id FROM companies WHERE name = proposals.company_name)                 WHERE company_id IS NULL;
UPDATE tasks                     SET company_id = (SELECT id FROM companies WHERE name = tasks.company_name)                     WHERE company_id IS NULL;
UPDATE invoices                  SET company_id = (SELECT id FROM companies WHERE name = invoices.company_name)                  WHERE company_id IS NULL;
UPDATE notifications             SET company_id = (SELECT id FROM companies WHERE name = notifications.company_name)             WHERE company_id IS NULL;
UPDATE financial_instruments     SET company_id = (SELECT id FROM companies WHERE name = financial_instruments.company_name)     WHERE company_id IS NULL;
UPDATE delivery_log              SET company_id = (SELECT id FROM companies WHERE name = delivery_log.company_name)              WHERE company_id IS NULL;
UPDATE treasury_accounts         SET company_id = (SELECT id FROM companies WHERE name = treasury_accounts.company_name)         WHERE company_id IS NULL;

-- 5) Index — M4.2 read path için.
CREATE INDEX IF NOT EXISTS idx_finance_ledger_entries_company_id    ON finance_ledger_entries(company_id);
CREATE INDEX IF NOT EXISTS idx_procurement_requests_company_id      ON procurement_requests(company_id);
CREATE INDEX IF NOT EXISTS idx_international_projects_company_id    ON international_projects(company_id);
CREATE INDEX IF NOT EXISTS idx_holding_companies_company_id         ON holding_companies(company_id);
CREATE INDEX IF NOT EXISTS idx_integration_connectors_company_id    ON integration_connectors(company_id);
CREATE INDEX IF NOT EXISTS idx_finance_recurring_entries_company_id ON finance_recurring_entries(company_id);
CREATE INDEX IF NOT EXISTS idx_finance_budgets_company_id           ON finance_budgets(company_id);
CREATE INDEX IF NOT EXISTS idx_scheduled_reports_company_id         ON scheduled_reports(company_id);
CREATE INDEX IF NOT EXISTS idx_customers_company_id                 ON customers(company_id);
CREATE INDEX IF NOT EXISTS idx_proposals_company_id                 ON proposals(company_id);
CREATE INDEX IF NOT EXISTS idx_tasks_company_id                     ON tasks(company_id);
CREATE INDEX IF NOT EXISTS idx_invoices_company_id                  ON invoices(company_id);
CREATE INDEX IF NOT EXISTS idx_notifications_company_id             ON notifications(company_id);
CREATE INDEX IF NOT EXISTS idx_financial_instruments_company_id     ON financial_instruments(company_id);
CREATE INDEX IF NOT EXISTS idx_delivery_log_company_id              ON delivery_log(company_id);
CREATE INDEX IF NOT EXISTS idx_treasury_accounts_company_id         ON treasury_accounts(company_id);
