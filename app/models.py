from pydantic import BaseModel, ConfigDict, Field


class InventoryItem(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1)
    quantity: int = Field(ge=0)
    min_level: int = Field(ge=0)


class Company(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1)
    balance: float
    inventory: list[InventoryItem] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    company: str
    status: str
    action: str
    critical_stock: list[InventoryItem]
    risk_score: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    trend: str


class LegacyAnalysisResult(BaseModel):
    company: str
    status: str
    action: str
    critical_stock: list[InventoryItem]


class UpdateResult(BaseModel):
    message: str
    companies: list[Company]


class LegacyUpdateResult(BaseModel):
    message: str


class HealthResponse(BaseModel):
    status: str
    environment: str
    company_count: int
    version: str


class DashboardSummary(BaseModel):
    total_companies: int
    critical_items: int
    total_balance: float
    risk_companies: int = 0


class InsightItem(BaseModel):
    company: str
    severity: str
    message: str
    action: str
    confidence: float = Field(ge=0, le=1)


class DashboardDataResponse(BaseModel):
    generated_at: str
    summary: DashboardSummary
    companies: list[Company]
    analyses: list[AnalysisResult]
    insights: list[InsightItem]


class CompanyOverviewItem(BaseModel):
    name: str
    balance: float
    inventory_items: int
    critical_items: int
    risk_level: str


class CompanyEngineResponse(BaseModel):
    total_companies: int
    companies: list[CompanyOverviewItem]


class InventoryCriticalItem(BaseModel):
    company: str
    item_name: str
    quantity: int
    min_level: int
    gap: int
    severity: str


class InventoryEngineResponse(BaseModel):
    total_critical_items: int
    items: list[InventoryCriticalItem]


class FinanceOverviewResponse(BaseModel):
    total_balance: float
    average_balance: float
    negative_balance_companies: int
    highest_balance_company: str | None = None
    lowest_balance_company: str | None = None
    health_status: str


class FinanceLedgerEntryCreateRequest(BaseModel):
    company: str = Field(min_length=1)
    entry_type: str = Field(pattern="^(income|expense)$")
    amount: float = Field(gt=0)
    category: str = Field(min_length=1)
    description: str = ""
    entry_date: str | None = None


class FinanceLedgerEntryRead(BaseModel):
    id: int
    company: str
    entry_type: str
    amount: float
    category: str
    description: str
    entry_date: str
    created_at: int


class FinanceLedgerResponse(BaseModel):
    total: int
    entries: list[FinanceLedgerEntryRead]


class FinanceCashflowResponse(BaseModel):
    company: str | None = None
    lookback_days: int
    total_income: float
    total_expense: float
    net_cashflow: float
    average_daily_net: float
    transaction_count: int


class FinanceForecastResponse(BaseModel):
    company: str | None = None
    lookback_days: int
    horizon_days: int
    baseline_balance: float
    projected_net_cashflow: float
    projected_balance: float
    confidence: float = Field(ge=0, le=1)
    model: str


class FinanceRecurringEntryCreateRequest(BaseModel):
    company: str = Field(min_length=1)
    entry_type: str = Field(pattern="^(income|expense)$")
    amount: float = Field(gt=0)
    category: str = Field(min_length=1)
    description: str = ""
    frequency: str = Field(pattern="^(weekly|monthly|quarterly|yearly)$")
    start_date: str
    end_date: str | None = None


class FinanceRecurringEntryRead(BaseModel):
    id: int
    company: str
    entry_type: str
    amount: float
    category: str
    description: str
    frequency: str
    start_date: str
    end_date: str | None = None
    last_generated_date: str | None = None
    is_active: bool
    created_at: int


class FinanceRecurringListResponse(BaseModel):
    total: int
    entries: list[FinanceRecurringEntryRead] = Field(default_factory=list)


class FinanceRecurringGenerateResponse(BaseModel):
    generated_count: int
    ledger_entry_ids: list[int] = Field(default_factory=list)
    message: str


class FinanceBudgetCreateRequest(BaseModel):
    company: str = Field(min_length=1)
    year: int = Field(ge=2000, le=2100)
    month: int | None = Field(default=None, ge=1, le=12)
    category: str = Field(min_length=1)
    entry_type: str = Field(pattern="^(income|expense)$")
    budget_amount: float = Field(ge=0)


class FinanceBudgetRead(BaseModel):
    id: int
    company: str
    year: int
    month: int | None = None
    category: str
    entry_type: str
    budget_amount: float
    created_at: int


class FinanceBudgetListResponse(BaseModel):
    total: int
    budgets: list[FinanceBudgetRead] = Field(default_factory=list)


class FinanceBudgetVsActualItem(BaseModel):
    category: str
    entry_type: str
    budget_amount: float
    actual_amount: float
    variance: float
    variance_pct: float
    status: str


class FinanceBudgetVsActualResponse(BaseModel):
    company: str | None = None
    year: int
    month: int | None = None
    items: list[FinanceBudgetVsActualItem] = Field(default_factory=list)
    total_budget_income: float
    total_budget_expense: float
    total_actual_income: float
    total_actual_expense: float
    net_budget: float
    net_actual: float
    net_variance: float


class MarketOHLCVBar(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class MarketOHLCVResponse(BaseModel):
    symbol: str
    timeframe: str
    source: str
    generated_at: str
    bars: list[MarketOHLCVBar]


class MarketIndicatorSet(BaseModel):
    trend: str
    rsi_14: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    macd_histogram: float | None = None


class MarketAnalysisResponse(BaseModel):
    symbol: str
    timeframe: str
    source: str
    as_of: str | None = None
    last_close: float | None = None
    indicators: MarketIndicatorSet
    signal: str
    confidence: float = Field(ge=0, le=1)
    rationale: str


class MarketSignalCard(BaseModel):
    symbol: str
    signal: str
    trend: str
    rsi_14: float | None = None
    macd_histogram: float | None = None
    confidence: float = Field(ge=0, le=1)
    last_close: float | None = None
    rationale: str


class MarketSignalsResponse(BaseModel):
    timeframe: str
    generated_at: str
    items: list[MarketSignalCard]


class MarketRefreshRequest(BaseModel):
    symbols: list[str] = Field(default_factory=list)
    timeframe: str = "1d"
    days: int = Field(default=180, ge=20, le=3650)


class MarketRefreshResponse(BaseModel):
    refreshed_count: int
    symbols: list[str] = Field(default_factory=list)


class MarketPageRequest(BaseModel):
    url: str = Field(min_length=8)
    focus_terms: list[str] = Field(default_factory=list)


class MarketIntelligenceRequest(BaseModel):
    pages: list[MarketPageRequest] = Field(default_factory=list, max_length=20)
    include_default_exchange_pages: bool = False
    regions: list[str] = Field(default_factory=list)
    focus_symbols: list[str] = Field(default_factory=list)
    timeframe: str = "1d"
    days: int = Field(default=180, ge=20, le=3650)
    refresh: bool = False
    max_symbols: int = Field(default=8, ge=1, le=30)
    max_pages: int = Field(default=12, ge=1, le=20)


class MarketPageInsight(BaseModel):
    url: str
    source_domain: str
    region: str | None = None
    exchange: str | None = None
    status: str
    title: str | None = None
    table_rows_count: int = 0
    extracted_symbols: list[str] = Field(default_factory=list)
    extracted_numbers: list[str] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)
    error: str | None = None


class MarketRecommendation(BaseModel):
    symbol: str
    signal: str
    confidence: float = Field(ge=0, le=1)
    risk_level: str
    rationale: str
    suggested_action: str


class MarketIntelligenceResponse(BaseModel):
    generated_at: str
    executive_summary: str
    pages: list[MarketPageInsight] = Field(default_factory=list)
    analyzed_symbols: list[str] = Field(default_factory=list)
    recommendations: list[MarketRecommendation] = Field(default_factory=list)
    disclaimer: str


class MarketSourceProfile(BaseModel):
    region: str
    exchange: str
    url: str
    focus_terms: list[str] = Field(default_factory=list)
    seed_symbols: list[str] = Field(default_factory=list)


class MarketSourceCatalogResponse(BaseModel):
    generated_at: str
    total_sources: int
    regions: list[str] = Field(default_factory=list)
    sources: list[MarketSourceProfile] = Field(default_factory=list)


class MarketBacktestResponse(BaseModel):
    symbol: str
    timeframe: str
    source: str
    generated_at: str
    lookback_days: int
    lookahead_days: int
    hold_band: float
    sample_size: int
    buy_signals: int
    sell_signals: int
    hold_signals: int
    win_rate: float = Field(ge=0, le=1)
    average_signal_return: float
    cumulative_return: float
    benchmark_return: float
    strategy_edge: float
    max_drawdown: float = Field(ge=0, le=1)
    notes: str


class SeriesPoint(BaseModel):
    label: str
    value: float


class CentralBankRateSnapshot(BaseModel):
    bank: str
    series_id: str
    currency: str
    latest_rate: float | None = None
    trend: str
    change_90d: float | None = None
    points: list[SeriesPoint] = Field(default_factory=list)
    source: str


class CentralBankPanelResponse(BaseModel):
    generated_at: str
    items: list[CentralBankRateSnapshot]


class WorldBankIndicatorSnapshot(BaseModel):
    country: str
    indicator: str
    indicator_name: str
    latest_value: float | None = None
    previous_value: float | None = None
    change: float | None = None
    points: list[SeriesPoint] = Field(default_factory=list)
    source: str


class WorldBankPanelResponse(BaseModel):
    generated_at: str
    items: list[WorldBankIndicatorSnapshot]


class ProfessionalReportResponse(BaseModel):
    generated_at: str
    risk_level: str
    executive_summary: str
    central_banks: list[CentralBankRateSnapshot]
    world_bank: list[WorldBankIndicatorSnapshot]
    bank_signals: list[MarketSignalCard]
    index_signals: list[MarketSignalCard]
    report_markdown: str


class InstitutionPageRequest(BaseModel):
    url: str = Field(min_length=8)
    focus_terms: list[str] = Field(default_factory=list)


class InstitutionReportRequest(BaseModel):
    pages: list[InstitutionPageRequest] = Field(default_factory=list, min_length=1, max_length=20)
    global_focus_terms: list[str] = Field(default_factory=list)


class InstitutionPageFinding(BaseModel):
    url: str
    source_domain: str
    status: str
    title: str | None = None
    summary: str
    matched_terms: list[str] = Field(default_factory=list)
    matched_snippets: list[str] = Field(default_factory=list)
    extracted_table_rows: list[list[str]] = Field(default_factory=list)
    fetched_at: str | None = None
    error: str | None = None


class InstitutionReportResponse(BaseModel):
    generated_at: str
    page_count: int
    requested_terms: list[str] = Field(default_factory=list)
    executive_summary: str
    pages: list[InstitutionPageFinding]


class TenderGenerationRequest(BaseModel):
    institution_name: str = Field(min_length=2)
    tender_title: str = Field(min_length=2)
    tender_reference: str | None = None
    company_name: str = Field(default="Bidder Company", min_length=2)
    administrative_spec: str = Field(min_length=20)
    technical_spec: str = Field(min_length=20)
    additional_requirements: list[str] = Field(default_factory=list)
    use_kik_baseline: bool = True


class TenderComplianceItem(BaseModel):
    requirement: str
    source: str
    evidence_document: str
    status: str
    priority: str


class TenderSection(BaseModel):
    code: str
    title: str
    content: str


class TenderChecklistItem(BaseModel):
    control_id: str
    category: str
    title: str
    description: str
    source_requirement: str | None = None
    evidence_required: str
    verification_method: str
    owner_role: str
    status: str
    blocking: bool = False
    notes: str = ""


class TenderTraceabilityItem(BaseModel):
    requirement: str
    source: str
    mapped_control_ids: list[str] = Field(default_factory=list)
    evidence_document: str
    verification_method: str


class TenderValidationSummary(BaseModel):
    total_controls: int
    completed_controls: int
    pending_controls: int
    blocking_pending_controls: int
    readiness_score: float = Field(ge=0, le=100)
    release_recommendation: str


class TenderDossierResponse(BaseModel):
    generated_at: str
    institution_name: str
    tender_title: str
    tender_reference: str | None = None
    executive_summary: str
    compliance_matrix: list[TenderComplianceItem]
    attachment_checklist: list[str] = Field(default_factory=list)
    control_checklist: list[TenderChecklistItem] = Field(default_factory=list)
    traceability_matrix: list[TenderTraceabilityItem] = Field(default_factory=list)
    validation_summary: TenderValidationSummary
    risk_notes: list[str] = Field(default_factory=list)
    legal_notice: str
    dossier_sections: list[TenderSection]
    dossier_markdown: str


class ProcurementRequestItemCreateRequest(BaseModel):
    item_name: str = Field(min_length=1)
    specification: str = ""
    quantity: int = Field(ge=1, le=1_000_000)
    min_quality_score: float = Field(default=0, ge=0, le=100)
    max_unit_price: float | None = Field(default=None, gt=0)
    required_by_date: str | None = None
    must_comply_tender: bool = False


class ProcurementRequestCreateRequest(BaseModel):
    company: str = Field(min_length=1)
    title: str = Field(min_length=2)
    strategy: str = Field(default="balanced", pattern="^(balanced|lowest_cost|highest_quality|fastest_delivery|tender_compliance)$")
    budget_limit: float | None = Field(default=None, gt=0)
    currency: str = Field(default="TRY", min_length=2, max_length=8)
    tender_reference: str | None = None
    tender_requirements: list[str] = Field(default_factory=list)
    items: list[ProcurementRequestItemCreateRequest] = Field(default_factory=list, min_length=1, max_length=200)


class ProcurementRequestItemRead(BaseModel):
    id: int
    request_id: int
    item_name: str
    specification: str
    quantity: int
    min_quality_score: float
    max_unit_price: float | None = None
    required_by_date: str | None = None
    must_comply_tender: bool


class ProcurementRequestRead(BaseModel):
    id: int
    company: str
    title: str
    strategy: str
    budget_limit: float | None = None
    currency: str
    tender_reference: str | None = None
    tender_requirements: list[str] = Field(default_factory=list)
    status: str
    created_at: int
    updated_at: int
    items: list[ProcurementRequestItemRead] = Field(default_factory=list)


class ProcurementRequestListResponse(BaseModel):
    total: int
    items: list[ProcurementRequestRead] = Field(default_factory=list)


class ProcurementQuoteItemCreateRequest(BaseModel):
    request_item_id: int
    unit_price: float = Field(gt=0)
    available_quantity: int = Field(ge=0)
    quality_score: float = Field(ge=0, le=100)
    brand: str = ""
    model: str = ""
    note: str = ""


class ProcurementVendorQuoteCreateRequest(BaseModel):
    request_id: int
    vendor_name: str = Field(min_length=2)
    vendor_rating: float = Field(default=60, ge=0, le=100)
    delivery_days: int = Field(default=7, ge=0, le=3650)
    warranty_months: int = Field(default=0, ge=0, le=240)
    compliance_score: float = Field(default=80, ge=0, le=100)
    status: str = Field(default="submitted", pattern="^(draft|submitted)$")
    quote_items: list[ProcurementQuoteItemCreateRequest] = Field(default_factory=list, min_length=1, max_length=500)


class ProcurementQuoteItemRead(BaseModel):
    id: int
    quote_id: int
    request_item_id: int
    unit_price: float
    available_quantity: int
    quality_score: float
    brand: str
    model: str
    note: str


class ProcurementVendorQuoteRead(BaseModel):
    id: int
    request_id: int
    vendor_name: str
    vendor_rating: float
    delivery_days: int
    warranty_months: int
    compliance_score: float
    status: str
    created_at: int
    items: list[ProcurementQuoteItemRead] = Field(default_factory=list)


class ProcurementVendorQuoteListResponse(BaseModel):
    request_id: int
    total: int
    items: list[ProcurementVendorQuoteRead] = Field(default_factory=list)


class ProcurementCandidateOption(BaseModel):
    quote_item_id: int
    quote_id: int
    vendor_name: str
    unit_price: float
    available_quantity: int
    quality_score: float
    delivery_days: int
    compliance_score: float
    vendor_rating: float
    weighted_score: float = Field(ge=0, le=100)
    feasible: bool
    feasibility_notes: list[str] = Field(default_factory=list)


class ProcurementItemRecommendation(BaseModel):
    request_item_id: int
    item_name: str
    required_quantity: int
    status: str
    selected_quote_item_id: int | None = None
    selected_vendor: str | None = None
    selected_unit_price: float | None = None
    expected_total: float | None = None
    weighted_score: float | None = None
    reasoning: str
    alternatives: list[ProcurementCandidateOption] = Field(default_factory=list)


class ProcurementEvaluationResponse(BaseModel):
    request_id: int
    strategy: str
    generated_at: str
    currency: str
    total_required_items: int
    resolved_items: int
    unresolved_items: int
    estimated_total_cost: float
    budget_limit: float | None = None
    within_budget: bool
    average_weighted_score: float
    recommendations: list[ProcurementItemRecommendation] = Field(default_factory=list)
    decision_notes: list[str] = Field(default_factory=list)


class ProcurementAutoOrderRequest(BaseModel):
    strategy_override: str | None = Field(default=None, pattern="^(balanced|lowest_cost|highest_quality|fastest_delivery|tender_compliance)$")
    require_full_coverage: bool = True
    auto_approve: bool = False
    max_vendor_split: int = Field(default=5, ge=1, le=50)


class ProcurementPurchaseOrderLineRead(BaseModel):
    id: int
    request_item_id: int | None = None
    item_name: str
    quantity: int
    unit_price: float
    line_total: float


class ProcurementPurchaseOrderRead(BaseModel):
    id: int
    request_id: int
    vendor_name: str
    currency: str
    total_amount: float
    status: str
    created_at: int
    approved_at: int | None = None
    lines: list[ProcurementPurchaseOrderLineRead] = Field(default_factory=list)


class ProcurementPurchaseOrderBatchResponse(BaseModel):
    request_id: int
    generated_at: str
    total_orders: int
    total_amount: float
    unresolved_items: int
    currency: str
    orders: list[ProcurementPurchaseOrderRead] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ProcurementTenderPlanRequest(BaseModel):
    tender: TenderGenerationRequest
    strategy: str = Field(default="tender_compliance", pattern="^(balanced|lowest_cost|highest_quality|fastest_delivery|tender_compliance)$")
    budget_limit: float | None = Field(default=None, gt=0)
    currency: str = Field(default="TRY", min_length=2, max_length=8)
    default_quantity: int = Field(default=1, ge=1, le=1000)
    max_items: int = Field(default=25, ge=1, le=200)


class ProcurementTenderPlanResponse(BaseModel):
    generated_at: str
    tender_reference: str | None = None
    institution_name: str
    tender_title: str
    extracted_item_count: int
    extraction_notes: list[str] = Field(default_factory=list)
    procurement_request: ProcurementRequestRead


class FeasibilityReportRequest(BaseModel):
    project_name: str = Field(min_length=2)
    sector: str = Field(min_length=2)
    geography: str = Field(min_length=2)
    objective: str = Field(min_length=10)
    company_name: str = Field(default="", description="Owning company for scope isolation (required for scoped users)")
    currency: str = Field(default="TRY", min_length=2, max_length=8)
    initial_investment: float = Field(gt=0)
    annual_opex: float = Field(gt=0)
    annual_revenue_base: float = Field(gt=0)
    project_lifetime_years: int = Field(default=5, ge=2, le=25)
    implementation_months: int = Field(default=6, ge=1, le=60)
    discount_rate: float = Field(default=0.15, ge=0.01, le=0.6)
    tax_rate: float = Field(default=0.2, ge=0, le=0.6)
    inflation_rate: float = Field(default=0.12, ge=0, le=1.0)
    revenue_growth_base: float = Field(default=0.08, ge=-0.5, le=1.5)
    revenue_growth_upside: float = Field(default=0.15, ge=-0.5, le=2.0)
    revenue_growth_downside: float = Field(default=-0.05, ge=-0.8, le=1.0)
    opex_growth_base: float = Field(default=0.1, ge=-0.5, le=1.5)
    capacity_utilization: float = Field(default=0.7, ge=0.05, le=1.0)
    financing_debt_ratio: float = Field(default=0.4, ge=0, le=1.0)
    regulatory_requirements: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    benchmark_symbols: list[str] = Field(default_factory=list)
    additional_notes: str = ""


class FeasibilityScenarioRow(BaseModel):
    scenario: str
    annual_revenue: float
    annual_opex: float
    annual_ebitda: float
    npv: float
    irr: float | None = None
    payback_year: float | None = None


class FeasibilityFinancialMetrics(BaseModel):
    npv: float
    irr: float | None = None
    payback_year: float | None = None
    break_even_revenue: float
    profitability_index: float
    average_ebitda_margin: float


class FeasibilitySensitivityItem(BaseModel):
    factor: str
    shock: str
    npv_impact: float
    note: str


class FeasibilityRiskItem(BaseModel):
    risk_id: str
    category: str
    description: str
    probability: str
    impact: str
    mitigation: str
    owner: str


class FeasibilityMilestone(BaseModel):
    phase: str
    month_start: int
    month_end: int
    deliverable: str
    gate: str


class FeasibilityKpiTarget(BaseModel):
    metric: str
    target: str
    rationale: str


class FeasibilityCoverageItem(BaseModel):
    topic: str
    status: str
    evidence: str


class FeasibilityReportResponse(BaseModel):
    generated_at: str
    project_name: str
    sector: str
    geography: str
    executive_summary: str
    recommendation: str
    confidence: float = Field(ge=0, le=1)
    scenarios: list[FeasibilityScenarioRow] = Field(default_factory=list)
    financial_metrics: FeasibilityFinancialMetrics
    sensitivity_analysis: list[FeasibilitySensitivityItem] = Field(default_factory=list)
    risk_register: list[FeasibilityRiskItem] = Field(default_factory=list)
    implementation_plan: list[FeasibilityMilestone] = Field(default_factory=list)
    procurement_checklist: list[str] = Field(default_factory=list)
    compliance_checklist: list[str] = Field(default_factory=list)
    kpi_targets: list[FeasibilityKpiTarget] = Field(default_factory=list)
    coverage: list[FeasibilityCoverageItem] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    report_markdown: str
    disclaimer: str


class FeasibilityReportListItem(BaseModel):
    id: int
    project_name: str
    sector: str
    geography: str
    status: str
    company_name: str = ""
    created_at: int
    recommendation: str
    confidence: float = Field(ge=0, le=1)
    npv: float


class FeasibilityReportListResponse(BaseModel):
    total: int
    items: list[FeasibilityReportListItem] = Field(default_factory=list)


class FeasibilityReportStoredResponse(BaseModel):
    id: int
    project_name: str
    sector: str
    geography: str
    status: str
    company_name: str = ""
    created_at: int
    request_payload: dict[str, object] = Field(default_factory=dict)
    report: FeasibilityReportResponse


class InternationalProjectRequest(BaseModel):
    project_name: str = Field(min_length=2)
    company_name: str = Field(min_length=2)
    base_country: str = Field(min_length=2, max_length=3)
    target_countries: list[str] = Field(default_factory=list, min_length=1, max_length=20)
    services: list[str] = Field(default_factory=list, min_length=1, max_length=8)
    sectors: list[str] = Field(default_factory=list, max_length=12)
    strategic_objectives: list[str] = Field(default_factory=list, max_length=20)
    budget_total: float = Field(gt=0)
    currency: str = Field(default="USD", min_length=2, max_length=8)
    timeline_months: int = Field(default=18, ge=3, le=120)
    risk_appetite: str = Field(default="medium", pattern="^(low|medium|high)$")
    local_partner_required: bool = True
    preferred_incoterms: list[str] = Field(default_factory=lambda: ["EXW", "FOB", "CIF", "DAP"], max_length=8)
    trade_lanes: list[str] = Field(default_factory=list, max_length=20)
    notes: str = ""


class InternationalCountryProfile(BaseModel):
    country_code: str
    country_name: str
    market_potential_score: float = Field(ge=0, le=100)
    operational_complexity_score: float = Field(ge=0, le=100)
    trade_readiness_score: float = Field(ge=0, le=100)
    compliance_readiness_score: float = Field(ge=0, le=100)
    recommended_entry_model: str
    top_priorities: list[str] = Field(default_factory=list)
    required_documents: list[str] = Field(default_factory=list)
    risk_level: str


class InternationalServicePlaybookItem(BaseModel):
    service: str
    operating_model: str
    key_deliverables: list[str] = Field(default_factory=list)
    capability_requirements: list[str] = Field(default_factory=list)
    expected_margin_band: str


class InternationalMilestone(BaseModel):
    phase: str
    month_start: int
    month_end: int
    deliverable: str
    owner: str


class InternationalRiskItem(BaseModel):
    risk_id: str
    category: str
    description: str
    probability: str
    impact: str
    mitigation: str
    owner: str


class InternationalKpiTarget(BaseModel):
    metric: str
    target: str
    period: str
    owner: str


class InternationalProjectReportResponse(BaseModel):
    generated_at: str
    project_name: str
    company_name: str
    base_country: str
    target_countries: list[str] = Field(default_factory=list)
    services: list[str] = Field(default_factory=list)
    executive_summary: str
    recommendation: str
    confidence: float = Field(ge=0, le=1)
    budget_allocation: dict[str, float] = Field(default_factory=dict)
    country_profiles: list[InternationalCountryProfile] = Field(default_factory=list)
    service_playbook: list[InternationalServicePlaybookItem] = Field(default_factory=list)
    trade_operating_model: list[str] = Field(default_factory=list)
    implementation_plan: list[InternationalMilestone] = Field(default_factory=list)
    risk_register: list[InternationalRiskItem] = Field(default_factory=list)
    kpi_targets: list[InternationalKpiTarget] = Field(default_factory=list)
    governance_model: list[str] = Field(default_factory=list)
    execution_checklist: list[str] = Field(default_factory=list)
    report_markdown: str
    disclaimer: str


class InternationalProjectListItem(BaseModel):
    id: int
    project_name: str
    company_name: str
    base_country: str
    target_country_count: int
    services: list[str] = Field(default_factory=list)
    status: str
    recommendation: str
    confidence: float = Field(ge=0, le=1)
    created_at: int
    updated_at: int


class InternationalProjectListResponse(BaseModel):
    total: int
    items: list[InternationalProjectListItem] = Field(default_factory=list)


class InternationalProjectStoredResponse(BaseModel):
    id: int
    project_name: str
    company_name: str
    base_country: str
    status: str
    created_at: int
    updated_at: int
    request_payload: dict[str, object] = Field(default_factory=dict)
    report: InternationalProjectReportResponse


class HoldingCreateRequest(BaseModel):
    name: str = Field(min_length=2)
    code: str | None = Field(default=None, max_length=32)
    description: str = ""
    status: str = Field(default="active", pattern="^(active|inactive|archived)$")


class HoldingRead(BaseModel):
    id: int
    name: str
    code: str | None = None
    description: str = ""
    status: str
    created_at: int
    updated_at: int


class HoldingListResponse(BaseModel):
    total: int
    items: list[HoldingRead] = Field(default_factory=list)


class HoldingCompanyOnboardInput(BaseModel):
    company_name: str = Field(min_length=2)
    sector: str = Field(default="General", min_length=2)
    country: str = Field(default="TR", min_length=2, max_length=3)
    initial_balance: float = 0.0
    data_quality_score: float = Field(default=70, ge=0, le=100)
    integration_completeness_score: float = Field(default=70, ge=0, le=100)
    security_compliance_score: float = Field(default=70, ge=0, le=100)
    process_standardization_score: float = Field(default=70, ge=0, le=100)
    master_data_health_score: float = Field(default=70, ge=0, le=100)
    team_readiness_score: float = Field(default=70, ge=0, le=100)
    notes: str = ""


class HoldingCompanyRead(BaseModel):
    id: int
    holding_id: int
    company_name: str
    sector: str
    country: str
    registered_in_platform: bool
    data_quality_score: float = Field(ge=0, le=100)
    integration_completeness_score: float = Field(ge=0, le=100)
    security_compliance_score: float = Field(ge=0, le=100)
    process_standardization_score: float = Field(ge=0, le=100)
    master_data_health_score: float = Field(ge=0, le=100)
    team_readiness_score: float = Field(ge=0, le=100)
    onboarding_readiness_score: float = Field(ge=0, le=100)
    onboarding_status: str
    recommendation: str
    notes: str = ""
    created_at: int
    updated_at: int


class HoldingOnboardRequest(BaseModel):
    companies: list[HoldingCompanyOnboardInput] = Field(default_factory=list, min_length=1, max_length=500)
    auto_register_companies: bool = True


class HoldingOnboardResponse(BaseModel):
    holding: HoldingRead
    total_companies: int
    go_count: int
    conditional_go_count: int
    block_count: int
    average_readiness_score: float = Field(ge=0, le=100)
    items: list[HoldingCompanyRead] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class HoldingDetailResponse(BaseModel):
    holding: HoldingRead
    total_companies: int
    go_count: int
    conditional_go_count: int
    block_count: int
    average_readiness_score: float = Field(ge=0, le=100)
    items: list[HoldingCompanyRead] = Field(default_factory=list)


class HoldingBulkOnboardRequest(BaseModel):
    holding: HoldingCreateRequest
    onboarding: HoldingOnboardRequest


class HoldingBulkOnboardResponse(BaseModel):
    holding: HoldingRead
    onboarding: HoldingOnboardResponse


class ConnectorCreateRequest(BaseModel):
    company_name: str = Field(min_length=2)
    connector_type: str = Field(min_length=2, max_length=64)
    provider: str = Field(min_length=2, max_length=128)
    base_url: str | None = None
    auth_mode: str = Field(default="api_key", pattern="^(none|api_key|oauth2|basic|mtls)$")
    config: dict[str, object] = Field(default_factory=dict)
    mapping: dict[str, str] = Field(default_factory=dict)


class ConnectorRead(BaseModel):
    id: int
    company_name: str
    connector_type: str
    provider: str
    base_url: str | None = None
    auth_mode: str
    config: dict[str, object] = Field(default_factory=dict)
    mapping: dict[str, str] = Field(default_factory=dict)
    status: str
    readiness_score: float = Field(ge=0, le=100)
    mapping_coverage_score: float = Field(ge=0, le=100)
    security_score: float = Field(ge=0, le=100)
    created_by: str | None = None
    created_at: int
    updated_at: int
    last_sync_at: int | None = None


class ConnectorListResponse(BaseModel):
    total: int
    items: list[ConnectorRead] = Field(default_factory=list)


class ConnectorCanonicalPreviewRequest(BaseModel):
    connector_type: str = Field(min_length=2, max_length=64)
    mapping: dict[str, str] = Field(default_factory=dict)
    sample_payload: dict[str, object] = Field(default_factory=dict)


class ConnectorCanonicalPreviewResponse(BaseModel):
    connector_type: str
    target_entity: str
    required_fields: list[str] = Field(default_factory=list)
    mapped_fields: list[str] = Field(default_factory=list)
    missing_required_fields: list[str] = Field(default_factory=list)
    coverage_score: float = Field(ge=0, le=100)
    suggested_mapping: dict[str, str] = Field(default_factory=dict)
    canonical_record_preview: dict[str, object] = Field(default_factory=dict)
    validation_notes: list[str] = Field(default_factory=list)


class ConnectorSyncJobCreateRequest(BaseModel):
    trigger_mode: str = Field(default="manual", pattern="^(manual|scheduled|webhook|reconcile)$")
    criticality: str = Field(default="standard", pattern="^(low|standard|high|critical)$")
    max_attempts: int = Field(default=3, ge=1, le=10)
    priority_boost: float = Field(default=0, ge=-50, le=50)
    request_payload: dict[str, object] = Field(default_factory=dict)


class ConnectorSyncJobRead(BaseModel):
    id: int
    connector_id: int
    company_name: str
    connector_type: str
    provider: str
    trigger_mode: str
    priority_score: float = Field(ge=0, le=100)
    status: str
    requested_by: str | None = None
    request_payload: dict[str, object] = Field(default_factory=dict)
    result_summary: str
    error_message: str | None = None
    error_code: str | None = None
    attempt_count: int = Field(ge=0)
    max_attempts: int = Field(ge=1)
    requested_at: int
    next_retry_at: int | None = None
    dead_lettered_at: int | None = None
    started_at: int | None = None
    finished_at: int | None = None


class ConnectorSyncJobListResponse(BaseModel):
    total: int
    items: list[ConnectorSyncJobRead] = Field(default_factory=list)


class ConnectorSyncDispatchRequest(BaseModel):
    company_name: str | None = None
    auto_complete: bool = True
    success: bool = True
    allow_retry: bool = False
    retry_backoff_seconds: int = Field(default=60, ge=5, le=3600)
    health_score: float = Field(default=85, ge=0, le=100)
    result_summary: str = ""
    error_message: str | None = None


class ConnectorQueueHealthResponse(BaseModel):
    generated_at: str
    total_connectors: int
    active_connectors: int
    staged_connectors: int
    blocked_connectors: int
    queued_jobs: int
    running_jobs: int
    success_jobs: int
    failed_jobs: int
    dead_letter_jobs: int
    due_retry_jobs: int
    average_readiness_score: float = Field(ge=0, le=100)
    average_security_score: float = Field(ge=0, le=100)


class ConnectorSyncDispatchResponse(BaseModel):
    claimed: bool
    message: str
    job: ConnectorSyncJobRead | None = None
    connector: ConnectorRead | None = None


class EcosystemProcurementItem(BaseModel):
    item_name: str = Field(min_length=1)
    quantity: int = Field(ge=1, le=1_000_000)
    specification: str = ""
    min_quality_score: float = Field(default=70, ge=0, le=100)
    max_unit_price: float | None = Field(default=None, gt=0)
    required_by_date: str | None = None
    must_comply_tender: bool = False


class EcosystemActivationRequest(BaseModel):
    project_name: str = Field(min_length=2)
    company_name: str = Field(min_length=2)
    sector: str = Field(min_length=2)
    geography: str = Field(min_length=2)
    objective: str = Field(min_length=10)
    budget_total: float = Field(gt=0)
    currency: str = Field(default="USD", min_length=2, max_length=8)
    base_country: str = Field(min_length=2, max_length=3)
    target_countries: list[str] = Field(default_factory=list, min_length=1, max_length=20)
    services: list[str] = Field(default_factory=lambda: ["management", "consulting", "installation", "import_export"], min_length=1, max_length=8)
    timeline_months: int = Field(default=18, ge=3, le=120)
    risk_appetite: str = Field(default="medium", pattern="^(low|medium|high)$")
    local_partner_required: bool = True
    strategic_objectives: list[str] = Field(default_factory=list, max_length=20)
    trade_lanes: list[str] = Field(default_factory=list, max_length=20)
    preferred_incoterms: list[str] = Field(default_factory=lambda: ["FOB", "CIF", "DAP"], max_length=8)
    procurement_strategy: str = Field(default="balanced", pattern="^(balanced|lowest_cost|highest_quality|fastest_delivery|tender_compliance)$")
    procurement_items: list[EcosystemProcurementItem] = Field(default_factory=list, max_length=200)
    notes: str = ""


class EcosystemActivationResponse(BaseModel):
    generated_at: str
    project_name: str
    company_name: str
    sector: str
    recommendation: str
    confidence: float = Field(ge=0, le=1)
    feasibility_report_id: int
    international_project_id: int
    procurement_request_id: int | None = None
    module_status: dict[str, str] = Field(default_factory=dict)
    action_plan: list[str] = Field(default_factory=list)
    feasibility_report_markdown_preview: str


class EcosystemPortfolioCompanyInput(BaseModel):
    company_name: str = Field(min_length=2)
    sector: str = Field(min_length=2)
    geography: str = Field(min_length=2)
    objective: str = Field(min_length=10)
    budget_total: float = Field(gt=0)
    procurement_items: list[EcosystemProcurementItem] = Field(default_factory=list, max_length=200)
    notes: str = ""


class EcosystemPortfolioActivationRequest(BaseModel):
    scope_mode: str = Field(default="single", pattern="^(single|multi|holding)$")
    project_name_prefix: str = Field(default="Strategic Program", min_length=2)
    holding_name: str | None = None
    currency: str = Field(default="USD", min_length=2, max_length=8)
    base_country: str = Field(min_length=2, max_length=3)
    target_countries: list[str] = Field(default_factory=list, min_length=1, max_length=20)
    services: list[str] = Field(default_factory=lambda: ["management", "consulting", "installation", "import_export"], min_length=1, max_length=8)
    timeline_months: int = Field(default=18, ge=3, le=120)
    risk_appetite: str = Field(default="medium", pattern="^(low|medium|high)$")
    local_partner_required: bool = True
    strategic_objectives: list[str] = Field(default_factory=list, max_length=20)
    trade_lanes: list[str] = Field(default_factory=list, max_length=20)
    preferred_incoterms: list[str] = Field(default_factory=lambda: ["FOB", "CIF", "DAP"], max_length=8)
    procurement_strategy: str = Field(default="balanced", pattern="^(balanced|lowest_cost|highest_quality|fastest_delivery|tender_compliance)$")
    companies: list[EcosystemPortfolioCompanyInput] = Field(default_factory=list, max_length=200)
    use_registered_companies_when_empty: bool = True
    default_sector: str = Field(default="General", min_length=2)
    default_geography: str = Field(default="Global", min_length=2)
    default_objective: str = Field(
        default=(
            "Scale integrated corporate operations across countries with coordinated feasibility, "
            "international operations, and procurement execution."
        ),
        min_length=10,
    )
    default_budget_total: float = Field(default=1_000_000, gt=0)
    notes: str = ""


class EcosystemPortfolioCompanyResult(BaseModel):
    company_name: str
    project_name: str
    recommendation: str
    confidence: float = Field(ge=0, le=1)
    feasibility_report_id: int
    international_project_id: int
    procurement_request_id: int | None = None
    module_status: dict[str, str] = Field(default_factory=dict)
    action_plan: list[str] = Field(default_factory=list)


class EcosystemPortfolioActivationResponse(BaseModel):
    generated_at: str
    scope_mode: str
    holding_name: str | None = None
    total_companies: int
    successful_companies: int
    failed_companies: int
    portfolio_recommendation: str
    average_confidence: float = Field(ge=0, le=1)
    items: list[EcosystemPortfolioCompanyResult] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    summary_notes: list[str] = Field(default_factory=list)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int
    refresh_expires_in: int | None = None


class UserProfile(BaseModel):
    id: int
    username: str
    role: str
    company_scopes: list[str] = Field(default_factory=lambda: ["*"])
    scope_mode: str = "holding"


class RoleRead(BaseModel):
    id: int
    name: str
    description: str
    created_at: int
    updated_at: int


class RoleCreateRequest(BaseModel):
    name: str = Field(min_length=2)
    description: str = ""


class RoleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2)
    description: str | None = None


class UserRead(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    created_at: int
    updated_at: int
    company_scopes: list[str] = Field(default_factory=lambda: ["*"])
    scope_mode: str = "holding"


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=3)
    password: str = Field(min_length=8)
    role: str = Field(min_length=2)
    is_active: bool = True
    company_scopes: list[str] = Field(default_factory=lambda: ["*"], max_length=200)


class UserUpdateRequest(BaseModel):
    role: str | None = Field(default=None, min_length=2)
    is_active: bool | None = None
    company_scopes: list[str] | None = Field(default=None, max_length=200)


class PasswordRotateRequest(BaseModel):
    current_password: str | None = None
    new_password: str = Field(min_length=8)


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=10)


class LogoutRequest(BaseModel):
    refresh_token: str | None = None
    revoke_all_devices: bool = False


class LogoutResponse(BaseModel):
    message: str


class AuditLogRead(BaseModel):
    id: int
    request_id: str | None = None
    username: str | None = None
    role: str | None = None
    method: str
    path: str
    status_code: int
    ip_address: str | None = None
    user_agent: str | None = None
    duration_ms: float
    created_at: int
    event_type: str | None = None
    event_detail: dict[str, object] | None = None


class PermissionRead(BaseModel):
    id: int
    name: str
    description: str
    created_at: int
    updated_at: int


class RolePermissionsRead(BaseModel):
    role_id: int
    role_name: str
    permissions: list[str]


class RolePermissionsUpdateRequest(BaseModel):
    permissions: list[str] = Field(default_factory=list)


class MigrationStatusItem(BaseModel):
    version: int
    name: str
    applied: bool
    applied_at: int | None = None


class MigrationActionResponse(BaseModel):
    message: str
    versions: list[int] = Field(default_factory=list)


class MigrationRollbackRequest(BaseModel):
    steps: int = Field(default=1, ge=1, le=20)
    force: bool = Field(default=False, description="Required to roll back migrations that touch critical tables")


class MigrationPreflightItem(BaseModel):
    version: int
    name: str
    sql_valid: bool
    touches_critical_tables: bool
    critical_tables_found: list[str] = Field(default_factory=list)
    warning: str = ""


class MigrationPreflightResponse(BaseModel):
    pending_count: int
    safe_to_apply: bool
    warnings: list[str] = Field(default_factory=list)
    items: list[MigrationPreflightItem] = Field(default_factory=list)


class MigrationDryRunResponse(BaseModel):
    would_apply: list[int] = Field(default_factory=list)
    already_applied: list[int] = Field(default_factory=list)
    total_pending: int
