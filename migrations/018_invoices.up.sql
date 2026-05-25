-- S-323: Collections – invoices and receivables
CREATE TABLE IF NOT EXISTS invoices (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name    TEXT NOT NULL,
    customer_id     INTEGER REFERENCES customers(id) ON DELETE SET NULL,
    proposal_id     INTEGER REFERENCES proposals(id) ON DELETE SET NULL,
    invoice_number  TEXT NOT NULL DEFAULT '',
    title           TEXT NOT NULL,
    amount          REAL NOT NULL CHECK(amount >= 0),
    paid_amount     REAL NOT NULL DEFAULT 0 CHECK(paid_amount >= 0),
    currency        TEXT NOT NULL DEFAULT 'TRY',
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK(status IN ('pending','partial','paid','overdue','cancelled')),
    issue_date      TEXT NOT NULL,
    due_date        TEXT NOT NULL,
    paid_date       TEXT,
    description     TEXT NOT NULL DEFAULT '',
    created_at      INTEGER NOT NULL,
    updated_at      INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_invoices_company_name ON invoices(company_name);
CREATE INDEX IF NOT EXISTS idx_invoices_customer_id  ON invoices(customer_id);
CREATE INDEX IF NOT EXISTS idx_invoices_status       ON invoices(status);
CREATE INDEX IF NOT EXISTS idx_invoices_due_date     ON invoices(due_date);
