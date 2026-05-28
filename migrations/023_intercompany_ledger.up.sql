-- G1.1: Intercompany ledger schema migration
--
-- Gap Analizi Critical Finding #1: finance_ledger_entries tablosu
-- çift-kayıt (double-entry) için tasarlanmamıştı. counterparty_company,
-- transfer_id, intercompany_flag kolonları yoktu → cross-company
-- transfer fiziksel olarak imkansızdı.
--
-- Bu migration:
--   1. finance_ledger_entries'e 3 yeni kolon ekler (geriye dönük uyumlu)
--   2. Yeni intercompany_transfers master tablosu oluşturur
--   3. 4-eyes onay workflow'u için approval_status alanı içerir
--   4. Performans için gerekli index'leri ekler
--
-- Mimari karar: ledger entry her zaman tek şirketin perspektifinden yazılır.
-- Bir intercompany transfer 2 ledger entry üretir (kaynak şirket: expense,
-- hedef şirket: income) ve her ikisi de aynı transfer_id'ye bağlanır.
-- counterparty_company alanı her entry'de "karşı taraf"ı saklar — bu
-- konsolidasyon eliminasyon mantığı için kritik (G1.2'de kullanılacak).

-- ─────────────────────────────────────────────────────────────────────
-- 1. finance_ledger_entries: yeni kolonlar (ALTER TABLE — geriye dönük uyumlu)
-- ─────────────────────────────────────────────────────────────────────

ALTER TABLE finance_ledger_entries
    ADD COLUMN counterparty_company TEXT;

ALTER TABLE finance_ledger_entries
    ADD COLUMN transfer_id INTEGER;

ALTER TABLE finance_ledger_entries
    ADD COLUMN intercompany_flag INTEGER NOT NULL DEFAULT 0
    CHECK(intercompany_flag IN (0, 1));

-- Index: konsolidasyon engine'i intercompany entry'leri hızlı filtrelemeli
CREATE INDEX IF NOT EXISTS idx_finance_ledger_intercompany
    ON finance_ledger_entries(intercompany_flag, transfer_id);

CREATE INDEX IF NOT EXISTS idx_finance_ledger_counterparty
    ON finance_ledger_entries(counterparty_company)
    WHERE counterparty_company IS NOT NULL;

-- ─────────────────────────────────────────────────────────────────────
-- 2. intercompany_transfers: master tablo (transfer'in "header"ı)
-- ─────────────────────────────────────────────────────────────────────
-- NOT: SQLite CREATE TABLE'da column tanımları ile table-level constraint'ler
-- KARIŞTIRILAMAZ. Tüm CHECK constraint'ler kolon tanımlarından SONRA gelir.
-- Bu yüzden from_company <> to_company CHECK'i tablonun sonunda.

CREATE TABLE IF NOT EXISTS intercompany_transfers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Holding scope (audit + filter için)
    holding_id INTEGER NOT NULL,

    -- Transfer iki ucu
    from_company TEXT NOT NULL,
    to_company TEXT NOT NULL,

    -- Para birimi ve tutar
    amount REAL NOT NULL CHECK(amount > 0),
    currency TEXT NOT NULL DEFAULT 'TRY',
    -- Eğer cross-currency ise hedef tutarı (FX conversion sonrası)
    target_amount REAL,
    fx_rate REAL,

    -- Açıklama (audit log için zorunlu)
    description TEXT NOT NULL DEFAULT '',

    -- Talep eden (initiator) — 4-eyes onay workflow'unda 1. göz
    requested_by TEXT NOT NULL,
    requested_at INTEGER NOT NULL,

    -- 4-eyes onay
    -- pending: 2. onay bekliyor
    -- approved: 2. göz onayladı, ledger'a yazıldı
    -- rejected: 2. göz reddetti
    -- completed: tamamlandı (approved + ledger entries oluşturuldu)
    approval_status TEXT NOT NULL DEFAULT 'pending'
        CHECK(approval_status IN ('pending', 'approved', 'rejected', 'completed')),

    -- 2. göz (approver) — initiator ile aynı OLMAMALI (engine-level enforcement)
    approved_by TEXT,
    approved_at INTEGER,
    reject_reason TEXT,

    -- Tamamlama
    completed_at INTEGER,

    -- Ledger entry referansları (atomic double-entry sonrası doldurulur)
    ledger_entry_from_id INTEGER,
    ledger_entry_to_id INTEGER,

    -- Table-level constraint: kendi kendine transfer mantıksız
    CHECK(from_company <> to_company),

    -- FK'ler (SQLite soft enforcement, business engine doğrular)
    FOREIGN KEY (ledger_entry_from_id) REFERENCES finance_ledger_entries(id),
    FOREIGN KEY (ledger_entry_to_id) REFERENCES finance_ledger_entries(id)
);

-- Index'ler
CREATE INDEX IF NOT EXISTS idx_intercompany_transfers_holding_status
    ON intercompany_transfers(holding_id, approval_status);

CREATE INDEX IF NOT EXISTS idx_intercompany_transfers_companies
    ON intercompany_transfers(from_company, to_company);

CREATE INDEX IF NOT EXISTS idx_intercompany_transfers_pending
    ON intercompany_transfers(approval_status, requested_at)
    WHERE approval_status = 'pending';

-- ─────────────────────────────────────────────────────────────────────
-- 3. finance_ledger_entries: FK'i intercompany_transfers'a bağla
-- ─────────────────────────────────────────────────────────────────────
-- NOT: SQLite ALTER TABLE FK ekleyemez. Soft referans olarak transfer_id
-- saklarız; business engine (G1.3) atomic write'da bütünlüğü garanti eder.
-- transfer_id IS NOT NULL iken intercompany_flag = 1 olmalı (engine doğrular).
