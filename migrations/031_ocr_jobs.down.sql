-- A4: OCR jobs rollback
DROP INDEX IF EXISTS idx_ocr_jobs_status;
DROP INDEX IF EXISTS idx_ocr_jobs_user_time;
DROP TABLE IF EXISTS ocr_jobs;
