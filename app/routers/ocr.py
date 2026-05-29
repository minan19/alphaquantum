"""A4: OCR router — fiş/fatura fotoğrafı yükle + extract + confirm."""
from __future__ import annotations

from dataclasses import asdict
from typing import cast

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile

from app.engines.ocr_engine import OcrEngine
from app.models import (
    OcrConfirmRequest,
    OcrJobListResponse,
    OcrJobResponse,
    UserProfile,
)
from app.routers._deps import _value_error_to_http
from app.security import require_permissions


router = APIRouter()


def _engine(request: Request) -> OcrEngine:
    return cast(OcrEngine, request.app.state.ocr_engine)


@router.post(
    "/api/v1/ocr/invoice",
    response_model=OcrJobResponse,
    tags=["ocr"],
)
async def process_invoice_image(
    request: Request,
    file: UploadFile = File(...),
    user: UserProfile = Depends(require_permissions("manage_finance")),
) -> OcrJobResponse:
    """Fiş/fatura fotoğrafı yükle → Claude Vision extract → status 'extracted'."""
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Boş dosya")
    try:
        view = _engine(request).process(
            user_id=user.username,
            image_bytes=data,
            mime_type=file.content_type or "image/jpeg",
            filename=file.filename,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc
    return OcrJobResponse(**asdict(view))


@router.post(
    "/api/v1/ocr/invoice/{job_id}/confirm",
    response_model=OcrJobResponse,
    tags=["ocr"],
)
def confirm_invoice(
    job_id: int,
    payload: OcrConfirmRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_finance")),
) -> OcrJobResponse:
    """User onaylar → ledger entry oluşur."""
    overrides = {
        k: v for k, v in payload.model_dump(exclude={"company_name"}).items()
        if v is not None
    }
    try:
        view = _engine(request).confirm(
            user_id=user.username,
            job_id=job_id,
            company_name=payload.company_name,
            overrides=overrides if overrides else None,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc
    return OcrJobResponse(**asdict(view))


@router.get(
    "/api/v1/ocr/invoice/{job_id}",
    response_model=OcrJobResponse,
    tags=["ocr"],
)
def get_ocr_job(
    job_id: int,
    request: Request,
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> OcrJobResponse:
    view = _engine(request).get_job(user_id=user.username, job_id=job_id)
    if view is None:
        raise HTTPException(status_code=404, detail="Job bulunamadı")
    return OcrJobResponse(**asdict(view))


@router.get(
    "/api/v1/ocr/jobs",
    response_model=OcrJobListResponse,
    tags=["ocr"],
)
def list_ocr_jobs(
    request: Request,
    limit: int = Query(default=20, ge=1, le=200),
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> OcrJobListResponse:
    views = _engine(request).list_jobs(user_id=user.username, limit=limit)
    return OcrJobListResponse(
        jobs=[OcrJobResponse(**asdict(v)) for v in views],
        total=len(views),
    )
