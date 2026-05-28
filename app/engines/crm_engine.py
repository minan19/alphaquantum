from __future__ import annotations

from typing import Any

from app.crm_repository import CRMRepository
from app.models import (
    CustomerCreateRequest,
    CustomerRead,
    CustomerListResponse,
    CustomerUpdateRequest,
    ProposalCreateRequest,
    ProposalRead,
    ProposalListResponse,
    ProposalStatusUpdateRequest,
    ProposalSummaryResponse,
)


class CRMEngine:
    def __init__(self, repo: CRMRepository) -> None:
        self._repo = repo

    # ── Customers ──────────────────────────────────────────────────────────────

    def create_customer(
        self, *, payload: CustomerCreateRequest
    ) -> CustomerRead:
        row = self._repo.create_customer(
            company_name=payload.company,
            full_name=payload.full_name,
            email=payload.email,
            phone=payload.phone,
            sector=payload.sector,
            tags=payload.tags,
            notes=payload.notes,
        )
        return self._to_customer_read(row)

    def get_customer(self, customer_id: int) -> CustomerRead | None:
        row = self._repo.get_customer(customer_id)
        return self._to_customer_read(row) if row else None

    def list_customers(
        self,
        *,
        company: str | None,
        active_only: bool = True,
        limit: int = 200,
    ) -> CustomerListResponse:
        rows = self._repo.list_customers(
            company_name=company, active_only=active_only, limit=limit
        )
        items = [self._to_customer_read(r) for r in rows]
        return CustomerListResponse(total=len(items), customers=items)

    def update_customer(
        self, customer_id: int, *, payload: CustomerUpdateRequest
    ) -> CustomerRead | None:
        row = self._repo.update_customer(
            customer_id,
            full_name=payload.full_name,
            email=payload.email,
            phone=payload.phone,
            sector=payload.sector,
            tags=payload.tags,
            notes=payload.notes,
            is_active=payload.is_active,
        )
        return self._to_customer_read(row) if row else None

    # ── Proposals ──────────────────────────────────────────────────────────────

    def create_proposal(
        self, *, payload: ProposalCreateRequest
    ) -> ProposalRead:
        row = self._repo.create_proposal(
            company_name=payload.company,
            customer_id=payload.customer_id,
            title=payload.title,
            amount=payload.amount,
            currency=payload.currency,
            valid_until=payload.valid_until,
            description=payload.description,
        )
        return self._to_proposal_read(row)

    def get_proposal(self, proposal_id: int) -> ProposalRead | None:
        row = self._repo.get_proposal(proposal_id)
        return self._to_proposal_read(row) if row else None

    def list_proposals(
        self,
        *,
        company: str | None,
        customer_id: int | None = None,
        status: str | None = None,
        limit: int = 200,
    ) -> ProposalListResponse:
        rows = self._repo.list_proposals(
            company_name=company, customer_id=customer_id,
            status=status, limit=limit,
        )
        items = [self._to_proposal_read(r) for r in rows]
        return ProposalListResponse(total=len(items), proposals=items)

    def update_proposal_status(
        self, proposal_id: int, *, payload: ProposalStatusUpdateRequest
    ) -> ProposalRead | None:
        row = self._repo.update_proposal_status(
            proposal_id,
            status=payload.status,
            amount=payload.amount,
            valid_until=payload.valid_until,
            description=payload.description,
        )
        return self._to_proposal_read(row) if row else None

    def proposal_summary(self, *, company: str | None) -> ProposalSummaryResponse:
        raw = self._repo.proposal_summary(company_name=company)
        total_count = sum(v["count"] for v in raw.values())
        total_amount = sum(v["total_amount"] for v in raw.values())
        accepted_amount = raw.get("accepted", {}).get("total_amount", 0.0)
        return ProposalSummaryResponse(
            company=company,
            total_count=total_count,
            total_amount=round(total_amount, 2),
            accepted_amount=round(accepted_amount, 2),
            by_status={k: v["count"] for k, v in raw.items()},
        )

    # ── Converters ─────────────────────────────────────────────────────────────

    def update_consent(
        self,
        customer_id: int,
        *,
        email_consent: bool | None = None,
        sms_consent: bool | None = None,
        whatsapp_consent: bool | None = None,
    ) -> CustomerRead | None:
        """S-343 — KVKK consent flag update."""
        row = self._repo.update_consent(
            customer_id,
            email_consent=email_consent,
            sms_consent=sms_consent,
            whatsapp_consent=whatsapp_consent,
        )
        return self._to_customer_read(row) if row else None

    @staticmethod
    def _to_customer_read(row: dict[str, Any]) -> CustomerRead:
        return CustomerRead(
            id=int(row["id"]),
            company=str(row["company_name"]),
            full_name=str(row["full_name"]),
            email=str(row.get("email") or ""),
            phone=str(row.get("phone") or ""),
            sector=str(row.get("sector") or "general"),
            tags=row.get("tags") or [],
            notes=str(row.get("notes") or ""),
            is_active=bool(row.get("is_active", 1)),
            email_consent=bool(row.get("email_consent", 0)),
            sms_consent=bool(row.get("sms_consent", 0)),
            whatsapp_consent=bool(row.get("whatsapp_consent", 0)),
            consent_updated_at=int(row.get("consent_updated_at") or 0),
            created_at=int(row["created_at"]),
            updated_at=int(row["updated_at"]),
        )

    @staticmethod
    def _to_proposal_read(row: dict[str, Any]) -> ProposalRead:
        return ProposalRead(
            id=int(row["id"]),
            company=str(row["company_name"]),
            customer_id=int(row["customer_id"]),
            title=str(row["title"]),
            amount=float(row["amount"]),
            currency=str(row.get("currency") or "TRY"),
            status=str(row["status"]),
            valid_until=row.get("valid_until"),
            description=str(row.get("description") or ""),
            created_at=int(row["created_at"]),
            updated_at=int(row["updated_at"]),
        )
