-- 034: Design Token Programı · Faz 1
-- ColorToken tablosu — design token sözlüğü için tek-doğruluk-kaynağı.
-- Faz 0'daki foundation.md + wcag-report.json bu tabloya seed edilir.
--
-- Scope governance (uygulama katmanında ek olarak guard'la):
--   core   = ortak token'lar (bg/surface/border, text, status, focus-ring)
--   aq     = AlphaQ çatı kimliği
--   finos  = FinOS kimliği
--   corpos = CorpOS kimliği
-- Modüller core-sahipli anahtarları EZEMEZ (whitelist app/color_token_repository.py'de).

CREATE TABLE IF NOT EXISTS color_tokens (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  scope         TEXT NOT NULL CHECK(scope IN ('core', 'aq', 'finos', 'corpos')),
  key           TEXT NOT NULL,
  value         TEXT NOT NULL,
  label         TEXT NOT NULL,
  category      TEXT NOT NULL,
  display_order INTEGER NOT NULL DEFAULT 0,
  updated_at    INTEGER NOT NULL,
  UNIQUE(scope, key)
);

CREATE INDEX IF NOT EXISTS idx_color_tokens_scope    ON color_tokens(scope);
CREATE INDEX IF NOT EXISTS idx_color_tokens_category ON color_tokens(category);
