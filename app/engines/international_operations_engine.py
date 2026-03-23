from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.international_repository import InternationalProjectRepository
from app.models import (
    InternationalCountryProfile,
    InternationalKpiTarget,
    InternationalMilestone,
    InternationalProjectListItem,
    InternationalProjectListResponse,
    InternationalProjectReportResponse,
    InternationalProjectRequest,
    InternationalProjectStoredResponse,
    InternationalRiskItem,
    InternationalServicePlaybookItem,
)

_ALLOWED_SERVICES = {"management", "consulting", "installation", "import_export"}

_COUNTRY_ALIASES = {
    "TUR": "TR",
    "USA": "US",
    "DEU": "DE",
    "GBR": "GB",
    "FRA": "FR",
    "ITA": "IT",
    "ESP": "ES",
    "NLD": "NL",
    "ARE": "AE",
    "SAU": "SA",
    "QAT": "QA",
    "CHN": "CN",
    "IND": "IN",
    "BRA": "BR",
    "RUS": "RU",
    "AZE": "AZ",
    "KAZ": "KZ",
    "EGY": "EG",
    "JPN": "JP",
    "KOR": "KR",
}


@dataclass(frozen=True)
class _CountryDefaults:
    name: str
    market: float
    complexity: float
    trade: float
    compliance: float


_COUNTRY_DEFAULTS: dict[str, _CountryDefaults] = {
    "TR": _CountryDefaults("Turkey", 72, 58, 68, 62),
    "US": _CountryDefaults("United States", 90, 55, 84, 78),
    "DE": _CountryDefaults("Germany", 85, 57, 82, 81),
    "GB": _CountryDefaults("United Kingdom", 82, 56, 79, 78),
    "FR": _CountryDefaults("France", 80, 59, 76, 77),
    "IT": _CountryDefaults("Italy", 77, 61, 73, 72),
    "ES": _CountryDefaults("Spain", 76, 57, 72, 73),
    "NL": _CountryDefaults("Netherlands", 79, 52, 86, 82),
    "AE": _CountryDefaults("United Arab Emirates", 81, 50, 83, 75),
    "SA": _CountryDefaults("Saudi Arabia", 78, 60, 74, 69),
    "QA": _CountryDefaults("Qatar", 74, 52, 73, 71),
    "CN": _CountryDefaults("China", 92, 72, 88, 60),
    "IN": _CountryDefaults("India", 86, 69, 74, 58),
    "BR": _CountryDefaults("Brazil", 79, 67, 70, 57),
    "RU": _CountryDefaults("Russia", 74, 78, 61, 45),
    "AZ": _CountryDefaults("Azerbaijan", 66, 56, 63, 61),
    "KZ": _CountryDefaults("Kazakhstan", 69, 58, 64, 60),
    "EG": _CountryDefaults("Egypt", 70, 65, 66, 56),
    "JP": _CountryDefaults("Japan", 84, 57, 79, 80),
    "KR": _CountryDefaults("South Korea", 83, 55, 78, 79),
}


class InternationalOperationsEngine:
    def __init__(self, repo: InternationalProjectRepository) -> None:
        self._repo = repo

    def create_project(self, payload: InternationalProjectRequest) -> InternationalProjectStoredResponse:
        report = self._build_report(payload)
        normalized_targets = _normalize_countries(payload.target_countries)
        normalized_services = _normalize_services(payload.services)
        base_country = _normalize_country(payload.base_country)

        row = self._repo.create_project(
            project_name=payload.project_name,
            company_name=payload.company_name,
            base_country=base_country,
            target_countries=normalized_targets,
            services=normalized_services,
            budget_total=payload.budget_total,
            currency=payload.currency.upper(),
            timeline_months=payload.timeline_months,
            payload=payload.model_dump(),
            report=report.model_dump(),
            status="generated",
        )
        return self._to_stored_response(row)

    def list_projects(
        self,
        *,
        limit: int = 100,
        status: str | None = None,
        country: str | None = None,
    ) -> InternationalProjectListResponse:
        normalized_country = _normalize_country(country) if country else None
        rows = self._repo.list_projects(limit=limit, status=status, country=normalized_country)
        return InternationalProjectListResponse(
            total=len(rows),
            items=[InternationalProjectListItem(**row) for row in rows],
        )

    def get_project(self, project_id: int) -> InternationalProjectStoredResponse:
        row = self._repo.get_project(project_id)
        return self._to_stored_response(row)

    def _build_report(self, payload: InternationalProjectRequest) -> InternationalProjectReportResponse:
        target_countries = _normalize_countries(payload.target_countries)
        services = _normalize_services(payload.services)
        base_country = _normalize_country(payload.base_country)
        country_profiles = self._build_country_profiles(target_countries, services, payload)
        budget_allocation = self._build_budget_allocation(country_profiles, payload.budget_total)
        service_playbook = self._build_service_playbook(services)
        implementation_plan = self._build_implementation_plan(payload.timeline_months)
        risk_register = self._build_risk_register(payload, country_profiles, services)
        kpi_targets = self._build_kpis(payload, services)
        trade_operating_model = self._build_trade_operating_model(payload, services)
        governance_model = self._build_governance_model(payload, services)
        execution_checklist = self._build_execution_checklist(payload, services)

        recommendation, confidence = self._recommendation_and_confidence(
            payload=payload,
            country_profiles=country_profiles,
            services=services,
        )
        executive_summary = self._build_executive_summary(
            payload=payload,
            services=services,
            recommendation=recommendation,
            confidence=confidence,
            country_profiles=country_profiles,
        )
        report_markdown = self._build_markdown(
            payload=payload,
            base_country=base_country,
            target_countries=target_countries,
            services=services,
            recommendation=recommendation,
            confidence=confidence,
            executive_summary=executive_summary,
            budget_allocation=budget_allocation,
            country_profiles=country_profiles,
            service_playbook=service_playbook,
            trade_operating_model=trade_operating_model,
            implementation_plan=implementation_plan,
            risk_register=risk_register,
            kpi_targets=kpi_targets,
            governance_model=governance_model,
            execution_checklist=execution_checklist,
        )

        return InternationalProjectReportResponse(
            generated_at=datetime.now(timezone.utc).isoformat(),
            project_name=payload.project_name,
            company_name=payload.company_name,
            base_country=base_country,
            target_countries=target_countries,
            services=services,
            executive_summary=executive_summary,
            recommendation=recommendation,
            confidence=confidence,
            budget_allocation=budget_allocation,
            country_profiles=country_profiles,
            service_playbook=service_playbook,
            trade_operating_model=trade_operating_model,
            implementation_plan=implementation_plan,
            risk_register=risk_register,
            kpi_targets=kpi_targets,
            governance_model=governance_model,
            execution_checklist=execution_checklist,
            report_markdown=report_markdown,
            disclaimer=(
                "Decision-support output only. Country-specific legal, tax, customs, and sector regulations "
                "must be validated by licensed local advisors before execution."
            ),
        )

    @staticmethod
    def _build_country_profiles(
        target_countries: list[str],
        services: list[str],
        payload: InternationalProjectRequest,
    ) -> list[InternationalCountryProfile]:
        risk_level = payload.risk_appetite.upper()
        results: list[InternationalCountryProfile] = []

        for code in target_countries:
            defaults = _COUNTRY_DEFAULTS.get(code, _CountryDefaults(code, 65, 62, 61, 55))
            entry_model = _recommended_entry_model(services, defaults.complexity, payload.local_partner_required)
            documents = _required_documents_for_country(services)
            priorities = _country_priorities(services)

            profile = InternationalCountryProfile(
                country_code=code,
                country_name=defaults.name,
                market_potential_score=round(defaults.market, 2),
                operational_complexity_score=round(defaults.complexity, 2),
                trade_readiness_score=round(defaults.trade, 2),
                compliance_readiness_score=round(defaults.compliance, 2),
                recommended_entry_model=entry_model,
                top_priorities=priorities,
                required_documents=documents,
                risk_level="HIGH" if defaults.complexity >= 70 else ("MEDIUM" if defaults.complexity >= 56 else "LOW"),
            )
            if risk_level == "LOW" and profile.risk_level == "HIGH":
                profile.risk_level = "HIGH"
            results.append(profile)
        return results

    @staticmethod
    def _build_budget_allocation(country_profiles: list[InternationalCountryProfile], total_budget: float) -> dict[str, float]:
        if not country_profiles:
            return {}
        weights: dict[str, float] = {}
        for item in country_profiles:
            weight = (
                item.market_potential_score * 0.45
                + item.trade_readiness_score * 0.30
                + (100 - item.operational_complexity_score) * 0.25
            )
            weights[item.country_code] = max(weight, 1.0)

        total_weight = sum(weights.values())
        if total_weight <= 0:
            return {}
        output: dict[str, float] = {}
        for code, weight in weights.items():
            output[code] = round(total_budget * (weight / total_weight), 2)
        return output

    @staticmethod
    def _build_service_playbook(services: list[str]) -> list[InternationalServicePlaybookItem]:
        playbook: list[InternationalServicePlaybookItem] = []
        for service in services:
            if service == "management":
                playbook.append(
                    InternationalServicePlaybookItem(
                        service=service,
                        operating_model="Regional PMO with country-level execution leads",
                        key_deliverables=[
                            "Governance charter and RACI",
                            "Country rollout control tower",
                            "Weekly KPI and risk steering",
                        ],
                        capability_requirements=[
                            "Program governance",
                            "Cross-border planning",
                            "Financial control",
                        ],
                        expected_margin_band="12%-18%",
                    )
                )
            elif service == "consulting":
                playbook.append(
                    InternationalServicePlaybookItem(
                        service=service,
                        operating_model="Central expert pool + local domain advisors",
                        key_deliverables=[
                            "Market entry strategy",
                            "Regulatory and tax advisory package",
                            "Operating model and transformation roadmap",
                        ],
                        capability_requirements=[
                            "Sector experts",
                            "Regulatory analysis",
                            "Change management",
                        ],
                        expected_margin_band="20%-35%",
                    )
                )
            elif service == "installation":
                playbook.append(
                    InternationalServicePlaybookItem(
                        service=service,
                        operating_model="Prime contractor + certified local installation partners",
                        key_deliverables=[
                            "Site survey and design freeze",
                            "Commissioning and acceptance tests",
                            "HSE and quality assurance dossier",
                        ],
                        capability_requirements=[
                            "Field engineering",
                            "HSE compliance",
                            "Commissioning management",
                        ],
                        expected_margin_band="10%-16%",
                    )
                )
            elif service == "import_export":
                playbook.append(
                    InternationalServicePlaybookItem(
                        service=service,
                        operating_model="Trade desk + customs broker network + logistics orchestrator",
                        key_deliverables=[
                            "HS classification and customs workflow",
                            "Incoterms and transport plan",
                            "Trade finance and payment security setup",
                        ],
                        capability_requirements=[
                            "Customs operations",
                            "Trade compliance",
                            "Supply chain control",
                        ],
                        expected_margin_band="8%-14%",
                    )
                )
        return playbook

    @staticmethod
    def _build_implementation_plan(timeline_months: int) -> list[InternationalMilestone]:
        phase1_end = min(2, timeline_months)
        phase2_end = min(max(phase1_end + 1, timeline_months // 3), timeline_months)
        phase3_end = min(max(phase2_end + 1, int(round(timeline_months * 0.6))), timeline_months)
        phase4_end = min(max(phase3_end + 1, int(round(timeline_months * 0.8))), timeline_months)
        return [
            InternationalMilestone(
                phase="Phase 1 - Mobilization",
                month_start=1,
                month_end=phase1_end,
                deliverable="Portfolio charter, country prioritization, and governance baseline.",
                owner="Executive Sponsor",
            ),
            InternationalMilestone(
                phase="Phase 2 - Country Due Diligence",
                month_start=min(phase1_end, phase2_end),
                month_end=phase2_end,
                deliverable="Country-specific legal, tax, partner, and market due diligence packs.",
                owner="Country Strategy Lead",
            ),
            InternationalMilestone(
                phase="Phase 3 - Trade and Setup",
                month_start=min(phase2_end, phase3_end),
                month_end=phase3_end,
                deliverable="Entity/partner setup, trade lanes activation, and compliance controls.",
                owner="Legal and Trade Lead",
            ),
            InternationalMilestone(
                phase="Phase 4 - Pilot Execution",
                month_start=min(phase3_end, phase4_end),
                month_end=phase4_end,
                deliverable="Pilot delivery in priority countries with KPI and SLA tracking.",
                owner="Program Director",
            ),
            InternationalMilestone(
                phase="Phase 5 - Scale and Optimization",
                month_start=min(phase4_end, timeline_months),
                month_end=timeline_months,
                deliverable="Scaled multi-country operating model and margin optimization plan.",
                owner="Operations Director",
            ),
        ]

    @staticmethod
    def _build_risk_register(
        payload: InternationalProjectRequest,
        country_profiles: list[InternationalCountryProfile],
        services: list[str],
    ) -> list[InternationalRiskItem]:
        avg_complexity = (
            sum(item.operational_complexity_score for item in country_profiles) / len(country_profiles)
            if country_profiles
            else 60
        )
        avg_trade = (
            sum(item.trade_readiness_score for item in country_profiles) / len(country_profiles)
            if country_profiles
            else 60
        )
        regulatory_prob = "HIGH" if avg_complexity >= 68 else "MEDIUM"
        trade_prob = "HIGH" if ("import_export" in services and avg_trade < 65) else "MEDIUM"
        installation_prob = "HIGH" if ("installation" in services and payload.timeline_months < 10) else "MEDIUM"

        return [
            InternationalRiskItem(
                risk_id="IR-001",
                category="Regulatory",
                description="Country-specific licensing and compliance misalignment may delay launch.",
                probability=regulatory_prob,
                impact="HIGH",
                mitigation="Pre-entry legal review, country compliance checklist, and release gates.",
                owner="Legal and Compliance Lead",
            ),
            InternationalRiskItem(
                risk_id="IR-002",
                category="Trade",
                description="Customs process or documentation gaps may delay import/export flows.",
                probability=trade_prob,
                impact="HIGH",
                mitigation="HS code governance, customs broker SLA, and document pre-clearance.",
                owner="Trade Operations Manager",
            ),
            InternationalRiskItem(
                risk_id="IR-003",
                category="Financial",
                description="FX volatility and local inflation can erode margin and forecast reliability.",
                probability="HIGH" if payload.currency.upper() != "USD" else "MEDIUM",
                impact="MEDIUM",
                mitigation="FX hedge policy, monthly repricing, and scenario-based pricing controls.",
                owner="Finance Director",
            ),
            InternationalRiskItem(
                risk_id="IR-004",
                category="Partner",
                description="Local partner quality and execution inconsistency may impact SLA targets.",
                probability="MEDIUM",
                impact="MEDIUM",
                mitigation="Partner qualification scorecard and quarterly performance review.",
                owner="Country Operations Lead",
            ),
            InternationalRiskItem(
                risk_id="IR-005",
                category="Execution",
                description="Cross-border implementation coordination may create schedule slippage.",
                probability=installation_prob,
                impact="MEDIUM",
                mitigation="Critical path controls, integrated PMO cadence, and issue escalation protocol.",
                owner="Program Manager",
            ),
            InternationalRiskItem(
                risk_id="IR-006",
                category="Commercial",
                description="Customer collection delays can increase working capital pressure.",
                probability="MEDIUM",
                impact="MEDIUM",
                mitigation="Advance payment clauses, trade finance instruments, and credit screening.",
                owner="Commercial Director",
            ),
        ]

    @staticmethod
    def _build_kpis(payload: InternationalProjectRequest, services: list[str]) -> list[InternationalKpiTarget]:
        targets = [
            InternationalKpiTarget(
                metric="Country launch readiness",
                target=">= 90% mandatory checklist completion before go-live",
                period="Monthly",
                owner="PMO",
            ),
            InternationalKpiTarget(
                metric="Gross margin",
                target=">= 18% blended margin",
                period="Monthly",
                owner="Finance",
            ),
            InternationalKpiTarget(
                metric="On-time delivery",
                target=">= 92% project milestone adherence",
                period="Monthly",
                owner="Operations",
            ),
            InternationalKpiTarget(
                metric="Compliance incidents",
                target="0 critical compliance breach",
                period="Quarterly",
                owner="Compliance",
            ),
        ]
        if "import_export" in services:
            targets.append(
                InternationalKpiTarget(
                    metric="Customs clearance lead time",
                    target="<= 72 hours average",
                    period="Monthly",
                    owner="Trade Operations",
                )
            )
        if "installation" in services:
            targets.append(
                InternationalKpiTarget(
                    metric="Commissioning first-pass success",
                    target=">= 95%",
                    period="Monthly",
                    owner="Engineering",
                )
            )
        if payload.timeline_months >= 12:
            targets.append(
                InternationalKpiTarget(
                    metric="Year-1 revenue realization",
                    target=">= 85% of plan",
                    period="Quarterly",
                    owner="Country GM",
                )
            )
        return targets

    @staticmethod
    def _build_trade_operating_model(payload: InternationalProjectRequest, services: list[str]) -> list[str]:
        model = [
            "Establish country-level compliance gate before every commercial commitment.",
            "Apply sanctions/denied-party screening for all counterparties and intermediaries.",
            "Use contract templates with jurisdiction, arbitration, and liability clauses.",
            "Operate centralized document control for legal, customs, tax, and technical evidence.",
        ]
        if "import_export" in services:
            terms = [term.strip().upper() for term in payload.preferred_incoterms if term.strip()]
            if terms:
                model.append(f"Preferred Incoterms matrix active: {', '.join(terms[:6])}.")
            model.append("Define importer/exporter of record responsibilities per country and product group.")
            model.append("Run HS code governance with periodic revalidation to avoid customs penalty exposure.")
        return model

    @staticmethod
    def _build_governance_model(payload: InternationalProjectRequest, services: list[str]) -> list[str]:
        governance = [
            "Executive steering committee: monthly strategic and financial decisions.",
            "Program management office: weekly schedule, cost, and risk control cadence.",
            "Country operations board: local execution blockers and regulatory actions.",
            "Audit and compliance board: quarterly control and evidence review.",
        ]
        if payload.local_partner_required or "installation" in services:
            governance.append("Partner governance council: SLA scorecard, issue log, and remediation plan.")
        return governance

    @staticmethod
    def _build_execution_checklist(payload: InternationalProjectRequest, services: list[str]) -> list[str]:
        checklist = [
            "Country entry legal and tax assessment completed.",
            "Customer contract templates validated for all target jurisdictions.",
            "Financial controls and approval matrix activated.",
            "Program-level KPI dashboard and risk dashboard published.",
            "Business continuity and incident response process validated.",
        ]
        if "consulting" in services:
            checklist.append("Consulting methodology and QA framework approved.")
        if "installation" in services:
            checklist.append("HSE documentation and field commissioning protocol approved.")
        if "import_export" in services:
            checklist.append("Customs broker contracts and shipping SOPs signed.")
        if payload.strategic_objectives:
            checklist.append("Strategic objective traceability matrix linked to KPI set.")
        return checklist

    @staticmethod
    def _recommendation_and_confidence(
        *,
        payload: InternationalProjectRequest,
        country_profiles: list[InternationalCountryProfile],
        services: list[str],
    ) -> tuple[str, float]:
        avg_market = (
            sum(item.market_potential_score for item in country_profiles) / len(country_profiles)
            if country_profiles
            else 60
        )
        avg_trade = (
            sum(item.trade_readiness_score for item in country_profiles) / len(country_profiles)
            if country_profiles
            else 60
        )
        avg_complexity = (
            sum(item.operational_complexity_score for item in country_profiles) / len(country_profiles)
            if country_profiles
            else 60
        )
        avg_compliance = (
            sum(item.compliance_readiness_score for item in country_profiles) / len(country_profiles)
            if country_profiles
            else 60
        )

        score = (
            avg_market * 0.40
            + avg_trade * 0.25
            + avg_compliance * 0.15
            + (100 - avg_complexity) * 0.20
        )
        score += min(len(services) * 1.5, 6.0)

        if payload.local_partner_required:
            score += 1.5
        if payload.timeline_months < 8 and "installation" in services:
            score -= 5.0
        if "import_export" in services and not payload.trade_lanes:
            score -= 4.0
        if not payload.strategic_objectives:
            score -= 3.0

        risk_penalty = {"low": 4.0, "medium": 2.0, "high": 0.0}[payload.risk_appetite]
        score -= risk_penalty

        if score >= 66:
            recommendation = "GO"
        elif score >= 52:
            recommendation = "CONDITIONAL_GO"
        else:
            recommendation = "NO_GO"

        confidence = 0.56
        if payload.sectors:
            confidence += 0.06
        if payload.strategic_objectives:
            confidence += 0.06
        if payload.notes.strip():
            confidence += 0.04
        if payload.trade_lanes:
            confidence += 0.04
        if payload.preferred_incoterms:
            confidence += 0.03
        if len(country_profiles) <= 6:
            confidence += 0.03
        if payload.timeline_months >= 12:
            confidence += 0.03
        if recommendation == "NO_GO":
            confidence -= 0.03
        confidence = max(0.50, min(0.95, confidence))
        return recommendation, round(confidence, 2)

    @staticmethod
    def _build_executive_summary(
        *,
        payload: InternationalProjectRequest,
        services: list[str],
        recommendation: str,
        confidence: float,
        country_profiles: list[InternationalCountryProfile],
    ) -> str:
        avg_market = (
            sum(item.market_potential_score for item in country_profiles) / len(country_profiles)
            if country_profiles
            else 0
        )
        avg_complexity = (
            sum(item.operational_complexity_score for item in country_profiles) / len(country_profiles)
            if country_profiles
            else 0
        )
        return (
            f"{payload.company_name} international expansion program evaluated for services "
            f"{', '.join(services)} across {len(country_profiles)} country(ies). "
            f"Recommendation={recommendation} with confidence={confidence:.2f}. "
            f"Average market potential={avg_market:.1f}/100 and complexity={avg_complexity:.1f}/100. "
            f"Total budget={payload.budget_total:.2f} {payload.currency.upper()} over {payload.timeline_months} months."
        )

    @staticmethod
    def _build_markdown(
        *,
        payload: InternationalProjectRequest,
        base_country: str,
        target_countries: list[str],
        services: list[str],
        recommendation: str,
        confidence: float,
        executive_summary: str,
        budget_allocation: dict[str, float],
        country_profiles: list[InternationalCountryProfile],
        service_playbook: list[InternationalServicePlaybookItem],
        trade_operating_model: list[str],
        implementation_plan: list[InternationalMilestone],
        risk_register: list[InternationalRiskItem],
        kpi_targets: list[InternationalKpiTarget],
        governance_model: list[str],
        execution_checklist: list[str],
    ) -> str:
        lines: list[str] = []
        lines.append("# International Project Development Report")
        lines.append("")
        lines.append(f"Project: **{payload.project_name}**")
        lines.append(f"Company: **{payload.company_name}**")
        lines.append(f"Base country: **{base_country}**")
        lines.append(f"Target countries: **{', '.join(target_countries)}**")
        lines.append(f"Services: **{', '.join(services)}**")
        lines.append(f"Recommendation: **{recommendation}** | Confidence: **{confidence:.2f}**")
        lines.append("")
        lines.append("## Executive Summary")
        lines.append(executive_summary)
        lines.append("")
        lines.append("## Budget Allocation")
        lines.append("| Country | Budget |")
        lines.append("|---|---:|")
        for code, amount in budget_allocation.items():
            lines.append(f"| {code} | {amount:.2f} {payload.currency.upper()} |")
        lines.append("")
        lines.append("## Country Profiles")
        lines.append("| Country | Market | Complexity | Trade | Compliance | Entry Model | Risk |")
        lines.append("|---|---:|---:|---:|---:|---|---|")
        for item in country_profiles:
            lines.append(
                f"| {item.country_code} ({item.country_name}) | {item.market_potential_score:.1f} | "
                f"{item.operational_complexity_score:.1f} | {item.trade_readiness_score:.1f} | "
                f"{item.compliance_readiness_score:.1f} | {item.recommended_entry_model} | {item.risk_level} |"
            )
        lines.append("")
        lines.append("## Service Playbook")
        for item in service_playbook:
            lines.append(f"### {item.service}")
            lines.append(f"- Operating model: {item.operating_model}")
            lines.append(f"- Expected margin: {item.expected_margin_band}")
            lines.append(f"- Key deliverables: {', '.join(item.key_deliverables)}")
            lines.append(f"- Capabilities: {', '.join(item.capability_requirements)}")
            lines.append("")
        lines.append("## Trade Operating Model")
        for row in trade_operating_model:
            lines.append(f"- {row}")
        lines.append("")
        lines.append("## Implementation Plan")
        lines.append("| Phase | Start | End | Deliverable | Owner |")
        lines.append("|---|---:|---:|---|---|")
        for row in implementation_plan:
            lines.append(
                f"| {row.phase} | {row.month_start} | {row.month_end} | {row.deliverable} | {row.owner} |"
            )
        lines.append("")
        lines.append("## Risk Register")
        lines.append("| ID | Category | Probability | Impact | Mitigation | Owner |")
        lines.append("|---|---|---|---|---|---|")
        for risk in risk_register:
            lines.append(
                f"| {risk.risk_id} | {risk.category} | {risk.probability} | {risk.impact} | "
                f"{risk.mitigation} | {risk.owner} |"
            )
        lines.append("")
        lines.append("## KPI Targets")
        lines.append("| Metric | Target | Period | Owner |")
        lines.append("|---|---|---|---|")
        for item in kpi_targets:
            lines.append(f"| {item.metric} | {item.target} | {item.period} | {item.owner} |")
        lines.append("")
        lines.append("## Governance Model")
        for row in governance_model:
            lines.append(f"- {row}")
        lines.append("")
        lines.append("## Execution Checklist")
        for row in execution_checklist:
            lines.append(f"- {row}")
        return "\n".join(lines)

    @staticmethod
    def _to_stored_response(row: dict) -> InternationalProjectStoredResponse:
        report = InternationalProjectReportResponse(**(row.get("report") or {}))
        return InternationalProjectStoredResponse(
            id=int(row["id"]),
            project_name=str(row["project_name"]),
            company_name=str(row["company_name"]),
            base_country=str(row["base_country"]),
            status=str(row["status"]),
            created_at=int(row["created_at"]),
            updated_at=int(row["updated_at"]),
            request_payload=dict(row.get("payload") or {}),
            report=report,
        )


def _normalize_country(raw: str | None) -> str:
    if raw is None:
        raise ValueError("Country value is required")
    code = raw.strip().upper()
    if not code:
        raise ValueError("Country value is required")
    if code in _COUNTRY_ALIASES:
        code = _COUNTRY_ALIASES[code]
    if len(code) not in (2, 3):
        raise ValueError(f"Invalid country code: {raw}")
    return code


def _normalize_countries(countries: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for raw in countries:
        code = _normalize_country(raw)
        if code in seen:
            continue
        seen.add(code)
        output.append(code)
    if not output:
        raise ValueError("At least one target country is required")
    return output


def _normalize_services(services: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for raw in services:
        normalized = raw.strip().lower().replace("-", "_").replace(" ", "_")
        if not normalized:
            continue
        if normalized not in _ALLOWED_SERVICES:
            raise ValueError(f"Unsupported service: {raw}")
        if normalized in seen:
            continue
        seen.add(normalized)
        output.append(normalized)
    if not output:
        raise ValueError("At least one service is required")
    return output


def _recommended_entry_model(services: list[str], complexity: float, local_partner_required: bool) -> str:
    if "installation" in services:
        if complexity >= 65:
            return "Local JV + Certified EPC partner"
        return "Prime contractor + local installation subcontractors"
    if "import_export" in services:
        if local_partner_required or complexity >= 60:
            return "Master distributor + customs broker network"
        return "Direct trade desk + 3PL logistics model"
    if "management" in services and "consulting" in services:
        return "Regional advisory hub + in-country partner offices"
    if "consulting" in services:
        return "Country advisory partners + central expert office"
    return "Representative office + strategic partner ecosystem"


def _required_documents_for_country(services: list[str]) -> list[str]:
    docs = [
        "Tax registration and legal entity documents",
        "Contract and signature authority package",
        "Country-specific compliance declaration set",
    ]
    if "import_export" in services:
        docs.extend(
            [
                "Commercial invoice and packing list",
                "Certificate of origin",
                "HS classification and customs declaration",
            ]
        )
    if "installation" in services:
        docs.extend(
            [
                "Site HSE and work permit package",
                "Installation QA/QC and commissioning protocols",
            ]
        )
    return docs


def _country_priorities(services: list[str]) -> list[str]:
    priorities = [
        "Regulatory mapping and local legal validation",
        "Partner shortlist and due diligence",
        "Country KPI baseline and reporting cadence",
    ]
    if "import_export" in services:
        priorities.append("Customs lane validation and trade finance controls")
    if "installation" in services:
        priorities.append("Field resource and commissioning readiness plan")
    return priorities
