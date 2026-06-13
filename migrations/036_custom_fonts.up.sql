-- 036: Design Token Programı · Faz 6
-- CustomFont — panel'den eklenip çalışma zamanında yüklenen dış fontlar.
--
-- Scope ekseni: core (her modül için ortak default) + aq/finos/corpos
-- (modül-bazlı aile; CorpOS executive serif, FinOS modern sans gibi).
-- Source = 'google' | 'upload'.
--   google → css_url (https://fonts.googleapis.com/...) sayfaya <link> olarak ekler.
--   upload → data (base64) baytları cache'lenir; @font-face src: /api/fonts/<id>.
--
-- is_default: scope başına yalnız bir font 'varsayılan' olabilir (atanırken
-- repository diğerini sıfırlar). Default font, --font-display zincirinin
-- BAŞINA scope-aware enjekte edilir; yüklenmezse zincir bozulmadan
-- framework Inter'a (next/font) → system-ui'a düşer.

CREATE TABLE IF NOT EXISTS custom_fonts (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  scope       TEXT NOT NULL CHECK(scope IN ('core', 'aq', 'finos', 'corpos')),
  family      TEXT NOT NULL,
  source      TEXT NOT NULL CHECK(source IN ('google', 'upload')),
  css_url     TEXT,
  data_b64    TEXT,
  format      TEXT,
  weight      TEXT,
  style       TEXT,
  is_default  INTEGER NOT NULL DEFAULT 0 CHECK(is_default IN (0, 1)),
  created_at  INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_custom_fonts_scope ON custom_fonts(scope);
CREATE UNIQUE INDEX IF NOT EXISTS uq_custom_fonts_scope_family
  ON custom_fonts(scope, family);
