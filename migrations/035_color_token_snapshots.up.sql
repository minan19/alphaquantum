-- 035: Design Token Programı · Faz 5
-- ColorTokenSnapshot tablosu — geri sarma zinciri için anlık görüntü kaydı.
--
-- Anlık görüntü kavramı:
--   * Her PATCH öncesi otomatik snapshot alınır ("pre_save").
--   * Her restore/reset öncesi otomatik snapshot alınır ("pre_restore" / "pre_reset").
--   * Kullanıcı manuel "etiketli kayıt" oluşturabilir ("manual").
-- Snapshot'lar scope bazlıdır (core/aq/finos/corpos) ve scope'un tam payload'unu
-- (JSON dizisi olarak) tutar. Restore = JSON'u dağıt + upsert.
--
-- Retention: scope başına son 20 snapshot tutulur (rotation repository tarafından).

CREATE TABLE IF NOT EXISTS color_token_snapshots (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  scope         TEXT NOT NULL CHECK(scope IN ('core', 'aq', 'finos', 'corpos')),
  source        TEXT NOT NULL CHECK(source IN ('pre_save', 'pre_restore', 'pre_reset', 'manual')),
  label         TEXT NOT NULL,
  payload_json  TEXT NOT NULL,
  created_by    TEXT,
  taken_at      INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_color_token_snapshots_scope_taken
  ON color_token_snapshots(scope, taken_at DESC);
