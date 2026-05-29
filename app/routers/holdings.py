"""A5.8: Holdings + International + Ecosystem router (extracted from app/api.py).

10 endpoint covering three related strategic-management domains:

International (3):
- POST /api/v1/international/projects
- GET  /api/v1/international/projects                 (status/country filter)
- GET  /api/v1/international/projects/{project_id}

Ecosystem (2):
- POST /api/v1/ecosystem/activate                     (single company)
- POST /api/v1/ecosystem/activate/portfolio           (multi-company)

Holdings (5):
- POST /api/v1/holdings                               (create)
- GET  /api/v1/holdings                               (list)
- GET  /api/v1/holdings/{holding_id}                  (detail)
- POST /api/v1/holdings/{holding_id}/onboard          (onboard companies)
- POST /api/v1/holdings/onboard/bulk                  (bulk onboard)

RBAC: read_international + write_international + read_holdings + manage_holdings
+ ecosystem composite (write_feasibility + write_international + write_procurement).

Bu üç domain birbirine yakın iş kuralı bağlamında çalışıyor:
- Holdings: çoklu şirket sahipliği
- International: yurtdışı proje portföyü
- Ecosystem: feasibility + procurement + international entegrasyonu
"""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.models import (
    ConsolidatedPLResponse,
    EcosystemActivationRequest,
    EcosystemActivationResponse,
    EcosystemPortfolioActivationRequest,
    EcosystemPortfolioActivationResponse,
    ExecSummaryRequest,
    ExecSummaryResponse,
    GroupFXPositionResponse,
    HoldingBulkOnboardRequest,
    HoldingBulkOnboardResponse,
    HoldingCreateRequest,
    HoldingDetailResponse,
    HoldingListResponse,
    HoldingOnboardRequest,
    HoldingOnboardResponse,
    HoldingRead,
    InternationalProjectListResponse,
    InternationalProjectRequest,
    InternationalProjectStoredResponse,
    UserProfile,
)
from app.routers._deps import (
    _consolidation_engine,
    _ecosystem_engine,
    _ensure_company_scope,
    _exec_summary_engine,
    _group_fx_engine,
    _holding_engine,
    _international_engine,
    _repo,
    _user_has_company_scope,
    _value_error_to_http,
)
from app.security import require_permissions


router = APIRouter()


# ── International projects ───────────────────────────────────────────────────


@router.post(
    "/api/v1/international/projects",
    response_model=InternationalProjectStoredResponse,
    status_code=201,
    tags=["international"],
)
def create_international_project(
    payload: InternationalProjectRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("write_international")),
) -> InternationalProjectStoredResponse:
    _ensure_company_scope(request, user, payload.company_name)
    try:
        return _international_engine(request).create_project(payload)
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


@router.get(
    "/api/v1/international/projects",
    response_model=InternationalProjectListResponse,
    tags=["international"],
)
def list_international_projects(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    status_filter: str | None = Query(default=None, alias="status"),
    country: str | None = Query(default=None),
    user: UserProfile = Depends(require_permissions("read_international")),
) -> InternationalProjectListResponse:
    try:
        result = _international_engine(request).list_projects(
            limit=limit,
            status=status_filter,
            country=country,
        )
        filtered_items = [
            item
            for item in result.items
            if _user_has_company_scope(request, user, item.company_name)
        ]
        return InternationalProjectListResponse(
            total=len(filtered_items),
            items=filtered_items,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


@router.get(
    "/api/v1/international/projects/{project_id}",
    response_model=InternationalProjectStoredResponse,
    tags=["international"],
)
def get_international_project(
    project_id: int,
    request: Request,
    user: UserProfile = Depends(require_permissions("read_international")),
) -> InternationalProjectStoredResponse:
    try:
        result = _international_engine(request).get_project(project_id)
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc
    _ensure_company_scope(request, user, result.company_name)
    return result


# ── Ecosystem activation ─────────────────────────────────────────────────────


@router.post(
    "/api/v1/ecosystem/activate",
    response_model=EcosystemActivationResponse,
    tags=["ecosystem"],
)
def activate_strategic_ecosystem(
    payload: EcosystemActivationRequest,
    request: Request,
    user: UserProfile = Depends(
        require_permissions(
            "write_feasibility",
            "write_international",
            "write_procurement",
        )
    ),
) -> EcosystemActivationResponse:
    _ensure_company_scope(request, user, payload.company_name)
    try:
        return _ecosystem_engine(request).activate(payload)
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


@router.post(
    "/api/v1/ecosystem/activate/portfolio",
    response_model=EcosystemPortfolioActivationResponse,
    tags=["ecosystem"],
)
def activate_strategic_ecosystem_portfolio(
    payload: EcosystemPortfolioActivationRequest,
    request: Request,
    user: UserProfile = Depends(
        require_permissions(
            "write_feasibility",
            "write_international",
            "write_procurement",
        )
    ),
) -> EcosystemPortfolioActivationResponse:
    for target in payload.companies:
        _ensure_company_scope(request, user, target.company_name)
    try:
        company_names = [company.name for company in _repo(request).list_companies()]
        company_names = [
            company_name
            for company_name in company_names
            if _user_has_company_scope(request, user, company_name)
        ]
        return _ecosystem_engine(request).activate_portfolio(
            payload,
            registered_company_names=company_names,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


# ── Holdings ─────────────────────────────────────────────────────────────────


@router.post(
    "/api/v1/holdings",
    response_model=HoldingRead,
    status_code=201,
    tags=["holding"],
)
def create_holding(
    payload: HoldingCreateRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_holdings")),
) -> HoldingRead:
    del user
    try:
        return _holding_engine(request).create_holding(payload)
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Holding already exists",
        ) from exc


@router.get(
    "/api/v1/holdings",
    response_model=HoldingListResponse,
    tags=["holding"],
)
def list_holdings(
    request: Request,
    limit: int = Query(default=200, ge=1, le=1000),
    user: UserProfile = Depends(require_permissions("read_holdings")),
) -> HoldingListResponse:
    del user
    return _holding_engine(request).list_holdings(limit=limit)


@router.get(
    "/api/v1/holdings/{holding_id}",
    response_model=HoldingDetailResponse,
    tags=["holding"],
)
def get_holding_detail(
    holding_id: int,
    request: Request,
    limit: int = Query(default=1000, ge=1, le=5000),
    user: UserProfile = Depends(require_permissions("read_holdings")),
) -> HoldingDetailResponse:
    del user
    try:
        return _holding_engine(request).get_holding_detail(
            holding_id=holding_id, limit=limit
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


@router.post(
    "/api/v1/holdings/{holding_id}/onboard",
    response_model=HoldingOnboardResponse,
    tags=["holding"],
)
def onboard_holding_companies(
    holding_id: int,
    payload: HoldingOnboardRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_holdings")),
) -> HoldingOnboardResponse:
    del user
    try:
        return _holding_engine(request).onboard_companies(
            holding_id=holding_id, payload=payload
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Holding onboarding conflict",
        ) from exc


@router.post(
    "/api/v1/holdings/onboard/bulk",
    response_model=HoldingBulkOnboardResponse,
    status_code=201,
    tags=["holding"],
)
def onboard_holding_bulk(
    payload: HoldingBulkOnboardRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_holdings")),
) -> HoldingBulkOnboardResponse:
    del user
    try:
        return _holding_engine(request).onboard_bulk(payload)
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Holding already exists",
        ) from exc


# ── G1.2: Konsolide P&L (intercompany eliminasyonlu) ─────────────────────────


@router.get(
    "/api/v1/holdings/{holding_id}/consolidated-pl",
    response_model=ConsolidatedPLResponse,
    tags=["holding"],
)
def get_consolidated_pl(
    holding_id: int,
    start_date: str,
    end_date: str,
    request: Request,
    user: UserProfile = Depends(require_permissions("read_holdings")),
) -> ConsolidatedPLResponse:
    """Holding'in konsolide P&L'i — intercompany kalemler ELİMİNE edilmiş.

    Karma holding (inşaat + lojistik + gıda + emlak) için kritik yetenek:
    grup-içi alışverişler ("Lojistik AŞ Gıda AŞ'ye nakliye faturalandırıyor")
    konsolide rakamdan düşülür, sadece üçüncü taraflarla yapılan iş kalır.

    Sahne 2 ("10:30 - Yönetim toplantısı, Konsolide P&L") burayı çağırır.

    Query params:
      - start_date: ISO YYYY-MM-DD (inclusive)
      - end_date:   ISO YYYY-MM-DD (inclusive, ≥ start_date)
    """
    del user
    try:
        return _consolidation_engine(request).consolidated_pl(
            holding_id=holding_id,
            start_date=start_date,
            end_date=end_date,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


# ── G1.4: Group FX Net Position ──────────────────────────────────────────────


@router.get(
    "/api/v1/holdings/{holding_id}/fx-position",
    response_model=GroupFXPositionResponse,
    tags=["holding"],
)
def get_group_fx_position(
    holding_id: int,
    request: Request,
    as_of_date: str | None = Query(
        default=None,
        description="ISO YYYY-MM-DD; default = today",
    ),
    user: UserProfile = Depends(require_permissions("read_holdings")),
) -> GroupFXPositionResponse:
    """Holding-wide multi-currency net pozisyon + sensitivity scenarios.

    Karma holding'te alt şirketler farklı para birimlerinde ticaret yapar:
    Gıda AŞ USD ithalatı (short), İnşaat AŞ EUR ihracatı (long). Bu endpoint
    holding seviyesinde net pozisyonu, TL devalüasyon senaryolarını ve
    risk seviyesini döner.

    Sahne 1 ("08:00 - Sabah kahvesi, FX değişimi") burayı çağırır.
    """
    del user
    try:
        return _group_fx_engine(request).group_fx_position(
            holding_id=holding_id,
            as_of_date=as_of_date,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


# ── G+1: AI Executive Summary (Claude LLM) ───────────────────────────────────


@router.post(
    "/api/v1/holdings/{holding_id}/exec-summary",
    response_model=ExecSummaryResponse,
    tags=["holding"],
)
def generate_exec_summary(
    holding_id: int,
    payload: ExecSummaryRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("read_holdings")),
) -> ExecSummaryResponse:
    """Holding yönetici özeti — Claude LLM ile Türkçe narrative.

    Sahne 5 ("17:00 günlük rapor — Exec summary") burayı çağırır.

    Backend zinciri:
      1. ConsolidationEngine.consolidated_pl (G1.2)
      2. GroupFXEngine.group_fx_position (G1.4)
      3. IntercompanyTransferEngine.list_pending (G1.3)
      4. LLM narrative generation (Claude opus-4-7, prompt cached)

    Production'da AQ_ANTHROPIC_API_KEY varsa Claude API. Yoksa
    deterministic rule-based fallback (OfflineLLMService).

    RBAC: read_holdings permission. Audit log: G+4 hash chain + G+5 event.
    """
    del user
    try:
        return _exec_summary_engine(request).generate_summary(
            holding_id=holding_id,
            payload=payload,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc
