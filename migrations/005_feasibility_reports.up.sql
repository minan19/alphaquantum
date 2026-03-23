CREATE TABLE IF NOT EXISTS feasibility_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_name TEXT NOT NULL,
    sector TEXT NOT NULL,
    geography TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'generated',
    payload_json TEXT NOT NULL,
    report_json TEXT NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_feasibility_reports_created_at
    ON feasibility_reports(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_feasibility_reports_sector
    ON feasibility_reports(sector);
