-- T1: Multi-bank Treasury — banka hesapları + günlük bakiye snapshot
--
-- 2 tablo:
--   * treasury_accounts        — banka hesap meta
--   * treasury_balance_history — günlük bakiye snapshot (trend için)

CREATE TABLE IF NOT EXISTS treasury_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    company_name TEXT NOT NULL,
    bank_name TEXT NOT NULL,                 -- "Garanti BBVA", "İş Bankası" vs.
    branch TEXT,
    iban TEXT,                               -- TR + 24 hane (unique constraint)
    account_no TEXT,                         -- IBAN yoksa fallback
    account_type TEXT NOT NULL DEFAULT 'vadesiz'
        CHECK (account_type IN ('vadesiz', 'vadeli', 'kredi', 'pos', 'doviz', 'diğer')),
    currency TEXT NOT NULL DEFAULT 'TRY',
    current_balance REAL NOT NULL DEFAULT 0,
    last_synced_at INTEGER,
    is_active INTEGER NOT NULL DEFAULT 1,
    notes TEXT,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    UNIQUE (user_id, iban) -- aynı IBAN tek hesap (NULL'lar çakışmaz SQLite'da)
);

CREATE INDEX IF NOT EXISTS idx_treasury_accounts_user
    ON treasury_accounts(user_id, is_active, currency);

CREATE INDEX IF NOT EXISTS idx_treasury_accounts_company
    ON treasury_accounts(company_name, is_active);


CREATE TABLE IF NOT EXISTS treasury_balance_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES treasury_accounts(id) ON DELETE CASCADE,
    snapshot_date TEXT NOT NULL,             -- YYYY-MM-DD
    balance REAL NOT NULL,
    snapshot_source TEXT NOT NULL DEFAULT 'manual'
        CHECK (snapshot_source IN ('manual', 'csv_import', 'mt940', 'camt053', 'open_banking')),
    created_at INTEGER NOT NULL,
    UNIQUE (account_id, snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_treasury_history_date
    ON treasury_balance_history(snapshot_date DESC);
