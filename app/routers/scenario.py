"""SP1: Scenario Planning router — A3 forecast + what-if adjustments."""
from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, Request

from app.engines.cashflow_forecast_engine import CashflowForecastEngine
from app.engines.scenario_planning_engine import (
    ScenarioAdjustment,
    ScenarioPlanningEngine,
)
from app.models import (
    ScenarioRequest,
    ScenarioResponse,
    UserProfile,
)
from app.routers._deps import _value_error_to_http
from app.security import require_permissions


router = APIRouter()


def _forecast_engine(request: Request) -> CashflowForecastEngine:
    return cast(
        CashflowForecastEngine,
        request.app.state.cashflow_forecast_engine,
    )


def _scenario_engine(request: Request) -> ScenarioPlanningEngine:
    return cast(
        ScenarioPlanningEngine,
        request.app.state.scenario_planning_engine,
    )


@router.post(
    "/api/v1/cashflow/scenario",
    response_model=ScenarioResponse,
    tags=["cashflow"],
)
def run_scenario(
    payload: ScenarioRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> ScenarioResponse:
    """A3 baseline forecast üret + senaryo adjustment'larını uygula."""
    # 1. Baseline forecast'i al (cache'i kullanır)
    forecast_payload = _forecast_engine(request).forecast(
        user_id=user.username,
        horizon_days=payload.horizon_days,
        scope_key=payload.scope,
    )
    if not forecast_payload.get("is_reliable"):
        return ScenarioResponse(
            horizon_days=payload.horizon_days,
            baseline_points=[],
            adjusted_points=[],
            p10_points=[],
            p90_points=[],
            cumulative_baseline=0,
            cumulative_adjusted=0,
            delta=0,
            delta_pct=0,
        )

    baseline = [
        float(p["point_estimate"])
        for p in forecast_payload.get("points", [])
    ]

    adjustments = [
        ScenarioAdjustment(
            type=a.type,
            pct_change=a.pct_change,
            day_offset=a.day_offset,
            amount=a.amount,
            category_filter=a.category_filter,
        )
        for a in payload.adjustments
    ]

    try:
        result = _scenario_engine(request).apply_scenario(
            baseline_forecast=baseline,
            adjustments=adjustments,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc

    return ScenarioResponse(
        horizon_days=result.horizon_days,
        baseline_points=result.baseline_points,
        adjusted_points=result.adjusted_points,
        p10_points=result.p10_points,
        p90_points=result.p90_points,
        cumulative_baseline=result.cumulative_baseline,
        cumulative_adjusted=result.cumulative_adjusted,
        delta=result.delta,
        delta_pct=result.delta_pct,
    )
