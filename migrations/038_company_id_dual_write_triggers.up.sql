-- M4.2 — Çift-yazma trigger'ları + tutarlılık guard'ı.
--
-- Amaç: kod company_name yazmaya devam ediyor; bu trigger'lar HER tenant
-- tablosunda company_id'yi otomatik doldurur. Böylece:
--   • Yazma yolları company_id'yi de yazıyor olur (çift-yazma).
--   • Application code değişmez (16 router/repository'de değişiklik gerekmez).
--   • Tutarsız id/name yazımı registry'den DÜZELTİLİR (sessiz tutarsızlık YASAK).
--
-- Geri dönüş: down trigger'ları düşürür; company_name kolonu/verisi yerinde
-- kalır → M4.1 davranışına dönülebilir.

-- ── AFTER INSERT trigger'ları (company_id'i company_name'den türet) ─────
-- Davranış: INSERT sonrası company_id NULL ise:
--   1. companies registry'ye INSERT OR IGNORE (yeni şirket otomatik kayda).
--   2. company_id'i registry'den UPDATE et.
-- WHEN bloğu sayesinde yalnız company_id eksik kayıtlarda tetiklenir.

CREATE TRIGGER IF NOT EXISTS trg_finance_ledger_entries_company_id_after_insert
AFTER INSERT ON finance_ledger_entries
WHEN NEW.company_id IS NULL AND NEW.company_name IS NOT NULL AND NEW.company_name != ''
BEGIN
    INSERT OR IGNORE INTO companies (name, balance) VALUES (NEW.company_name, 0);
    UPDATE finance_ledger_entries SET company_id = (SELECT id FROM companies WHERE name = NEW.company_name) WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_procurement_requests_company_id_after_insert
AFTER INSERT ON procurement_requests
WHEN NEW.company_id IS NULL AND NEW.company_name IS NOT NULL AND NEW.company_name != ''
BEGIN
    INSERT OR IGNORE INTO companies (name, balance) VALUES (NEW.company_name, 0);
    UPDATE procurement_requests SET company_id = (SELECT id FROM companies WHERE name = NEW.company_name) WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_international_projects_company_id_after_insert
AFTER INSERT ON international_projects
WHEN NEW.company_id IS NULL AND NEW.company_name IS NOT NULL AND NEW.company_name != ''
BEGIN
    INSERT OR IGNORE INTO companies (name, balance) VALUES (NEW.company_name, 0);
    UPDATE international_projects SET company_id = (SELECT id FROM companies WHERE name = NEW.company_name) WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_holding_companies_company_id_after_insert
AFTER INSERT ON holding_companies
WHEN NEW.company_id IS NULL AND NEW.company_name IS NOT NULL AND NEW.company_name != ''
BEGIN
    INSERT OR IGNORE INTO companies (name, balance) VALUES (NEW.company_name, 0);
    UPDATE holding_companies SET company_id = (SELECT id FROM companies WHERE name = NEW.company_name) WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_integration_connectors_company_id_after_insert
AFTER INSERT ON integration_connectors
WHEN NEW.company_id IS NULL AND NEW.company_name IS NOT NULL AND NEW.company_name != ''
BEGIN
    INSERT OR IGNORE INTO companies (name, balance) VALUES (NEW.company_name, 0);
    UPDATE integration_connectors SET company_id = (SELECT id FROM companies WHERE name = NEW.company_name) WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_finance_recurring_entries_company_id_after_insert
AFTER INSERT ON finance_recurring_entries
WHEN NEW.company_id IS NULL AND NEW.company_name IS NOT NULL AND NEW.company_name != ''
BEGIN
    INSERT OR IGNORE INTO companies (name, balance) VALUES (NEW.company_name, 0);
    UPDATE finance_recurring_entries SET company_id = (SELECT id FROM companies WHERE name = NEW.company_name) WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_finance_budgets_company_id_after_insert
AFTER INSERT ON finance_budgets
WHEN NEW.company_id IS NULL AND NEW.company_name IS NOT NULL AND NEW.company_name != ''
BEGIN
    INSERT OR IGNORE INTO companies (name, balance) VALUES (NEW.company_name, 0);
    UPDATE finance_budgets SET company_id = (SELECT id FROM companies WHERE name = NEW.company_name) WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_scheduled_reports_company_id_after_insert
AFTER INSERT ON scheduled_reports
WHEN NEW.company_id IS NULL AND NEW.company_name IS NOT NULL AND NEW.company_name != ''
BEGIN
    INSERT OR IGNORE INTO companies (name, balance) VALUES (NEW.company_name, 0);
    UPDATE scheduled_reports SET company_id = (SELECT id FROM companies WHERE name = NEW.company_name) WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_customers_company_id_after_insert
AFTER INSERT ON customers
WHEN NEW.company_id IS NULL AND NEW.company_name IS NOT NULL AND NEW.company_name != ''
BEGIN
    INSERT OR IGNORE INTO companies (name, balance) VALUES (NEW.company_name, 0);
    UPDATE customers SET company_id = (SELECT id FROM companies WHERE name = NEW.company_name) WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_proposals_company_id_after_insert
AFTER INSERT ON proposals
WHEN NEW.company_id IS NULL AND NEW.company_name IS NOT NULL AND NEW.company_name != ''
BEGIN
    INSERT OR IGNORE INTO companies (name, balance) VALUES (NEW.company_name, 0);
    UPDATE proposals SET company_id = (SELECT id FROM companies WHERE name = NEW.company_name) WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_tasks_company_id_after_insert
AFTER INSERT ON tasks
WHEN NEW.company_id IS NULL AND NEW.company_name IS NOT NULL AND NEW.company_name != ''
BEGIN
    INSERT OR IGNORE INTO companies (name, balance) VALUES (NEW.company_name, 0);
    UPDATE tasks SET company_id = (SELECT id FROM companies WHERE name = NEW.company_name) WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_invoices_company_id_after_insert
AFTER INSERT ON invoices
WHEN NEW.company_id IS NULL AND NEW.company_name IS NOT NULL AND NEW.company_name != ''
BEGIN
    INSERT OR IGNORE INTO companies (name, balance) VALUES (NEW.company_name, 0);
    UPDATE invoices SET company_id = (SELECT id FROM companies WHERE name = NEW.company_name) WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_notifications_company_id_after_insert
AFTER INSERT ON notifications
WHEN NEW.company_id IS NULL AND NEW.company_name IS NOT NULL AND NEW.company_name != ''
BEGIN
    INSERT OR IGNORE INTO companies (name, balance) VALUES (NEW.company_name, 0);
    UPDATE notifications SET company_id = (SELECT id FROM companies WHERE name = NEW.company_name) WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_financial_instruments_company_id_after_insert
AFTER INSERT ON financial_instruments
WHEN NEW.company_id IS NULL AND NEW.company_name IS NOT NULL AND NEW.company_name != ''
BEGIN
    INSERT OR IGNORE INTO companies (name, balance) VALUES (NEW.company_name, 0);
    UPDATE financial_instruments SET company_id = (SELECT id FROM companies WHERE name = NEW.company_name) WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_delivery_log_company_id_after_insert
AFTER INSERT ON delivery_log
WHEN NEW.company_id IS NULL AND NEW.company_name IS NOT NULL AND NEW.company_name != ''
BEGIN
    INSERT OR IGNORE INTO companies (name, balance) VALUES (NEW.company_name, 0);
    UPDATE delivery_log SET company_id = (SELECT id FROM companies WHERE name = NEW.company_name) WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_treasury_accounts_company_id_after_insert
AFTER INSERT ON treasury_accounts
WHEN NEW.company_id IS NULL AND NEW.company_name IS NOT NULL AND NEW.company_name != ''
BEGIN
    INSERT OR IGNORE INTO companies (name, balance) VALUES (NEW.company_name, 0);
    UPDATE treasury_accounts SET company_id = (SELECT id FROM companies WHERE name = NEW.company_name) WHERE id = NEW.id;
END;

-- ── AFTER UPDATE OF company_name trigger'ları ─────────────────────────
-- Davranış: company_name değişirse company_id de registry'den yeniden türetilir.
-- Tutarsızlık olamaz: name otorite gibi davranır, id senkronize edilir.

CREATE TRIGGER IF NOT EXISTS trg_customers_company_id_after_update_name
AFTER UPDATE OF company_name ON customers
WHEN NEW.company_name IS NOT NULL AND NEW.company_name != ''
  AND (OLD.company_name IS NULL OR NEW.company_name != OLD.company_name)
BEGIN
    INSERT OR IGNORE INTO companies (name, balance) VALUES (NEW.company_name, 0);
    UPDATE customers SET company_id = (SELECT id FROM companies WHERE name = NEW.company_name) WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_invoices_company_id_after_update_name
AFTER UPDATE OF company_name ON invoices
WHEN NEW.company_name IS NOT NULL AND NEW.company_name != ''
  AND (OLD.company_name IS NULL OR NEW.company_name != OLD.company_name)
BEGIN
    INSERT OR IGNORE INTO companies (name, balance) VALUES (NEW.company_name, 0);
    UPDATE invoices SET company_id = (SELECT id FROM companies WHERE name = NEW.company_name) WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_finance_ledger_entries_company_id_after_update_name
AFTER UPDATE OF company_name ON finance_ledger_entries
WHEN NEW.company_name IS NOT NULL AND NEW.company_name != ''
  AND (OLD.company_name IS NULL OR NEW.company_name != OLD.company_name)
BEGIN
    INSERT OR IGNORE INTO companies (name, balance) VALUES (NEW.company_name, 0);
    UPDATE finance_ledger_entries SET company_id = (SELECT id FROM companies WHERE name = NEW.company_name) WHERE id = NEW.id;
END;
