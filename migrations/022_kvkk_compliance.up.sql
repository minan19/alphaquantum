-- A4: KVKK Uyum (Kişisel Verilerin Korunması Kanunu)
-- Madde 11 veri sahibinin haklarını teknik olarak destekler.
-- Yasal risk: KVK Kurumu cezası 50.000-1.000.000 TL.

-- ──────────────────────────────────────────────────────────────────────────
-- account_deletion_requests: KVKK madde 11(e) silme talepleri kuyruğu
-- ──────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS account_deletion_requests (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id          INTEGER NOT NULL,
    requested_at     INTEGER NOT NULL,
    reason           TEXT NOT NULL DEFAULT '',
    status           TEXT NOT NULL DEFAULT 'pending'
                       CHECK (status IN ('pending','approved','rejected','completed')),
    decision_at      INTEGER,
    decision_by      INTEGER,
    decision_note    TEXT NOT NULL DEFAULT '',
    completed_at     INTEGER,
    -- Anonymization audit: hangi alanlar maskelendi?
    anonymized_fields TEXT NOT NULL DEFAULT '',  -- JSON list
    created_at       INTEGER NOT NULL,
    updated_at       INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_adr_user      ON account_deletion_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_adr_status    ON account_deletion_requests(status);
CREATE INDEX IF NOT EXISTS idx_adr_requested ON account_deletion_requests(requested_at);

-- ──────────────────────────────────────────────────────────────────────────
-- security_incidents: KVKK madde 12 veri ihlal raporları
-- KVK Kurumu'na 72 saat içinde bildirim zorunluluğu (high/critical için)
-- ──────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS security_incidents (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_type               TEXT NOT NULL,
    severity                    TEXT NOT NULL
                                  CHECK (severity IN ('low','medium','high','critical')),
    affected_user_id            INTEGER,
    affected_record_count       INTEGER NOT NULL DEFAULT 0,
    description                 TEXT NOT NULL,
    reported_by                 INTEGER,
    reported_at                 INTEGER NOT NULL,
    -- KVKK madde 12: ihlali öğrendikten sonra 72 saat içinde bildirim
    kvkk_notification_required  INTEGER NOT NULL DEFAULT 0,
    kvkk_notification_sent_at   INTEGER,
    kvkk_notification_reference TEXT NOT NULL DEFAULT '',
    -- Veri sahibi bildirimi
    data_subject_notified_at    INTEGER,
    resolution_status           TEXT NOT NULL DEFAULT 'open'
                                  CHECK (resolution_status IN ('open','investigating','resolved','closed')),
    resolution_summary          TEXT NOT NULL DEFAULT '',
    resolved_at                 INTEGER,
    created_at                  INTEGER NOT NULL,
    updated_at                  INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_si_severity ON security_incidents(severity);
CREATE INDEX IF NOT EXISTS idx_si_status   ON security_incidents(resolution_status);
CREATE INDEX IF NOT EXISTS idx_si_user     ON security_incidents(affected_user_id);
CREATE INDEX IF NOT EXISTS idx_si_reported ON security_incidents(reported_at);

-- ──────────────────────────────────────────────────────────────────────────
-- users tablo extension: KVKK consent + son veri erişim/export izleri
-- ──────────────────────────────────────────────────────────────────────────
ALTER TABLE users ADD COLUMN kvkk_consent_at      INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN kvkk_consent_version TEXT NOT NULL DEFAULT 'v1';
ALTER TABLE users ADD COLUMN last_data_export_at  INTEGER;
ALTER TABLE users ADD COLUMN last_data_access_at  INTEGER;
-- Soft delete flag (anonymize sonrası)
ALTER TABLE users ADD COLUMN anonymized_at        INTEGER;
