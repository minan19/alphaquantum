"""A3: Cashflow forecast router.

Endpoints:
  * GET  /api/v1/cashflow/forecast?horizon=30&scope=*
  * POST /api/v1/cashflow/forecast/feedback
  * GET  /api/v1/cashflow/forecast/accuracy
"""
from __future__ import annotations

import statistics
from typing import cast

from fastapi import APIRouter, Depends, Query, Request

from app.engines.cashflow_forecast_engine import (
    DEFAULT_HORIZONS,
    CashflowForecastEngine,
)
from app.models import (
    CashflowAccuracyHistoryEntry,
    CashflowAccuracyHistoryResponse,
    CashflowForecastFeedbackRequest,
    CashflowForecastResponse,
    UserProfile,
)
from app.routers._deps import _value_error_to_http
from app.security import require_permissions


router = APIRouter()


def _engine(request: Request) -> CashflowForecastEngine:
    return cast(
        CashflowForecastEngine,
        request.app.state.cashflow_forecast_engine,
    )


@router.get(
    "/api/v1/cashflow/forecast",
    response_model=CashflowForecastResponse,
    tags=["cashflow"],
)
def get_cashflow_forecast(
    request: Request,
    horizon: int = Query(default=30, ge=1, le=180),
    scope: str = Query(default="*", max_length=100),
    force_refresh: bool = Query(default=False),
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> CashflowForecastResponse:
    """Adaptive Holt-Winters cashflow forecast.

    horizon: 30 / 60 / 90 önerilir ama 1–180 arası geçerli.
    scope: '*' tüm şirketler, 'AcmeCo' tek şirket, 'AcmeCo::sales' kategori.
    """
    try:
        payload = _engine(request).forecast(
            user_id=user.username,
            horizon_days=horizon,
            scope_key=scope,
            force_refresh=force_refresh,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc
    return CashflowForecastResponse(**payload)


@router.post(
    "/api/v1/cashflow/forecast/feedback",
    response_model=dict[str, bool],
    tags=["cashflow"],
)
def post_forecast_feedback(
    payload: CashflowForecastFeedbackRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> dict[str, bool]:
    """Kullanıcı: 'forecast doğru çıktı / yanılttı'. Misleading → model retrain."""
    ok = _engine(request).record_feedback(
        user_id=user.username,
        snapshot_date=payload.snapshot_date,
        feedback=payload.feedback,
        scope_key=payload.scope_key,
    )
    return {"recorded": ok}


@router.get(
    "/api/v1/cashflow/forecast/accuracy",
    response_model=CashflowAccuracyHistoryResponse,
    tags=["cashflow"],
)
def get_forecast_accuracy(
    request: Request,
    scope: str = Query(default="*", max_length=100),
    limit: int = Query(default=30, ge=1, le=180),
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> CashflowAccuracyHistoryResponse:
    """MAPE trend grafiği + ölçülmüş feedback hassasiyeti."""
    entries = _engine(request).accuracy_history(
        user_id=user.username, scope_key=scope, limit=limit,
    )
    parsed = [CashflowAccuracyHistoryEntry(**e) for e in entries]
    mape_values = [e.mape for e in parsed if e.mape != float("inf")]
    median_mape = statistics.median(mape_values) if mape_values else None

    accurate = sum(1 for e in parsed if e.user_feedback == "accurate")
    misleading = sum(1 for e in parsed if e.user_feedback == "misleading")
    total_feedback = accurate + misleading
    ratio = (accurate / total_feedback) if total_feedback > 0 else None

    return CashflowAccuracyHistoryResponse(
        entries=parsed,
        median_mape_last_30d=median_mape,
        feedback_accuracy_ratio=ratio,
    )


__all__ = ["router", "DEFAULT_HORIZONS"]
