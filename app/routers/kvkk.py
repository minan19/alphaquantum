"""A4 KVKK Router — veri sahibi hakları + admin paneli.

Endpoint planı (madde 11 hakları + madde 12-13 yükümlülükleri):

User-facing (authenticated, kendi verisi için):
- POST   /api/v1/me/consent                        → KVKK onayı kaydet
- GET    /api/v1/me/consent                        → onay durumu
- GET    /api/v1/me/data                           → veri export (imzalı JSON)
- POST   /api/v1/me/deletion-request               → silme talebi aç
- GET    /api/v1/me/deletion-request               → kendi silme talepleri
- GET    /api/v1/data-processing-activities        → KVKK aydınlatma metni

Admin (manage_users):
- GET    /api/v1/admin/kvkk/deletion-requests      → tüm bekleyen talepler
- POST   /api/v1/admin/kvkk/deletion-requests/{id} → onayla/reddet
- GET    /api/v1/admin/kvkk/incidents              → güvenlik ihlali listesi
- POST   /api/v1/admin/kvkk/incidents              → yeni ihlal raporu
"""
from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.engines import KVKKEngine
from app.models import (
    KVKKConsentRequest,
    KVKKConsentStatusResponse,
    KVKKDataExportResponse,
    KVKKDataProcessingActivitiesResponse,
    KVKKDeletionDecisionRequest,
    KVKKDeletionRequestCreate,
    KVKKDeletionRequestListResponse,
    KVKKDeletionRequestRead,
    KVKKSecurityIncidentCreate,
    KVKKSecurityIncidentListResponse,
    KVKKSecurityIncidentRead,
    UserProfile,
)
from app.routers._deps import _emit_audit_event, _settings
from app.security import get_current_user, require_permissions


router = APIRouter()


def _kvkk_engine(request: Request) -> KVKKEngine:
    return cast(KVKKEngine, request.app.state.kvkk_engine)


# ── Self-service endpoints (madde 11 user rights) ───────────────────────────

@router.post(
    "/api/v1/me/consent",
    response_model=KVKKConsentStatusResponse,
    tags=["kvkk"],
)
def record_consent(
    payload: KVKKConsentRequest,
    request: Request,
    user: UserProfile = Depends(get_current_user),
) -> KVKKConsentStatusResponse:
    """Kullanıcının kendi KVKK onay kaydını oluşturur/günceller."""
    status = _kvkk_engine(request).record_consent(
        user.id, version=payload.consent_version
    )
    _emit_audit_event(
        request, user, "kvkk_consent_recorded",
        event_detail={"version": payload.consent_version},
    )
    return status


@router.get(
    "/api/v1/me/consent",
    response_model=KVKKConsentStatusResponse,
    tags=["kvkk"],
)
def get_consent_status(
    request: Request,
    user: UserProfile = Depends(get_current_user),
) -> KVKKConsentStatusResponse:
    return _kvkk_engine(request).get_consent_status(user.id)


@router.get(
    "/api/v1/me/data",
    response_model=KVKKDataExportResponse,
    tags=["kvkk"],
)
def export_my_data(
    request: Request,
    user: UserProfile = Depends(get_current_user),
) -> KVKKDataExportResponse:
    """KVKK madde 11(b) — bilgi talep etme hakkı.

    Kullanıcının kendi verisi HMAC-SHA256 imzalı JSON olarak döner.
    Her çağrı audit_log'a yazılır.
    """
    settings = _settings(request)
    response = _kvkk_engine(request).export_user_data(
        user.id,
        username=user.username,
        role=user.role,
        company_scopes=list(user.company_scopes),
        created_at=0,
        updated_at=0,
        related_records={},
        signing_secret=settings.jwt_secret,
    )
    _emit_audit_event(
        request, user, "kvkk_data_exported",
        event_detail={"signature": response.export_signature[:24] + "..."},
    )
    return response


@router.post(
    "/api/v1/me/deletion-request",
    response_model=KVKKDeletionRequestRead,
    status_code=status.HTTP_201_CREATED,
    tags=["kvkk"],
)
def create_my_deletion_request(
    payload: KVKKDeletionRequestCreate,
    request: Request,
    user: UserProfile = Depends(get_current_user),
) -> KVKKDeletionRequestRead:
    """KVKK madde 11(e) — silme/yok etme talebi başlat (pending status).
    Admin onayı gerekir."""
    result = _kvkk_engine(request).create_deletion_request(
        user_id=user.id, reason=payload.reason,
    )
    _emit_audit_event(
        request, user, "kvkk_deletion_requested",
        event_detail={"request_id": result.id, "reason": payload.reason[:80]},
    )
    return result


@router.get(
    "/api/v1/me/deletion-request",
    response_model=KVKKDeletionRequestListResponse,
    tags=["kvkk"],
)
def my_deletion_requests(
    request: Request,
    user: UserProfile = Depends(get_current_user),
) -> KVKKDeletionRequestListResponse:
    return _kvkk_engine(request).list_deletion_requests(user_id=user.id)


@router.get(
    "/api/v1/data-processing-activities",
    response_model=KVKKDataProcessingActivitiesResponse,
    tags=["kvkk"],
)
def list_processing_activities(
    request: Request,
    user: UserProfile = Depends(get_current_user),
) -> KVKKDataProcessingActivitiesResponse:
    """KVKK madde 13 — aydınlatma metni: hangi veri, hangi amaçla işlenir."""
    return _kvkk_engine(request).get_processing_activities()


# ── Admin endpoints (madde 12 incident management) ──────────────────────────

@router.get(
    "/api/v1/admin/kvkk/deletion-requests",
    response_model=KVKKDeletionRequestListResponse,
    tags=["admin", "kvkk"],
)
def admin_list_deletion_requests(
    request: Request,
    deletion_status: str | None = Query(
        default=None, alias="status",
        pattern="^(pending|approved|rejected|completed)$",
    ),
    limit: int = Query(default=200, ge=1, le=1000),
    user: UserProfile = Depends(require_permissions("manage_users")),
) -> KVKKDeletionRequestListResponse:
    return _kvkk_engine(request).list_deletion_requests(
        status=deletion_status, limit=limit
    )


@router.post(
    "/api/v1/admin/kvkk/deletion-requests/{request_id}",
    response_model=KVKKDeletionRequestRead,
    tags=["admin", "kvkk"],
)
def admin_decide_deletion_request(
    request_id: int,
    payload: KVKKDeletionDecisionRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_users")),
) -> KVKKDeletionRequestRead:
    """KVKK silme talebini onayla veya reddet.

    `approved` ise: KVKKRepository.anonymize_user çalıştırılır, kullanıcının
    PII alanları maskelenir (yasal saklama yükümlülüğü için kayıt korunur,
    KVKK madde 7). `rejected` ise: status güncellenir, veriler dokunulmaz.
    """
    existing = _kvkk_engine(request).get_deletion_request(request_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Deletion request not found")
    if existing.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Request is not pending (current: {existing.status})",
        )
    try:
        result = _kvkk_engine(request).decide_deletion(
            request_id,
            decision=payload.decision,
            decision_by=user.id,
            decision_note=payload.decision_note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail="Deletion request not found")
    _emit_audit_event(
        request, user, "kvkk_deletion_decided",
        event_detail={
            "request_id": request_id,
            "decision": payload.decision,
            "note": payload.decision_note[:80],
        },
    )
    return result


@router.get(
    "/api/v1/admin/kvkk/incidents",
    response_model=KVKKSecurityIncidentListResponse,
    tags=["admin", "kvkk"],
)
def admin_list_incidents(
    request: Request,
    severity: str | None = Query(
        default=None, pattern="^(low|medium|high|critical)$"
    ),
    resolution: str | None = Query(
        default=None, alias="status",
        pattern="^(open|investigating|resolved|closed)$",
    ),
    limit: int = Query(default=200, ge=1, le=1000),
    user: UserProfile = Depends(require_permissions("manage_users")),
) -> KVKKSecurityIncidentListResponse:
    return _kvkk_engine(request).list_incidents(
        severity=severity, status=resolution, limit=limit
    )


@router.post(
    "/api/v1/admin/kvkk/incidents",
    response_model=KVKKSecurityIncidentRead,
    status_code=status.HTTP_201_CREATED,
    tags=["admin", "kvkk"],
)
def admin_report_incident(
    payload: KVKKSecurityIncidentCreate,
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_users")),
) -> KVKKSecurityIncidentRead:
    """KVKK madde 12 — veri ihlali kaydı.

    `severity` high/critical ise `kvkk_notification_required=1` otomatik set.
    KVK Kurumu'na 72 saat içinde resmi bildirim sorumluluğu hatırlatılır.
    """
    result = _kvkk_engine(request).report_incident(
        reported_by=user.id,
        incident_type=payload.incident_type,
        severity=payload.severity,
        description=payload.description,
        affected_user_id=payload.affected_user_id,
        affected_record_count=payload.affected_record_count,
    )
    _emit_audit_event(
        request, user, "kvkk_incident_reported",
        event_detail={
            "incident_id": result.id,
            "severity": result.severity,
            "kvkk_notification_required": result.kvkk_notification_required,
        },
    )
    return result
