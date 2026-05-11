-- S-322: Task / job tracking
CREATE TABLE IF NOT EXISTS tasks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name TEXT NOT NULL,
    title        TEXT NOT NULL,
    description  TEXT NOT NULL DEFAULT '',
    assigned_to  TEXT NOT NULL DEFAULT '',
    priority     TEXT NOT NULL DEFAULT 'medium'
                 CHECK(priority IN ('low','medium','high','critical')),
    status       TEXT NOT NULL DEFAULT 'open'
                 CHECK(status IN ('open','in_progress','done','cancelled')),
    due_date     TEXT,
    customer_id  INTEGER REFERENCES customers(id) ON DELETE SET NULL,
    created_by   TEXT NOT NULL DEFAULT '',
    created_at   INTEGER NOT NULL,
    updated_at   INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_company_name ON tasks(company_name);
CREATE INDEX IF NOT EXISTS idx_tasks_assigned_to  ON tasks(assigned_to);
CREATE INDEX IF NOT EXISTS idx_tasks_status       ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_due_date     ON tasks(due_date);
