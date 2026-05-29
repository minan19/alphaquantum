"""A5.13 (part 3): System router — health + legacy + simple overviews.

8 endpoint covering system health, legacy compatibility, company catalog,
and lightweight engine summaries:

System (1):
- GET  /api/v1/health                            (env + version + count)

Companies + engine overviews (3):
- GET  /api/v1/companies                         (catalog)
- GET  /api/v1/company-engine/overview           (engine summary)
- GET  /api/v1/inventory-engine/critical         (critical stock list)

Simulation (1):
- POST /api/v1/simulate                          (run_simulation, random update)

Legacy / pre-A4 compatibility (3):
- GET  /                                         (root catalog)
- GET  /analyze_all                              (legacy analysis result list)
- GET  /auto_update                              (legacy random update)

Legacy endpoint'ler eski client/integrations için tutulmaya devam ediyor.
Frontend yeni endpoint'leri kullanır (/api/v1/analysis vs /analyze_all).
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request

from app.models import (
    Company,
    CompanyEngineResponse,
    HealthResponse,
    InventoryEngineResponse,
    LegacyAnalysisResult,
    LegacyUpdateResult,
    UpdateResult,
    UserProfile,
)
from app.observability import get_performance_counter
from app.routers._deps import (
    _analysis_service,
    _company_engine,
    _inventory_engine,
    _repo,
)
from app.security import require_permissions


router = APIRouter()


# ── Health ───────────────────────────────────────────────────────────────────


@router.get("/api/v1/health", response_model=HealthResponse, tags=["system"])
def health(request: Request) -> HealthResponse:
    settings = request.app.state.settings
    return HealthResponse(
        status="ok",
        environment=settings.environment,
        company_count=_repo(request).company_count(),
        version=settings.app_version,
    )


# ── Companies + engine overviews ─────────────────────────────────────────────


@router.get(
    "/api/v1/companies",
    response_model=list[Company],
    tags=["companies"],
)
def list_companies(request: Request) -> list[Company]:
    return _repo(request).list_companies()


@router.get(
    "/api/v1/company-engine/overview",
    response_model=CompanyEngineResponse,
    tags=["company_engine"],
)
def company_engine_overview(request: Request) -> CompanyEngineResponse:
    companies = _repo(request).list_companies()
    return _company_engine(request).build_overview(companies)


@router.get(
    "/api/v1/inventory-engine/critical",
    response_model=InventoryEngineResponse,
    tags=["inventory_engine"],
)
def inventory_engine_critical(request: Request) -> InventoryEngineResponse:
    companies = _repo(request).list_companies()
    return _inventory_engine(request).list_critical(companies)


# ── Simulation ───────────────────────────────────────────────────────────────


@router.post(
    "/api/v1/simulate",
    response_model=UpdateResult,
    tags=["simulation"],
)
def simulate_update(
    request: Request,
    user: UserProfile = Depends(require_permissions("run_simulation")),
) -> UpdateResult:
    del user
    companies = _repo(request).update_random()
    return UpdateResult(message="Simulation completed", companies=companies)


# ── Legacy (pre-A4 compatibility) ────────────────────────────────────────────


@router.get("/", tags=["legacy"])
def root(request: Request) -> dict[str, Any]:
    companies = _repo(request).list_companies()
    return {
        "message": "Alpha Quantum aktif",
        "companies": [company.model_dump() for company in companies],
    }


@router.get(
    "/analyze_all",
    response_model=list[LegacyAnalysisResult],
    tags=["legacy"],
)
def analyze_all_legacy(request: Request) -> list[LegacyAnalysisResult]:
    companies = _repo(request).list_companies()
    analyses = _analysis_service(request).analyze_all(companies)
    return [
        LegacyAnalysisResult(
            company=analysis.company,
            status=analysis.status,
            action=analysis.action,
            critical_stock=analysis.critical_stock,
        )
        for analysis in analyses
    ]


@router.get(
    "/auto_update",
    response_model=LegacyUpdateResult,
    tags=["legacy"],
)
def auto_update_legacy(
    request: Request,
    user: UserProfile = Depends(require_permissions("run_simulation")),
) -> LegacyUpdateResult:
    del user
    _repo(request).update_random()
    return LegacyUpdateResult(message="Sistem guncellendi")


# ── G+5: Operational metrics (admin-only) ────────────────────────────────────


@router.get(
    "/api/v1/system/metrics",
    tags=["system"],
)
def system_metrics(
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_users")),
) -> dict[str, Any]:
    """G+5: Operational metrics snapshot.

    In-memory request counter (PerformanceCounter): uptime, request count,
    error rate, status breakdown (2xx/3xx/4xx/5xx), latency p50/p95/p99,
    top 20 path by traffic.

    RBAC: manage_users (admin yetkisi). Production'da Prometheus/Grafana
    için ayrı public scrape endpoint G+5.2'de eklenecek (yetkilendirme
    farklı pattern).

    Restart'ta sıfırlanır (in-memory) — bu pilot için yeterli, scale için
    Prometheus pull model.
    """
    del request, user
    return get_performance_counter().snapshot()
