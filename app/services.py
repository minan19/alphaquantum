from app.models import AnalysisResult, Company, DashboardSummary, InsightItem


class AnalysisService:
    def analyze_company(self, company: Company) -> AnalysisResult:
        critical_stock = [
            item for item in company.inventory if item.quantity <= item.min_level
        ]

        stock_gap = sum(
            max(item.min_level - item.quantity, 0) for item in company.inventory
        )
        stock_risk = min(70, stock_gap * 8)
        balance_risk = 30 if company.balance < 0 else 0
        risk_score = min(100, stock_risk + balance_risk)

        status = "Riskli" if risk_score >= 50 else "Saglikli"
        if risk_score >= 70:
            action = "Acil stok ve nakit plani"
        elif risk_score >= 50:
            action = "Maliyet azalt ve stok tamamlama"
        else:
            action = "Yatirim yapilabilir"

        confidence = round(max(0.55, 1 - (risk_score / 180)), 2)
        trend = self._trend_for_balance(company.balance)

        return AnalysisResult(
            company=company.name,
            status=status,
            action=action,
            critical_stock=critical_stock,
            risk_score=risk_score,
            confidence=confidence,
            trend=trend,
        )

    def analyze_all(self, companies: list[Company]) -> list[AnalysisResult]:
        return [self.analyze_company(company) for company in companies]

    @staticmethod
    def _trend_for_balance(balance: float) -> str:
        if balance < 0:
            return "Dusus"
        if balance >= 100_000:
            return "Yukselis"
        return "Stabil"


class DashboardService:
    @staticmethod
    def build_summary(
        companies: list[Company],
        analyses: list[AnalysisResult] | None = None,
    ) -> DashboardSummary:
        critical_count = sum(
            1
            for company in companies
            for item in company.inventory
            if item.quantity <= item.min_level
        )
        total_balance = sum(company.balance for company in companies)
        risk_companies = 0
        if analyses is not None:
            risk_companies = sum(1 for analysis in analyses if analysis.status == "Riskli")
        return DashboardSummary(
            total_companies=len(companies),
            critical_items=critical_count,
            total_balance=total_balance,
            risk_companies=risk_companies,
        )

    @staticmethod
    def build_insights(analyses: list[AnalysisResult]) -> list[InsightItem]:
        ranked = sorted(analyses, key=lambda item: item.risk_score, reverse=True)
        insights: list[InsightItem] = []

        for analysis in ranked[:5]:
            severity = "HIGH" if analysis.risk_score >= 70 else "MEDIUM"
            if analysis.risk_score < 50:
                severity = "LOW"

            insights.append(
                InsightItem(
                    company=analysis.company,
                    severity=severity,
                    message=(
                        f"Risk score {analysis.risk_score}/100 with trend {analysis.trend}"
                    ),
                    action=analysis.action,
                    confidence=analysis.confidence,
                )
            )

        if not insights:
            insights.append(
                InsightItem(
                    company="System",
                    severity="INFO",
                    message="No company data found for analysis",
                    action="Load company data",
                    confidence=1.0,
                )
            )

        return insights
