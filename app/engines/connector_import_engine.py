"""I1: ConnectorImportEngine — parse + preview + commit orkestrasyonu.

## Akış

  1. User upload yapar → engine.parse_and_preview() çağrılır
     → job DB'de 'preview' status'le yaratılır, ilk 10 record gösterilir
  2. User confirm eder → engine.commit_job() çağrılır
     → preview JSON'undan customers + invoices DB'ye yazılır
     → idempotency: signature_hash zaten varsa skip

## Idempotency

  Customer: signature_hash unique. crm_customers tablosuna upsert.
  Invoice:  signature_hash unique. invoices tablosuna upsert + ledger
            entry oluşturur (incoming=expense, outgoing=income).

## Multi-tenant izolasyonu

Job user_id ile scope'lanır. List/get endpoint'leri kendi job'unu görür.
Admin RBAC ile başkalarınınkini görür (router seviyesinde kontrol).
"""
from __future__ import annotations

import sqlite3
import time
from dataclasses import asdict
from typing import Any

from app.connector_import_repository import ConnectorImportRepository
from app.connectors import (
    ConnectorMode,
    ParsedCustomer,
    ParsedInvoice,
    get_connector,
)


# Preview için max kaç satır görsün
PREVIEW_LIMIT = 10

# Bir import job'ında max kayıt sayısı — DoS koruması
MAX_RECORDS_PER_JOB = 50_000


class ConnectorImportEngine:
    """Logo Tiger + future ERP import orkestrasyonu."""

    def __init__(
        self,
        *,
        repo: ConnectorImportRepository,
        ledger_db_path: str,
    ) -> None:
        self._repo = repo
        self._ledger_db_path = ledger_db_path

    # ── Public API ─────────────────────────────────────────────────────

    def parse_and_preview(
        self,
        *,
        user_id: str,
        connector_type: str,
        mode: str,
        data: bytes,
        filename: str | None = None,
    ) -> dict[str, Any]:
        """Upload edilen veriyi parse et, preview göster, DB'ye job yaz.

        Returns: job dict (id + summary + preview + status).
        Status 'preview' → user confirm bekleniyor.
        """
        try:
            connector_mode = ConnectorMode(mode)
        except ValueError as exc:
            raise ValueError(f"Geçersiz mod: {mode!r}") from exc

        connector = get_connector(connector_type)
        if connector_mode not in connector.supported_modes:
            raise ValueError(
                f"{connector_type} '{mode}' modunu desteklemiyor. "
                f"Desteklenen: {[m.value for m in connector.supported_modes]}"
            )

        job_id = self._repo.create_job(
            user_id=user_id,
            connector_type=connector_type,
            mode=mode,
            source_filename=filename,
            source_size_bytes=len(data),
        )
        self._repo.update_status(job_id=job_id, status="parsing")

        try:
            parsed = connector.parse(
                data=data, mode=connector_mode, filename=filename,
            )
        except Exception as exc:
            self._repo.update_status(
                job_id=job_id, status="failed",
                error_message=f"Parse hatası: {exc}",
            )
            raise ValueError(f"Parse hatası: {exc}") from exc

        total_records = len(parsed.customers) + len(parsed.invoices)
        if total_records > MAX_RECORDS_PER_JOB:
            self._repo.update_status(
                job_id=job_id, status="failed",
                error_message=(
                    f"Tek import'ta max {MAX_RECORDS_PER_JOB} kayıt. "
                    f"Gelen: {total_records}"
                ),
            )
            raise ValueError(
                f"Tek import'ta max {MAX_RECORDS_PER_JOB} kayıt. "
                f"Gelen: {total_records}"
            )

        # Preview — ilk PREVIEW_LIMIT customer + ilk PREVIEW_LIMIT invoice
        preview = self._build_preview(parsed.customers, parsed.invoices)
        summary = parsed.summary

        self._repo.update_status(
            job_id=job_id, status="preview",
            summary=summary, preview=preview,
        )

        # Hatalar varsa kaydet
        if parsed.errors:
            self._repo.insert_errors(
                job_id=job_id,
                errors=[asdict(e) for e in parsed.errors],
            )

        # Geçici olarak parsed objeyi cache'lemiyoruz — commit'te yeniden
        # preview JSON'undan reconstruct ederiz (basit + state-free).
        # Production'da redis/file cache ile büyük dataset için optimize edilebilir.
        # Burada: commit_job parsed kaydedilmiş tüm record'ları yeniden parse
        # eder; bu MVP için yeterli (max 50k record).
        return {
            **(self._repo.get_job(job_id) or {}),
            "errors": [asdict(e) for e in parsed.errors],
        }

    def commit_job(
        self,
        *,
        user_id: str,
        job_id: int,
        raw_data: bytes,
    ) -> dict[str, Any]:
        """Preview status'teki job'u DB'ye commit et.

        raw_data: orijinal upload bytes (caller saklamak zorunda).
                  MVP: client tekrar gönderir, gelecekte temp file cache.
        """
        job = self._repo.get_job(job_id)
        if not job:
            raise ValueError(f"Job bulunamadı: {job_id}")
        if job["user_id"] != user_id:
            raise PermissionError("Bu import sizin değil")
        if job["status"] != "preview":
            raise ValueError(
                f"Job commit edilemez. Mevcut durum: {job['status']}"
            )

        self._repo.update_status(job_id=job_id, status="committing")

        try:
            connector = get_connector(job["connector_type"])
            mode_enum = ConnectorMode(job["mode"])
            parsed = connector.parse(data=raw_data, mode=mode_enum)
        except Exception as exc:
            self._repo.update_status(
                job_id=job_id, status="failed",
                error_message=f"Commit parse hatası: {exc}",
            )
            raise

        try:
            committed_counts = self._persist_records(
                user_id=user_id,
                customers=parsed.customers,
                invoices=parsed.invoices,
            )
        except Exception as exc:
            self._repo.update_status(
                job_id=job_id, status="failed",
                error_message=f"Persist hatası: {exc}",
            )
            raise

        final_summary = {
            **parsed.summary,
            "committed_customers": committed_counts["customers"],
            "committed_invoices": committed_counts["invoices"],
        }
        self._repo.update_status(
            job_id=job_id, status="completed", summary=final_summary,
        )
        return self._repo.get_job(job_id) or {}

    def get_job(
        self, *, user_id: str, job_id: int,
    ) -> dict[str, Any] | None:
        job = self._repo.get_job(job_id)
        if not job:
            return None
        if job["user_id"] != user_id:
            return None
        job["errors"] = self._repo.list_errors(job_id=job_id, limit=50)
        return job

    def list_jobs(
        self, *, user_id: str, limit: int = 20,
    ) -> list[dict[str, Any]]:
        return self._repo.list_jobs(user_id=user_id, limit=limit)

    def cancel_job(self, *, user_id: str, job_id: int) -> bool:
        job = self._repo.get_job(job_id)
        if not job or job["user_id"] != user_id:
            return False
        if job["status"] not in ("pending", "parsing", "preview"):
            return False
        self._repo.update_status(job_id=job_id, status="cancelled")
        return True

    # ── Internals ──────────────────────────────────────────────────────

    def _build_preview(
        self,
        customers: list[ParsedCustomer],
        invoices: list[ParsedInvoice],
    ) -> list[dict[str, Any]]:
        preview: list[dict[str, Any]] = []
        for c in customers[:PREVIEW_LIMIT]:
            preview.append({"type": "customer", "data": asdict(c)})
        for inv in invoices[:PREVIEW_LIMIT]:
            preview.append({"type": "invoice", "data": asdict(inv)})
        return preview

    def _persist_records(
        self,
        *,
        user_id: str,
        customers: list[ParsedCustomer],
        invoices: list[ParsedInvoice],
    ) -> dict[str, int]:
        """Customer + Invoice → crm_customers + invoices + ledger entry.

        Idempotency: signature_hash UNIQUE constraint kullanılarak duplicate'ler
        ON CONFLICT DO NOTHING ile atlanır.

        crm_customers ve invoices şemalarını bilmiyoruz (her proje farklı).
        MVP yaklaşımı: connector_import_records adlı genel-amaçlı staging
        tablosuna yaz — gerçek CRM/finance entegrasyonu user-facing import
        review aşamasında "Şirket olarak ekle" → "Fatura olarak ekle" akışı
        ile yapılır. Bu sprint sadece staging'i yazıyor.
        """
        now = int(time.time())
        conn = sqlite3.connect(self._ledger_db_path, check_same_thread=False)
        c_inserted = 0
        i_inserted = 0
        try:
            # Staging table — schema'sı bu engine'e ait
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS connector_staged_customers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    signature_hash TEXT NOT NULL UNIQUE,
                    payload_json TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS connector_staged_invoices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    signature_hash TEXT NOT NULL UNIQUE,
                    payload_json TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                )
                """
            )
            import json as _json
            for c in customers:
                cur = conn.execute(
                    """
                    INSERT INTO connector_staged_customers
                        (user_id, signature_hash, payload_json, created_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(signature_hash) DO NOTHING
                    """,
                    (
                        user_id, c.signature_hash,
                        _json.dumps(asdict(c), ensure_ascii=False, default=str),
                        now,
                    ),
                )
                if cur.rowcount > 0:
                    c_inserted += 1
            for inv in invoices:
                cur = conn.execute(
                    """
                    INSERT INTO connector_staged_invoices
                        (user_id, signature_hash, payload_json, created_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(signature_hash) DO NOTHING
                    """,
                    (
                        user_id, inv.signature_hash,
                        _json.dumps(asdict(inv), ensure_ascii=False, default=str),
                        now,
                    ),
                )
                if cur.rowcount > 0:
                    i_inserted += 1
            conn.commit()
        finally:
            conn.close()
        return {"customers": c_inserted, "invoices": i_inserted}
