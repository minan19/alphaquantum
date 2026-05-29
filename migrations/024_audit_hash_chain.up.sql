-- G+4: Audit hash chain — bağımsız denetçi-grade immutability.
--
-- audit_logs tablosuna 2 yeni kolon:
--   entry_hash TEXT — bu entry'nin SHA-256 hash'i (kanonik content + prev_hash)
--   prev_hash TEXT — önceki entry'nin entry_hash'i (zincir bağlantısı)
--
-- Genesis entry: prev_hash = "0" × 64 (sentinel).
--
-- Bir entry değiştirilirse:
--   1. entry_hash artık içerikle uyuşmaz → tespit (verify_entry False)
--   2. Sonraki entry'nin prev_hash'i artık önceki hash ile uyuşmaz → zincir kırılır
--
-- KVKK madde 12 + ISO 27001 A.12.4 + SOC 2 CC7.2 zorunluluğu.
-- Bağımsız denetçi "log dokunulmamış mı?" sorusunu O(N) verify ile cevaplar.

ALTER TABLE audit_logs ADD COLUMN entry_hash TEXT;
ALTER TABLE audit_logs ADD COLUMN prev_hash TEXT;

-- Index: zincir verify O(N) — id sıralı tarama
CREATE INDEX IF NOT EXISTS idx_audit_logs_id_hash
    ON audit_logs(id, entry_hash);

-- NOT: mevcut entries (pre-G+4) için entry_hash/prev_hash NULL kalır.
-- Bunlar "legacy entries" — hash chain bu migration sonrası başlar.
-- verify_chain bunları "genesis öncesi" olarak işaretler.
