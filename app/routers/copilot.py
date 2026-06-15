"""AC1 + M3: AI Finance Copilot router.

M3 katmanları:
- Onay kapısı: `confirm=False` → SQL + params + intent görünür, çalıştırılmaz.
  `confirm=True` → sunucu sorguyu yeniden TÜRETİR (client SQL'i geri yollamaz)
  ve çalıştırır. Re-derivation deterministiktir (aynı query → aynı SQL).
- Tenant izolasyonu: `user.company_scopes` sunucu tarafında engine'e geçer;
  client'tan şirket parametresi alınmaz.
- Rate limit: kullanıcı-başına `CopilotRateLimiter` (varsayılan 10/dk).
- Hata redaksiyonu: iç istisnalar log'a, yanıta sanitize edilmiş mesaj.
- Read-only assert: engine SELECT-only zorlar; ihlalde 400.
"""
from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.copilot_limiter import CopilotRateLimitExceeded, CopilotRateLimiter
from app.engines.copilot_engine import CopilotEngine
from app.engines.sql_guard import ReadOnlyViolation
from app.models import UserProfile
from app.security import require_permissions


router = APIRouter()
logger = logging.getLogger("alpha_quantum.copilot")


class CopilotQueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    # M3 onay kapısı: True → çalıştır, False → sadece SQL preview.
    confirm: bool = False


class CopilotIntentPayload(BaseModel):
    intent: str
    entity_name: str | None = None
    time_window_days: int | None = None
    direction: str | None = None
    category: str | None = None
    confidence_pct: float
    raw_query: str


class CopilotResponsePayload(BaseModel):
    intent: CopilotIntentPayload
    results: list[dict[str, Any]]
    summary_text: str
    explanation: str
    sql_template_used: str | None = None
    # M3: kullanıcının onay öncesi gördüğü tam SQL ve param tuple'ı.
    sql: str | None = None
    params: list[Any] = Field(default_factory=list)
    executed: bool = False


def _engine(request: Request) -> CopilotEngine:
    return cast(CopilotEngine, request.app.state.copilot_engine)


def _limiter(request: Request) -> CopilotRateLimiter | None:
    return cast(
        CopilotRateLimiter | None,
        getattr(request.app.state, "copilot_limiter", None),
    )


@router.post(
    "/api/v1/copilot/ask",
    response_model=CopilotResponsePayload,
    tags=["copilot"],
)
def ask_copilot(
    payload: CopilotQueryRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> CopilotResponsePayload:
    """Doğal dil sorgu → preview (SQL + params) → onay → çalıştırma.

    GÜVENLİK katmanları:
    - Whitelist intent → template SQL (LLM-direct SQL üretimi YOK)
    - Engine-level `assert_select_only` (defense-in-depth)
    - Tenant scope sunucudan enjekte (client şirket parametresi göndermez)
    - Onay kapısı: `confirm=False` çalıştırmaz
    - Rate limit + hata redaksiyonu (iç bilgi sızıntısı yok)
    """
    limiter = _limiter(request)
    if limiter is not None:
        try:
            limiter.hit(f"user:{user.id}")
        except CopilotRateLimitExceeded as err:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=str(err),
            ) from None

    try:
        response = _engine(request).ask(
            query=payload.query,
            company_scopes=list(user.company_scopes),
            execute=payload.confirm,
        )
    except ReadOnlyViolation as err:
        # Whitelist bozulduysa (defense-in-depth yakaladı) → istemci dostu hata.
        logger.error(
            "copilot_read_only_violation user=%s reason=%s",
            user.id, err,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sorgu çalıştırılamadı: salt-okunur kısıtlaması.",
        ) from None
    except Exception:
        # Tüm diğer istisnalar — şema/iç detay sızdırmaya YOK.
        logger.exception("copilot_internal_error user=%s", user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Sorgu işlenemedi. Lütfen tekrar deneyin.",
        ) from None

    return CopilotResponsePayload(
        intent=CopilotIntentPayload(**asdict(response.intent)),
        results=response.results,
        summary_text=response.summary_text,
        explanation=response.explanation,
        sql_template_used=response.sql_template_used,
        sql=response.sql,
        params=list(response.params),
        executed=response.executed,
    )
