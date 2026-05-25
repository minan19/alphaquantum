-- S-334: Vade Uyarı / Bildirim Motoru
-- Stores generated notifications (invoice due windows, overdue events, etc.)
-- The UNIQUE constraint enforces idempotency: re-running the scanner cannot
-- duplicate a notification for the same (subject, window).

CREATE TABLE IF NOT EXISTS notifications (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name  TEXT NOT NULL,
    kind          TEXT NOT NULL,                         -- 'invoice_due_soon' | 'invoice_overdue'
    severity      TEXT NOT NULL DEFAULT 'info',          -- info | warning | critical
    subject_type  TEXT NOT NULL,                         -- 'invoice' (future: 'task', 'proposal')
    subject_id    INTEGER NOT NULL,
    window_key    TEXT NOT NULL,                         -- 'T-3' | 'T-1' | 'T+1' | 'T+7' | 'T+14'
    title         TEXT NOT NULL,
    message       TEXT NOT NULL DEFAULT '',
    is_read       INTEGER NOT NULL DEFAULT 0,
    created_at    INTEGER NOT NULL,
    updated_at    INTEGER NOT NULL,
    UNIQUE(subject_type, subject_id, window_key)
);

CREATE INDEX IF NOT EXISTS idx_notifications_company
    ON notifications(company_name);

CREATE INDEX IF NOT EXISTS idx_notifications_unread
    ON notifications(company_name, is_read);

CREATE INDEX IF NOT EXISTS idx_notifications_severity
    ON notifications(company_name, severity);
