"""A2: Anomalies router — cross-company anomaly detection endpoint'leri.

Endpoint'ler:
  * GET    /api/v1/anomalies            — listele (filter: severity, holding)
  * GET    /api/v1/anomalies/summary    — severity counts
  * POST   /api/v1/anomalies/run        — manuel detection trigger
  * POST   /api/v1/anomalies/{id}/review — confirm/dismiss

RBAC: read_finance (list/summary), manage_finance (run/review).
"""
from __future__ import annotations

import time
from typing import cast

from fastapi import APIRouter, Depends, Query, Request

from app.engines.anomaly_detection_engine import AnomalyDetectionEngine
from app.models import (
    AnomalyDetectionRunResponse,
    AnomalyReviewRequest,
    AnomalySignalResponse,
    AnomalySignalsListResponse,
    UserProfile,
)
from app.routers._deps import _value_error_to_http
from app.security import require_permissions

router = APIRouter()


def _engine(request: Request) -> AnomalyDetectionEngine:
    return cast(
        AnomalyDetectionEngine,
        request.app.state.anomaly_detection_engine,
    )


@router.get(
    "/api/v1/anomalies",
    response_model=AnomalySignalsListResponse,
    tags=["anomalies"],
)
def list_anomalies(
    request: Request,
    holding_id: int | None = Query(default=None),
    min_severity: str = Query(default="high", pattern="^(critical|high|medium|low)$"),
    limit: int = Query(default=50, ge=1, le=200),
    _user: UserProfile = Depends(require_permissions("read_finance")),
) -> AnomalySignalsListResponse:
    """Açık (open) anomalileri listele.

    Default: sadece high+ severity → false-positive yorgunluğu sıfır.
    """
    engine = _engine(request)
    signals = engine.list_signals(
        holding_id=holding_id,
        min_severity=min_severity,
        limit=limit,
    )
    counts = engine.summary(holding_id=holding_id)
    return AnomalySignalsListResponse(
        signals=[AnomalySignalResponse(**s) for s in signals],
        critical_count=counts.get("critical", 0),
        high_count=counts.get("high", 0),
        medium_count=counts.get("medium", 0),
        total_open=counts.get("total_open", 0),
        generated_at=int(time.time()),
    )


@router.post(
    "/api/v1/anomalies/run",
    response_model=AnomalyDetectionRunResponse,
    tags=["anomalies"],
)
def run_detection(
    request: Request,
    holding_id: int | None = Query(default=None),
    _user: UserProfile = Depends(require_permissions("manage_finance")),
) -> AnomalyDetectionRunResponse:
    """4 detector'u manuel olarak çalıştır → yeni sinyalleri persist et."""
    summary = _engine(request).run_all(holding_id=holding_id)
    return AnomalyDetectionRunResponse(
        new_signals=summary.new_signals,
        detectors_run=summary.detectors_run,
        duration_ms=summary.duration_ms,
        generated_at=summary.generated_at,
    )


@router.post(
    "/api/v1/anomalies/{signal_id}/review",
    response_model=AnomalySignalResponse,
    tags=["anomalies"],
)
def review_anomaly(
    signal_id: int,
    payload: AnomalyReviewRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_finance")),
) -> AnomalySignalResponse:
    """Sinyali onayla veya yanlış-alarm olarak işaretle.

    Bu feedback gelecek kalibrasyon turlarında kullanılacak.
    """
    try:
        result = _engine(request).review(
            signal_id=signal_id,
            action=payload.action,
            reviewed_by=user.username,
            note=payload.note,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc
    if result is None:
        # Either does not exist or not open anymore
        raise _value_error_to_http(
            ValueError("Anomali bulunamadı veya zaten incelenmiş")
        )
    return AnomalySignalResponse(**result)
