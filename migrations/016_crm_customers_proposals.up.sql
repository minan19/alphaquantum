-- S-321: CRM – customers and proposals
CREATE TABLE IF NOT EXISTS customers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name TEXT NOT NULL,
    full_name   TEXT NOT NULL,
    email       TEXT NOT NULL DEFAULT '',
    phone       TEXT NOT NULL DEFAULT '',
    sector      TEXT NOT NULL DEFAULT 'general',
    tags        TEXT NOT NULL DEFAULT '[]',
    notes       TEXT NOT NULL DEFAULT '',
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  INTEGER NOT NULL,
    updated_at  INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_customers_company_name  ON customers(company_name);
CREATE INDEX IF NOT EXISTS idx_customers_is_active     ON customers(is_active);

CREATE TABLE IF NOT EXISTS proposals (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name  TEXT NOT NULL,
    customer_id   INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    title         TEXT NOT NULL,
    amount        REAL NOT NULL CHECK(amount >= 0),
    currency      TEXT NOT NULL DEFAULT 'TRY',
    status        TEXT NOT NULL DEFAULT 'draft'
                  CHECK(status IN ('draft','sent','accepted','rejected','expired')),
    valid_until   TEXT,
    description   TEXT NOT NULL DEFAULT '',
    created_at    INTEGER NOT NULL,
    updated_at    INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_proposals_company_name ON proposals(company_name);
CREATE INDEX IF NOT EXISTS idx_proposals_customer_id  ON proposals(customer_id);
CREATE INDEX IF NOT EXISTS idx_proposals_status       ON proposals(status);
