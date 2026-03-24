ALTER TABLE feasibility_reports ADD COLUMN company_name TEXT NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS idx_feasibility_reports_company_name
    ON feasibility_reports(company_name);
