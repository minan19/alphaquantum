"""G1.3: Intercompany transfer router — 4-eyes onay endpoint'leri.

5 endpoint:
  - POST   /api/v1/holdings/{id}/intercompany-transfers          (request)
  - GET    /api/v1/holdings/{id}/intercompany-transfers/pending  (approval queue)
  - GET    /api/v1/holdings/{id}/intercompany-transfers          (list)
  - GET    /api/v1/intercompany-transfers/{id}                   (detail)
  - POST   /api/v1/intercompany-transfers/{id}/approve           (2. göz onay)
  - POST   /api/v1/intercompany-transfers/{id}/reject            (2. göz red)

RBAC:
  - manage_holdings: request + approve + reject
  - read_holdings: get + list (transparency)

Sahne 4 ("15:00 - Cross-company transfer") burayı çağırır.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from app.models import (
    IntercompanyTransferApproveRequest,
    IntercompanyTransferListResponse,
    IntercompanyTransferRead,
    IntercompanyTransferRejectRequest,
    IntercompanyTransferRequestCreate,
    UserProfile,
)
from app.routers._deps import (
    _intercompany_transfer_engine,
    _value_error_to_http,
)
from app.security import require_permissions


router = APIRouter()


@router.post(
    "/api/v1/holdings/{holding_id}/intercompany-transfers",
    response_model=IntercompanyTransferRead,
    status_code=201,
    tags=["intercompany"],
)
def request_intercompany_transfer(
    holding_id: int,
    payload: IntercompanyTransferRequestCreate,
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_holdings")),
) -> IntercompanyTransferRead:
    """Yeni intercompany transfer talebi — pending state'inde oluşur.

    Ledger entry'ler henüz yazılmaz — 2. göz onayı (approve endpoint'i)
    atomic olarak yazacak.
    """
    try:
        return _intercompany_transfer_engine(request).request_transfer(
            holding_id=holding_id,
            payload=payload,
            requested_by=user.username,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


@router.get(
    "/api/v1/holdings/{holding_id}/intercompany-transfers/pending",
    response_model=IntercompanyTransferListResponse,
    tags=["intercompany"],
)
def list_pending_intercompany_transfers(
    holding_id: int,
    request: Request,
    user: UserProfile = Depends(require_permissions("read_holdings")),
) -> IntercompanyTransferListResponse:
    """Onay bekleyen transfer kuyruğu (eskiden yeniye)."""
    del user
    return _intercompany_transfer_engine(request).list_pending(
        holding_id=holding_id
    )


@router.get(
    "/api/v1/holdings/{holding_id}/intercompany-transfers",
    response_model=IntercompanyTransferListResponse,
    tags=["intercompany"],
)
def list_holding_intercompany_transfers(
    holding_id: int,
    request: Request,
    limit: int = Query(default=200, ge=1, le=1000),
    user: UserProfile = Depends(require_permissions("read_holdings")),
) -> IntercompanyTransferListResponse:
    """Holding'in tüm transferleri (yeniden eskiye, tüm state'ler)."""
    del user
    return _intercompany_transfer_engine(request).list_by_holding(
        holding_id=holding_id, limit=limit
    )


@router.get(
    "/api/v1/intercompany-transfers/{transfer_id}",
    response_model=IntercompanyTransferRead,
    tags=["intercompany"],
)
def get_intercompany_transfer(
    transfer_id: int,
    request: Request,
    user: UserProfile = Depends(require_permissions("read_holdings")),
) -> IntercompanyTransferRead:
    """Tek transfer detay (audit + UI için)."""
    del user
    try:
        return _intercompany_transfer_engine(request).get_transfer(transfer_id)
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


@router.post(
    "/api/v1/intercompany-transfers/{transfer_id}/approve",
    response_model=IntercompanyTransferRead,
    tags=["intercompany"],
)
def approve_intercompany_transfer(
    transfer_id: int,
    payload: IntercompanyTransferApproveRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_holdings")),
) -> IntercompanyTransferRead:
    """4-eyes onay — atomic ledger write tetiklenir.

    Enforce: requester != approver. Aksi halde 400 + Türkçe hata mesajı.

    Atomic transaction:
      1. UPDATE intercompany_transfers status='approved'
      2. INSERT ledger entry (from, expense, intercompany_flag=1)
      3. INSERT ledger entry (to, income, intercompany_flag=1)
      4. UPDATE ledger ref'leri + status='completed'

    Herhangi bir adım fail → tüm transaction rollback.
    """
    del user  # approver_user_id payload'da gelir (UI explicit seçim)
    try:
        return _intercompany_transfer_engine(request).approve(
            transfer_id=transfer_id,
            approver_user_id=payload.approver_user_id,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


@router.post(
    "/api/v1/intercompany-transfers/{transfer_id}/reject",
    response_model=IntercompanyTransferRead,
    tags=["intercompany"],
)
def reject_intercompany_transfer(
    transfer_id: int,
    payload: IntercompanyTransferRejectRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_holdings")),
) -> IntercompanyTransferRead:
    """2. göz reddi — sebep zorunlu (audit log için)."""
    del user
    try:
        return _intercompany_transfer_engine(request).reject(
            transfer_id=transfer_id,
            approver_user_id=payload.approver_user_id,
            reject_reason=payload.reject_reason,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc
