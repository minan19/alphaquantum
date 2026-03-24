CREATE TABLE IF NOT EXISTS finance_recurring_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name TEXT NOT NULL,
    entry_type TEXT NOT NULL CHECK(entry_type IN ('income', 'expense')),
    amount REAL NOT NULL CHECK(amount > 0),
    category TEXT NOT NULL DEFAULT 'general',
    description TEXT NOT NULL DEFAULT '',
    frequency TEXT NOT NULL CHECK(frequency IN ('weekly', 'monthly', 'quarterly', 'yearly')),
    start_date TEXT NOT NULL,
    end_date TEXT,
    last_generated_date TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_finance_recurring_company
    ON finance_recurring_entries(company_name);

CREATE INDEX IF NOT EXISTS idx_finance_recurring_active
    ON finance_recurring_entries(company_name, is_active);

CREATE TABLE IF NOT EXISTS finance_budgets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name TEXT NOT NULL,
    year INTEGER NOT NULL,
    month INTEGER,
    category TEXT NOT NULL,
    entry_type TEXT NOT NULL CHECK(entry_type IN ('income', 'expense')),
    budget_amount REAL NOT NULL CHECK(budget_amount >= 0),
    created_at INTEGER NOT NULL,
    UNIQUE(company_name, year, month, category, entry_type)
);

CREATE INDEX IF NOT EXISTS idx_finance_budgets_company_year
    ON finance_budgets(company_name, year, month);
