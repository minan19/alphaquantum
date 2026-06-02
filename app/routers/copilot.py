"""AC1: AI Finance Copilot router."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, cast

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.engines.copilot_engine import CopilotEngine
from app.models import UserProfile
from app.security import require_permissions


router = APIRouter()


class CopilotQueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)


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


def _engine(request: Request) -> CopilotEngine:
    return cast(CopilotEngine, request.app.state.copilot_engine)


@router.post(
    "/api/v1/copilot/ask",
    response_model=CopilotResponsePayload,
    tags=["copilot"],
)
def ask_copilot(
    payload: CopilotQueryRequest,
    request: Request,
    _user: UserProfile = Depends(require_permissions("read_finance")),
) -> CopilotResponsePayload:
    """Doğal dil soru → intent classification → whitelist SQL → cevap.

    GÜVENLİK: Direkt SQL execution YOK. Sadece predefined query
    template'leri kullanılır. LLM → SQL pipeline'ı injection'a
    kapalıdır.
    """
    response = _engine(request).ask(query=payload.query)
    return CopilotResponsePayload(
        intent=CopilotIntentPayload(**asdict(response.intent)),
        results=response.results,
        summary_text=response.summary_text,
        explanation=response.explanation,
        sql_template_used=response.sql_template_used,
    )
