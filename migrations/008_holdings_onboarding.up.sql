CREATE TABLE IF NOT EXISTS holdings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    code TEXT UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS holding_companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    holding_id INTEGER NOT NULL,
    company_name TEXT NOT NULL,
    sector TEXT NOT NULL DEFAULT 'General',
    country TEXT NOT NULL DEFAULT 'TR',
    registered_in_platform INTEGER NOT NULL DEFAULT 0,
    data_quality_score REAL NOT NULL,
    integration_completeness_score REAL NOT NULL,
    security_compliance_score REAL NOT NULL,
    process_standardization_score REAL NOT NULL,
    master_data_health_score REAL NOT NULL,
    team_readiness_score REAL NOT NULL,
    onboarding_readiness_score REAL NOT NULL,
    onboarding_status TEXT NOT NULL,
    recommendation TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    UNIQUE(holding_id, company_name),
    FOREIGN KEY(holding_id) REFERENCES holdings(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_holding_companies_holding_id
    ON holding_companies(holding_id);

CREATE INDEX IF NOT EXISTS idx_holding_companies_company_name
    ON holding_companies(company_name);
