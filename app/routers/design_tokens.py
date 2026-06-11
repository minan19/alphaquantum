"""Design Token Programı — Faz 1+4 · Read + Write endpoints.

GET /api/v1/design-tokens                 — public read (Faz 1)
PATCH /api/v1/design-tokens               — admin write (Faz 4)
POST /api/v1/design-tokens/reset          — admin factory reset (Faz 4)
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.color_token_repository import (
    VALID_SCOPES,
    ColorTokenRepository,
    GovernanceViolation,
    assert_governance,
)
from app.color_token_seed import build_seed_items
from app.models import (
    ColorTokenListResponse,
    ColorTokenPatchRequest,
    ColorTokenPatchResponse,
    ColorTokenResetRequest,
    ColorTokenResetResponse,
    ColorTokenResponse,
    ColorTokenScope,
    UserProfile,
)
from app.security import require_permissions

router = APIRouter()

# Renk token değer formatı: #RRGGBB (büyük/küçük harf serbest).
_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

# Sayısal değer kabul edilen anahtarlar (corpos.cta_text_weight gibi).
_NUMERIC_KEYS: frozenset[str] = frozenset({"cta_text_weight"})


def _repo(request: Request) -> ColorTokenRepository:
    return cast(ColorTokenRepository, request.app.state.color_token_repo)


def _validate_value(key: str, value: str | int) -> str | int:
    """Bir token değerinin formatını doğrula.

    - Renk anahtarları: '#RRGGBB' bekler (string).
    - Numeric anahtarlar (cta_text_weight): int kabul.
    """
    if key in _NUMERIC_KEYS:
        if not isinstance(value, int):
            try:
                return int(value)
            except (TypeError, ValueError) as err:
                raise HTTPException(
                    status_code=422,
                    detail=f"'{key}' için sayısal değer beklendi: {value!r}",
                ) from err
        return value
    # Color key
    if not isinstance(value, str) or not _HEX_RE.match(value):
        raise HTTPException(
            status_code=422,
            detail=f"'{key}' geçersiz renk değeri (#RRGGBB beklendi): {value!r}",
        )
    return value.upper()


@router.get(
    "/api/v1/design-tokens",
    response_model=ColorTokenListResponse,
    tags=["design-tokens"],
)
def list_tokens(
    request: Request,
    scope: ColorTokenScope | None = Query(
        default=None,
        description="Opsiyonel scope filtresi (core/aq/finos/corpos).",
    ),
) -> ColorTokenListResponse:
    """Tasarım token'larını listele.

    `scope` verilmezse hepsini döner (deterministic sıralama).
    Frontend `getTokens` bu ucu çağırır; başarısızlıkta `DEFAULT_TOKENS`'a düşer.
    """
    if scope is not None and scope not in VALID_SCOPES:
        raise HTTPException(status_code=400, detail=f"invalid scope: {scope}")

    repo = _repo(request)
    rows = repo.list_tokens(scope=scope)
    tokens = [
        ColorTokenResponse(
            scope=cast(ColorTokenScope, row["scope"]),
            key=str(row["key"]),
            value=str(row["value"]),
            label=str(row["label"]),
            category=str(row["category"]),
            display_order=int(row["display_order"]),
            updated_at=int(row["updated_at"]),
        )
        for row in rows
    ]
    return ColorTokenListResponse(
        tokens=tokens,
        scope_filter=scope,
        seeded_at=repo.latest_updated_at(),
    )


@router.patch(
    "/api/v1/design-tokens",
    response_model=ColorTokenPatchResponse,
    tags=["design-tokens"],
    responses={
        401: {"description": "Auth gerekli"},
        403: {"description": "Insufficient permissions (manage_design_tokens)"},
        422: {"description": "Governance ihlali veya geçersiz değer"},
    },
)
def patch_tokens(
    payload: ColorTokenPatchRequest,
    request: Request,
    _user: UserProfile = Depends(require_permissions("manage_design_tokens")),
) -> ColorTokenPatchResponse:
    """Faz 4: panel yazma ucu.

    Tek scope'ta delta update. Governance API'de zorlanır:
      - Modül scope'unda core-sahipli key → 422 (assertGovernance fırlar)
      - Bilinmeyen key → 422 (ne core ne module whitelist'inde)
      - Geçersiz hex değer → 422 (_validate_value)
    """
    if payload.scope not in VALID_SCOPES:
        raise HTTPException(status_code=422, detail=f"invalid scope: {payload.scope}")

    # Önce hepsini doğrula (early fail; partial write yok).
    for key, value in payload.changes.items():
        # Governance: scope/key whitelist
        try:
            assert_governance(payload.scope, key)
        except GovernanceViolation as err:
            raise HTTPException(status_code=422, detail=str(err)) from err
        # Value format
        _validate_value(key, value)

    repo = _repo(request)
    updated: list[str] = []
    for key, raw_value in payload.changes.items():
        normalized = _validate_value(key, raw_value)
        ok = repo.update_value(payload.scope, key, str(normalized))
        if ok:
            updated.append(key)

    return ColorTokenPatchResponse(
        scope=payload.scope,
        updated=updated,
        updated_count=len(updated),
    )


@router.post(
    "/api/v1/design-tokens/reset",
    response_model=ColorTokenResetResponse,
    tags=["design-tokens"],
    responses={
        401: {"description": "Auth gerekli"},
        403: {"description": "Insufficient permissions (manage_design_tokens)"},
    },
)
def reset_scope(
    payload: ColorTokenResetRequest,
    request: Request,
    _user: UserProfile = Depends(require_permissions("manage_design_tokens")),
) -> ColorTokenResetResponse:
    """Faz 4: bir scope'u Faz 0 seed'ine döndür (fabrika = foundation kilidi).

    İki adımlı onay UI'da; backend tek atomik op:
      1. Belirtilen scope'taki tüm token'ları sil
      2. wcag-report.json'dan o scope için seed'i upsert et
    """
    if payload.scope not in VALID_SCOPES:
        raise HTTPException(status_code=422, detail=f"invalid scope: {payload.scope}")

    # Foundation kilidini oku, scope filter uygula
    foundation_path = (
        Path(__file__).resolve().parent.parent.parent
        / "docs" / "design-tokens" / "wcag-report.json"
    )
    seed_items = [it for it in build_seed_items(foundation_path) if it["scope"] == payload.scope]

    repo = _repo(request)
    deleted = repo.delete_scope(payload.scope)
    inserted = repo.upsert_many(seed_items)

    return ColorTokenResetResponse(
        scope=payload.scope,
        deleted=deleted,
        inserted=inserted,
    )
