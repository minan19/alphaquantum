-- SQLite does not support DROP COLUMN; recreate the table without company_name

CREATE TABLE feasibility_reports_v0 AS
    SELECT id, project_name, sector, geography, status, payload_json, report_json, created_at
    FROM feasibility_reports;

DROP TABLE feasibility_reports;

ALTER TABLE feasibility_reports_v0 RENAME TO feasibility_reports;

CREATE INDEX IF NOT EXISTS idx_feasibility_reports_created_at
    ON feasibility_reports(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_feasibility_reports_sector
    ON feasibility_reports(sector);
