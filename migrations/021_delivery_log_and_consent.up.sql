-- S-343: Tahsilat Kanalı (WhatsApp / SMS / E-posta)
-- Two additions:
--   1) delivery_log: one row per dispatch attempt, with provider metadata
--   2) customers.{email,sms,whatsapp}_consent: KVKK opt-in flags
--      (default 0 = no consent → channel blocks the dispatch)

CREATE TABLE IF NOT EXISTS delivery_log (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name        TEXT NOT NULL,
    notification_id     INTEGER NOT NULL
                          REFERENCES notifications(id) ON DELETE CASCADE,
    channel             TEXT NOT NULL
                          CHECK (channel IN ('email','sms','whatsapp','console')),
    provider            TEXT NOT NULL,
    recipient           TEXT NOT NULL DEFAULT '',
    status              TEXT NOT NULL DEFAULT 'queued'
                          CHECK (status IN ('queued','sent','failed','sandbox',
                                            'skipped_no_consent','skipped_no_contact')),
    error_message       TEXT NOT NULL DEFAULT '',
    provider_message_id TEXT NOT NULL DEFAULT '',
    subject             TEXT NOT NULL DEFAULT '',
    body                TEXT NOT NULL DEFAULT '',
    sent_at             INTEGER,
    created_at          INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_delivery_log_company
    ON delivery_log(company_name);
CREATE INDEX IF NOT EXISTS idx_delivery_log_notification
    ON delivery_log(notification_id);
CREATE INDEX IF NOT EXISTS idx_delivery_log_status
    ON delivery_log(company_name, status);

-- KVKK consent flags on customers. Default 0 = no consent; explicit opt-in required.
ALTER TABLE customers ADD COLUMN email_consent INTEGER NOT NULL DEFAULT 0;
ALTER TABLE customers ADD COLUMN sms_consent INTEGER NOT NULL DEFAULT 0;
ALTER TABLE customers ADD COLUMN whatsapp_consent INTEGER NOT NULL DEFAULT 0;
ALTER TABLE customers ADD COLUMN consent_updated_at INTEGER NOT NULL DEFAULT 0;
