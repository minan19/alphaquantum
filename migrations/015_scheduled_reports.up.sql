CREATE TABLE IF NOT EXISTS scheduled_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    report_type TEXT NOT NULL CHECK(report_type IN ('ledger', 'budget_vs_actual')),
    format TEXT NOT NULL CHECK(format IN ('xlsx', 'pdf')),
    company_name TEXT,
    params_json TEXT NOT NULL DEFAULT '{}',
    schedule_cron TEXT NOT NULL,
    recipient TEXT NOT NULL DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,
    last_run_at INTEGER,
    last_status TEXT,
    created_by TEXT NOT NULL DEFAULT '',
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_scheduled_reports_active ON scheduled_reports(is_active);
CREATE INDEX IF NOT EXISTS idx_scheduled_reports_report_type ON scheduled_reports(report_type);
