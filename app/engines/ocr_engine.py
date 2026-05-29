"""A4: OcrEngine — orchestration + persistence + ledger entry oluşturma."""
from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from threading import Lock
from typing import Any

from app.ocr_service import (
    ExtractedInvoice,
    OcrServiceProtocol,
)


# Max upload boyutu — 10 MB
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024

# Desteklenen MIME türleri
VALID_MIME_TYPES = frozenset({
    "image/jpeg", "image/jpg", "image/png",
    "image/webp", "image/gif",
})


@dataclass(frozen=True)
class OcrJobView:
    id: int
    user_id: str
    source_filename: str | None
    status: str
    extract: dict[str, Any]
    confidence_pct: float
    ledger_entry_id: int | None
    error_message: str | None
    created_at: int
    extracted_at: int | None
    confirmed_at: int | None


class OcrEngine:
    """OCR upload → extract → confirm → ledger orchestration."""

    def __init__(
        self,
        *,
        database_path: str,
        ocr_service: OcrServiceProtocol,
    ) -> None:
        self._lock = Lock()
        self._database_path = database_path
        self._ocr = ocr_service

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._database_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    # ── Public API ─────────────────────────────────────────────────────

    def process(
        self,
        *,
        user_id: str,
        image_bytes: bytes,
        mime_type: str,
        filename: str | None = None,
    ) -> OcrJobView:
        """Upload + extract → 'extracted' status. Confirm ayrı çağrı."""
        if not image_bytes:
            raise ValueError("Boş görüntü")
        if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
            raise ValueError(
                f"Görüntü {MAX_IMAGE_SIZE_BYTES // 1024 // 1024} MB'ı geçemez"
            )
        if mime_type not in VALID_MIME_TYPES:
            raise ValueError(
                f"Desteklenmeyen MIME: {mime_type!r}. "
                f"Geçerli: {sorted(VALID_MIME_TYPES)}"
            )

        # 1. Create job 'pending'
        job_id = self._create_job(
            user_id=user_id, filename=filename,
            size_bytes=len(image_bytes), mime_type=mime_type,
        )

        # 2. Mark processing
        self._update_status(job_id=job_id, status="processing")

        # 3. Extract via OCR service
        try:
            extracted = self._ocr.extract_invoice(
                image_bytes=image_bytes, mime_type=mime_type,
            )
        except Exception as exc:
            self._update_status(
                job_id=job_id, status="failed",
                error_message=f"OCR hatası: {exc}",
            )
            raise ValueError(f"OCR çıkartım başarısız: {exc}") from exc

        # 4. Persist extract result
        self._save_extract(job_id=job_id, extracted=extracted)
        view = self.get_job(user_id=user_id, job_id=job_id)
        assert view is not None
        return view

    def confirm(
        self,
        *,
        user_id: str,
        job_id: int,
        company_name: str,
        overrides: dict[str, Any] | None = None,
    ) -> OcrJobView:
        """User extract'i onaylar → ledger entry oluşturulur.

        overrides: kullanıcı UI'da düzeltmişse bu field'lar kullanılır
        (extract_json'ı update etmez, sadece ledger entry için).
        """
        job = self._fetch_job(job_id)
        if not job:
            raise ValueError(f"Job bulunamadı: {job_id}")
        if job["user_id"] != user_id:
            raise PermissionError("Bu job sizin değil")
        if job["status"] != "extracted":
            raise ValueError(
                f"Job onaylanamaz. Mevcut durum: {job['status']}"
            )

        extract: dict[str, Any] = self._safe_extract(job["extract_json"])
        # Apply user overrides
        if overrides:
            extract = {**extract, **{k: v for k, v in overrides.items() if v is not None}}

        ledger_id = self._create_ledger_entry(
            company_name=company_name, extract=extract,
        )

        self._update_after_confirm(
            job_id=job_id, ledger_entry_id=ledger_id,
        )

        view = self.get_job(user_id=user_id, job_id=job_id)
        assert view is not None
        return view

    def get_job(
        self, *, user_id: str, job_id: int,
    ) -> OcrJobView | None:
        row = self._fetch_job(job_id)
        if not row or row["user_id"] != user_id:
            return None
        return self._row_to_view(row)

    def list_jobs(
        self, *, user_id: str, limit: int = 20,
    ) -> list[OcrJobView]:
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    """
                    SELECT id, user_id, source_filename, source_size_bytes,
                           mime_type, status, extract_json, confidence_pct,
                           ledger_entry_id, error_message,
                           created_at, extracted_at, confirmed_at
                    FROM ocr_jobs
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (user_id, min(max(1, limit), 200)),
                ).fetchall()
            finally:
                conn.close()
        return [self._row_to_view(r) for r in rows]

    # ── Internal ───────────────────────────────────────────────────────

    def _create_job(
        self,
        *,
        user_id: str,
        filename: str | None,
        size_bytes: int,
        mime_type: str,
    ) -> int:
        now = int(time.time())
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    """
                    INSERT INTO ocr_jobs
                        (user_id, source_filename, source_size_bytes,
                         mime_type, status, created_at)
                    VALUES (?, ?, ?, ?, 'pending', ?)
                    """,
                    (user_id, filename, size_bytes, mime_type, now),
                )
                conn.commit()
                return int(cur.lastrowid or 0)
            finally:
                conn.close()

    def _update_status(
        self,
        *,
        job_id: int,
        status: str,
        error_message: str | None = None,
    ) -> None:
        with self._lock:
            conn = self._connect()
            try:
                if error_message is not None:
                    conn.execute(
                        """
                        UPDATE ocr_jobs
                        SET status = ?, error_message = ?
                        WHERE id = ?
                        """,
                        (status, error_message, job_id),
                    )
                else:
                    conn.execute(
                        "UPDATE ocr_jobs SET status = ? WHERE id = ?",
                        (status, job_id),
                    )
                conn.commit()
            finally:
                conn.close()

    def _save_extract(
        self, *, job_id: int, extracted: ExtractedInvoice,
    ) -> None:
        now = int(time.time())
        extract_json = json.dumps(
            extracted.to_dict(), ensure_ascii=False, default=str,
        )
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    UPDATE ocr_jobs
                    SET status = 'extracted',
                        extract_json = ?,
                        confidence_pct = ?,
                        extracted_at = ?
                    WHERE id = ?
                    """,
                    (extract_json, extracted.confidence_pct, now, job_id),
                )
                conn.commit()
            finally:
                conn.close()

    def _update_after_confirm(
        self, *, job_id: int, ledger_entry_id: int,
    ) -> None:
        now = int(time.time())
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    UPDATE ocr_jobs
                    SET status = 'confirmed',
                        ledger_entry_id = ?,
                        confirmed_at = ?
                    WHERE id = ?
                    """,
                    (ledger_entry_id, now, job_id),
                )
                conn.commit()
            finally:
                conn.close()

    def _fetch_job(self, job_id: int) -> sqlite3.Row | None:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    """
                    SELECT id, user_id, source_filename, source_size_bytes,
                           mime_type, status, extract_json, confidence_pct,
                           ledger_entry_id, error_message,
                           created_at, extracted_at, confirmed_at
                    FROM ocr_jobs
                    WHERE id = ?
                    """,
                    (job_id,),
                ).fetchone()
                return row  # type: ignore[no-any-return]
            finally:
                conn.close()

    def _create_ledger_entry(
        self, *, company_name: str, extract: dict[str, Any],
    ) -> int:
        amount = float(extract.get("total_amount") or 0)
        if amount <= 0:
            raise ValueError("Tutar > 0 olmalı")
        direction = str(extract.get("direction") or "incoming")
        entry_type = "income" if direction == "outgoing" else "expense"
        category = str(extract.get("category") or "ocr_import")
        desc = self._build_description(extract)
        entry_date = str(extract.get("issue_date") or time.strftime("%Y-%m-%d"))
        now = int(time.time())
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    """
                    INSERT INTO finance_ledger_entries
                        (company_name, entry_type, amount, category,
                         description, entry_date, created_at,
                         intercompany_flag)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                    """,
                    (
                        company_name, entry_type, amount, category,
                        desc, entry_date, now,
                    ),
                )
                conn.commit()
                return int(cur.lastrowid or 0)
            finally:
                conn.close()

    @staticmethod
    def _build_description(extract: dict[str, Any]) -> str:
        parts: list[str] = ["[OCR]"]
        vendor = extract.get("vendor_name")
        if vendor:
            parts.append(str(vendor))
        no = extract.get("invoice_no")
        if no:
            parts.append(f"#{no}")
        return " ".join(parts)[:500]

    @staticmethod
    def _safe_extract(raw: Any) -> dict[str, Any]:
        if not raw:
            return {}
        try:
            data = json.loads(str(raw))
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    def _row_to_view(self, row: sqlite3.Row) -> OcrJobView:
        return OcrJobView(
            id=int(row["id"]),
            user_id=str(row["user_id"]),
            source_filename=row["source_filename"],
            status=str(row["status"]),
            extract=self._safe_extract(row["extract_json"]),
            confidence_pct=float(row["confidence_pct"]),
            ledger_entry_id=(
                int(row["ledger_entry_id"])
                if row["ledger_entry_id"] is not None else None
            ),
            error_message=row["error_message"],
            created_at=int(row["created_at"]),
            extracted_at=(
                int(row["extracted_at"])
                if row["extracted_at"] is not None else None
            ),
            confirmed_at=(
                int(row["confirmed_at"])
                if row["confirmed_at"] is not None else None
            ),
        )
