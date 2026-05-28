"""A5.3: Authentication & RBAC router (extracted from app/api.py).

Bu modül 16 endpoint'i taşır:

Auth core (4):
- POST /api/v1/auth/login    → token + refresh
- POST /api/v1/auth/refresh  → access token rotate
- POST /api/v1/auth/logout   → revoke token (+all devices opt)
- GET  /api/v1/auth/me       → current user profile

Roles & permissions (7):
- GET    /api/v1/roles                          → list
- POST   /api/v1/roles                          → create
- PATCH  /api/v1/roles/{role_id}                → update
- DELETE /api/v1/roles/{role_id}                → delete
- GET    /api/v1/permissions                    → list permissions catalog
- GET    /api/v1/roles/{role_id}/permissions    → fetch role's perms
- PUT    /api/v1/roles/{role_id}/permissions    → set role's perms

Users (5):
- GET    /api/v1/users                          → list users
- POST   /api/v1/users                          → create user
- PATCH  /api/v1/users/{user_id}                → update user
- DELETE /api/v1/users/{user_id}                → delete user
- POST   /api/v1/users/{user_id}/password-rotate → password change

Tüm RBAC permission isimleri korundu: manage_roles, manage_users.
Auth rate limiter davranışı + audit event'ları birebir aynı.
"""
from __future__ import annotations

import logging
import sqlite3

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status

from app.models import (
    LoginRequest,
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
    UserCreateRequest,
    UserProfile,
    UserRead,
    UserUpdateRequest,
)
from app.routers._deps import (
    _auth_service,
    _emit_audit_event,
    _scope_mode_from_scopes,
    _settings,
    _value_error_to_http,
)
from app.security import (
    create_access_token,
    get_current_user,
    require_permissions,
)


router = APIRouter()
logger = logging.getLogger("alpha_quantum.auth")


# ── Local helpers (auth-domain only) ─────────────────────────────────────────


def _raise_auth_limiter_unavailable(
    *, client_host: str, username: str, stage: str
) -> None:
    """503 ile birlikte fail-closed log — limiter backend'i down olduğunda."""
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


def _to_role_read(row: dict) -> RoleRead:
    return RoleRead(
        id=int(row["id"]),
        name=str(row["name"]),
        description=str(row.get("description") or ""),
        created_at=int(row["created_at"]),
        updated_at=int(row["updated_at"]),
    )


def _to_user_read(
    row: dict, *, company_scopes: list[str] | None = None
) -> UserRead:
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


# ── Auth core ────────────────────────────────────────────────────────────────


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
    logger.info(
        "auth_success host=%s username=%s role=%s",
        client_host,
        user.username,
        user.role,
    )

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
def refresh_token(
    payload: RefreshTokenRequest, request: Request
) -> TokenResponse:
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


@router.post(
    "/api/v1/auth/logout", response_model=LogoutResponse, tags=["auth"]
)
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
        auth_service.revoke_all_refresh_tokens_for_user(
            user.id, reason="logout_all"
        )

    return LogoutResponse(message="Logout successful")


@router.get("/api/v1/auth/me", response_model=UserProfile, tags=["auth"])
def auth_me(user: UserProfile = Depends(get_current_user)) -> UserProfile:
    return user


# ── Roles ────────────────────────────────────────────────────────────────────


@router.get("/api/v1/roles", response_model=list[RoleRead], tags=["auth"])
def list_roles(
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_roles")),
) -> list[RoleRead]:
    del user
    return [_to_role_read(row) for row in _auth_service(request).list_roles()]


@router.post(
    "/api/v1/roles", response_model=RoleRead, status_code=201, tags=["auth"]
)
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

    _emit_audit_event(
        request, user, "role.create", {"role_name": payload.name}
    )
    return _to_role_read(row)


@router.patch(
    "/api/v1/roles/{role_id}", response_model=RoleRead, tags=["auth"]
)
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
        raise _value_error_to_http(exc) from exc
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Role already exists",
        ) from exc

    _emit_audit_event(
        request,
        user,
        "role.update",
        {"role_id": role_id, "new_name": payload.name},
    )
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
        raise _value_error_to_http(exc) from exc
    _emit_audit_event(request, user, "role.delete", {"role_id": role_id})


@router.get(
    "/api/v1/permissions", response_model=list[PermissionRead], tags=["auth"]
)
def list_permissions(
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_roles")),
) -> list[PermissionRead]:
    del user
    return [
        _to_permission_read(row)
        for row in _auth_service(request).list_permissions()
    ]


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
        raise _value_error_to_http(exc) from exc
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
        raise _value_error_to_http(exc) from exc

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


# ── Users ────────────────────────────────────────────────────────────────────


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


@router.post(
    "/api/v1/users", response_model=UserRead, status_code=201, tags=["auth"]
)
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
        raise _value_error_to_http(exc) from exc
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        ) from exc

    _emit_audit_event(
        request,
        user,
        "user.create",
        {
            "target_username": payload.username,
            "role": payload.role,
            "is_active": payload.is_active,
        },
    )
    return _to_user_read(
        row,
        company_scopes=_auth_service(request).user_company_scopes(
            int(row["id"])
        ),
    )


@router.patch(
    "/api/v1/users/{user_id}", response_model=UserRead, tags=["auth"]
)
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
        raise _value_error_to_http(exc) from exc

    _emit_audit_event(
        request,
        user,
        "user.update",
        {
            "target_user_id": user_id,
            "role": payload.role,
            "is_active": payload.is_active,
        },
    )
    return _to_user_read(
        row,
        company_scopes=_auth_service(request).user_company_scopes(
            int(row["id"])
        ),
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
        raise _value_error_to_http(exc) from exc
    _emit_audit_event(
        request, user, "user.delete", {"target_user_id": user_id}
    )


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
        raise _value_error_to_http(exc) from exc

    return LogoutResponse(message="Password rotated")
