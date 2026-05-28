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
def root(request: Request) -> dict:
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
