from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math

from app.engines.market_data_engine import MarketDataEngine
from app.feasibility_repository import FeasibilityRepository
from app.models import (
    FeasibilityCoverageItem,
    FeasibilityFinancialMetrics,
    FeasibilityKpiTarget,
    FeasibilityMilestone,
    FeasibilityReportListItem,
    FeasibilityReportListResponse,
    FeasibilityReportRequest,
    FeasibilityReportResponse,
    FeasibilityReportStoredResponse,
    FeasibilityRiskItem,
    FeasibilityScenarioRow,
    FeasibilitySensitivityItem,
)


@dataclass(frozen=True)
class _SectorDefaults:
    revenue_growth_shift: float
    opex_growth_shift: float
    risk_multiplier: float
    margin_target: float


_SECTOR_DEFAULTS: dict[str, _SectorDefaults] = {
    "energy": _SectorDefaults(0.01, 0.02, 1.18, 0.24),
    "healthcare": _SectorDefaults(0.03, 0.01, 1.05, 0.26),
    "manufacturing": _SectorDefaults(0.0, 0.02, 1.12, 0.2),
    "retail": _SectorDefaults(0.02, 0.03, 1.15, 0.16),
    "fintech": _SectorDefaults(0.04, 0.015, 1.2, 0.3),
    "logistics": _SectorDefaults(0.015, 0.025, 1.1, 0.18),
    "construction": _SectorDefaults(0.0, 0.03, 1.16, 0.19),
    "telecom": _SectorDefaults(0.02, 0.015, 1.08, 0.23),
    "education": _SectorDefaults(0.02, 0.015, 1.02, 0.21),
    "agriculture": _SectorDefaults(0.01, 0.025, 1.17, 0.2),
    "tourism": _SectorDefaults(0.03, 0.03, 1.14, 0.19),
    "software": _SectorDefaults(0.05, 0.01, 1.07, 0.34),
}


class FeasibilityEngine:
    def __init__(
        self,
        repo: FeasibilityRepository,
        market_engine: MarketDataEngine | None = None,
    ) -> None:
        self._repo = repo
        self._market_engine = market_engine

    def generate(self, payload: FeasibilityReportRequest) -> FeasibilityReportStoredResponse:
        report = self._build_report(payload)
        row = self._repo.create_report(
            project_name=payload.project_name,
            sector=payload.sector,
            geography=payload.geography,
            company_name=payload.company_name,
            payload=payload.model_dump(),
            report=report.model_dump(),
            status="generated",
        )
        return self._to_stored_response(row)

    def list_reports(
        self,
        *,
        limit: int = 100,
        sector: str | None = None,
        company_name: str | None = None,
    ) -> FeasibilityReportListResponse:
        rows = self._repo.list_reports(limit=limit, sector=sector, company_name=company_name)
        return FeasibilityReportListResponse(
            total=len(rows),
            items=[FeasibilityReportListItem(**row) for row in rows],
        )

    def get_report(self, report_id: int) -> FeasibilityReportStoredResponse:
        row = self._repo.get_report(report_id)
        return self._to_stored_response(row)

    def _build_report(self, payload: FeasibilityReportRequest) -> FeasibilityReportResponse:
        sector_defaults = self._resolve_sector_defaults(payload.sector)
        growth_base = payload.revenue_growth_base + sector_defaults.revenue_growth_shift
        growth_upside = payload.revenue_growth_upside + sector_defaults.revenue_growth_shift
        growth_downside = payload.revenue_growth_downside + (sector_defaults.revenue_growth_shift * 0.5)
        opex_base = payload.opex_growth_base + sector_defaults.opex_growth_shift

        base_eval = self._evaluate_scenario(
            payload=payload,
            scenario_name="BASE",
            revenue_growth=growth_base,
            opex_growth=opex_base,
            revenue_multiplier=1.0,
            opex_multiplier=1.0,
        )
        upside_eval = self._evaluate_scenario(
            payload=payload,
            scenario_name="UPSIDE",
            revenue_growth=growth_upside,
            opex_growth=max(0.0, opex_base - 0.02),
            revenue_multiplier=1.08,
            opex_multiplier=0.97,
        )
        downside_eval = self._evaluate_scenario(
            payload=payload,
            scenario_name="DOWNSIDE",
            revenue_growth=growth_downside,
            opex_growth=opex_base + 0.03,
            revenue_multiplier=0.9,
            opex_multiplier=1.08,
        )

        scenarios = [
            FeasibilityScenarioRow(**base_eval),
            FeasibilityScenarioRow(**upside_eval),
            FeasibilityScenarioRow(**downside_eval),
        ]
        financial_metrics = FeasibilityFinancialMetrics(
            npv=base_eval["npv"],
            irr=base_eval["irr"],
            payback_year=base_eval["payback_year"],
            break_even_revenue=base_eval["break_even_revenue"],
            profitability_index=base_eval["profitability_index"],
            average_ebitda_margin=base_eval["average_ebitda_margin"],
        )

        sensitivity = self._build_sensitivity(payload, base_eval)
        risk_register = self._build_risk_register(payload, sector_defaults)
        implementation = self._build_implementation_plan(payload)
        procurement_checklist = self._build_procurement_checklist(payload)
        compliance_checklist = self._build_compliance_checklist(payload)
        kpis = self._build_kpi_targets(payload, financial_metrics, sector_defaults)
        assumptions = self._build_assumptions(payload, sector_defaults)
        benchmark_note = self._benchmark_note(payload.benchmark_symbols)
        if benchmark_note:
            assumptions.append(benchmark_note)

        coverage = self._build_coverage()
        recommendation, confidence = self._recommendation_and_confidence(
            payload=payload,
            base_eval=base_eval,
            downside_eval=downside_eval,
            risk_register=risk_register,
            sector_defaults=sector_defaults,
        )
        executive_summary = self._build_executive_summary(
            payload=payload,
            recommendation=recommendation,
            confidence=confidence,
            financial_metrics=financial_metrics,
            downside_npv=downside_eval["npv"],
        )
        report_markdown = self._build_markdown(
            payload=payload,
            executive_summary=executive_summary,
            recommendation=recommendation,
            confidence=confidence,
            scenarios=scenarios,
            financial_metrics=financial_metrics,
            sensitivity=sensitivity,
            risk_register=risk_register,
            implementation=implementation,
            procurement_checklist=procurement_checklist,
            compliance_checklist=compliance_checklist,
            kpis=kpis,
            assumptions=assumptions,
        )

        return FeasibilityReportResponse(
            generated_at=datetime.now(timezone.utc).isoformat(),
            project_name=payload.project_name,
            sector=payload.sector,
            geography=payload.geography,
            executive_summary=executive_summary,
            recommendation=recommendation,
            confidence=confidence,
            scenarios=scenarios,
            financial_metrics=financial_metrics,
            sensitivity_analysis=sensitivity,
            risk_register=risk_register,
            implementation_plan=implementation,
            procurement_checklist=procurement_checklist,
            compliance_checklist=compliance_checklist,
            kpi_targets=kpis,
            coverage=coverage,
            assumptions=assumptions,
            report_markdown=report_markdown,
            disclaimer=(
                "This feasibility output is a decision-support artifact. "
                "Final investment, legal, and compliance decisions must be validated by domain professionals."
            ),
        )

    @staticmethod
    def _resolve_sector_defaults(sector: str) -> _SectorDefaults:
        normalized = sector.strip().lower()
        for key, defaults in _SECTOR_DEFAULTS.items():
            if key in normalized:
                return defaults
        return _SectorDefaults(0.01, 0.015, 1.1, 0.22)

    def _evaluate_scenario(
        self,
        *,
        payload: FeasibilityReportRequest,
        scenario_name: str,
        revenue_growth: float,
        opex_growth: float,
        revenue_multiplier: float,
        opex_multiplier: float,
    ) -> dict[str, float | str | None]:
        years = payload.project_lifetime_years
        tax_rate = payload.tax_rate
        discount_rate = payload.discount_rate
        capex = payload.initial_investment
        annual_revenue = payload.annual_revenue_base * revenue_multiplier
        annual_opex = payload.annual_opex * opex_multiplier

        depreciation = capex / years
        year1_ramp = max(0.35, min(1.0, 1 - (payload.implementation_months / 24)))
        cashflows: list[float] = [-capex]
        yearly_revenues: list[float] = []
        yearly_opex: list[float] = []
        yearly_ebitda: list[float] = []

        for year in range(1, years + 1):
            rev = annual_revenue * ((1 + revenue_growth) ** (year - 1))
            if year == 1:
                rev *= year1_ramp
            rev *= payload.capacity_utilization

            opx = annual_opex * ((1 + opex_growth) ** (year - 1))
            ebitda = rev - opx
            ebit = ebitda - depreciation
            tax = max(0.0, ebit) * tax_rate
            fcf = ebit - tax + depreciation

            yearly_revenues.append(rev)
            yearly_opex.append(opx)
            yearly_ebitda.append(ebitda)
            cashflows.append(fcf)

        npv = _npv(discount_rate, cashflows)
        irr = _irr(cashflows)
        payback = _payback_year(cashflows)
        avg_revenue = sum(yearly_revenues) / years
        avg_opex = sum(yearly_opex) / years
        avg_ebitda = sum(yearly_ebitda) / years
        break_even_revenue = avg_opex + (capex / years)
        profitability_index = (npv + capex) / capex if capex > 0 else 0.0
        avg_ebitda_margin = (avg_ebitda / avg_revenue) if avg_revenue > 0 else 0.0

        return {
            "scenario": scenario_name,
            "annual_revenue": round(avg_revenue, 2),
            "annual_opex": round(avg_opex, 2),
            "annual_ebitda": round(avg_ebitda, 2),
            "npv": round(npv, 2),
            "irr": round(irr, 4) if irr is not None else None,
            "payback_year": round(payback, 2) if payback is not None else None,
            "break_even_revenue": round(break_even_revenue, 2),
            "profitability_index": round(profitability_index, 4),
            "average_ebitda_margin": round(avg_ebitda_margin, 4),
        }

    def _build_sensitivity(self, payload: FeasibilityReportRequest, base_eval: dict[str, float | str | None]) -> list[FeasibilitySensitivityItem]:
        baseline_npv = float(base_eval["npv"])
        checks = [
            ("Revenue", "-10%", dict(revenue_multiplier=0.9, opex_multiplier=1.0, implementation_delta=0)),
            ("Revenue", "+10%", dict(revenue_multiplier=1.1, opex_multiplier=1.0, implementation_delta=0)),
            ("OPEX", "+10%", dict(revenue_multiplier=1.0, opex_multiplier=1.1, implementation_delta=0)),
            ("OPEX", "-10%", dict(revenue_multiplier=1.0, opex_multiplier=0.9, implementation_delta=0)),
            ("CAPEX", "+10%", dict(capex_multiplier=1.1)),
            ("Implementation Delay", "+3 months", dict(revenue_multiplier=1.0, opex_multiplier=1.04, implementation_delta=3)),
        ]
        output: list[FeasibilitySensitivityItem] = []
        for factor, shock, params in checks:
            capex_multiplier = float(params.get("capex_multiplier", 1.0))
            implementation_delta = int(params.get("implementation_delta", 0))
            shifted_payload = payload.model_copy(
                update={
                    "initial_investment": payload.initial_investment * capex_multiplier,
                    "implementation_months": min(60, payload.implementation_months + implementation_delta),
                }
            )
            eval_row = self._evaluate_scenario(
                payload=shifted_payload,
                scenario_name="SENS",
                revenue_growth=payload.revenue_growth_base,
                opex_growth=payload.opex_growth_base,
                revenue_multiplier=float(params.get("revenue_multiplier", 1.0)),
                opex_multiplier=float(params.get("opex_multiplier", 1.0)),
            )
            npv_impact = float(eval_row["npv"]) - baseline_npv
            output.append(
                FeasibilitySensitivityItem(
                    factor=factor,
                    shock=shock,
                    npv_impact=round(npv_impact, 2),
                    note="Positive impact improves project value; negative impact increases feasibility risk.",
                )
            )
        return output

    @staticmethod
    def _build_risk_register(payload: FeasibilityReportRequest, sector_defaults: _SectorDefaults) -> list[FeasibilityRiskItem]:
        risk_scale = sector_defaults.risk_multiplier
        high_prob = "HIGH" if risk_scale >= 1.15 else "MEDIUM"
        debt_prob = "HIGH" if payload.financing_debt_ratio >= 0.7 else "MEDIUM"
        regulation_prob = "HIGH" if payload.regulatory_requirements else "MEDIUM"
        return [
            FeasibilityRiskItem(
                risk_id="R-001",
                category="Market",
                description="Demand volatility may reduce expected revenue realization.",
                probability=high_prob,
                impact="HIGH",
                mitigation="Staged launch, dynamic pricing, and monthly demand trigger review.",
                owner="Commercial Director",
            ),
            FeasibilityRiskItem(
                risk_id="R-002",
                category="Financial",
                description="Cost inflation may compress EBITDA margin.",
                probability="MEDIUM",
                impact="HIGH",
                mitigation="Supplier framework agreements and quarterly cost reset mechanism.",
                owner="Finance Director",
            ),
            FeasibilityRiskItem(
                risk_id="R-003",
                category="Execution",
                description="Implementation delay may postpone break-even timing.",
                probability="MEDIUM",
                impact="MEDIUM",
                mitigation="Phase-gate PMO governance with critical path buffer and vendor SLA penalties.",
                owner="PMO Lead",
            ),
            FeasibilityRiskItem(
                risk_id="R-004",
                category="Compliance",
                description="Regulatory or tender compliance non-conformity may block go-live.",
                probability=regulation_prob,
                impact="HIGH",
                mitigation="Pre-audit compliance checklist and legal gate before procurement commitment.",
                owner="Legal & Compliance",
            ),
            FeasibilityRiskItem(
                risk_id="R-005",
                category="Funding",
                description="Debt service burden can increase liquidity stress.",
                probability=debt_prob,
                impact="MEDIUM",
                mitigation="Debt covenant monitoring and DSCR threshold alerting.",
                owner="Treasury Lead",
            ),
        ]

    @staticmethod
    def _build_implementation_plan(payload: FeasibilityReportRequest) -> list[FeasibilityMilestone]:
        build_end = max(2, payload.implementation_months)
        optimize_end = payload.implementation_months + 6
        return [
            FeasibilityMilestone(
                phase="Phase 1 - Mobilization",
                month_start=1,
                month_end=2,
                deliverable="Detailed business case baseline, governance model, and success KPI framework.",
                gate="Executive investment gate",
            ),
            FeasibilityMilestone(
                phase="Phase 2 - Design & Procurement",
                month_start=2,
                month_end=build_end,
                deliverable="Technical design freeze, supplier shortlist, signed procurement packages.",
                gate="Design freeze and contract gate",
            ),
            FeasibilityMilestone(
                phase="Phase 3 - Build & Pilot",
                month_start=build_end,
                month_end=build_end + 4,
                deliverable="Pilot operation, operational readiness test, and risk burn-down.",
                gate="Pilot performance gate",
            ),
            FeasibilityMilestone(
                phase="Phase 4 - Scale & Optimize",
                month_start=build_end + 4,
                month_end=optimize_end,
                deliverable="Scale-up, benefit realization tracking, post-implementation optimization plan.",
                gate="Value realization gate",
            ),
        ]

    @staticmethod
    def _build_procurement_checklist(payload: FeasibilityReportRequest) -> list[str]:
        checklist = [
            "RFQ package finalized with measurable technical acceptance criteria.",
            "At least three qualified vendor quotations collected for key cost drivers.",
            "Weighted scoring matrix approved (price, quality, delivery, compliance, vendor reliability).",
            "Contract clauses include warranty, SLA, penalty, and change-order governance.",
            "Total procurement envelope aligned with approved CAPEX/OPEX budget.",
        ]
        if payload.regulatory_requirements:
            checklist.append("Regulatory/tender-specific procurement clauses cross-checked before PO issuance.")
        return checklist

    @staticmethod
    def _build_compliance_checklist(payload: FeasibilityReportRequest) -> list[str]:
        base = [
            "Tax and corporate compliance check completed.",
            "Data protection and information security obligations validated.",
            "Sector-specific licenses, permits, and reporting obligations mapped.",
            "Operational HSE and quality governance requirements confirmed.",
        ]
        for requirement in payload.regulatory_requirements[:8]:
            text = requirement.strip()
            if text:
                base.append(f"Regulatory requirement captured: {text}")
        return base

    @staticmethod
    def _build_kpi_targets(
        payload: FeasibilityReportRequest,
        financial_metrics: FeasibilityFinancialMetrics,
        sector_defaults: _SectorDefaults,
    ) -> list[FeasibilityKpiTarget]:
        return [
            FeasibilityKpiTarget(
                metric="Payback",
                target=f"<= {max(2, math.ceil(payload.project_lifetime_years * 0.7))} years",
                rationale="Aligns with capital discipline and liquidity resilience.",
            ),
            FeasibilityKpiTarget(
                metric="EBITDA Margin",
                target=f">= {sector_defaults.margin_target * 100:.0f}%",
                rationale="Sustains sector benchmark profitability and downside protection.",
            ),
            FeasibilityKpiTarget(
                metric="NPV",
                target="Positive under base scenario",
                rationale="Ensures value creation above cost of capital.",
            ),
            FeasibilityKpiTarget(
                metric="Feasibility Confidence",
                target=f">= {max(0.7, financial_metrics.average_ebitda_margin):.2f}",
                rationale="Combines data completeness and robustness of project economics.",
            ),
        ]

    @staticmethod
    def _build_coverage() -> list[FeasibilityCoverageItem]:
        topics = [
            "Market demand logic",
            "Revenue model",
            "Cost model",
            "CAPEX adequacy",
            "NPV/IRR/payback",
            "Break-even",
            "Scenario analysis",
            "Sensitivity analysis",
            "Risk register",
            "Implementation roadmap",
            "Procurement readiness",
            "Compliance readiness",
            "KPI target map",
        ]
        return [
            FeasibilityCoverageItem(
                topic=topic,
                status="COVERED",
                evidence="Included in structured section outputs and markdown report body.",
            )
            for topic in topics
        ]

    def _recommendation_and_confidence(
        self,
        *,
        payload: FeasibilityReportRequest,
        base_eval: dict[str, float | str | None],
        downside_eval: dict[str, float | str | None],
        risk_register: list[FeasibilityRiskItem],
        sector_defaults: _SectorDefaults,
    ) -> tuple[str, float]:
        npv = float(base_eval["npv"])
        irr = float(base_eval["irr"]) if base_eval["irr"] is not None else 0.0
        payback = float(base_eval["payback_year"]) if base_eval["payback_year"] is not None else 999.0
        downside_npv = float(downside_eval["npv"])
        avg_margin = float(base_eval["average_ebitda_margin"])

        score = 0
        if npv > 0:
            score += 2
        else:
            score -= 2
        if irr > payload.discount_rate:
            score += 1
        if payback <= (payload.project_lifetime_years * 0.75):
            score += 1
        if avg_margin >= sector_defaults.margin_target:
            score += 1
        if downside_npv < 0:
            score -= 1
        if payload.financing_debt_ratio > 0.75:
            score -= 1
        high_risk_count = sum(1 for item in risk_register if item.probability == "HIGH" and item.impact == "HIGH")
        if high_risk_count >= 2:
            score -= 1

        if score >= 3:
            recommendation = "GO"
        elif score >= 1:
            recommendation = "CONDITIONAL_GO"
        else:
            recommendation = "NO_GO"

        completeness = 0.62
        if payload.regulatory_requirements:
            completeness += 0.08
        if payload.constraints:
            completeness += 0.05
        if payload.benchmark_symbols:
            completeness += 0.05
        if payload.additional_notes.strip():
            completeness += 0.03
        if payload.implementation_months > 0:
            completeness += 0.04
        if payload.project_lifetime_years >= 3:
            completeness += 0.03

        robustness_bonus = 0.0
        if npv > 0:
            robustness_bonus += 0.04
        if downside_npv > 0:
            robustness_bonus += 0.04
        if irr > payload.discount_rate:
            robustness_bonus += 0.04
        confidence = max(0.45, min(0.97, completeness + robustness_bonus))
        return recommendation, round(confidence, 2)

    @staticmethod
    def _build_executive_summary(
        *,
        payload: FeasibilityReportRequest,
        recommendation: str,
        confidence: float,
        financial_metrics: FeasibilityFinancialMetrics,
        downside_npv: float,
    ) -> str:
        irr_text = "-" if financial_metrics.irr is None else f"{financial_metrics.irr * 100:.2f}%"
        payback_text = "-" if financial_metrics.payback_year is None else f"{financial_metrics.payback_year:.2f} year"
        return (
            f"{payload.project_name} feasibility for {payload.sector} in {payload.geography} evaluated with "
            f"multi-scenario financial and operational analysis. Recommendation: {recommendation}. "
            f"Base NPV={financial_metrics.npv:.2f} {payload.currency}, IRR={irr_text}, payback={payback_text}. "
            f"Downside NPV={downside_npv:.2f} {payload.currency}. Confidence={confidence:.2f}."
        )

    def _build_assumptions(self, payload: FeasibilityReportRequest, sector_defaults: _SectorDefaults) -> list[str]:
        assumptions = [
            f"Project lifetime={payload.project_lifetime_years} years with discount rate={payload.discount_rate:.2%}.",
            f"Baseline annual revenue={payload.annual_revenue_base:.2f} {payload.currency}, annual OPEX={payload.annual_opex:.2f} {payload.currency}.",
            f"Sector calibration uses risk multiplier={sector_defaults.risk_multiplier:.2f} and target margin={sector_defaults.margin_target:.2%}.",
            f"Implementation lead time={payload.implementation_months} month(s), capacity utilization={payload.capacity_utilization:.2%}.",
            f"Debt financing ratio={payload.financing_debt_ratio:.2%}, tax rate={payload.tax_rate:.2%}.",
        ]
        if payload.constraints:
            assumptions.append(f"Key constraints: {', '.join(payload.constraints[:6])}.")
        if payload.regulatory_requirements:
            assumptions.append("Regulatory constraints were embedded into compliance and procurement gates.")
        return assumptions

    def _benchmark_note(self, symbols: list[str]) -> str:
        if not symbols or self._market_engine is None:
            return ""
        try:
            analysis = self._market_engine.analyze_symbols(
                symbols=symbols[:8],
                days=220,
                refresh=False,
            )
        except Exception:
            return ""

        buy = sum(1 for item in analysis.items if item.signal == "BUY")
        sell = sum(1 for item in analysis.items if item.signal == "SELL")
        hold = sum(1 for item in analysis.items if item.signal == "HOLD")
        return (
            f"Benchmark symbol signals evaluated ({len(analysis.items)}): "
            f"BUY={buy}, SELL={sell}, HOLD={hold}."
        )

    @staticmethod
    def _build_markdown(
        *,
        payload: FeasibilityReportRequest,
        executive_summary: str,
        recommendation: str,
        confidence: float,
        scenarios: list[FeasibilityScenarioRow],
        financial_metrics: FeasibilityFinancialMetrics,
        sensitivity: list[FeasibilitySensitivityItem],
        risk_register: list[FeasibilityRiskItem],
        implementation: list[FeasibilityMilestone],
        procurement_checklist: list[str],
        compliance_checklist: list[str],
        kpis: list[FeasibilityKpiTarget],
        assumptions: list[str],
    ) -> str:
        lines: list[str] = []
        lines.append("# Feasibility Report")
        lines.append("")
        lines.append(f"Project: **{payload.project_name}**")
        lines.append(f"Sector: **{payload.sector}** | Geography: **{payload.geography}**")
        lines.append(f"Recommendation: **{recommendation}** | Confidence: **{confidence:.2f}**")
        lines.append("")
        lines.append("## Executive Summary")
        lines.append(executive_summary)
        lines.append("")
        lines.append("## Scenario Analysis")
        lines.append("| Scenario | Annual Revenue | Annual OPEX | Annual EBITDA | NPV | IRR | Payback (year) |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|")
        for row in scenarios:
            irr = "-" if row.irr is None else f"{row.irr * 100:.2f}%"
            payback = "-" if row.payback_year is None else f"{row.payback_year:.2f}"
            lines.append(
                f"| {row.scenario} | {row.annual_revenue:.2f} | {row.annual_opex:.2f} | {row.annual_ebitda:.2f} | "
                f"{row.npv:.2f} | {irr} | {payback} |"
            )
        lines.append("")
        lines.append("## Financial Metrics")
        irr = "-" if financial_metrics.irr is None else f"{financial_metrics.irr * 100:.2f}%"
        payback = "-" if financial_metrics.payback_year is None else f"{financial_metrics.payback_year:.2f}"
        lines.append(f"- NPV: {financial_metrics.npv:.2f} {payload.currency}")
        lines.append(f"- IRR: {irr}")
        lines.append(f"- Payback: {payback} year")
        lines.append(f"- Break-even Revenue: {financial_metrics.break_even_revenue:.2f} {payload.currency}")
        lines.append(f"- Profitability Index: {financial_metrics.profitability_index:.4f}")
        lines.append(f"- Average EBITDA Margin: {financial_metrics.average_ebitda_margin * 100:.2f}%")
        lines.append("")
        lines.append("## Sensitivity Analysis")
        lines.append("| Factor | Shock | NPV Impact | Note |")
        lines.append("|---|---|---:|---|")
        for item in sensitivity:
            lines.append(f"| {item.factor} | {item.shock} | {item.npv_impact:.2f} | {item.note} |")
        lines.append("")
        lines.append("## Risk Register")
        lines.append("| ID | Category | Probability | Impact | Mitigation | Owner |")
        lines.append("|---|---|---|---|---|---|")
        for risk in risk_register:
            lines.append(
                f"| {risk.risk_id} | {risk.category} | {risk.probability} | {risk.impact} | {risk.mitigation} | {risk.owner} |"
            )
        lines.append("")
        lines.append("## Implementation Plan")
        lines.append("| Phase | Start | End | Deliverable | Gate |")
        lines.append("|---|---:|---:|---|---|")
        for row in implementation:
            lines.append(
                f"| {row.phase} | {row.month_start} | {row.month_end} | {row.deliverable} | {row.gate} |"
            )
        lines.append("")
        lines.append("## Procurement Checklist")
        for item in procurement_checklist:
            lines.append(f"- {item}")
        lines.append("")
        lines.append("## Compliance Checklist")
        for item in compliance_checklist:
            lines.append(f"- {item}")
        lines.append("")
        lines.append("## KPI Targets")
        lines.append("| Metric | Target | Rationale |")
        lines.append("|---|---|---|")
        for item in kpis:
            lines.append(f"| {item.metric} | {item.target} | {item.rationale} |")
        lines.append("")
        lines.append("## Assumptions")
        for item in assumptions:
            lines.append(f"- {item}")
        return "\n".join(lines)

    @staticmethod
    def _to_stored_response(row: dict) -> FeasibilityReportStoredResponse:
        report_dict = row.get("report") or {}
        report = FeasibilityReportResponse(**report_dict)
        return FeasibilityReportStoredResponse(
            id=int(row["id"]),
            project_name=str(row["project_name"]),
            sector=str(row["sector"]),
            geography=str(row["geography"]),
            company_name=str(row.get("company_name") or ""),
            status=str(row["status"]),
            created_at=int(row["created_at"]),
            request_payload=dict(row.get("payload") or {}),
            report=report,
        )


def _npv(rate: float, cashflows: list[float]) -> float:
    total = 0.0
    for idx, value in enumerate(cashflows):
        total += value / ((1 + rate) ** idx)
    return total


def _irr(cashflows: list[float]) -> float | None:
    if not cashflows or all(value >= 0 for value in cashflows) or all(value <= 0 for value in cashflows):
        return None

    low = -0.95
    high = 3.0
    for _ in range(80):
        mid = (low + high) / 2
        value = _npv(mid, cashflows)
        if value > 0:
            low = mid
        else:
            high = mid
    result = (low + high) / 2
    if math.isnan(result) or math.isinf(result):
        return None
    return result


def _payback_year(cashflows: list[float]) -> float | None:
    cumulative = 0.0
    if not cashflows:
        return None
    for idx, value in enumerate(cashflows):
        cumulative += value
        if cumulative >= 0:
            if idx == 0:
                return 0.0
            prev = cumulative - value
            if value == 0:
                return float(idx)
            fraction = abs(prev) / value
            return max(0.0, idx - 1 + fraction)
    return None
