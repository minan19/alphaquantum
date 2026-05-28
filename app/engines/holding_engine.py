from __future__ import annotations

from typing import Any, TypedDict

from app.holding_repository import HoldingRepository
from app.models import (
    HoldingBulkOnboardRequest,
    HoldingBulkOnboardResponse,
    HoldingCompanyOnboardInput,
    HoldingCompanyRead,
    HoldingCreateRequest,
    HoldingDetailResponse,
    HoldingListResponse,
    HoldingOnboardRequest,
    HoldingOnboardResponse,
    HoldingRead,
)
from app.repository import CompanyRepository


class HoldingEngine:
    def __init__(self, holding_repo: HoldingRepository, company_repo: CompanyRepository) -> None:
        self._holding_repo = holding_repo
        self._company_repo = company_repo

    def create_holding(self, payload: HoldingCreateRequest) -> HoldingRead:
        existing = self._holding_repo.get_holding_by_name(payload.name)
        if existing is not None:
            raise ValueError("Holding already exists")

        row = self._holding_repo.create_holding(
            name=payload.name,
            code=payload.code,
            description=payload.description,
            status=payload.status,
        )
        return _to_holding_read(row)

    def list_holdings(self, limit: int = 200) -> HoldingListResponse:
        rows = self._holding_repo.list_holdings(limit=limit)
        items = [_to_holding_read(row) for row in rows]
        return HoldingListResponse(total=len(items), items=items)

    def get_holding_detail(self, holding_id: int, limit: int = 1000) -> HoldingDetailResponse:
        holding_row = self._holding_repo.get_holding(holding_id)
        if holding_row is None:
            raise ValueError("Holding not found")

        company_rows = self._holding_repo.list_holding_companies(holding_id=holding_id, limit=limit)
        items = [_to_holding_company_read(row) for row in company_rows]
        summary = _build_holding_summary(items)

        return HoldingDetailResponse(
            holding=_to_holding_read(holding_row),
            total_companies=summary["total_companies"],
            go_count=summary["go_count"],
            conditional_go_count=summary["conditional_go_count"],
            block_count=summary["block_count"],
            average_readiness_score=summary["average_readiness_score"],
            items=items,
        )

    def onboard_companies(self, holding_id: int, payload: HoldingOnboardRequest) -> HoldingOnboardResponse:
        holding_row = self._holding_repo.get_holding(holding_id)
        if holding_row is None:
            raise ValueError("Holding not found")

        results: list[HoldingCompanyRead] = []
        for company in payload.companies:
            results.append(
                self._onboard_company(
                    holding_id=holding_id,
                    company=company,
                    auto_register=payload.auto_register_companies,
                )
            )

        summary = _build_holding_summary(results)
        recommendations = _build_holding_recommendations(summary)

        return HoldingOnboardResponse(
            holding=_to_holding_read(holding_row),
            total_companies=summary["total_companies"],
            go_count=summary["go_count"],
            conditional_go_count=summary["conditional_go_count"],
            block_count=summary["block_count"],
            average_readiness_score=summary["average_readiness_score"],
            items=results,
            recommendations=recommendations,
        )

    def onboard_bulk(self, payload: HoldingBulkOnboardRequest) -> HoldingBulkOnboardResponse:
        holding = self.create_holding(payload.holding)
        onboarding = self.onboard_companies(holding.id, payload.onboarding)
        return HoldingBulkOnboardResponse(
            holding=holding,
            onboarding=onboarding,
        )

    def _onboard_company(
        self,
        *,
        holding_id: int,
        company: HoldingCompanyOnboardInput,
        auto_register: bool,
    ) -> HoldingCompanyRead:
        registered = self._company_repo.has_company(company.company_name)
        if auto_register and not registered:
            self._company_repo.ensure_company(
                company.company_name,
                initial_balance=company.initial_balance,
            )
            registered = True

        readiness_score = _onboarding_readiness_score(company)
        onboarding_status = _onboarding_status_for_score(readiness_score)
        recommendation = _recommendation_for_onboarding_status(onboarding_status)

        row = self._holding_repo.upsert_holding_company(
            holding_id=holding_id,
            company_name=company.company_name,
            sector=company.sector,
            country=company.country,
            registered_in_platform=registered,
            data_quality_score=company.data_quality_score,
            integration_completeness_score=company.integration_completeness_score,
            security_compliance_score=company.security_compliance_score,
            process_standardization_score=company.process_standardization_score,
            master_data_health_score=company.master_data_health_score,
            team_readiness_score=company.team_readiness_score,
            onboarding_readiness_score=readiness_score,
            onboarding_status=onboarding_status,
            recommendation=recommendation,
            notes=company.notes,
        )
        return _to_holding_company_read(row)


def _onboarding_readiness_score(company: HoldingCompanyOnboardInput) -> float:
    score = (
        0.25 * company.data_quality_score
        + 0.20 * company.integration_completeness_score
        + 0.20 * company.security_compliance_score
        + 0.15 * company.process_standardization_score
        + 0.10 * company.master_data_health_score
        + 0.10 * company.team_readiness_score
    )
    return round(score, 2)


def _onboarding_status_for_score(score: float) -> str:
    if score >= 80:
        return "GO"
    if score >= 60:
        return "CONDITIONAL_GO"
    return "BLOCK"


def _recommendation_for_onboarding_status(status: str) -> str:
    if status == "GO":
        return "Proceed with full integration and cross-module activation."
    if status == "CONDITIONAL_GO":
        return "Proceed with remediation gates and milestone-based controls."
    return "Block onboarding until critical remediation plan is completed."


def _to_holding_read(row: dict[str, Any]) -> HoldingRead:
    return HoldingRead(
        id=int(row["id"]),
        name=str(row["name"]),
        code=str(row["code"]) if row.get("code") else None,
        description=str(row.get("description") or ""),
        status=str(row["status"]),
        created_at=int(row["created_at"]),
        updated_at=int(row["updated_at"]),
    )


def _to_holding_company_read(row: dict[str, Any]) -> HoldingCompanyRead:
    return HoldingCompanyRead(
        id=int(row["id"]),
        holding_id=int(row["holding_id"]),
        company_name=str(row["company_name"]),
        sector=str(row["sector"]),
        country=str(row["country"]),
        registered_in_platform=bool(int(row["registered_in_platform"])),
        data_quality_score=float(row["data_quality_score"]),
        integration_completeness_score=float(row["integration_completeness_score"]),
        security_compliance_score=float(row["security_compliance_score"]),
        process_standardization_score=float(row["process_standardization_score"]),
        master_data_health_score=float(row["master_data_health_score"]),
        team_readiness_score=float(row["team_readiness_score"]),
        onboarding_readiness_score=float(row["onboarding_readiness_score"]),
        onboarding_status=str(row["onboarding_status"]),
        recommendation=str(row["recommendation"]),
        notes=str(row.get("notes") or ""),
        created_at=int(row["created_at"]),
        updated_at=int(row["updated_at"]),
    )


class _HoldingSummary(TypedDict):
    total_companies: int
    go_count: int
    conditional_go_count: int
    block_count: int
    average_readiness_score: float


def _build_holding_summary(items: list[HoldingCompanyRead]) -> _HoldingSummary:
    total = len(items)
    go_count = sum(1 for item in items if item.onboarding_status == "GO")
    conditional_count = sum(1 for item in items if item.onboarding_status == "CONDITIONAL_GO")
    block_count = sum(1 for item in items if item.onboarding_status == "BLOCK")
    avg_score = round(sum(item.onboarding_readiness_score for item in items) / total, 2) if total > 0 else 0.0
    return {
        "total_companies": total,
        "go_count": go_count,
        "conditional_go_count": conditional_count,
        "block_count": block_count,
        "average_readiness_score": avg_score,
    }


def _build_holding_recommendations(summary: _HoldingSummary) -> list[str]:
    total = summary["total_companies"]
    go_count = summary["go_count"]
    conditional_count = summary["conditional_go_count"]
    block_count = summary["block_count"]
    avg_score = summary["average_readiness_score"]

    notes = [
        f"Portfolio readiness average: {avg_score:.2f}/100",
        f"GO={go_count}, CONDITIONAL_GO={conditional_count}, BLOCK={block_count}",
    ]
    if total == 0:
        notes.append("No companies onboarded yet.")
        return notes

    if block_count > 0:
        notes.append("Prioritize remediation for BLOCK companies before portfolio-wide activation.")
    elif conditional_count > 0:
        notes.append("Apply gated rollout and monitor remediation KPIs weekly.")
    else:
        notes.append("Portfolio is ready for full integrated activation.")
    return notes
