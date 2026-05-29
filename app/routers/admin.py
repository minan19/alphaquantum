"""A5.13 (part 1): Admin router (migrations + audit logs).

6 endpoint covering DB migration management + audit trail:

Migrations (5, manage_migrations):
- GET  /api/v1/admin/migrations/status      (applied versions)
- POST /api/v1/admin/migrations/apply       (apply all pending)
- POST /api/v1/admin/migrations/rollback    (steps + force)
- GET  /api/v1/admin/migrations/dry-run     (preview)
- POST /api/v1/admin/migrations/preflight   (safety check)

Audit (1, view_audit_logs):
- GET  /api/v1/audit-logs                   (recent events)
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request

from app.models import (
    AuditLogRead,
    MigrationActionResponse,
    MigrationDryRunResponse,
    MigrationPreflightResponse,
    MigrationRollbackRequest,
    MigrationStatusItem,
    UserProfile,
)
from app.routers._deps import (
    _audit_repo,
    _emit_audit_event,
    _migration_manager,
    _value_error_to_http,
)
from app.security import require_permissions


router = APIRouter()


# ── Migrations ───────────────────────────────────────────────────────────────


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
    _emit_audit_event(
        request, user, "migration.apply", {"versions_applied": versions}
    )
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
        versions = _migration_manager(request).rollback(
            steps=payload.steps, force=payload.force
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc
    _emit_audit_event(
        request,
        user,
        "migration.rollback",
        {
            "versions_rolled_back": versions,
            "steps": payload.steps,
            "force": payload.force,
        },
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


# ── Audit ────────────────────────────────────────────────────────────────────


@router.get(
    "/api/v1/audit-logs",
    response_model=list[AuditLogRead],
    tags=["audit"],
)
def list_audit_logs(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    user: UserProfile = Depends(require_permissions("view_audit_logs")),
) -> list[AuditLogRead]:
    del user
    rows = _audit_repo(request).list_logs(limit=limit)
    # AuditLogRead'in tanımadığı hash kolonlarını çıkar
    cleaned = [
        {k: v for k, v in row.items() if k not in {"prev_hash", "entry_hash"}}
        for row in rows
    ]
    return [AuditLogRead(**row) for row in cleaned]


# ── G+4: Hash chain verify (audit integrity) ─────────────────────────────────


@router.get(
    "/api/v1/audit-logs/verify",
    tags=["audit"],
)
def verify_audit_chain(
    request: Request,
    limit: int = Query(default=10_000, ge=1, le=100_000),
    user: UserProfile = Depends(require_permissions("view_audit_logs")),
) -> dict[str, Any]:
    """G+4: Audit hash chain integrity verification.

    Bağımsız denetçi-grade: O(N) tarama ile zincir bütünlüğünü doğrular.
    Bir entry değiştirilirse first_break_id ile tespit edilir.

    KVKK madde 12 + ISO 27001 A.12.4 + SOC 2 CC7.2 compliance.

    Returns:
      - verified: bool (zincir sağlam mı)
      - checked_count: kontrol edilen entry sayısı
      - first_break_id: ilk kırılma id'si (None = sağlam)
      - first_break_reason: entry_hash_mismatch | prev_hash_mismatch | ""
      - genesis_id: ilk hash-chain entry id'si
      - legacy_count: pre-G+4 entries (entry_hash NULL)
    """
    del user
    return _audit_repo(request).verify_chain(limit=limit)
