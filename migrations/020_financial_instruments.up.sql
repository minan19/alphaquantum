-- S-342: Senet / Çek / Bono Takibi
-- Tracks structured payment instruments separately from invoices:
--   senet  = promissory note (yazılı ödeme taahhüdü)
--   cek    = cheque (banka çeki)
--   bono   = corporate bond / longer-form note
--
-- Status FSM:
--   pending  → cleared    (tahsil edildi)
--   pending  → bounced    (karşılıksız çıktı)
--   pending  → cancelled  (iptal)
-- cleared/bounced/cancelled are terminal.

CREATE TABLE IF NOT EXISTS financial_instruments (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name      TEXT NOT NULL,
    customer_id       INTEGER REFERENCES customers(id) ON DELETE SET NULL,
    kind              TEXT NOT NULL CHECK (kind IN ('senet','cek','bono')),
    instrument_number TEXT NOT NULL DEFAULT '',
    amount            REAL NOT NULL,
    currency          TEXT NOT NULL DEFAULT 'TRY',
    issue_date        TEXT NOT NULL,
    due_date          TEXT NOT NULL,
    payer_name        TEXT NOT NULL DEFAULT '',
    bank_name         TEXT NOT NULL DEFAULT '',
    status            TEXT NOT NULL DEFAULT 'pending'
                       CHECK (status IN ('pending','cleared','bounced','cancelled')),
    cleared_date      TEXT,
    notes             TEXT NOT NULL DEFAULT '',
    created_at        INTEGER NOT NULL,
    updated_at        INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_instr_company  ON financial_instruments(company_name);
CREATE INDEX IF NOT EXISTS idx_instr_status   ON financial_instruments(company_name, status);
CREATE INDEX IF NOT EXISTS idx_instr_due      ON financial_instruments(due_date);
CREATE INDEX IF NOT EXISTS idx_instr_customer ON financial_instruments(customer_id);
