"""Design Token Programı — Faz 6 · Custom Fonts router.

Endpoints:
  GET    /api/v1/fonts                  → liste (public — font_loader'a beslenir)
  POST   /api/v1/fonts/google           → Google Fonts CSS URL ile ekle
  POST   /api/v1/fonts/upload           → multipart .woff2/.woff/.ttf/.otf yükle
  DELETE /api/v1/fonts/{id}             → sil
  POST   /api/v1/fonts/{id}/default     → varsayılan ata
  GET    /api/v1/fonts/{id}/file        → upload baytları (public, cache'li)

Auth:
  Yazma uçları (POST/DELETE) → require_permissions("manage_design_tokens").
  Liste + dosya GET → public (font yüklemek için anon erişim gerek; bayt
  içeriği zaten tarayıcıdan herkes tarafından çekilebilir — gizli değil).
"""
from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response

from app.color_token_repository import VALID_SCOPES
from app.custom_font_repository import (
    ALLOWED_UPLOAD_FORMATS,
    CustomFontRepository,
    FontValidationError,
)
from app.models import (
    ColorTokenScope,
    CustomFontCreateResponse,
    CustomFontDeleteResponse,
    CustomFontGoogleCreateRequest,
    CustomFontListResponse,
    CustomFontSetDefaultResponse,
    CustomFontSource,
    CustomFontSummary,
    UserProfile,
)
from app.security import require_permissions

router = APIRouter()


def _repo(request: Request) -> CustomFontRepository:
    return cast(CustomFontRepository, request.app.state.custom_font_repo)


# MIME type per format — /file endpoint için.
_FORMAT_MIME: dict[str, str] = {
    "woff2": "font/woff2",
    "woff":  "font/woff",
    "ttf":   "font/ttf",
    "otf":   "font/otf",
}


@router.get(
    "/api/v1/fonts",
    response_model=CustomFontListResponse,
    tags=["fonts"],
)
def list_fonts(
    request: Request,
    scope: ColorTokenScope | None = Query(default=None),
) -> CustomFontListResponse:
    """Tüm fontları (veya scope filtreli) döndür — public.

    `font_loader` (frontend SSR) bu ucu çağırıp <link>/@font-face emiter.
    """
    if scope is not None and scope not in VALID_SCOPES:
        raise HTTPException(status_code=400, detail=f"invalid scope: {scope}")
    rows = _repo(request).list_fonts(scope=scope)
    return CustomFontListResponse(
        scope_filter=scope,
        fonts=[
            CustomFontSummary(
                id=int(r["id"]),
                scope=cast(ColorTokenScope, r["scope"]),
                family=str(r["family"]),
                source=cast(CustomFontSource, r["source"]),
                css_url=(str(r["css_url"]) if r.get("css_url") else None),
                format=(str(r["format"]) if r.get("format") else None),
                weight=(str(r["weight"]) if r.get("weight") else None),
                style=(str(r["style"]) if r.get("style") else None),
                is_default=bool(r["is_default"]),
                created_at=int(r["created_at"]),
            )
            for r in rows
        ],
    )


@router.post(
    "/api/v1/fonts/google",
    response_model=CustomFontCreateResponse,
    tags=["fonts"],
    responses={
        401: {"description": "Auth gerekli"},
        403: {"description": "Insufficient permissions (manage_design_tokens)"},
        422: {"description": "URL whitelist veya scope ihlali"},
    },
)
def create_google_font(
    payload: CustomFontGoogleCreateRequest,
    request: Request,
    _user: UserProfile = Depends(require_permissions("manage_design_tokens")),
) -> CustomFontCreateResponse:
    if payload.scope not in VALID_SCOPES:
        raise HTTPException(status_code=422, detail=f"invalid scope: {payload.scope}")
    try:
        font_id = _repo(request).create_google_font(
            scope=payload.scope,
            family=payload.family,
            css_url=payload.css_url,
            weight=payload.weight,
            style=payload.style,
            make_default=payload.make_default,
        )
    except FontValidationError as err:
        raise HTTPException(status_code=422, detail=str(err)) from err
    return CustomFontCreateResponse(
        id=font_id,
        scope=payload.scope,
        family=payload.family.strip(),
        source="google",
        is_default=payload.make_default,
    )


@router.post(
    "/api/v1/fonts/upload",
    response_model=CustomFontCreateResponse,
    tags=["fonts"],
    responses={
        401: {"description": "Auth gerekli"},
        403: {"description": "Insufficient permissions"},
        422: {"description": "Magic-byte, format veya boyut ihlali"},
    },
)
async def upload_font(
    request: Request,
    scope: str = Form(...),
    family: str = Form(...),
    fmt: str = Form(..., alias="format"),
    file: UploadFile = File(...),
    weight: str | None = Form(default=None),
    style: str | None = Form(default=None),
    make_default: bool = Form(default=False),
    _user: UserProfile = Depends(require_permissions("manage_design_tokens")),
) -> CustomFontCreateResponse:
    if scope not in VALID_SCOPES:
        raise HTTPException(status_code=422, detail=f"invalid scope: {scope}")
    fmt_norm = fmt.lower().strip()
    if fmt_norm not in ALLOWED_UPLOAD_FORMATS:
        raise HTTPException(
            status_code=422,
            detail=f"izinsiz format: {fmt_norm!r}. İzinli: {sorted(ALLOWED_UPLOAD_FORMATS)}",
        )
    data = await file.read()
    try:
        font_id = _repo(request).create_upload_font(
            scope=scope,
            family=family,
            data=data,
            fmt=fmt_norm,
            weight=weight,
            style=style,
            make_default=make_default,
        )
    except FontValidationError as err:
        raise HTTPException(status_code=422, detail=str(err)) from err
    return CustomFontCreateResponse(
        id=font_id,
        scope=scope,
        family=family.strip(),
        source="upload",
        is_default=make_default,
    )


@router.post(
    "/api/v1/fonts/{font_id}/default",
    response_model=CustomFontSetDefaultResponse,
    tags=["fonts"],
)
def set_default_font(
    font_id: int,
    request: Request,
    _user: UserProfile = Depends(require_permissions("manage_design_tokens")),
) -> CustomFontSetDefaultResponse:
    repo = _repo(request)
    if not repo.set_default(font_id):
        raise HTTPException(status_code=404, detail=f"font bulunamadı: {font_id}")
    row = repo.get_font(font_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"font bulunamadı: {font_id}")
    return CustomFontSetDefaultResponse(
        id=font_id,
        scope=cast(ColorTokenScope, row["scope"]),
        is_default=True,
    )


@router.delete(
    "/api/v1/fonts/{font_id}",
    response_model=CustomFontDeleteResponse,
    tags=["fonts"],
)
def delete_font(
    font_id: int,
    request: Request,
    _user: UserProfile = Depends(require_permissions("manage_design_tokens")),
) -> CustomFontDeleteResponse:
    ok = _repo(request).delete_font(font_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"font bulunamadı: {font_id}")
    return CustomFontDeleteResponse(id=font_id, deleted=True)


@router.get(
    "/api/v1/fonts/{font_id}/file",
    tags=["fonts"],
    responses={404: {"description": "Font yok veya upload tipinde değil"}},
)
def get_font_file(font_id: int, request: Request) -> Response:
    """Upload'lu fontun ham baytları — public + uzun ömürlü cache.

    /@font-face src: bu ucu işaret eder. Bytes immutable kabul edilir
    (font güncellenirse yeni id alır).
    """
    result = _repo(request).get_font_bytes(font_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"font bulunamadı: {font_id}")
    data, fmt = result
    mime = _FORMAT_MIME.get(fmt, "application/octet-stream")
    return Response(
        content=data,
        media_type=mime,
        headers={
            # 1 yıl + immutable — id değişirse cache'i delik etmez.
            "Cache-Control": "public, max-age=31536000, immutable",
            "Content-Length": str(len(data)),
        },
    )
