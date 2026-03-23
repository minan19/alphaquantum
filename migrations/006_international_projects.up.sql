CREATE TABLE IF NOT EXISTS international_projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_name TEXT NOT NULL,
    company_name TEXT NOT NULL,
    base_country TEXT NOT NULL,
    target_countries_json TEXT NOT NULL,
    services_json TEXT NOT NULL,
    budget_total REAL NOT NULL,
    currency TEXT NOT NULL,
    timeline_months INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'generated',
    payload_json TEXT NOT NULL,
    report_json TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_international_projects_status
    ON international_projects(status);

CREATE INDEX IF NOT EXISTS idx_international_projects_updated_at
    ON international_projects(updated_at DESC);
