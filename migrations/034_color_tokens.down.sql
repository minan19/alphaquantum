-- 034 rollback: color_tokens tablosunu sil.
DROP INDEX IF EXISTS idx_color_tokens_category;
DROP INDEX IF EXISTS idx_color_tokens_scope;
DROP TABLE IF EXISTS color_tokens;
