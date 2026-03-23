CREATE TABLE IF NOT EXISTS finance_ledger_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name TEXT NOT NULL,
    entry_type TEXT NOT NULL CHECK(entry_type IN ('income', 'expense')),
    amount REAL NOT NULL CHECK(amount > 0),
    category TEXT NOT NULL DEFAULT 'general',
    description TEXT NOT NULL DEFAULT '',
    entry_date TEXT NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_finance_ledger_company_date
    ON finance_ledger_entries(company_name, entry_date);

CREATE INDEX IF NOT EXISTS idx_finance_ledger_date
    ON finance_ledger_entries(entry_date);
