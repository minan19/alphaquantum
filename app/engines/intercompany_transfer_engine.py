"""G1.3: IntercompanyTransferEngine — 4-eyes onay business mantığı.

Karma sektörlü holding'in en kritik operasyonel feature'ı. Bu engine:
  - Transfer talebini doğrular (holding + şirket varlığı, self-transfer reddi)
  - 4-eyes onayı ENFORCE eder (requester != approver)
  - Atomic write için repository'ye delege eder
  - Audit log'a uygun şekilde state transition'ları sağlar

Mimari notlar:
  - "4-eyes" = "iki çift göz" — talep eden ile onaylayan farklı kişi olmalı.
    Bu enterprise security feature'ı (SOC 2 CC8.1, ISO 27001 A.12.1.2)
    hile/yanlışlık riskini sıfırlar. Yüksek tutarlı kararlarda tek imzalı
    işlem riski sıfırlanır — özellikle karma holding'de farklı sektör
    finans ekipleri arası kontrol.
  - State machine:
      pending → approved → completed  (happy path)
      pending → rejected               (red yolu)
    "approved" ara state (atomic write fail olursa kalır, manual recovery).
    "completed" final state (ledger entry'ler oluşturuldu).
  - Holding varlığı kontrol edilir ama şirket varlığı şu an opt-in
    (kullanıcı transfer öncesi UI'da seçer). G1.5'te bağlanacak.
"""
from __future__ import annotations

from app.holding_repository import HoldingRepository
from app.intercompany_transfer_repository import IntercompanyTransferRepository
from app.models import (
    IntercompanyTransferListResponse,
    IntercompanyTransferRead,
    IntercompanyTransferRequestCreate,
)


class IntercompanyTransferEngine:
    """Atomic intercompany transfer + 4-eyes approval workflow."""

    def __init__(
        self,
        *,
        transfer_repo: IntercompanyTransferRepository,
        holding_repo: HoldingRepository,
    ) -> None:
        self._repo = transfer_repo
        self._holding_repo = holding_repo

    # ── REQUEST ────────────────────────────────────────────────────────

    def request_transfer(
        self,
        *,
        holding_id: int,
        payload: IntercompanyTransferRequestCreate,
        requested_by: str,
    ) -> IntercompanyTransferRead:
        """Create a pending transfer. Validates holding + business rules.

        Raises:
            ValueError: holding not found, self-transfer, invalid FX setup.
        """
        # Holding varlığı kontrolü
        holding_row = self._holding_repo.get_holding(holding_id)
        if holding_row is None:
            raise ValueError(f"Holding {holding_id} not found")

        # Self-transfer mantıksız — DB CHECK constraint zaten engelliyor
        # ama engine seviyesinde daha net hata mesajı verelim
        if payload.from_company == payload.to_company:
            raise ValueError(
                "from_company ve to_company aynı olamaz (self-transfer yasak)"
            )

        # Cross-currency tutarlılık: target_amount ve fx_rate ya ikisi de
        # verilir ya hiçbiri (TRY → TRY default davranış)
        has_target = payload.target_amount is not None
        has_rate = payload.fx_rate is not None
        if has_target != has_rate:
            raise ValueError(
                "Cross-currency için target_amount ve fx_rate beraber verilmelidir"
            )

        row = self._repo.request_transfer(
            holding_id=holding_id,
            from_company=payload.from_company,
            to_company=payload.to_company,
            amount=payload.amount,
            currency=payload.currency,
            description=payload.description,
            requested_by=requested_by,
            target_amount=payload.target_amount,
            fx_rate=payload.fx_rate,
        )
        return _to_read(row)

    # ── APPROVE (4-eyes enforcement + atomic) ──────────────────────────

    def approve(
        self,
        *,
        transfer_id: int,
        approver_user_id: str,
    ) -> IntercompanyTransferRead:
        """4-eyes onay + atomic ledger write.

        Enforces:
          - Transfer exists and is pending
          - Approver != requester (4-eyes core rule)
          - Atomic double-entry write to ledger

        Raises:
            ValueError: transfer not found, not pending, 4-eyes violated.
        """
        existing = self._repo.get_transfer(transfer_id)
        if existing is None:
            raise ValueError(f"Transfer {transfer_id} not found")
        if existing["approval_status"] != "pending":
            raise ValueError(
                f"Transfer {transfer_id} not in pending state "
                f"(current: {existing['approval_status']})"
            )
        if str(existing["requested_by"]) == str(approver_user_id):
            raise ValueError(
                "4-eyes ihlali: talep eden ile onaylayan aynı kullanıcı olamaz"
            )

        row = self._repo.approve_atomic(
            transfer_id=transfer_id,
            approver_user_id=approver_user_id,
        )
        return _to_read(row)

    # ── REJECT ─────────────────────────────────────────────────────────

    def reject(
        self,
        *,
        transfer_id: int,
        approver_user_id: str,
        reject_reason: str,
    ) -> IntercompanyTransferRead:
        """Mark transfer as rejected. Same 4-eyes rule as approve.

        Note: rejection da approve gibi audit-critical — talep eden ile
        reddeden aynı kişi olamaz (kötü niyetli self-reject engeli).
        """
        existing = self._repo.get_transfer(transfer_id)
        if existing is None:
            raise ValueError(f"Transfer {transfer_id} not found")
        if existing["approval_status"] != "pending":
            raise ValueError(
                f"Transfer {transfer_id} not in pending state "
                f"(current: {existing['approval_status']})"
            )
        if str(existing["requested_by"]) == str(approver_user_id):
            raise ValueError(
                "4-eyes ihlali: talep eden ile reddeden aynı kullanıcı olamaz"
            )

        row = self._repo.reject(
            transfer_id=transfer_id,
            approver_user_id=approver_user_id,
            reject_reason=reject_reason,
        )
        return _to_read(row)

    # ── READ ───────────────────────────────────────────────────────────

    def get_transfer(self, transfer_id: int) -> IntercompanyTransferRead:
        row = self._repo.get_transfer(transfer_id)
        if row is None:
            raise ValueError(f"Transfer {transfer_id} not found")
        return _to_read(row)

    def list_pending(
        self, *, holding_id: int
    ) -> IntercompanyTransferListResponse:
        rows = self._repo.list_pending(holding_id=holding_id)
        transfers = [_to_read(r) for r in rows]
        return IntercompanyTransferListResponse(
            total=len(transfers), transfers=transfers
        )

    def list_by_holding(
        self, *, holding_id: int, limit: int = 200
    ) -> IntercompanyTransferListResponse:
        rows = self._repo.list_by_holding(holding_id=holding_id, limit=limit)
        transfers = [_to_read(r) for r in rows]
        return IntercompanyTransferListResponse(
            total=len(transfers), transfers=transfers
        )


def _to_read(row: dict) -> IntercompanyTransferRead:
    """SQLite row → Pydantic IntercompanyTransferRead."""
    return IntercompanyTransferRead(
        id=int(row["id"]),
        holding_id=int(row["holding_id"]),
        from_company=str(row["from_company"]),
        to_company=str(row["to_company"]),
        amount=float(row["amount"]),
        currency=str(row["currency"]),
        target_amount=(
            float(row["target_amount"]) if row["target_amount"] is not None else None
        ),
        fx_rate=(
            float(row["fx_rate"]) if row["fx_rate"] is not None else None
        ),
        description=str(row["description"] or ""),
        requested_by=str(row["requested_by"]),
        requested_at=int(row["requested_at"]),
        approval_status=str(row["approval_status"]),
        approved_by=(
            str(row["approved_by"]) if row["approved_by"] is not None else None
        ),
        approved_at=(
            int(row["approved_at"]) if row["approved_at"] is not None else None
        ),
        reject_reason=(
            str(row["reject_reason"]) if row["reject_reason"] is not None else None
        ),
        completed_at=(
            int(row["completed_at"]) if row["completed_at"] is not None else None
        ),
        ledger_entry_from_id=(
            int(row["ledger_entry_from_id"])
            if row["ledger_entry_from_id"] is not None
            else None
        ),
        ledger_entry_to_id=(
            int(row["ledger_entry_to_id"])
            if row["ledger_entry_to_id"] is not None
            else None
        ),
    )
