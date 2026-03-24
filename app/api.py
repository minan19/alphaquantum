from __future__ import annotations

from datetime import datetime, timezone
from html import escape
import logging
import sqlite3

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse

from app.audit_repository import AuditRepository
from app.auth_service import AuthService
from app.engines import (
    CompanyEngine,
    ConnectorEngine,
    FeasibilityEngine,
    FinanceEngine,
    HoldingEngine,
    InternationalOperationsEngine,
    InstitutionWebEngine,
    InventoryEngine,
    MarketDataEngine,
    MarketIntelligenceEngine,
    ProcurementEngine,
    StrategicEcosystemEngine,
    TenderEngine,
)
from app.models import (
    AnalysisResult,
    AuditLogRead,
    CentralBankPanelResponse,
    Company,
    CompanyEngineResponse,
    MigrationDryRunResponse,
    MigrationPreflightResponse,
    ConnectorCanonicalPreviewRequest,
    ConnectorCanonicalPreviewResponse,
    ConnectorCreateRequest,
    ConnectorListResponse,
    ConnectorQueueHealthResponse,
    ConnectorRead,
    ConnectorSyncDispatchRequest,
    ConnectorSyncDispatchResponse,
    ConnectorSyncJobCreateRequest,
    ConnectorSyncJobListResponse,
    ConnectorSyncJobRead,
    DashboardDataResponse,
    DashboardSummary,
    EcosystemActivationRequest,
    EcosystemActivationResponse,
    EcosystemPortfolioActivationRequest,
    EcosystemPortfolioActivationResponse,
    FeasibilityReportListResponse,
    FeasibilityReportRequest,
    FeasibilityReportStoredResponse,
    FinanceCashflowResponse,
    FinanceForecastResponse,
    FinanceLedgerEntryCreateRequest,
    FinanceLedgerEntryRead,
    FinanceLedgerResponse,
    FinanceOverviewResponse,
    HealthResponse,
    HoldingBulkOnboardRequest,
    HoldingBulkOnboardResponse,
    HoldingCreateRequest,
    HoldingDetailResponse,
    HoldingListResponse,
    HoldingOnboardRequest,
    HoldingOnboardResponse,
    HoldingRead,
    InstitutionReportRequest,
    InstitutionReportResponse,
    InsightItem,
    InternationalProjectListResponse,
    InternationalProjectRequest,
    InternationalProjectStoredResponse,
    InventoryEngineResponse,
    LegacyAnalysisResult,
    LegacyUpdateResult,
    LoginRequest,
    MigrationActionResponse,
    MigrationRollbackRequest,
    MigrationStatusItem,
    MarketAnalysisResponse,
    MarketBacktestResponse,
    MarketIntelligenceRequest,
    MarketIntelligenceResponse,
    MarketOHLCVResponse,
    MarketRefreshRequest,
    MarketRefreshResponse,
    MarketSourceCatalogResponse,
    MarketSignalsResponse,
    ProfessionalReportResponse,
    ProcurementAutoOrderRequest,
    ProcurementEvaluationResponse,
    ProcurementPurchaseOrderBatchResponse,
    ProcurementRequestCreateRequest,
    ProcurementRequestListResponse,
    ProcurementRequestRead,
    ProcurementTenderPlanRequest,
    ProcurementTenderPlanResponse,
    ProcurementVendorQuoteCreateRequest,
    ProcurementVendorQuoteListResponse,
    ProcurementVendorQuoteRead,
    TenderDossierResponse,
    TenderGenerationRequest,
    LogoutRequest,
    LogoutResponse,
    PasswordRotateRequest,
    PermissionRead,
    RefreshTokenRequest,
    RoleCreateRequest,
    RolePermissionsRead,
    RolePermissionsUpdateRequest,
    RoleRead,
    RoleUpdateRequest,
    TokenResponse,
    UpdateResult,
    UserCreateRequest,
    UserProfile,
    UserRead,
    UserUpdateRequest,
    WorldBankPanelResponse,
)
from app.migration_manager import MigrationManager
from app.repository import CompanyRepository
from app.security import (
    create_access_token,
    get_current_user,
    require_permissions,
)
from app.services import AnalysisService, DashboardService

router = APIRouter()
logger = logging.getLogger("alpha_quantum.auth")


def _repo(request: Request) -> CompanyRepository:
    return request.app.state.company_repository


def _analysis_service(request: Request) -> AnalysisService:
    return request.app.state.analysis_service


def _dashboard_service(request: Request) -> DashboardService:
    return request.app.state.dashboard_service


def _auth_service(request: Request) -> AuthService:
    return request.app.state.auth_service


def _audit_repo(request: Request) -> AuditRepository:
    return request.app.state.audit_repository


def _emit_audit_event(
    request: Request,
    user: UserProfile,
    event_type: str,
    event_detail: dict | None = None,
) -> None:
    request_id = getattr(request.state, "request_id", "")
    _audit_repo(request).write_event(
        username=user.username,
        role=user.role,
        event_type=event_type,
        event_detail=event_detail,
        request_id=str(request_id),
        ip_address=request.client.host if request.client else None,
    )


def _settings(request: Request):
    return request.app.state.settings


def _migration_manager(request: Request) -> MigrationManager:
    return request.app.state.migration_manager


def _company_engine(request: Request) -> CompanyEngine:
    return request.app.state.company_engine


def _connector_engine(request: Request) -> ConnectorEngine:
    return request.app.state.connector_engine


def _inventory_engine(request: Request) -> InventoryEngine:
    return request.app.state.inventory_engine


def _finance_engine(request: Request) -> FinanceEngine:
    return request.app.state.finance_engine


def _market_engine(request: Request) -> MarketDataEngine:
    return request.app.state.market_data_engine


def _market_intelligence_engine(request: Request) -> MarketIntelligenceEngine:
    return request.app.state.market_intelligence_engine


def _global_engine(request: Request):
    return request.app.state.global_analysis_engine


def _institution_engine(request: Request) -> InstitutionWebEngine:
    return request.app.state.institution_web_engine


def _tender_engine(request: Request) -> TenderEngine:
    return request.app.state.tender_engine


def _procurement_engine(request: Request) -> ProcurementEngine:
    return request.app.state.procurement_engine


def _feasibility_engine(request: Request) -> FeasibilityEngine:
    return request.app.state.feasibility_engine


def _international_engine(request: Request) -> InternationalOperationsEngine:
    return request.app.state.international_operations_engine


def _ecosystem_engine(request: Request) -> StrategicEcosystemEngine:
    return request.app.state.strategic_ecosystem_engine


def _holding_engine(request: Request) -> HoldingEngine:
    return request.app.state.holding_engine


def _raise_auth_limiter_unavailable(*, client_host: str, username: str, stage: str) -> None:
    logger.exception(
        "auth_rate_limiter_unavailable stage=%s host=%s username=%s",
        stage,
        client_host,
        username,
    )
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Authentication rate limiter unavailable. Please retry shortly.",
    )


@router.post("/api/v1/auth/login", response_model=TokenResponse, tags=["auth"])
def login(payload: LoginRequest, request: Request) -> TokenResponse:
    settings = _settings(request)
    client_host = request.client.host if request.client else "unknown"
    limiter_key = f"{client_host}:{payload.username}"
    limiter = request.app.state.auth_limiter
    auth_service = _auth_service(request)

    try:
        is_allowed = limiter.is_allowed(limiter_key)
    except Exception:
        _raise_auth_limiter_unavailable(
            client_host=client_host,
            username=payload.username,
            stage="is_allowed",
        )

    if not is_allowed:
        logger.warning(
            "auth_rate_limited host=%s username=%s",
            client_host,
            payload.username,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
        )

    auth_service.cleanup_tokens()
    user = auth_service.authenticate(payload.username, payload.password)
    if user is None:
        try:
            limiter.register_failure(limiter_key)
        except Exception:
            _raise_auth_limiter_unavailable(
                client_host=client_host,
                username=payload.username,
                stage="register_failure",
            )
        logger.warning(
            "auth_failed host=%s username=%s",
            client_host,
            payload.username,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    try:
        limiter.register_success(limiter_key)
    except Exception:
        _raise_auth_limiter_unavailable(
            client_host=client_host,
            username=payload.username,
            stage="register_success",
        )
    logger.info("auth_success host=%s username=%s role=%s", client_host, user.username, user.role)

    access_token = create_access_token(
        user_id=user.id,
        username=user.username,
        role=user.role,
        secret=settings.jwt_secret,
        expire_minutes=settings.access_token_expire_minutes,
    )
    refresh_token = auth_service.create_refresh_token(user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
        refresh_expires_in=auth_service.refresh_token_expire_seconds,
    )


@router.post("/api/v1/auth/refresh", response_model=TokenResponse, tags=["auth"])
def refresh_token(payload: RefreshTokenRequest, request: Request) -> TokenResponse:
    settings = _settings(request)
    auth_service = _auth_service(request)
    auth_service.cleanup_tokens()

    rotated = auth_service.rotate_refresh_token(payload.refresh_token)
    if rotated is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    new_refresh_token, user = rotated
    access_token = create_access_token(
        user_id=user.id,
        username=user.username,
        role=user.role,
        secret=settings.jwt_secret,
        expire_minutes=settings.access_token_expire_minutes,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
        refresh_expires_in=auth_service.refresh_token_expire_seconds,
    )


@router.post("/api/v1/auth/logout", response_model=LogoutResponse, tags=["auth"])
def logout(
    request: Request,
    payload: LogoutRequest | None = Body(default=None),
    user: UserProfile = Depends(get_current_user),
) -> LogoutResponse:
    auth_service = _auth_service(request)
    payload = payload or LogoutRequest()

    token_payload = getattr(request.state, "access_token_payload", None)
    if token_payload is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Access token payload missing",
        )

    jti = token_payload.get("jti")
    exp = token_payload.get("exp")
    if not jti or exp is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Access token payload missing revoke metadata",
        )

    auth_service.revoke_access_token(
        jti=str(jti),
        exp=int(exp),
        reason="logout",
    )

    if payload.refresh_token:
        auth_service.revoke_refresh_token(payload.refresh_token, reason="logout")

    if payload.revoke_all_devices:
        auth_service.revoke_all_refresh_tokens_for_user(user.id, reason="logout_all")

    return LogoutResponse(message="Logout successful")


@router.get("/api/v1/auth/me", response_model=UserProfile, tags=["auth"])
def auth_me(user: UserProfile = Depends(get_current_user)) -> UserProfile:
    return user


@router.get("/api/v1/roles", response_model=list[RoleRead], tags=["auth"])
def list_roles(
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_roles")),
) -> list[RoleRead]:
    del user
    return [_to_role_read(row) for row in _auth_service(request).list_roles()]


@router.post("/api/v1/roles", response_model=RoleRead, status_code=201, tags=["auth"])
def create_role(
    payload: RoleCreateRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_roles")),
) -> RoleRead:
    try:
        row = _auth_service(request).create_role(
            name=payload.name,
            description=payload.description,
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Role already exists",
        ) from exc

    _emit_audit_event(request, user, "role.create", {"role_name": payload.name})
    return _to_role_read(row)


@router.patch("/api/v1/roles/{role_id}", response_model=RoleRead, tags=["auth"])
def update_role(
    role_id: int,
    payload: RoleUpdateRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_roles")),
) -> RoleRead:
    try:
        row = _auth_service(request).update_role(
            role_id,
            name=payload.name,
            description=payload.description,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Role already exists",
        ) from exc

    _emit_audit_event(request, user, "role.update", {"role_id": role_id, "new_name": payload.name})
    return _to_role_read(row)


@router.delete("/api/v1/roles/{role_id}", status_code=204, tags=["auth"])
def delete_role(
    role_id: int,
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_roles")),
) -> None:
    try:
        _auth_service(request).delete_role(role_id)
    except ValueError as exc:
        raise _value_error_to_http(exc)
    _emit_audit_event(request, user, "role.delete", {"role_id": role_id})


@router.get("/api/v1/permissions", response_model=list[PermissionRead], tags=["auth"])
def list_permissions(
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_roles")),
) -> list[PermissionRead]:
    del user
    return [_to_permission_read(row) for row in _auth_service(request).list_permissions()]


@router.get(
    "/api/v1/roles/{role_id}/permissions",
    response_model=RolePermissionsRead,
    tags=["auth"],
)
def get_role_permissions(
    role_id: int,
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_roles")),
) -> RolePermissionsRead:
    del user
    try:
        role = _auth_service(request).get_role(role_id)
        permissions = _auth_service(request).role_permissions(role_id)
    except ValueError as exc:
        raise _value_error_to_http(exc)
    return RolePermissionsRead(
        role_id=role_id,
        role_name=str(role["name"]),
        permissions=permissions,
    )


@router.put(
    "/api/v1/roles/{role_id}/permissions",
    response_model=RolePermissionsRead,
    tags=["auth"],
)
def update_role_permissions(
    role_id: int,
    payload: RolePermissionsUpdateRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_roles")),
) -> RolePermissionsRead:
    try:
        old_permissions = _auth_service(request).role_permissions(role_id)
        permissions = _auth_service(request).update_role_permissions(
            role_id,
            payload.permissions,
        )
        role = _auth_service(request).get_role(role_id)
    except ValueError as exc:
        raise _value_error_to_http(exc)

    added = sorted(set(permissions) - set(old_permissions))
    removed = sorted(set(old_permissions) - set(permissions))
    _emit_audit_event(
        request,
        user,
        "role.permissions.update",
        {
            "role_id": role_id,
            "role_name": str(role["name"]),
            "added": added,
            "removed": removed,
            "permissions_after": sorted(permissions),
        },
    )
    return RolePermissionsRead(
        role_id=role_id,
        role_name=str(role["name"]),
        permissions=permissions,
    )


@router.get(
    "/api/v1/admin/migrations/status",
    response_model=list[MigrationStatusItem],
    tags=["admin"],
)
def migration_status(
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_migrations")),
) -> list[MigrationStatusItem]:
    del user
    rows = _migration_manager(request).status()
    return [MigrationStatusItem(**row) for row in rows]


@router.post(
    "/api/v1/admin/migrations/apply",
    response_model=MigrationActionResponse,
    tags=["admin"],
)
def migration_apply(
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_migrations")),
) -> MigrationActionResponse:
    versions = _migration_manager(request).apply_all()
    _emit_audit_event(request, user, "migration.apply", {"versions_applied": versions})
    return MigrationActionResponse(
        message="Migrations applied",
        versions=versions,
    )


@router.post(
    "/api/v1/admin/migrations/rollback",
    response_model=MigrationActionResponse,
    tags=["admin"],
)
def migration_rollback(
    payload: MigrationRollbackRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_migrations")),
) -> MigrationActionResponse:
    try:
        versions = _migration_manager(request).rollback(steps=payload.steps, force=payload.force)
    except ValueError as exc:
        raise _value_error_to_http(exc)
    _emit_audit_event(
        request, user, "migration.rollback",
        {"versions_rolled_back": versions, "steps": payload.steps, "force": payload.force},
    )
    return MigrationActionResponse(
        message="Migrations rolled back",
        versions=versions,
    )


@router.get(
    "/api/v1/admin/migrations/dry-run",
    response_model=MigrationDryRunResponse,
    tags=["admin"],
)
def migration_dry_run(
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_migrations")),
) -> MigrationDryRunResponse:
    del user
    result = _migration_manager(request).dry_run()
    return MigrationDryRunResponse(**result)


@router.post(
    "/api/v1/admin/migrations/preflight",
    response_model=MigrationPreflightResponse,
    tags=["admin"],
)
def migration_preflight(
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_migrations")),
) -> MigrationPreflightResponse:
    del user
    result = _migration_manager(request).preflight()
    return MigrationPreflightResponse(**result)


@router.get("/api/v1/users", response_model=list[UserRead], tags=["auth"])
def list_users(
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_users")),
) -> list[UserRead]:
    del user
    auth_service = _auth_service(request)
    rows = auth_service.list_users()
    return [
        _to_user_read(
            row,
            company_scopes=auth_service.user_company_scopes(int(row["id"])),
        )
        for row in rows
    ]


@router.post("/api/v1/users", response_model=UserRead, status_code=201, tags=["auth"])
def create_user(
    payload: UserCreateRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_users")),
) -> UserRead:
    try:
        row = _auth_service(request).create_user(
            username=payload.username,
            password=payload.password,
            role=payload.role,
            is_active=payload.is_active,
            company_scopes=payload.company_scopes,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        ) from exc

    _emit_audit_event(
        request, user, "user.create",
        {"target_username": payload.username, "role": payload.role, "is_active": payload.is_active},
    )
    return _to_user_read(
        row,
        company_scopes=_auth_service(request).user_company_scopes(int(row["id"])),
    )


@router.patch("/api/v1/users/{user_id}", response_model=UserRead, tags=["auth"])
def update_user(
    user_id: int,
    payload: UserUpdateRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_users")),
) -> UserRead:
    try:
        row = _auth_service(request).update_user(
            user_id,
            role=payload.role,
            is_active=payload.is_active,
            company_scopes=payload.company_scopes,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc)

    _emit_audit_event(
        request, user, "user.update",
        {"target_user_id": user_id, "role": payload.role, "is_active": payload.is_active},
    )
    return _to_user_read(
        row,
        company_scopes=_auth_service(request).user_company_scopes(int(row["id"])),
    )


@router.delete("/api/v1/users/{user_id}", status_code=204, tags=["auth"])
def delete_user(
    user_id: int,
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_users")),
) -> None:
    try:
        _auth_service(request).delete_user(user_id)
    except ValueError as exc:
        raise _value_error_to_http(exc)
    _emit_audit_event(request, user, "user.delete", {"target_user_id": user_id})


@router.post(
    "/api/v1/users/{user_id}/password-rotate",
    response_model=LogoutResponse,
    tags=["auth"],
)
def rotate_password(
    user_id: int,
    payload: PasswordRotateRequest,
    request: Request,
    user: UserProfile = Depends(get_current_user),
) -> LogoutResponse:
    try:
        _auth_service(request).rotate_password(
            actor=user,
            target_user_id=user_id,
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise _value_error_to_http(exc)

    return LogoutResponse(message="Password rotated")


@router.get("/api/v1/audit-logs", response_model=list[AuditLogRead], tags=["audit"])
def list_audit_logs(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    user: UserProfile = Depends(require_permissions("view_audit_logs")),
) -> list[AuditLogRead]:
    del user
    rows = _audit_repo(request).list_logs(limit=limit)
    return [AuditLogRead(**row) for row in rows]


@router.get("/", tags=["legacy"])
def root(request: Request) -> dict:
    companies = _repo(request).list_companies()
    return {
        "message": "Alpha Quantum aktif",
        "companies": [company.model_dump() for company in companies],
    }


@router.get("/api/v1/companies", response_model=list[Company], tags=["companies"])
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


@router.get(
    "/api/v1/finance-engine/overview",
    response_model=FinanceOverviewResponse,
    tags=["finance_engine"],
)
def finance_engine_overview(
    request: Request,
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> FinanceOverviewResponse:
    companies = _filter_companies_by_user_scope(
        request,
        user,
        _repo(request).list_companies(),
    )
    return _finance_engine(request).build_overview(companies)


@router.post(
    "/api/v1/finance-engine/ledger",
    response_model=FinanceLedgerEntryRead,
    status_code=201,
    tags=["finance_engine"],
)
def create_finance_ledger_entry(
    payload: FinanceLedgerEntryCreateRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("write_finance")),
) -> FinanceLedgerEntryRead:
    _ensure_company_scope(request, user, payload.company)
    try:
        return _finance_engine(request).create_ledger_entry(payload=payload)
    except ValueError as exc:
        raise _value_error_to_http(exc)


@router.get(
    "/api/v1/finance-engine/ledger",
    response_model=FinanceLedgerResponse,
    tags=["finance_engine"],
)
def list_finance_ledger_entries(
    request: Request,
    company: str | None = Query(default=None),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> FinanceLedgerResponse:
    if company:
        _ensure_company_scope(request, user, company)
    elif not _is_holding_scope(request, user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scoped users must provide company parameter",
        )
    try:
        return _finance_engine(request).list_ledger_entries(
            company=company,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc)


@router.get(
    "/api/v1/finance-engine/cashflow",
    response_model=FinanceCashflowResponse,
    tags=["finance_engine"],
)
def finance_cashflow(
    request: Request,
    company: str | None = Query(default=None),
    lookback_days: int = Query(default=30, ge=1, le=365),
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> FinanceCashflowResponse:
    if company:
        _ensure_company_scope(request, user, company)
    elif not _is_holding_scope(request, user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scoped users must provide company parameter",
        )
    try:
        return _finance_engine(request).build_cashflow(
            company=company,
            lookback_days=lookback_days,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc)


@router.get(
    "/api/v1/finance-engine/forecast",
    response_model=FinanceForecastResponse,
    tags=["finance_engine"],
)
def finance_forecast(
    request: Request,
    company: str | None = Query(default=None),
    lookback_days: int = Query(default=30, ge=1, le=365),
    horizon_days: int = Query(default=30, ge=1, le=365),
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> FinanceForecastResponse:
    if company:
        _ensure_company_scope(request, user, company)
    elif not _is_holding_scope(request, user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scoped users must provide company parameter",
        )
    companies = _filter_companies_by_user_scope(
        request,
        user,
        _repo(request).list_companies(),
    )
    try:
        return _finance_engine(request).forecast_cashflow(
            companies=companies,
            company=company,
            lookback_days=lookback_days,
            horizon_days=horizon_days,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc)


@router.get(
    "/api/v1/market/ohlcv",
    response_model=MarketOHLCVResponse,
    tags=["market"],
)
def market_ohlcv(
    request: Request,
    symbol: str = Query(default="AAPL", min_length=1),
    timeframe: str = Query(default="1d"),
    days: int = Query(default=180, ge=20, le=3650),
    refresh: bool = Query(default=False),
    user: UserProfile = Depends(require_permissions("read_market")),
) -> MarketOHLCVResponse:
    del user
    try:
        return _market_engine(request).get_ohlcv(
            symbol=symbol,
            timeframe=timeframe,
            days=days,
            refresh=refresh,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc)


@router.get(
    "/api/v1/market/analysis",
    response_model=MarketAnalysisResponse,
    tags=["market"],
)
def market_analysis(
    request: Request,
    symbol: str = Query(default="AAPL", min_length=1),
    timeframe: str = Query(default="1d"),
    days: int = Query(default=180, ge=20, le=3650),
    refresh: bool = Query(default=False),
    user: UserProfile = Depends(require_permissions("read_market")),
) -> MarketAnalysisResponse:
    del user
    try:
        return _market_engine(request).analyze_symbol(
            symbol=symbol,
            timeframe=timeframe,
            days=days,
            refresh=refresh,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc)


@router.get(
    "/api/v1/market/signals",
    response_model=MarketSignalsResponse,
    tags=["market"],
)
def market_signals(
    request: Request,
    symbols: str = Query(default="AAPL,MSFT,NVDA,TSLA"),
    timeframe: str = Query(default="1d"),
    days: int = Query(default=180, ge=20, le=3650),
    refresh: bool = Query(default=False),
    user: UserProfile = Depends(require_permissions("read_market")),
) -> MarketSignalsResponse:
    del user
    parsed_symbols = _parse_symbols_csv(symbols)
    if not parsed_symbols:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="symbols parameter is empty")

    try:
        return _market_engine(request).analyze_symbols(
            symbols=parsed_symbols,
            timeframe=timeframe,
            days=days,
            refresh=refresh,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc)


@router.post(
    "/api/v1/market/refresh",
    response_model=MarketRefreshResponse,
    tags=["market"],
)
def market_refresh(
    payload: MarketRefreshRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("refresh_market")),
) -> MarketRefreshResponse:
    del user
    symbols = payload.symbols or ["AAPL", "MSFT", "NVDA", "TSLA"]

    try:
        refreshed = _market_engine(request).refresh_symbols(
            symbols=symbols,
            timeframe=payload.timeframe,
            days=payload.days,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc)

    return MarketRefreshResponse(
        refreshed_count=len(refreshed),
        symbols=refreshed,
    )


@router.get(
    "/api/v1/global/central-banks",
    response_model=CentralBankPanelResponse,
    tags=["global_intel"],
)
def global_central_banks(
    request: Request,
    days: int = Query(default=720, ge=90, le=3650),
    user: UserProfile = Depends(require_permissions("read_global_intel")),
) -> CentralBankPanelResponse:
    del user
    return _global_engine(request).central_bank_panel(days=days)


@router.get(
    "/api/v1/global/world-bank",
    response_model=WorldBankPanelResponse,
    tags=["global_intel"],
)
def global_world_bank(
    request: Request,
    countries: str = Query(default="USA,TUR,DEU"),
    indicators: str = Query(default="FP.CPI.TOTL.ZG,NY.GDP.MKTP.KD.ZG,SL.UEM.TOTL.ZS"),
    years: int = Query(default=20, ge=5, le=60),
    user: UserProfile = Depends(require_permissions("read_global_intel")),
) -> WorldBankPanelResponse:
    del user
    return _global_engine(request).world_bank_panel(
        countries=_parse_symbols_csv(countries),
        indicators=_parse_symbols_csv(indicators),
        years=years,
    )


@router.get(
    "/api/v1/global/report",
    response_model=ProfessionalReportResponse,
    tags=["global_intel"],
)
def global_professional_report(
    request: Request,
    countries: str = Query(default="USA,TUR,DEU"),
    indicators: str = Query(default="FP.CPI.TOTL.ZG,NY.GDP.MKTP.KD.ZG,SL.UEM.TOTL.ZS"),
    bank_symbols: str = Query(default="JPM,BAC,HSBC,BNP.PA"),
    index_symbols: str = Query(default="SPX,NDX,DAX,XU100"),
    market_days: int = Query(default=260, ge=60, le=3650),
    macro_days: int = Query(default=720, ge=90, le=3650),
    macro_years: int = Query(default=20, ge=5, le=60),
    refresh_market: bool = Query(default=False),
    user: UserProfile = Depends(require_permissions("read_global_intel")),
) -> ProfessionalReportResponse:
    del user
    return _global_engine(request).build_professional_report(
        countries=_parse_symbols_csv(countries),
        indicators=_parse_symbols_csv(indicators),
        bank_symbols=_parse_symbols_csv(bank_symbols),
        index_symbols=_parse_symbols_csv(index_symbols),
        market_days=market_days,
        macro_days=macro_days,
        macro_years=macro_years,
        refresh_market=refresh_market,
    )


@router.post(
    "/api/v1/public-institutions/report",
    response_model=InstitutionReportResponse,
    tags=["public_intel"],
)
def public_institutions_report(
    payload: InstitutionReportRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("read_public_sources")),
) -> InstitutionReportResponse:
    del user
    return _institution_engine(request).build_report(payload)


@router.post(
    "/api/v1/market/intelligence",
    response_model=MarketIntelligenceResponse,
    tags=["market"],
)
def market_intelligence_report(
    payload: MarketIntelligenceRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("read_market", "read_public_sources")),
) -> MarketIntelligenceResponse:
    del user
    try:
        return _market_intelligence_engine(request).build_report(payload)
    except ValueError as exc:
        raise _value_error_to_http(exc)


@router.post(
    "/api/v1/procurement/requests",
    response_model=ProcurementRequestRead,
    status_code=201,
    tags=["procurement"],
)
def create_procurement_request(
    payload: ProcurementRequestCreateRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("write_procurement")),
) -> ProcurementRequestRead:
    _ensure_company_scope(request, user, payload.company)
    try:
        return _procurement_engine(request).create_request(payload)
    except ValueError as exc:
        raise _value_error_to_http(exc)


@router.get(
    "/api/v1/procurement/requests",
    response_model=ProcurementRequestListResponse,
    tags=["procurement"],
)
def list_procurement_requests(
    request: Request,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    user: UserProfile = Depends(require_permissions("read_procurement")),
) -> ProcurementRequestListResponse:
    response = _procurement_engine(request).list_requests(
        status=status_filter,
        limit=limit,
    )
    filtered_items = [
        item
        for item in response.items
        if _user_has_company_scope(request, user, item.company)
    ]
    return ProcurementRequestListResponse(
        total=len(filtered_items),
        items=filtered_items,
    )


@router.get(
    "/api/v1/procurement/requests/{request_id}",
    response_model=ProcurementRequestRead,
    tags=["procurement"],
)
def get_procurement_request(
    request_id: int,
    request: Request,
    user: UserProfile = Depends(require_permissions("read_procurement")),
) -> ProcurementRequestRead:
    try:
        result = _procurement_engine(request).get_request(request_id)
    except ValueError as exc:
        raise _value_error_to_http(exc)
    _ensure_company_scope(request, user, result.company)
    return result


@router.post(
    "/api/v1/procurement/requests/from-tender",
    response_model=ProcurementTenderPlanResponse,
    status_code=201,
    tags=["procurement"],
)
def create_procurement_from_tender(
    payload: ProcurementTenderPlanRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("write_procurement", "prepare_tender_docs")),
) -> ProcurementTenderPlanResponse:
    _ensure_company_scope(request, user, payload.tender.company_name)
    try:
        return _procurement_engine(request).create_request_from_tender(payload)
    except ValueError as exc:
        raise _value_error_to_http(exc)


@router.post(
    "/api/v1/procurement/quotes",
    response_model=ProcurementVendorQuoteRead,
    status_code=201,
    tags=["procurement"],
)
def create_procurement_quote(
    payload: ProcurementVendorQuoteCreateRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("write_procurement")),
) -> ProcurementVendorQuoteRead:
    try:
        target_request = _procurement_engine(request).get_request(payload.request_id)
    except ValueError as exc:
        raise _value_error_to_http(exc)
    _ensure_company_scope(request, user, target_request.company)

    try:
        return _procurement_engine(request).submit_quote(payload)
    except ValueError as exc:
        raise _value_error_to_http(exc)


@router.get(
    "/api/v1/procurement/requests/{request_id}/quotes",
    response_model=ProcurementVendorQuoteListResponse,
    tags=["procurement"],
)
def list_procurement_quotes(
    request_id: int,
    request: Request,
    user: UserProfile = Depends(require_permissions("read_procurement")),
) -> ProcurementVendorQuoteListResponse:
    try:
        target_request = _procurement_engine(request).get_request(request_id)
        _ensure_company_scope(request, user, target_request.company)
        return _procurement_engine(request).list_quotes(request_id)
    except ValueError as exc:
        raise _value_error_to_http(exc)


@router.get(
    "/api/v1/procurement/requests/{request_id}/evaluation",
    response_model=ProcurementEvaluationResponse,
    tags=["procurement"],
)
def evaluate_procurement_request(
    request_id: int,
    request: Request,
    strategy_override: str | None = Query(default=None),
    user: UserProfile = Depends(require_permissions("read_procurement")),
) -> ProcurementEvaluationResponse:
    try:
        target_request = _procurement_engine(request).get_request(request_id)
        _ensure_company_scope(request, user, target_request.company)
        return _procurement_engine(request).evaluate_request(
            request_id=request_id,
            strategy_override=strategy_override,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc)


@router.post(
    "/api/v1/procurement/requests/{request_id}/purchase-orders/auto",
    response_model=ProcurementPurchaseOrderBatchResponse,
    tags=["procurement"],
)
def auto_create_purchase_orders(
    request_id: int,
    payload: ProcurementAutoOrderRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("approve_procurement")),
) -> ProcurementPurchaseOrderBatchResponse:
    try:
        target_request = _procurement_engine(request).get_request(request_id)
        _ensure_company_scope(request, user, target_request.company)
        return _procurement_engine(request).create_auto_purchase_orders(request_id, payload)
    except ValueError as exc:
        raise _value_error_to_http(exc)


@router.get(
    "/api/v1/procurement/requests/{request_id}/purchase-orders",
    response_model=ProcurementPurchaseOrderBatchResponse,
    tags=["procurement"],
)
def list_procurement_purchase_orders(
    request_id: int,
    request: Request,
    user: UserProfile = Depends(require_permissions("read_procurement")),
) -> ProcurementPurchaseOrderBatchResponse:
    try:
        target_request = _procurement_engine(request).get_request(request_id)
        _ensure_company_scope(request, user, target_request.company)
        return _procurement_engine(request).list_purchase_orders(request_id)
    except ValueError as exc:
        raise _value_error_to_http(exc)


@router.post(
    "/api/v1/feasibility/report",
    response_model=FeasibilityReportStoredResponse,
    status_code=201,
    tags=["feasibility"],
)
def generate_feasibility_report(
    payload: FeasibilityReportRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("write_feasibility")),
) -> FeasibilityReportStoredResponse:
    if payload.company_name:
        _ensure_company_scope(request, user, payload.company_name)
    elif not _is_holding_scope(request, user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scoped users must provide company_name in feasibility report request",
        )
    try:
        return _feasibility_engine(request).generate(payload)
    except ValueError as exc:
        raise _value_error_to_http(exc)


@router.get(
    "/api/v1/feasibility/reports",
    response_model=FeasibilityReportListResponse,
    tags=["feasibility"],
)
def list_feasibility_reports(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    sector: str | None = Query(default=None),
    company: str | None = Query(default=None),
    user: UserProfile = Depends(require_permissions("read_feasibility")),
) -> FeasibilityReportListResponse:
    if company:
        _ensure_company_scope(request, user, company)
        return _feasibility_engine(request).list_reports(limit=limit, sector=sector, company_name=company)
    if not _is_holding_scope(request, user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scoped users must provide company parameter",
        )
    return _feasibility_engine(request).list_reports(limit=limit, sector=sector)


@router.get(
    "/api/v1/feasibility/reports/{report_id}",
    response_model=FeasibilityReportStoredResponse,
    tags=["feasibility"],
)
def get_feasibility_report(
    report_id: int,
    request: Request,
    user: UserProfile = Depends(require_permissions("read_feasibility")),
) -> FeasibilityReportStoredResponse:
    try:
        result = _feasibility_engine(request).get_report(report_id)
    except ValueError as exc:
        raise _value_error_to_http(exc)
    if result.company_name:
        _ensure_company_scope(request, user, result.company_name)
    elif not _is_holding_scope(request, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Scoped users cannot access unscoped feasibility reports",
        )
    return result


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
        raise _value_error_to_http(exc)


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
        raise _value_error_to_http(exc)


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
        raise _value_error_to_http(exc)
    _ensure_company_scope(request, user, result.company_name)
    return result


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
        raise _value_error_to_http(exc)


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
        raise _value_error_to_http(exc)


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
        raise _value_error_to_http(exc)
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
        return _holding_engine(request).get_holding_detail(holding_id=holding_id, limit=limit)
    except ValueError as exc:
        raise _value_error_to_http(exc)


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
        return _holding_engine(request).onboard_companies(holding_id=holding_id, payload=payload)
    except ValueError as exc:
        raise _value_error_to_http(exc)
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
        raise _value_error_to_http(exc)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Holding already exists",
        ) from exc


@router.post(
    "/api/v1/connectors",
    response_model=ConnectorRead,
    status_code=201,
    tags=["connector"],
)
def create_connector(
    payload: ConnectorCreateRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_connectors")),
) -> ConnectorRead:
    _ensure_company_scope(request, user, payload.company_name)
    try:
        return _connector_engine(request).create_connector(
            payload,
            created_by=user.username,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Connector already exists",
        ) from exc


@router.get(
    "/api/v1/connectors",
    response_model=ConnectorListResponse,
    tags=["connector"],
)
def list_connectors(
    request: Request,
    company: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=200, ge=1, le=1000),
    user: UserProfile = Depends(require_permissions("read_connectors")),
) -> ConnectorListResponse:
    if company:
        _ensure_company_scope(request, user, company)
    result = _connector_engine(request).list_connectors(
        company_name=company,
        status=status_filter,
        limit=limit,
    )
    if company or _is_holding_scope(request, user):
        return result

    filtered = [
        item
        for item in result.items
        if _user_has_company_scope(request, user, item.company_name)
    ]
    return ConnectorListResponse(total=len(filtered), items=filtered)


@router.get(
    "/api/v1/connectors/{connector_id}",
    response_model=ConnectorRead,
    tags=["connector"],
)
def get_connector(
    connector_id: int,
    request: Request,
    user: UserProfile = Depends(require_permissions("read_connectors")),
) -> ConnectorRead:
    try:
        result = _connector_engine(request).get_connector(connector_id)
    except ValueError as exc:
        raise _value_error_to_http(exc)
    _ensure_company_scope(request, user, result.company_name)
    return result


@router.post(
    "/api/v1/connectors/canonical/preview",
    response_model=ConnectorCanonicalPreviewResponse,
    tags=["connector"],
)
def preview_connector_canonical_mapping(
    payload: ConnectorCanonicalPreviewRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("read_connectors")),
) -> ConnectorCanonicalPreviewResponse:
    del user
    return _connector_engine(request).preview_canonical_mapping(payload)


@router.post(
    "/api/v1/connectors/{connector_id}/sync-jobs",
    response_model=ConnectorSyncJobRead,
    status_code=201,
    tags=["connector"],
)
def create_connector_sync_job(
    connector_id: int,
    payload: ConnectorSyncJobCreateRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_connectors")),
) -> ConnectorSyncJobRead:
    try:
        connector = _connector_engine(request).get_connector(connector_id)
    except ValueError as exc:
        raise _value_error_to_http(exc)
    _ensure_company_scope(request, user, connector.company_name)
    try:
        return _connector_engine(request).create_sync_job(
            connector_id,
            payload,
            requested_by=user.username,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc)


@router.get(
    "/api/v1/connectors/{connector_id}/sync-jobs",
    response_model=ConnectorSyncJobListResponse,
    tags=["connector"],
)
def list_connector_sync_jobs(
    connector_id: int,
    request: Request,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=200, ge=1, le=2000),
    user: UserProfile = Depends(require_permissions("read_connectors")),
) -> ConnectorSyncJobListResponse:
    try:
        connector = _connector_engine(request).get_connector(connector_id)
    except ValueError as exc:
        raise _value_error_to_http(exc)
    _ensure_company_scope(request, user, connector.company_name)
    return _connector_engine(request).list_sync_jobs(
        connector_id=connector_id,
        status=status_filter,
        limit=limit,
    )


@router.get(
    "/api/v1/connectors/sync-jobs",
    response_model=ConnectorSyncJobListResponse,
    tags=["connector"],
)
def list_sync_jobs(
    request: Request,
    connector_id: int | None = Query(default=None),
    company: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=200, ge=1, le=2000),
    user: UserProfile = Depends(require_permissions("read_connectors")),
) -> ConnectorSyncJobListResponse:
    if company:
        _ensure_company_scope(request, user, company)
    if connector_id is not None:
        try:
            connector = _connector_engine(request).get_connector(connector_id)
        except ValueError as exc:
            raise _value_error_to_http(exc)
        _ensure_company_scope(request, user, connector.company_name)
        company = connector.company_name

    result = _connector_engine(request).list_sync_jobs(
        connector_id=connector_id,
        company_name=company,
        status=status_filter,
        limit=limit,
    )
    if company or _is_holding_scope(request, user):
        return result
    filtered = [
        item
        for item in result.items
        if _user_has_company_scope(request, user, item.company_name)
    ]
    return ConnectorSyncJobListResponse(total=len(filtered), items=filtered)


@router.get(
    "/api/v1/connectors/health/summary",
    response_model=ConnectorQueueHealthResponse,
    tags=["connector"],
)
def connector_health_summary(
    request: Request,
    company: str | None = Query(default=None),
    user: UserProfile = Depends(require_permissions("read_connectors")),
) -> ConnectorQueueHealthResponse:
    if company:
        _ensure_company_scope(request, user, company)
        return _connector_engine(request).build_queue_health(company_name=company)

    if _is_holding_scope(request, user):
        return _connector_engine(request).build_queue_health()

    scoped_companies = sorted({scope for scope in user.company_scopes if scope != "*"})
    if not scoped_companies:
        return _connector_engine(request).build_queue_health(company_name="__no_connector_scope__")

    # Aggregate scoped companies without exposing out-of-scope data.
    aggregate = ConnectorQueueHealthResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        total_connectors=0,
        active_connectors=0,
        staged_connectors=0,
        blocked_connectors=0,
        queued_jobs=0,
        running_jobs=0,
        success_jobs=0,
        failed_jobs=0,
        dead_letter_jobs=0,
        due_retry_jobs=0,
        average_readiness_score=0.0,
        average_security_score=0.0,
    )
    readiness_weighted = 0.0
    security_weighted = 0.0
    for company_name in scoped_companies:
        item = _connector_engine(request).build_queue_health(company_name=company_name)
        aggregate.total_connectors += item.total_connectors
        aggregate.active_connectors += item.active_connectors
        aggregate.staged_connectors += item.staged_connectors
        aggregate.blocked_connectors += item.blocked_connectors
        aggregate.queued_jobs += item.queued_jobs
        aggregate.running_jobs += item.running_jobs
        aggregate.success_jobs += item.success_jobs
        aggregate.failed_jobs += item.failed_jobs
        aggregate.dead_letter_jobs += item.dead_letter_jobs
        aggregate.due_retry_jobs += item.due_retry_jobs
        readiness_weighted += item.average_readiness_score * item.total_connectors
        security_weighted += item.average_security_score * item.total_connectors

    if aggregate.total_connectors > 0:
        aggregate.average_readiness_score = round(readiness_weighted / aggregate.total_connectors, 2)
        aggregate.average_security_score = round(security_weighted / aggregate.total_connectors, 2)
    return aggregate


@router.post(
    "/api/v1/connectors/sync-jobs/dispatch",
    response_model=ConnectorSyncDispatchResponse,
    tags=["connector"],
)
def dispatch_sync_job(
    payload: ConnectorSyncDispatchRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_connectors")),
) -> ConnectorSyncDispatchResponse:
    allowed_company_names: list[str] | None = None
    if payload.company_name:
        _ensure_company_scope(request, user, payload.company_name)
        allowed_company_names = [payload.company_name]
    elif not _is_holding_scope(request, user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scoped users must provide company_name for dispatch",
        )

    return _connector_engine(request).dispatch_next_sync_job(
        payload,
        requested_by=user.username,
        allowed_company_names=allowed_company_names,
    )


@router.get(
    "/api/v1/market/sources",
    response_model=MarketSourceCatalogResponse,
    tags=["market"],
)
def market_sources(
    request: Request,
    regions: str = Query(default="TR,EU,GLOBAL"),
    limit: int = Query(default=20, ge=1, le=50),
    user: UserProfile = Depends(require_permissions("read_market")),
) -> MarketSourceCatalogResponse:
    del user
    return _market_intelligence_engine(request).list_sources(
        regions=_parse_symbols_csv(regions),
        limit=limit,
    )


@router.get(
    "/api/v1/market/backtest",
    response_model=MarketBacktestResponse,
    tags=["market"],
)
def market_backtest(
    request: Request,
    symbol: str = Query(default="AAPL", min_length=1),
    timeframe: str = Query(default="1d"),
    days: int = Query(default=360, ge=80, le=3650),
    lookahead_days: int = Query(default=5, ge=1, le=30),
    hold_band: float = Query(default=0.01, ge=0, le=0.2),
    refresh: bool = Query(default=False),
    user: UserProfile = Depends(require_permissions("read_market")),
) -> MarketBacktestResponse:
    del user
    try:
        return _market_engine(request).backtest_signal_strategy(
            symbol=symbol,
            timeframe=timeframe,
            days=days,
            lookahead_days=lookahead_days,
            hold_band=hold_band,
            refresh=refresh,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc)


@router.post(
    "/api/v1/tender/generate",
    response_model=TenderDossierResponse,
    tags=["tender"],
)
def generate_tender_dossier(
    payload: TenderGenerationRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("prepare_tender_docs")),
) -> TenderDossierResponse:
    _ensure_company_scope(request, user, payload.company_name)
    return _tender_engine(request).build_dossier(payload)


@router.get("/analyze_all", response_model=list[LegacyAnalysisResult], tags=["legacy"])
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


@router.get("/api/v1/analysis", response_model=list[AnalysisResult], tags=["analysis"])
def analyze_all(request: Request) -> list[AnalysisResult]:
    companies = _repo(request).list_companies()
    return _analysis_service(request).analyze_all(companies)


@router.get("/api/v1/summary", response_model=DashboardSummary, tags=["dashboard"])
def summary(request: Request) -> DashboardSummary:
    snapshot = _build_dashboard_data(request)
    return snapshot.summary


@router.get("/api/v1/insights", response_model=list[InsightItem], tags=["dashboard"])
def insights(request: Request) -> list[InsightItem]:
    snapshot = _build_dashboard_data(request)
    return snapshot.insights


@router.get(
    "/api/v1/dashboard-data",
    response_model=DashboardDataResponse,
    tags=["dashboard"],
)
def dashboard_data(request: Request) -> DashboardDataResponse:
    return _build_dashboard_data(request)


@router.get("/auto_update", response_model=LegacyUpdateResult, tags=["legacy"])
def auto_update_legacy(
    request: Request,
    user: UserProfile = Depends(require_permissions("run_simulation")),
) -> LegacyUpdateResult:
    del user
    _repo(request).update_random()
    return LegacyUpdateResult(message="Sistem guncellendi")


@router.post("/api/v1/simulate", response_model=UpdateResult, tags=["simulation"])
def simulate_update(
    request: Request,
    user: UserProfile = Depends(require_permissions("run_simulation")),
) -> UpdateResult:
    del user
    companies = _repo(request).update_random()
    return UpdateResult(message="Simulation completed", companies=companies)


@router.get("/api/v1/health", response_model=HealthResponse, tags=["system"])
def health(request: Request) -> HealthResponse:
    settings = request.app.state.settings
    return HealthResponse(
        status="ok",
        environment=settings.environment,
        company_count=_repo(request).company_count(),
        version=settings.app_version,
    )


def _value_error_to_http(exc: ValueError) -> HTTPException:
    text = str(exc)
    if "not found" in text.lower():
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=text)
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=text)


def _to_role_read(row: dict) -> RoleRead:
    return RoleRead(
        id=int(row["id"]),
        name=str(row["name"]),
        description=str(row.get("description") or ""),
        created_at=int(row["created_at"]),
        updated_at=int(row["updated_at"]),
    )


def _to_user_read(row: dict, *, company_scopes: list[str] | None = None) -> UserRead:
    role = row.get("role_name", row.get("role"))
    scopes = company_scopes or ["*"]
    scope_mode = _scope_mode_from_scopes(scopes)
    return UserRead(
        id=int(row["id"]),
        username=str(row["username"]),
        role=str(role),
        is_active=bool(int(row["is_active"])),
        created_at=int(row["created_at"]),
        updated_at=int(row["updated_at"]),
        company_scopes=scopes,
        scope_mode=scope_mode,
    )


def _to_permission_read(row: dict) -> PermissionRead:
    return PermissionRead(
        id=int(row["id"]),
        name=str(row["name"]),
        description=str(row.get("description") or ""),
        created_at=int(row["created_at"]),
        updated_at=int(row["updated_at"]),
    )


def _parse_symbols_csv(raw: str) -> list[str]:
    symbols: list[str] = []
    seen: set[str] = set()
    for item in raw.split(","):
        normalized = item.strip().upper()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        symbols.append(normalized)
    return symbols


def _scope_mode_from_scopes(scopes: list[str]) -> str:
    if "*" in scopes:
        return "holding"
    if len(scopes) <= 1:
        return "single"
    return "multi"


def _is_holding_scope(request: Request, user: UserProfile) -> bool:
    return _auth_service(request).is_holding_scope(user.id)


def _user_has_company_scope(request: Request, user: UserProfile, company_name: str) -> bool:
    return _auth_service(request).user_has_company_scope(user.id, company_name)


def _ensure_company_scope(request: Request, user: UserProfile, company_name: str) -> None:
    if _user_has_company_scope(request, user, company_name):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"User scope does not allow company: {company_name}",
    )


def _filter_companies_by_user_scope(
    request: Request,
    user: UserProfile,
    companies: list[Company],
) -> list[Company]:
    if _is_holding_scope(request, user):
        return companies
    return [
        company
        for company in companies
        if _user_has_company_scope(request, user, company.name)
    ]


def _build_dashboard_data(request: Request) -> DashboardDataResponse:
    companies = _repo(request).list_companies()
    analyses = _analysis_service(request).analyze_all(companies)
    summary = _dashboard_service(request).build_summary(companies, analyses)
    insights = _dashboard_service(request).build_insights(analyses)

    return DashboardDataResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        summary=summary,
        companies=companies,
        analyses=analyses,
        insights=insights,
    )


@router.get("/dashboard", response_class=HTMLResponse, tags=["dashboard"])
def dashboard_ui(request: Request) -> HTMLResponse:
    snapshot = _build_dashboard_data(request)
    analysis_map = {analysis.company: analysis for analysis in snapshot.analyses}
    market_symbols = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "BTCUSD"]
    html = _render_dashboard(
        companies=snapshot.companies,
        analysis_map=analysis_map,
        summary=snapshot.summary,
        insights=snapshot.insights,
        market_symbols=market_symbols,
    )
    return HTMLResponse(content=html)


def _render_dashboard(
    companies: list[Company],
    analysis_map: dict[str, AnalysisResult],
    summary: DashboardSummary,
    insights: list[InsightItem],
    market_symbols: list[str],
) -> str:
    card_html = "".join(_render_company_card(company, analysis_map[company.name]) for company in companies)
    insight_html = "".join(_render_insight_item(item) for item in insights)
    market_options = "".join(
        f'<option value="{escape(symbol)}">{escape(symbol)}</option>'
        for symbol in market_symbols
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Alpha Quantum Dashboard</title>
  <style>
    :root {{
      --bg: #081426;
      --panel: #102a43;
      --panel-alt: #1f3f63;
      --accent: #2cb1bc;
      --ok: #7bd88f;
      --critical: #ff6b6b;
      --text: #f0f4f8;
      --muted: #b0beca;
      --border: rgba(255, 255, 255, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "Arial", sans-serif;
      color: var(--text);
      background: radial-gradient(circle at 20% 10%, #163d5f 0%, var(--bg) 55%);
      min-height: 100vh;
    }}
    .container {{
      width: min(1180px, 94vw);
      margin: 2rem auto 3rem;
    }}
    .header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 1rem;
      flex-wrap: wrap;
      margin-bottom: 1.5rem;
    }}
    .title {{
      margin: 0;
      font-size: clamp(1.6rem, 3vw, 2.2rem);
      letter-spacing: 0.4px;
    }}
    .muted {{
      color: var(--muted);
      margin-top: 0.2rem;
      font-size: 0.92rem;
    }}
    .actions {{
      display: flex;
      gap: 0.6rem;
      flex-wrap: wrap;
    }}
    button, .link-btn, select {{
      border: none;
      border-radius: 10px;
      padding: 0.65rem 1rem;
      cursor: pointer;
      background: var(--accent);
      color: #06202a;
      font-weight: 700;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      transition: transform 0.15s ease, opacity 0.15s ease;
    }}
    select {{
      background: #e6f7f9;
      min-width: 130px;
    }}
    button:hover, .link-btn:hover {{
      transform: translateY(-1px);
      opacity: 0.92;
    }}
    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 0.75rem;
      margin-bottom: 1rem;
    }}
    .summary-card {{
      background: linear-gradient(145deg, var(--panel), var(--panel-alt));
      border-radius: 12px;
      border: 1px solid var(--border);
      padding: 0.9rem 1rem;
      box-shadow: 0 8px 18px rgba(1, 13, 28, 0.3);
    }}
    .summary-label {{
      color: var(--muted);
      font-size: 0.82rem;
    }}
    .summary-value {{
      margin-top: 0.2rem;
      font-size: 1.25rem;
      font-weight: 700;
    }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 0.85rem;
    }}
    .card {{
      background: linear-gradient(160deg, #0f2c45, #12314d);
      border-radius: 14px;
      border: 1px solid rgba(255, 255, 255, 0.06);
      padding: 1rem;
    }}
    .card h3 {{
      margin: 0 0 0.7rem;
      font-size: 1.05rem;
    }}
    .line {{
      display: flex;
      justify-content: space-between;
      gap: 1rem;
      margin-bottom: 0.35rem;
      font-size: 0.94rem;
    }}
    .inventory {{
      margin-top: 0.75rem;
      margin-bottom: 0;
      padding-left: 1.1rem;
    }}
    .inventory li {{
      margin-bottom: 0.3rem;
    }}
    .market-grid {{
      display: grid;
      grid-template-columns: 1.55fr 1fr;
      gap: 0.85rem;
      margin-top: 1rem;
    }}
    .market-toolbar {{
      display: flex;
      gap: 0.5rem;
      align-items: center;
      flex-wrap: wrap;
      margin-top: 0.65rem;
      margin-bottom: 0.5rem;
    }}
    #market-chart {{
      width: 100%;
      height: 240px;
      border-radius: 10px;
      background: linear-gradient(180deg, rgba(26, 65, 98, 0.5), rgba(8, 20, 38, 0.3));
      border: 1px solid var(--border);
    }}
    .market-signals {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 0.45rem;
      margin-top: 0.65rem;
      max-height: 260px;
      overflow: auto;
    }}
    .signal-card {{
      border-radius: 10px;
      border: 1px solid var(--border);
      padding: 0.55rem 0.65rem;
      background: rgba(9, 27, 41, 0.55);
    }}
    .signal-card .row {{
      display: flex;
      justify-content: space-between;
      gap: 0.5rem;
      font-size: 0.9rem;
    }}
    .signal-buy {{ border-left: 4px solid var(--ok); }}
    .signal-sell {{ border-left: 4px solid var(--critical); }}
    .signal-hold {{ border-left: 4px solid #f9d65b; }}
    .report-summary {{
      margin-top: 0.65rem;
      color: var(--text);
      font-size: 0.92rem;
    }}
    .tag {{
      display: inline-block;
      margin-right: 0.4rem;
      margin-top: 0.25rem;
      padding: 0.2rem 0.48rem;
      border-radius: 999px;
      font-size: 0.74rem;
      background: rgba(44, 177, 188, 0.16);
      border: 1px solid rgba(44, 177, 188, 0.35);
      color: #d5f4f7;
    }}
    .region-set {{
      display: flex;
      gap: 0.45rem;
      flex-wrap: wrap;
      align-items: center;
    }}
    .region-pill {{
      display: inline-flex;
      align-items: center;
      gap: 0.35rem;
      border: 1px solid var(--border);
      background: rgba(5, 18, 33, 0.6);
      padding: 0.28rem 0.52rem;
      border-radius: 999px;
      font-size: 0.78rem;
      color: var(--text);
    }}
    .region-pill input {{
      margin: 0;
    }}
    #global-report {{
      margin-top: 0.75rem;
      padding: 0.75rem;
      border-radius: 10px;
      border: 1px solid var(--border);
      background: rgba(3, 11, 25, 0.62);
      color: #dce7f1;
      max-height: 260px;
      overflow: auto;
      font-size: 0.8rem;
      line-height: 1.45;
      white-space: pre-wrap;
    }}
    .critical {{ color: var(--critical); }}
    .ok {{ color: var(--ok); }}
    @media (max-width: 920px) {{
      .market-grid {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div>
        <h1 class="title">Alpha Quantum Dashboard</h1>
        <div class="muted">Professional control panel for ERP + Finance + AI operations</div>
      </div>
      <div class="actions">
        <button id="simulate-btn" onclick="simulateAndReload()">Veri Guncelle</button>
        <button id="market-refresh-btn" onclick="refreshMarketWidgets()">Market Yenile</button>
        <a class="link-btn" href="/api/v1/analysis" target="_blank" rel="noreferrer">Analiz JSON</a>
        <a class="link-btn" href="/api/v1/market/sources?regions=TR,EU,GLOBAL" target="_blank" rel="noreferrer">Market Sources</a>
      </div>
    </div>

    <section class="summary-grid">
      <article class="summary-card">
        <div class="summary-label">Sirket Sayisi</div>
        <div class="summary-value">{summary.total_companies}</div>
      </article>
      <article class="summary-card">
        <div class="summary-label">Toplam Bakiye</div>
        <div class="summary-value">{summary.total_balance:,.0f}</div>
      </article>
      <article class="summary-card">
        <div class="summary-label">Kritik Stok Kalemi</div>
        <div class="summary-value">{summary.critical_items}</div>
      </article>
      <article class="summary-card">
        <div class="summary-label">Riskli Sirket</div>
        <div class="summary-value">{summary.risk_companies}</div>
      </article>
    </section>

    <section class="cards">
      {card_html}
    </section>

    <section class="market-grid">
      <article class="summary-card">
        <div class="summary-label">Live Market Chart (OHLCV)</div>
        <div class="market-toolbar">
          <select id="market-symbol">
            {market_options}
          </select>
          <button onclick="loadMarketChart(true)">Grafik Yenile</button>
        </div>
        <svg id="market-chart" viewBox="0 0 900 260" preserveAspectRatio="none"></svg>
        <div id="market-meta" class="muted">Yukleniyor...</div>
        <div id="backtest-meta" class="muted"></div>
      </article>

      <article class="summary-card">
        <div class="summary-label">AI Market Signal Cards</div>
        <div id="market-signals" class="market-signals">
          <div class="muted">Yukleniyor...</div>
        </div>
      </article>
    </section>

    <section style="margin-top: 1rem;">
      <article class="summary-card">
        <div class="summary-label">Market Intelligence (TR + EU + Global Borsalar)</div>
        <div class="market-toolbar">
          <div class="region-set">
            <label class="region-pill"><input type="checkbox" class="intel-region" value="TR" checked />TR</label>
            <label class="region-pill"><input type="checkbox" class="intel-region" value="EU" checked />EU</label>
            <label class="region-pill"><input type="checkbox" class="intel-region" value="GLOBAL" checked />GLOBAL</label>
          </div>
          <button onclick="loadMarketIntelligence(true)">Intelligence Yenile</button>
        </div>
        <div id="intel-summary" class="report-summary">Yukleniyor...</div>
        <div id="intel-pages" class="muted"></div>
        <div id="intel-cards" class="market-signals">
          <div class="muted">Yukleniyor...</div>
        </div>
      </article>
    </section>

    <section style="margin-top: 1rem;">
      <article class="summary-card">
        <div class="summary-label">Connector Sync Health (Queue + DLQ)</div>
        <div id="connector-health" class="report-summary">Yukleniyor...</div>
        <div class="market-toolbar">
          <button onclick="loadConnectorHealth()">Health Yenile</button>
          <button onclick="dispatchConnectorQueue()">Queue'dan 1 Islem</button>
        </div>
        <div id="connector-jobs" class="market-signals">
          <div class="muted">Yukleniyor...</div>
        </div>
      </article>
    </section>

    <section style="margin-top: 1rem;">
      <article class="summary-card">
        <div class="summary-label">Global Intelligence Report</div>
        <div id="global-summary" class="report-summary">Yukleniyor...</div>
        <pre id="global-report">Global rapor bekleniyor...</pre>
      </article>
    </section>

    <section style="margin-top: 1rem;">
      <article class="summary-card">
        <div class="summary-label">AI Insight Feed</div>
        <ul style="margin: 0.75rem 0 0; padding-left: 1rem;">
          {insight_html}
        </ul>
        <div id="live-info" class="muted" style="margin-top: 0.7rem;">
          Market veri yenileme acik (30 saniye)
        </div>
      </article>
    </section>
  </div>

  <script>
    function authHeaders() {{
      const token = window.localStorage.getItem("aq_token");
      if (!token) {{
        return {{}};
      }}
      return {{ Authorization: `Bearer ${{token}}` }};
    }}

    function escapeHtml(value) {{
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;");
    }}

    async function simulateAndReload() {{
      const button = document.getElementById("simulate-btn");
      button.disabled = true;
      button.textContent = "Guncelleniyor...";
      try {{
        const response = await fetch("/api/v1/simulate", {{
          method: "POST",
          headers: authHeaders(),
        }});
        if (response.status === 401 || response.status === 403) {{
          alert("Auth gerekli. /api/v1/auth/login ile token alip localStorage.aq_token set edin.");
          return;
        }}
        if (!response.ok) {{
          alert("Simulation failed");
          return;
        }}
        window.location.reload();
      }} finally {{
        button.disabled = false;
        button.textContent = "Veri Guncelle";
      }}
    }}

    function renderChart(bars) {{
      const svg = document.getElementById("market-chart");
      if (!bars || bars.length < 2) {{
        svg.innerHTML = `<text x="16" y="28" fill="#b0beca">Yeterli market veri yok.</text>`;
        return;
      }}

      const closes = bars.map((item) => Number(item.close));
      const min = Math.min(...closes);
      const max = Math.max(...closes);
      const width = 900;
      const height = 260;
      const left = 35;
      const right = 15;
      const top = 14;
      const bottom = 24;
      const innerW = width - left - right;
      const innerH = height - top - bottom;
      const range = Math.max(max - min, 0.00001);
      const points = closes.map((value, idx) => {{
        const x = left + (idx / (closes.length - 1)) * innerW;
        const y = top + (1 - ((value - min) / range)) * innerH;
        return `${{x.toFixed(2)}},${{y.toFixed(2)}}`;
      }}).join(" ");

      svg.innerHTML = `
        <line x1="${{left}}" y1="${{top}}" x2="${{left}}" y2="${{height - bottom}}" stroke="rgba(176,190,202,0.35)" stroke-width="1" />
        <line x1="${{left}}" y1="${{height - bottom}}" x2="${{width - right}}" y2="${{height - bottom}}" stroke="rgba(176,190,202,0.35)" stroke-width="1" />
        <polyline points="${{points}}" fill="none" stroke="#2cb1bc" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round" />
        <text x="${{left + 4}}" y="${{top + 11}}" fill="#b0beca" font-size="11">${{max.toFixed(2)}}</text>
        <text x="${{left + 4}}" y="${{height - bottom - 4}}" fill="#b0beca" font-size="11">${{min.toFixed(2)}}</text>
      `;
    }}

    async function loadMarketChart(forceRefresh) {{
      const symbol = document.getElementById("market-symbol").value;
      const meta = document.getElementById("market-meta");
      const backtestMeta = document.getElementById("backtest-meta");
      const refresh = forceRefresh ? "true" : "false";
      const response = await fetch(`/api/v1/market/ohlcv?symbol=${{encodeURIComponent(symbol)}}&days=220&refresh=${{refresh}}`, {{
        headers: authHeaders(),
      }});

      if (response.status === 401 || response.status === 403) {{
        meta.textContent = "Market grafikleri icin aq_token gerekli (read_market).";
        backtestMeta.textContent = "";
        renderChart([]);
        return;
      }}
      if (!response.ok) {{
        meta.textContent = "Market grafikleri yuklenemedi.";
        backtestMeta.textContent = "";
        renderChart([]);
        return;
      }}

      const payload = await response.json();
      renderChart(payload.bars || []);
      const last = payload.bars && payload.bars.length ? payload.bars[payload.bars.length - 1] : null;
      meta.textContent = `Symbol: ${{payload.symbol}} | Source: ${{payload.source}} | Last: ${{last ? Number(last.close).toFixed(2) : "-"}}`;
      backtestMeta.textContent = "Backtest yukleniyor...";
      await loadBacktest(symbol, forceRefresh);
    }}

    async function loadBacktest(symbol, forceRefresh) {{
      const target = document.getElementById("backtest-meta");
      const refresh = forceRefresh ? "true" : "false";
      const response = await fetch(
        `/api/v1/market/backtest?symbol=${{encodeURIComponent(symbol)}}&days=540&lookahead_days=5&hold_band=0.012&refresh=${{refresh}}`,
        {{
          headers: authHeaders(),
        }},
      );
      if (!response.ok) {{
        target.textContent = "Backtest bilgisi yuklenemedi.";
        return;
      }}
      const payload = await response.json();
      target.textContent = `Backtest(win=${{(Number(payload.win_rate) * 100).toFixed(1)}}%, edge=${{(Number(payload.strategy_edge) * 100).toFixed(2)}}%, maxDD=${{(Number(payload.max_drawdown) * 100).toFixed(1)}}%)`;
    }}

    function renderSignalCards(items) {{
      const container = document.getElementById("market-signals");
      if (!items || !items.length) {{
        container.innerHTML = `<div class="muted">Signal bulunamadi.</div>`;
        return;
      }}

      container.innerHTML = items.map((item) => {{
        const cls = item.signal === "BUY" ? "signal-buy" : (item.signal === "SELL" ? "signal-sell" : "signal-hold");
        return `
          <article class="signal-card ${{cls}}">
            <div class="row"><strong>${{escapeHtml(item.symbol)}}</strong><strong>${{escapeHtml(item.signal)}}</strong></div>
            <div class="row"><span>Trend: ${{escapeHtml(item.trend)}}</span><span>Conf: ${{Number(item.confidence).toFixed(2)}}</span></div>
            <div class="row"><span>RSI14: ${{item.rsi_14 === null ? "-" : Number(item.rsi_14).toFixed(2)}}</span><span>MACD Hist: ${{item.macd_histogram === null ? "-" : Number(item.macd_histogram).toFixed(4)}}</span></div>
            <div class="row"><span>Fiyat: ${{item.last_close === null ? "-" : Number(item.last_close).toFixed(2)}}</span><span>${{escapeHtml(item.rationale)}}</span></div>
          </article>
        `;
      }}).join("");
    }}

    async function loadMarketSignals(forceRefresh) {{
      const refresh = forceRefresh ? "true" : "false";
      const symbols = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "BTCUSD"];
      const query = encodeURIComponent(symbols.join(","));
      const response = await fetch(`/api/v1/market/signals?symbols=${{query}}&days=220&refresh=${{refresh}}`, {{
        headers: authHeaders(),
      }});

      if (response.status === 401 || response.status === 403) {{
        document.getElementById("market-signals").innerHTML = `<div class="muted">Signal kartlari icin aq_token gerekli.</div>`;
        return;
      }}
      if (!response.ok) {{
        document.getElementById("market-signals").innerHTML = `<div class="muted">Signal kartlari yuklenemedi.</div>`;
        return;
      }}

      const payload = await response.json();
      renderSignalCards(payload.items || []);
    }}

    function selectedIntelRegions() {{
      const nodes = Array.from(document.querySelectorAll(".intel-region:checked"));
      return nodes.map((node) => node.value);
    }}

    function renderIntelCards(items) {{
      const container = document.getElementById("intel-cards");
      if (!items || !items.length) {{
        container.innerHTML = `<div class="muted">Oneri bulunamadi.</div>`;
        return;
      }}
      container.innerHTML = items.slice(0, 12).map((item) => {{
        const cls = item.signal === "BUY" ? "signal-buy" : (item.signal === "SELL" ? "signal-sell" : "signal-hold");
        return `
          <article class="signal-card ${{cls}}">
            <div class="row"><strong>${{escapeHtml(item.symbol)}}</strong><strong>${{escapeHtml(item.signal)}}</strong></div>
            <div class="row"><span>Risk: ${{escapeHtml(item.risk_level)}}</span><span>Conf: ${{Number(item.confidence).toFixed(2)}}</span></div>
            <div class="row"><span>${{escapeHtml(item.rationale)}}</span><span>${{escapeHtml(item.suggested_action)}}</span></div>
          </article>
        `;
      }}).join("");
    }}

    async function loadMarketIntelligence(forceRefresh) {{
      const summaryNode = document.getElementById("intel-summary");
      const pagesNode = document.getElementById("intel-pages");
      const regions = selectedIntelRegions();
      if (!regions.length) {{
        summaryNode.textContent = "En az bir bolge secin (TR/EU/GLOBAL).";
        pagesNode.textContent = "";
        return;
      }}

      const selectedSymbol = document.getElementById("market-symbol").value;
      const response = await fetch("/api/v1/market/intelligence", {{
        method: "POST",
        headers: {{
          "Content-Type": "application/json",
          ...authHeaders(),
        }},
        body: JSON.stringify({{
          pages: [],
          include_default_exchange_pages: true,
          regions,
          focus_symbols: [selectedSymbol, "AAPL", "MSFT", "NVDA", "XU100.IS", "DAX.DE", "SPX"],
          timeframe: "1d",
          days: 240,
          refresh: !!forceRefresh,
          max_symbols: 10,
          max_pages: 15,
        }}),
      }});

      if (response.status === 401 || response.status === 403) {{
        summaryNode.textContent = "Market intelligence icin aq_token gerekli (read_market + read_public_sources).";
        pagesNode.textContent = "";
        document.getElementById("intel-cards").innerHTML = `<div class="muted">Yetkisiz</div>`;
        return;
      }}

      if (!response.ok) {{
        summaryNode.textContent = "Market intelligence yuklenemedi.";
        pagesNode.textContent = "";
        document.getElementById("intel-cards").innerHTML = `<div class="muted">Hata</div>`;
        return;
      }}

      const payload = await response.json();
      summaryNode.textContent = payload.executive_summary || "";

      const tags = (payload.pages || [])
        .slice(0, 8)
        .map((item) => {{
          const exchange = item.exchange || item.source_domain || "source";
          const region = item.region || "N/A";
          return `<span class="tag">${{escapeHtml(region)}}:${{escapeHtml(exchange)}}</span>`;
        }})
        .join("");
      pagesNode.innerHTML = tags || "<span class=\"muted\">Kaynak etiketi yok.</span>";
      renderIntelCards(payload.recommendations || []);
    }}

    function renderConnectorJobs(items) {{
      const container = document.getElementById("connector-jobs");
      if (!items || !items.length) {{
        container.innerHTML = `<div class="muted">Queue is bulunamadi.</div>`;
        return;
      }}
      container.innerHTML = items.map((item) => {{
        let cls = "signal-hold";
        if (item.status === "success") cls = "signal-buy";
        if (item.status === "failed" || item.status === "dead_letter") cls = "signal-sell";
        const retryInfo = item.next_retry_at ? `next_retry=${{new Date(item.next_retry_at * 1000).toLocaleTimeString()}}` : "-";
        return `
          <article class="signal-card ${{cls}}">
            <div class="row"><strong>#${{item.id}}</strong><strong>${{escapeHtml(item.company_name)}} / ${{escapeHtml(item.status)}}</strong></div>
            <div class="row"><span>${{escapeHtml(item.connector_type)}}:${{escapeHtml(item.provider)}}</span><span>attempt ${{item.attempt_count}}/${{item.max_attempts}}</span></div>
            <div class="row"><span>retry: ${{escapeHtml(retryInfo)}}</span><span>${{item.error_code ? escapeHtml(item.error_code) : "-"}}</span></div>
          </article>
        `;
      }}).join("");
    }}

    async function loadConnectorHealth() {{
      const summaryNode = document.getElementById("connector-health");
      const jobsNode = document.getElementById("connector-jobs");

      const [healthResponse, jobsResponse] = await Promise.all([
        fetch("/api/v1/connectors/health/summary", {{ headers: authHeaders() }}),
        fetch("/api/v1/connectors/sync-jobs?limit=12", {{ headers: authHeaders() }}),
      ]);

      if (healthResponse.status === 401 || healthResponse.status === 403) {{
        summaryNode.textContent = "Connector health icin aq_token gerekli (read_connectors).";
        jobsNode.innerHTML = `<div class="muted">Yetkisiz</div>`;
        return;
      }}
      if (!healthResponse.ok) {{
        summaryNode.textContent = "Connector health yuklenemedi.";
      }} else {{
        const health = await healthResponse.json();
        summaryNode.textContent = `Connectors=${{health.total_connectors}} | active=${{health.active_connectors}} staged=${{health.staged_connectors}} blocked=${{health.blocked_connectors}} | queued=${{health.queued_jobs}} running=${{health.running_jobs}} dead_letter=${{health.dead_letter_jobs}} due_retry=${{health.due_retry_jobs}} | readiness=${{Number(health.average_readiness_score).toFixed(1)}} security=${{Number(health.average_security_score).toFixed(1)}}`;
      }}

      if (jobsResponse.status === 401 || jobsResponse.status === 403) {{
        jobsNode.innerHTML = `<div class="muted">Queue goruntuleme yetkisi yok.</div>`;
        return;
      }}
      if (!jobsResponse.ok) {{
        jobsNode.innerHTML = `<div class="muted">Queue listesi yuklenemedi.</div>`;
        return;
      }}
      const jobsPayload = await jobsResponse.json();
      renderConnectorJobs(jobsPayload.items || []);
    }}

    async function dispatchConnectorQueue() {{
      const response = await fetch("/api/v1/connectors/sync-jobs/dispatch", {{
        method: "POST",
        headers: {{
          "Content-Type": "application/json",
          ...authHeaders(),
        }},
        body: JSON.stringify({{
          auto_complete: true,
          success: true,
          allow_retry: true,
          retry_backoff_seconds: 60,
        }}),
      }});
      if (response.status === 401 || response.status === 403) {{
        alert("Connector dispatch icin aq_token gerekli (manage_connectors).");
        return;
      }}
      await loadConnectorHealth();
    }}

    async function loadGlobalReport() {{
      const summaryNode = document.getElementById("global-summary");
      const reportNode = document.getElementById("global-report");
      const response = await fetch(
        "/api/v1/global/report?countries=USA,TUR,DEU&bank_symbols=JPM,BAC,HSBC,BNP.PA&index_symbols=SPX,NDX,DAX,XU100",
        {{
          headers: authHeaders(),
        }},
      );

      if (response.status === 401 || response.status === 403) {{
        summaryNode.textContent = "Global rapor icin aq_token gerekli (read_global_intel).";
        reportNode.textContent = "Yetkisiz";
        return;
      }}
      if (!response.ok) {{
        summaryNode.textContent = "Global rapor yuklenemedi.";
        reportNode.textContent = "Hata";
        return;
      }}

      const payload = await response.json();
      summaryNode.textContent = `Risk: ${{payload.risk_level}} | ${{payload.executive_summary}}`;
      reportNode.textContent = payload.report_markdown || "";
    }}

    async function refreshMarketWidgets() {{
      const button = document.getElementById("market-refresh-btn");
      button.disabled = true;
      button.textContent = "Yenileniyor...";
      try {{
        await Promise.all([
          loadMarketChart(true),
          loadMarketSignals(true),
          loadMarketIntelligence(true),
          loadConnectorHealth(),
          loadGlobalReport(),
        ]);
      }} finally {{
        button.disabled = false;
        button.textContent = "Market Yenile";
      }}
    }}

    document.getElementById("market-symbol").addEventListener("change", () => {{
      loadMarketChart(false);
    }});

    loadMarketChart(false);
    loadMarketSignals(false);
    loadMarketIntelligence(false);
    loadConnectorHealth();
    loadGlobalReport();
    setInterval(() => {{
      loadMarketChart(false);
      loadMarketSignals(false);
      loadConnectorHealth();
    }}, 30000);
    setInterval(() => {{
      loadMarketIntelligence(false);
      loadGlobalReport();
    }}, 180000);
  </script>
</body>
</html>"""


def _render_company_card(company: Company, analysis: AnalysisResult) -> str:
    inventory_rows = "".join(
        _render_inventory_line(item.name, item.quantity, item.min_level)
        for item in company.inventory
    )
    status_class = "critical" if analysis.status == "Riskli" else "ok"

    return f"""
      <article class="card">
        <h3>{escape(company.name)}</h3>
        <div class="line"><span>Bakiye</span><strong>{company.balance:,.0f}</strong></div>
        <div class="line"><span>Risk Skoru</span><strong>{analysis.risk_score}/100</strong></div>
        <div class="line"><span>Durum</span><strong class="{status_class}">{escape(analysis.status)}</strong></div>
        <div class="line"><span>Trend</span><strong>{escape(analysis.trend)}</strong></div>
        <div class="line"><span>Oncelikli Aksiyon</span><strong>{escape(analysis.action)}</strong></div>
        <ul class="inventory">
          {inventory_rows}
        </ul>
      </article>
    """


def _render_inventory_line(name: str, quantity: int, min_level: int) -> str:
    is_critical = quantity <= min_level
    css_class = "critical" if is_critical else "ok"
    label = "Kritik" if is_critical else "Normal"
    return (
        f'<li class="{css_class}">{escape(name)}: {label} ({quantity}) '
        f'- Min: {min_level}</li>'
    )


def _render_insight_item(item: InsightItem) -> str:
    severity_class = "critical" if item.severity == "HIGH" else "ok"
    return (
        f'<li style="margin-bottom:0.45rem;">'
        f'<strong class="{severity_class}">{escape(item.severity)}</strong> '
        f'<strong>{escape(item.company)}</strong>: {escape(item.message)} '
        f'| Action: {escape(item.action)} '
        f'| Confidence: {item.confidence:.2f}'
        f"</li>"
    )
