"""A4: KVKK Engine — veri sahibi hakları + güvenlik ihlali yönetimi.

KVKK (Kişisel Verilerin Korunması Kanunu) madde 11-13 kapsamı:
- Madde 11: veri sahibi hakları (erişim, düzeltme, silme, kısıtlama)
- Madde 12: güvenlik tedbirleri + ihlal bildirimi (72 saat)
- Madde 13: aydınlatma yükümlülüğü

Bu engine yalnızca KVKK iş kuralları için. Asıl PII anonymize işlemi
KVKKRepository.anonymize_user içinde yapılır; diğer repository'lerin
(CRM, invoice, vb.) kendi anonymize fonksiyonları gerekiyorsa onlar da
ayrı eklenecek (gelecek sprint).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any

from app.identity_repository import IdentityRepository
from app.kvkk_repository import KVKKRepository
from app.models import (
    KVKKConsentStatusResponse,
    KVKKDataExportResponse,
    KVKKDataProcessingActivitiesResponse,
    KVKKDataProcessingActivity,
    KVKKDeletionRequestListResponse,
    KVKKDeletionRequestRead,
    KVKKSecurityIncidentListResponse,
    KVKKSecurityIncidentRead,
)


# Static aydınlatma metni — kanuni gereklilik.
# Yeni bir engine eklendiğinde buraya da bir kayıt eklenmelidir.
STATIC_DATA_PROCESSING_ACTIVITIES: list[dict[str, Any]] = [
    {
        "activity": "Kullanıcı kimlik doğrulama",
        "purpose": "Hizmet sunumu, oturum yönetimi, audit log",
        "legal_basis": "KVKK madde 5/2-f (meşru menfaat)",
        "data_categories": ["kimlik (kullanıcı adı)", "iletişim (giriş IP'si)"],
        "retention_period": "Hesap aktif olduğu sürece + 5 yıl arşiv",
        "third_party_sharing": False,
    },
    {
        "activity": "Müşteri ilişkileri yönetimi (CRM)",
        "purpose": "Müşteri kayıtları, teklif yönetimi, satış izleme",
        "legal_basis": "KVKK madde 5/2-c (sözleşmenin ifası)",
        "data_categories": ["kimlik", "iletişim", "müşteri profili"],
        "retention_period": "Sözleşme süresi + 10 yıl (TTK)",
        "third_party_sharing": False,
    },
    {
        "activity": "Tahsilat ve fatura yönetimi",
        "purpose": "Fatura kesimi, ödeme takibi, alacak yönetimi",
        "legal_basis": "KVKK madde 5/2-c (sözleşmenin ifası) + 5/2-ç (yasal yükümlülük)",
        "data_categories": ["finansal", "ticari (fatura)"],
        "retention_period": "Yasal saklama 10 yıl (VUK)",
        "third_party_sharing": True,  # GİB e-fatura için
    },
    {
        "activity": "Vade uyarı ve bildirim",
        "purpose": "Otomatik tahsilat hatırlatma (e-posta/SMS/WhatsApp)",
        "legal_basis": "Açık rıza (S-343 consent flag)",
        "data_categories": ["iletişim", "tahsilat geçmişi"],
        "retention_period": "Onay geri çekilene kadar",
        "third_party_sharing": True,  # SendGrid/Twilio/360dialog
    },
    {
        "activity": "Müşteri ödeme risk skoru",
        "purpose": "Davranışsal ödeme güvenilirlik analizi",
        "legal_basis": "KVKK madde 5/2-f (meşru menfaat) + madde 6/3 (açık rıza)",
        "data_categories": ["finansal davranış"],
        "retention_period": "5 yıl",
        "third_party_sharing": False,
    },
    {
        "activity": "Audit log",
        "purpose": "Güvenlik izlenebilirlik, KVKK madde 12 uyumu",
        "legal_basis": "KVKK madde 12 (güvenlik tedbiri)",
        "data_categories": ["sistem erişim kaydı", "IP, request_id"],
        "retention_period": "5 yıl",
        "third_party_sharing": False,
    },
]


class KVKKEngine:
    def __init__(
        self,
        *,
        kvkk_repo: KVKKRepository,
        identity_repo: IdentityRepository,
    ) -> None:
        self._kvkk = kvkk_repo
        self._identity = identity_repo

    # ── Consent ──────────────────────────────────────────────────────────────

    def record_consent(
        self, user_id: int, *, version: str = "v1"
    ) -> KVKKConsentStatusResponse:
        self._kvkk.record_consent(user_id, version=version)
        return self.get_consent_status(user_id)

    def get_consent_status(self, user_id: int) -> KVKKConsentStatusResponse:
        raw = self._kvkk.get_user_kvkk_status(user_id)
        return KVKKConsentStatusResponse(
            user_id=int(raw.get("user_id", user_id)),
            consent_at=int(raw.get("consent_at") or 0),
            consent_version=str(raw.get("consent_version") or ""),
            last_data_access_at=raw.get("last_data_access_at"),
            last_data_export_at=raw.get("last_data_export_at"),
            anonymized_at=raw.get("anonymized_at"),
        )

    # ── Data export ──────────────────────────────────────────────────────────

    def export_user_data(
        self,
        user_id: int,
        *,
        username: str,
        role: str,
        company_scopes: list[str],
        created_at: int,
        updated_at: int,
        related_records: dict[str, int] | None = None,
        signing_secret: str | None = None,
    ) -> KVKKDataExportResponse:
        """KVKK madde 11(b) — bilgi talep etme. Kullanıcının kendi verilerinin
        JSON dökümü; HMAC-SHA256 ile imzalı (delil olarak kullanılabilir)."""
        self._kvkk.mark_data_export(user_id)
        self._kvkk.mark_data_access(user_id)

        consent_status = self.get_consent_status(user_id)
        now = int(time.time())

        payload = {
            "user_id": user_id,
            "username": username,
            "role": role,
            "company_scopes": company_scopes,
            "created_at": created_at,
            "updated_at": updated_at,
            "consent_at": consent_status.consent_at,
            "consent_version": consent_status.consent_version,
            "exported_at": now,
        }
        # HMAC-SHA256 signature
        secret = (signing_secret or "kvkk-default").encode()
        signature = hmac.new(
            secret, json.dumps(payload, sort_keys=True).encode(), hashlib.sha256
        ).hexdigest()

        return KVKKDataExportResponse(
            user_id=user_id,
            username=username,
            role=role,
            company_scopes=company_scopes,
            created_at=created_at,
            updated_at=updated_at,
            kvkk_consent={
                "consent_at": consent_status.consent_at,
                "consent_version": consent_status.consent_version,
                "last_export_at": now,
            },
            audit_trail=[],  # gelecek: AuditRepository'den çekilebilir
            related_records=related_records or {},
            exported_at=now,
            export_signature=f"hmac-sha256={signature}",
        )

    # ── Deletion requests ───────────────────────────────────────────────────

    def create_deletion_request(
        self, *, user_id: int, reason: str = ""
    ) -> KVKKDeletionRequestRead:
        row = self._kvkk.create_deletion_request(user_id=user_id, reason=reason)
        return self._to_deletion_read(row)

    def get_deletion_request(
        self, request_id: int
    ) -> KVKKDeletionRequestRead | None:
        row = self._kvkk.get_deletion_request(request_id)
        return self._to_deletion_read(row) if row else None

    def list_deletion_requests(
        self,
        *,
        status: str | None = None,
        user_id: int | None = None,
        limit: int = 200,
    ) -> KVKKDeletionRequestListResponse:
        rows = self._kvkk.list_deletion_requests(
            status=status, user_id=user_id, limit=limit
        )
        items = [self._to_deletion_read(r) for r in rows]
        return KVKKDeletionRequestListResponse(total=len(items), requests=items)

    def decide_deletion(
        self,
        request_id: int,
        *,
        decision: str,
        decision_by: int,
        decision_note: str = "",
    ) -> KVKKDeletionRequestRead | None:
        row = self._kvkk.decide_deletion_request(
            request_id,
            decision=decision,
            decision_by=decision_by,
            decision_note=decision_note,
        )
        if row is None:
            return None
        # If approved → execute anonymization right away
        if decision == "approved":
            anonymized = self._kvkk.anonymize_user(int(row["user_id"]))
            completed = self._kvkk.mark_deletion_completed(request_id, anonymized)
            if completed is not None:
                row = completed
        return self._to_deletion_read(row)

    # ── Security incidents ──────────────────────────────────────────────────

    def report_incident(
        self,
        *,
        reported_by: int,
        incident_type: str,
        severity: str,
        description: str,
        affected_user_id: int | None = None,
        affected_record_count: int = 0,
    ) -> KVKKSecurityIncidentRead:
        row = self._kvkk.create_incident(
            incident_type=incident_type,
            severity=severity,
            description=description,
            reported_by=reported_by,
            affected_user_id=affected_user_id,
            affected_record_count=affected_record_count,
        )
        return self._to_incident_read(row)

    def list_incidents(
        self,
        *,
        severity: str | None = None,
        status: str | None = None,
        limit: int = 200,
    ) -> KVKKSecurityIncidentListResponse:
        rows = self._kvkk.list_incidents(
            severity=severity, status=status, limit=limit
        )
        items = [self._to_incident_read(r) for r in rows]
        return KVKKSecurityIncidentListResponse(total=len(items), incidents=items)

    # ── Aydınlatma metni ─────────────────────────────────────────────────────

    @staticmethod
    def get_processing_activities() -> KVKKDataProcessingActivitiesResponse:
        return KVKKDataProcessingActivitiesResponse(
            company=None,
            activities=[
                KVKKDataProcessingActivity(**a)
                for a in STATIC_DATA_PROCESSING_ACTIVITIES
            ],
            last_updated="2026-05-26",
        )

    # ── Converters ──────────────────────────────────────────────────────────

    @staticmethod
    def _to_deletion_read(row: dict[str, Any]) -> KVKKDeletionRequestRead:
        anonymized_fields_raw = row.get("anonymized_fields") or ""
        try:
            anonymized_fields = (
                json.loads(anonymized_fields_raw)
                if isinstance(anonymized_fields_raw, str) and anonymized_fields_raw
                else []
            )
        except (ValueError, TypeError):
            anonymized_fields = []

        return KVKKDeletionRequestRead(
            id=int(row["id"]),
            user_id=int(row["user_id"]),
            requested_at=int(row["requested_at"]),
            reason=str(row.get("reason") or ""),
            status=str(row["status"]),
            decision_at=row.get("decision_at"),
            decision_by=row.get("decision_by"),
            decision_note=str(row.get("decision_note") or ""),
            completed_at=row.get("completed_at"),
            anonymized_fields=anonymized_fields,
            created_at=int(row["created_at"]),
            updated_at=int(row["updated_at"]),
        )

    @staticmethod
    def _to_incident_read(row: dict[str, Any]) -> KVKKSecurityIncidentRead:
        return KVKKSecurityIncidentRead(
            id=int(row["id"]),
            incident_type=str(row["incident_type"]),
            severity=str(row["severity"]),
            affected_user_id=row.get("affected_user_id"),
            affected_record_count=int(row.get("affected_record_count") or 0),
            description=str(row.get("description") or ""),
            reported_by=row.get("reported_by"),
            reported_at=int(row["reported_at"]),
            kvkk_notification_required=bool(row.get("kvkk_notification_required") or 0),
            kvkk_notification_sent_at=row.get("kvkk_notification_sent_at"),
            kvkk_notification_reference=str(row.get("kvkk_notification_reference") or ""),
            data_subject_notified_at=row.get("data_subject_notified_at"),
            resolution_status=str(row.get("resolution_status") or "open"),
            resolution_summary=str(row.get("resolution_summary") or ""),
            resolved_at=row.get("resolved_at"),
            created_at=int(row["created_at"]),
            updated_at=int(row["updated_at"]),
        )
