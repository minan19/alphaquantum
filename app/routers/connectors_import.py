"""I1: Connector Import router.

Endpoint'ler:
  * GET    /api/v1/connectors/types                 — desteklenen connector'lar
  * POST   /api/v1/connectors/{type}/preview        — file upload + parse + preview
  * POST   /api/v1/connectors/imports/{id}/commit   — preview onayla (file re-upload)
  * GET    /api/v1/connectors/imports               — kullanıcının job listesi
  * GET    /api/v1/connectors/imports/{id}          — detail + errors
  * POST   /api/v1/connectors/imports/{id}/cancel
"""
from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from app.connectors import CONNECTOR_REGISTRY
from app.engines.connector_import_engine import ConnectorImportEngine
from app.models import (
    ConnectorImportError,
    ConnectorImportJobResponse,
    ConnectorImportListResponse,
    ConnectorTypeInfo,
    UserProfile,
)
from app.routers._deps import _value_error_to_http
from app.security import require_permissions


router = APIRouter()


# Connector type → human label (Logo Tiger gelecek versiyonlarda dahili)
_CONNECTOR_LABELS = {
    "logo_tiger": "Logo Tiger",
}


def _engine(request: Request) -> ConnectorImportEngine:
    return cast(
        ConnectorImportEngine,
        request.app.state.connector_import_engine,
    )


# ── List connector types ───────────────────────────────────────────────


@router.get(
    "/api/v1/connectors/types",
    response_model=list[ConnectorTypeInfo],
    tags=["connectors"],
)
def list_connector_types(
    _user: UserProfile = Depends(require_permissions("read_finance")),
) -> list[ConnectorTypeInfo]:
    """Wizard için: hangi ERP'ler desteklenir, hangi modlar var."""
    out: list[ConnectorTypeInfo] = []
    for conn_type, cls in CONNECTOR_REGISTRY.items():
        instance = cls()
        out.append(ConnectorTypeInfo(
            connector_type=conn_type,
            label=_CONNECTOR_LABELS.get(conn_type, conn_type),
            supported_modes=[m.value for m in instance.supported_modes],
        ))
    return out


# ── Preview (upload + parse) ───────────────────────────────────────────


@router.post(
    "/api/v1/connectors/{connector_type}/preview",
    response_model=ConnectorImportJobResponse,
    tags=["connectors"],
)
async def preview_import(
    connector_type: str,
    request: Request,
    file: UploadFile = File(...),
    mode: str = Form(...),
    user: UserProfile = Depends(require_permissions("manage_finance")),
) -> ConnectorImportJobResponse:
    """Dosyayı yükle + parse et + ilk 10 kayıt preview göster.

    Job 'preview' status'le yaratılır. Commit ayrı çağrıda yapılır.
    """
    if connector_type not in CONNECTOR_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Bilinmeyen connector: {connector_type}",
        )
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Boş dosya")
    if len(data) > 50 * 1024 * 1024:  # 50 MB üst sınır
        raise HTTPException(status_code=413, detail="Dosya 50 MB'ı geçemez")

    try:
        job = _engine(request).parse_and_preview(
            user_id=user.username,
            connector_type=connector_type,
            mode=mode,
            data=data,
            filename=file.filename,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc

    errors = [
        ConnectorImportError(**e)
        for e in job.get("errors", [])
    ]
    return ConnectorImportJobResponse(**{**job, "errors": errors})


# ── Commit ─────────────────────────────────────────────────────────────


@router.post(
    "/api/v1/connectors/imports/{job_id}/commit",
    response_model=ConnectorImportJobResponse,
    tags=["connectors"],
)
async def commit_import(
    job_id: int,
    request: Request,
    file: UploadFile = File(...),
    user: UserProfile = Depends(require_permissions("manage_finance")),
) -> ConnectorImportJobResponse:
    """Preview status'teki job'u onayla → DB'ye persist et.

    File: orijinal upload (MVP: client re-upload). Sonraki sprint'lerde
    temp file cache ile bypass.
    """
    data = await file.read()
    try:
        job = _engine(request).commit_job(
            user_id=user.username, job_id=job_id, raw_data=data,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc
    return ConnectorImportJobResponse(
        **{**job, "errors": []},
    )


# ── List + detail + cancel ─────────────────────────────────────────────


@router.get(
    "/api/v1/connectors/imports",
    response_model=ConnectorImportListResponse,
    tags=["connectors"],
)
def list_imports(
    request: Request,
    limit: int = 20,
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> ConnectorImportListResponse:
    jobs = _engine(request).list_jobs(user_id=user.username, limit=limit)
    parsed = [
        ConnectorImportJobResponse(**{**j, "errors": []})
        for j in jobs
    ]
    return ConnectorImportListResponse(jobs=parsed, total=len(parsed))


@router.get(
    "/api/v1/connectors/imports/{job_id}",
    response_model=ConnectorImportJobResponse,
    tags=["connectors"],
)
def get_import(
    job_id: int,
    request: Request,
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> ConnectorImportJobResponse:
    job = _engine(request).get_job(user_id=user.username, job_id=job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job bulunamadı")
    errors = [ConnectorImportError(**e) for e in job.get("errors", [])]
    return ConnectorImportJobResponse(**{**job, "errors": errors})


@router.post(
    "/api/v1/connectors/imports/{job_id}/cancel",
    response_model=dict[str, bool],
    tags=["connectors"],
)
def cancel_import(
    job_id: int,
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_finance")),
) -> dict[str, bool]:
    cancelled = _engine(request).cancel_job(
        user_id=user.username, job_id=job_id,
    )
    return {"cancelled": cancelled}
