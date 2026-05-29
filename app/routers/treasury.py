"""T1: Treasury router — multi-bank konsolide bakiye + CSV import."""
from __future__ import annotations

from dataclasses import asdict
from typing import cast

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile

from app.engines.treasury_engine import TreasuryEngine
from app.models import (
    TreasuryAccountCreateRequest,
    TreasuryAccountResponse,
    TreasuryBalanceUpdateRequest,
    TreasuryCsvImportResponse,
    TreasuryHistoryEntry,
    TreasuryHistoryResponse,
    TreasurySummaryResponse,
    UserProfile,
)
from app.routers._deps import _value_error_to_http
from app.security import require_permissions


router = APIRouter()


def _engine(request: Request) -> TreasuryEngine:
    return cast(TreasuryEngine, request.app.state.treasury_engine)


@router.get(
    "/api/v1/treasury/accounts",
    response_model=list[TreasuryAccountResponse],
    tags=["treasury"],
)
def list_accounts(
    request: Request,
    active_only: bool = Query(default=True),
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> list[TreasuryAccountResponse]:
    views = _engine(request).list_accounts(
        user_id=user.username, active_only=active_only,
    )
    return [TreasuryAccountResponse(**asdict(v)) for v in views]


@router.post(
    "/api/v1/treasury/accounts",
    response_model=TreasuryAccountResponse,
    tags=["treasury"],
)
def add_account(
    payload: TreasuryAccountCreateRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_finance")),
) -> TreasuryAccountResponse:
    try:
        view = _engine(request).add_account(
            user_id=user.username, **payload.model_dump(),
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc
    return TreasuryAccountResponse(**asdict(view))


@router.post(
    "/api/v1/treasury/accounts/{account_id}/balance",
    response_model=TreasuryAccountResponse,
    tags=["treasury"],
)
def update_balance(
    account_id: int,
    payload: TreasuryBalanceUpdateRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_finance")),
) -> TreasuryAccountResponse:
    try:
        view = _engine(request).update_balance(
            user_id=user.username,
            account_id=account_id,
            new_balance=payload.new_balance,
            source=payload.source,
            snapshot_date=payload.snapshot_date,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc
    return TreasuryAccountResponse(**asdict(view))


@router.get(
    "/api/v1/treasury/summary",
    response_model=TreasurySummaryResponse,
    tags=["treasury"],
)
def get_summary(
    request: Request,
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> TreasurySummaryResponse:
    summary = _engine(request).summary(user_id=user.username)
    return TreasurySummaryResponse(
        total_in_try=summary.total_in_try,
        by_currency=summary.by_currency,
        by_bank=summary.by_bank,
        by_company=summary.by_company,
        account_count=summary.account_count,
        last_synced_at=summary.last_synced_at,
    )


@router.get(
    "/api/v1/treasury/accounts/{account_id}/history",
    response_model=TreasuryHistoryResponse,
    tags=["treasury"],
)
def get_history(
    account_id: int,
    request: Request,
    days: int = Query(default=30, ge=1, le=365),
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> TreasuryHistoryResponse:
    try:
        entries = _engine(request).history(
            user_id=user.username, account_id=account_id, days=days,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc
    return TreasuryHistoryResponse(
        entries=[TreasuryHistoryEntry(**e) for e in entries],
    )


@router.post(
    "/api/v1/treasury/accounts/{account_id}/import-csv",
    response_model=TreasuryCsvImportResponse,
    tags=["treasury"],
)
async def import_csv(
    account_id: int,
    request: Request,
    file: UploadFile = File(...),
    user: UserProfile = Depends(require_permissions("manage_finance")),
) -> TreasuryCsvImportResponse:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Boş dosya")
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Max 5 MB CSV")
    try:
        csv_text = data.decode("utf-8", errors="replace")
        result = _engine(request).import_csv(
            user_id=user.username,
            account_id=account_id,
            csv_content=csv_text,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc
    return TreasuryCsvImportResponse(**result)
