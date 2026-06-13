-- 036: Design Token Programı · Faz 6 — rollback.
DROP INDEX IF EXISTS uq_custom_fonts_scope_family;
DROP INDEX IF EXISTS idx_custom_fonts_scope;
DROP TABLE IF EXISTS custom_fonts;
