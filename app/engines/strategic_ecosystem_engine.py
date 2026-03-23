from __future__ import annotations

from datetime import datetime, timezone

from app.engines.feasibility_engine import FeasibilityEngine
from app.engines.international_operations_engine import InternationalOperationsEngine
from app.engines.procurement_engine import ProcurementEngine
from app.models import (
    EcosystemActivationRequest,
    EcosystemActivationResponse,
    EcosystemPortfolioActivationRequest,
    EcosystemPortfolioActivationResponse,
    EcosystemPortfolioCompanyInput,
    EcosystemPortfolioCompanyResult,
    FeasibilityReportRequest,
    InternationalProjectRequest,
    ProcurementRequestCreateRequest,
    ProcurementRequestItemCreateRequest,
)


class StrategicEcosystemEngine:
    def __init__(
        self,
        feasibility_engine: FeasibilityEngine,
        international_engine: InternationalOperationsEngine,
        procurement_engine: ProcurementEngine,
    ) -> None:
        self._feasibility_engine = feasibility_engine
        self._international_engine = international_engine
        self._procurement_engine = procurement_engine

    def activate(self, payload: EcosystemActivationRequest) -> EcosystemActivationResponse:
        feasibility_input = self._build_feasibility_payload(payload)
        feasibility = self._feasibility_engine.generate(feasibility_input)

        international_input = self._build_international_payload(payload)
        international = self._international_engine.create_project(international_input)

        procurement_request_id: int | None = None
        if payload.procurement_items:
            procurement_input = self._build_procurement_payload(payload)
            procurement = self._procurement_engine.create_request(procurement_input)
            procurement_request_id = procurement.id

        recommendation = feasibility.report.recommendation
        confidence = round((feasibility.report.confidence + international.report.confidence) / 2, 2)
        action_plan = self._build_action_plan(
            payload=payload,
            recommendation=recommendation,
            feasibility_id=feasibility.id,
            international_id=international.id,
            procurement_id=procurement_request_id,
        )

        module_status = {
            "feasibility": f"active(report_id={feasibility.id})",
            "international_operations": f"active(project_id={international.id})",
            "procurement": (
                f"active(request_id={procurement_request_id})"
                if procurement_request_id is not None
                else "ready(no_bootstrap_request)"
            ),
        }

        preview = _markdown_preview(feasibility.report.report_markdown)

        return EcosystemActivationResponse(
            generated_at=datetime.now(timezone.utc).isoformat(),
            project_name=payload.project_name,
            company_name=payload.company_name,
            sector=payload.sector,
            recommendation=recommendation,
            confidence=confidence,
            feasibility_report_id=feasibility.id,
            international_project_id=international.id,
            procurement_request_id=procurement_request_id,
            module_status=module_status,
            action_plan=action_plan,
            feasibility_report_markdown_preview=preview,
        )

    def activate_portfolio(
        self,
        payload: EcosystemPortfolioActivationRequest,
        *,
        registered_company_names: list[str] | None = None,
    ) -> EcosystemPortfolioActivationResponse:
        targets = self._resolve_targets(payload, registered_company_names=registered_company_names or [])
        results: list[EcosystemPortfolioCompanyResult] = []
        errors: list[str] = []

        for idx, target in enumerate(targets, start=1):
            project_name = f"{payload.project_name_prefix} - {target.company_name}"
            try:
                activation = self.activate(
                    EcosystemActivationRequest(
                        project_name=project_name,
                        company_name=target.company_name,
                        sector=target.sector,
                        geography=target.geography,
                        objective=target.objective,
                        budget_total=target.budget_total,
                        currency=payload.currency,
                        base_country=payload.base_country,
                        target_countries=payload.target_countries,
                        services=payload.services,
                        timeline_months=payload.timeline_months,
                        risk_appetite=payload.risk_appetite,
                        local_partner_required=payload.local_partner_required,
                        strategic_objectives=payload.strategic_objectives,
                        trade_lanes=payload.trade_lanes,
                        preferred_incoterms=payload.preferred_incoterms,
                        procurement_strategy=payload.procurement_strategy,
                        procurement_items=target.procurement_items,
                        notes=_merge_notes(payload.notes, target.notes),
                    )
                )
                results.append(
                    EcosystemPortfolioCompanyResult(
                        company_name=activation.company_name,
                        project_name=activation.project_name,
                        recommendation=activation.recommendation,
                        confidence=activation.confidence,
                        feasibility_report_id=activation.feasibility_report_id,
                        international_project_id=activation.international_project_id,
                        procurement_request_id=activation.procurement_request_id,
                        module_status=activation.module_status,
                        action_plan=activation.action_plan,
                    )
                )
            except Exception as exc:
                errors.append(
                    f"{target.company_name} (item={idx}): {str(exc)}"
                )

        successful = len(results)
        failed = len(errors)
        avg_conf = round(sum(item.confidence for item in results) / successful, 2) if successful > 0 else 0.0
        portfolio_recommendation = _portfolio_recommendation(results, failed_companies=failed)
        summary_notes = self._portfolio_summary_notes(
            payload=payload,
            successful=successful,
            failed=failed,
            average_confidence=avg_conf,
            recommendation=portfolio_recommendation,
        )

        return EcosystemPortfolioActivationResponse(
            generated_at=datetime.now(timezone.utc).isoformat(),
            scope_mode=payload.scope_mode,
            holding_name=payload.holding_name,
            total_companies=len(targets),
            successful_companies=successful,
            failed_companies=failed,
            portfolio_recommendation=portfolio_recommendation,
            average_confidence=avg_conf,
            items=results,
            errors=errors,
            summary_notes=summary_notes,
        )

    @staticmethod
    def _build_feasibility_payload(payload: EcosystemActivationRequest) -> FeasibilityReportRequest:
        budget = payload.budget_total
        initial_investment = budget * 0.55
        annual_opex = budget * 0.12
        annual_revenue = budget * 0.25
        implementation_months = min(60, max(3, payload.timeline_months // 2))
        project_lifetime_years = min(25, max(5, payload.timeline_months // 2))

        constraints: list[str] = []
        if payload.local_partner_required:
            constraints.append("Local partner onboarding and governance controls")
        if payload.trade_lanes:
            constraints.append(f"Trade lanes active: {', '.join(payload.trade_lanes[:6])}")

        return FeasibilityReportRequest(
            project_name=payload.project_name,
            sector=payload.sector,
            geography=payload.geography,
            objective=payload.objective,
            currency=payload.currency.upper(),
            initial_investment=initial_investment,
            annual_opex=annual_opex,
            annual_revenue_base=annual_revenue,
            project_lifetime_years=project_lifetime_years,
            implementation_months=implementation_months,
            discount_rate=0.15,
            tax_rate=0.2,
            inflation_rate=0.12,
            revenue_growth_base=0.08,
            revenue_growth_upside=0.15,
            revenue_growth_downside=-0.05,
            opex_growth_base=0.09,
            capacity_utilization=0.72,
            financing_debt_ratio=0.45,
            regulatory_requirements=[
                "Country-specific legal and tax compliance",
                "Sector-specific license and permit controls",
            ],
            constraints=constraints,
            benchmark_symbols=[],
            additional_notes=payload.notes,
        )

    @staticmethod
    def _build_international_payload(payload: EcosystemActivationRequest) -> InternationalProjectRequest:
        return InternationalProjectRequest(
            project_name=payload.project_name,
            company_name=payload.company_name,
            base_country=payload.base_country,
            target_countries=payload.target_countries,
            services=payload.services,
            sectors=[payload.sector],
            strategic_objectives=payload.strategic_objectives or [
                "Cross-border growth and recurring revenue expansion",
                "Operational resilience via multi-country footprint",
            ],
            budget_total=payload.budget_total,
            currency=payload.currency.upper(),
            timeline_months=payload.timeline_months,
            risk_appetite=payload.risk_appetite,
            local_partner_required=payload.local_partner_required,
            preferred_incoterms=payload.preferred_incoterms,
            trade_lanes=payload.trade_lanes,
            notes=payload.notes,
        )

    @staticmethod
    def _build_procurement_payload(payload: EcosystemActivationRequest) -> ProcurementRequestCreateRequest:
        items = [
            ProcurementRequestItemCreateRequest(
                item_name=item.item_name,
                specification=item.specification,
                quantity=item.quantity,
                min_quality_score=item.min_quality_score,
                max_unit_price=item.max_unit_price,
                required_by_date=item.required_by_date,
                must_comply_tender=item.must_comply_tender,
            )
            for item in payload.procurement_items
        ]
        return ProcurementRequestCreateRequest(
            company=payload.company_name,
            title=f"{payload.project_name} - Initial Strategic Procurement",
            strategy=payload.procurement_strategy,
            budget_limit=round(payload.budget_total * 0.30, 2),
            currency=payload.currency.upper(),
            tender_reference=None,
            tender_requirements=[
                "Supplier compliance and technical acceptance evidence",
                "Delivery SLA and warranty terms",
                "Country-level legal and customs conformity",
            ],
            items=items,
        )

    @staticmethod
    def _build_action_plan(
        *,
        payload: EcosystemActivationRequest,
        recommendation: str,
        feasibility_id: int,
        international_id: int,
        procurement_id: int | None,
    ) -> list[str]:
        actions = [
            f"Review feasibility report #{feasibility_id} at executive committee.",
            f"Launch country workstreams from international project #{international_id}.",
            "Open legal/tax/compliance due diligence per target country.",
            "Activate KPI and risk dashboards with weekly PMO cadence.",
        ]
        if procurement_id is not None:
            actions.append(f"Start RFQ cycle from procurement request #{procurement_id}.")
        if recommendation == "CONDITIONAL_GO":
            actions.append("Apply conditional-go gates before capex commitment.")
        if recommendation == "NO_GO":
            actions.append("Stop expansion commitment and rerun scenario parameters.")
        if payload.local_partner_required:
            actions.append("Initiate local partner qualification and governance contract process.")
        return actions

    @staticmethod
    def _resolve_targets(
        payload: EcosystemPortfolioActivationRequest,
        *,
        registered_company_names: list[str],
    ) -> list[EcosystemPortfolioCompanyInput]:
        targets = list(payload.companies)
        if not targets and payload.use_registered_companies_when_empty:
            for company_name in registered_company_names:
                normalized_name = company_name.strip()
                if not normalized_name:
                    continue
                targets.append(
                    EcosystemPortfolioCompanyInput(
                        company_name=normalized_name,
                        sector=payload.default_sector,
                        geography=payload.default_geography,
                        objective=payload.default_objective,
                        budget_total=payload.default_budget_total,
                    )
                )

        if not targets:
            raise ValueError("No company targets found for portfolio activation")

        if payload.scope_mode == "single" and len(targets) != 1:
            raise ValueError("Single scope requires exactly one company")
        if payload.scope_mode == "multi" and len(targets) < 2:
            raise ValueError("Multi scope requires at least two companies")
        if payload.scope_mode == "holding":
            if not payload.holding_name:
                raise ValueError("Holding scope requires holding_name")
            if len(targets) < 1:
                raise ValueError("Holding scope requires at least one company")

        return targets

    @staticmethod
    def _portfolio_summary_notes(
        *,
        payload: EcosystemPortfolioActivationRequest,
        successful: int,
        failed: int,
        average_confidence: float,
        recommendation: str,
    ) -> list[str]:
        notes = [
            f"Scope mode: {payload.scope_mode}",
            f"Successful activations: {successful}",
            f"Failed activations: {failed}",
            f"Average confidence: {average_confidence:.2f}",
            f"Portfolio recommendation: {recommendation}",
        ]
        if payload.scope_mode == "holding" and payload.holding_name:
            notes.append(f"Holding context: {payload.holding_name}")
        if payload.target_countries:
            notes.append(f"Target countries: {', '.join(payload.target_countries[:10])}")
        return notes


def _markdown_preview(markdown_text: str, max_lines: int = 16) -> str:
    lines = [line for line in markdown_text.splitlines() if line.strip()]
    return "\n".join(lines[:max_lines])


def _merge_notes(global_notes: str, local_notes: str) -> str:
    g = global_notes.strip()
    l = local_notes.strip()
    if g and l:
        return f"{g} | {l}"
    return g or l


def _portfolio_recommendation(
    items: list[EcosystemPortfolioCompanyResult],
    *,
    failed_companies: int,
) -> str:
    if not items:
        return "NO_GO"
    if failed_companies > 0:
        return "CONDITIONAL_GO"
    rankings = {"GO": 2, "CONDITIONAL_GO": 1, "NO_GO": 0}
    score = sum(rankings.get(item.recommendation, 0) for item in items) / len(items)
    if score >= 1.5:
        return "GO"
    if score >= 0.75:
        return "CONDITIONAL_GO"
    return "NO_GO"
