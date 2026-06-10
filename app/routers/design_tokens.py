"""Design Token Programı — Faz 1 · Read endpoint.

GET /api/v1/design-tokens?scope=<optional> — public (auth gerektirmez).
Faz 4'te POST/PUT eklenir (panel mutations); şu an yalnız okuma.
"""
from __future__ import annotations

from typing import cast

from fastapi import APIRouter, HTTPException, Query, Request

from app.color_token_repository import VALID_SCOPES, ColorTokenRepository
from app.models import ColorTokenListResponse, ColorTokenResponse, ColorTokenScope

router = APIRouter()


def _repo(request: Request) -> ColorTokenRepository:
    return cast(ColorTokenRepository, request.app.state.color_token_repo)


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
