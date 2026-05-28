/**
 * G1.6: CorpOS API client helpers
 *
 * Backend endpoint'lerine TypeScript-typed çağrı sarmalayıcıları.
 * Storytelling mockup'ları bu shape'lere göre tasarlandı — yani landing
 * "vapor demo" değil, backend API contract'ı ile birebir uyumlu.
 *
 * Endpoint kapsamı (G1.2 + G1.3 + G1.4 + G1.5):
 *   - GET /api/v1/finance-engine/overview/ledger-derived       (sahne 1)
 *   - GET /api/v1/holdings/{id}/consolidated-pl                (sahne 2)
 *   - GET /api/v1/holdings/{id}/fx-position                    (sahne 1 FX)
 *   - GET /api/v1/holdings/{id}/intercompany-transfers/pending (sahne 4 kuyruk)
 *   - POST /api/v1/intercompany-transfers/{id}/approve         (sahne 4 onay)
 *
 * Pricing sayfası public — auth gerektirmediği için bu helper'lar
 * dashboard ve demo modunda kullanılacak. Hard-coded fallback seed
 * (storytelling-seed.ts) backend down'ken bile sayfa render eder.
 */
import { apiRequest } from "@/lib/api";

// ── Sahne 1: Ledger-derived overview ──────────────────────────────────────

export interface FinanceOverviewResponse {
  total_balance: number;
  average_balance: number;
  negative_balance_companies: number;
  highest_balance_company: string | null;
  lowest_balance_company: string | null;
  health_status: string;
}

export async function getLedgerDerivedOverview(): Promise<FinanceOverviewResponse> {
  return apiRequest<FinanceOverviewResponse>(
    "/api/v1/finance-engine/overview/ledger-derived",
  );
}

// ── Sahne 1 (FX): Group FX position ───────────────────────────────────────

export interface FXCurrencyExposure {
  currency: string;
  fx_rate_to_try: number;
  receivable_open: number;
  receivable_overdue: number;
  intercompany_inflow: number;
  intercompany_outflow: number;
  net_position_fx: number;
  net_position_try: number;
  position_type: "long" | "short" | "flat";
}

export interface FXSensitivityScenario {
  scenario_name: string;
  devaluation_pct: number;
  total_impact_try: number;
}

export interface GroupFXPositionResponse {
  holding_id: number;
  holding_name: string;
  as_of_date: string;
  exposures: FXCurrencyExposure[];
  total_long_try: number;
  total_short_try: number;
  net_exposure_try: number;
  sensitivity_scenarios: FXSensitivityScenario[];
  risk_level: "balanced" | "moderate" | "concentrated" | "critical";
  recommendations: string[];
}

export async function getGroupFXPosition(
  holdingId: number,
  asOfDate?: string,
): Promise<GroupFXPositionResponse> {
  const params = asOfDate ? `?as_of_date=${asOfDate}` : "";
  return apiRequest<GroupFXPositionResponse>(
    `/api/v1/holdings/${holdingId}/fx-position${params}`,
  );
}

// ── Sahne 2: Consolidated P&L ─────────────────────────────────────────────

export interface ConsolidatedPLLine {
  company: string;
  gross_income: number;
  intercompany_income: number;
  external_income: number;
  gross_expense: number;
  intercompany_expense: number;
  external_expense: number;
  net_total: number;
  net_external: number;
}

export interface ConsolidatedPLElimination {
  total_intercompany_income: number;
  total_intercompany_expense: number;
  elimination_amount: number;
  is_balanced: boolean;
}

export interface ConsolidatedPLResponse {
  holding_id: number;
  holding_name: string;
  period_start: string;
  period_end: string;
  lines: ConsolidatedPLLine[];
  gross_total_income: number;
  gross_total_expense: number;
  gross_net: number;
  consolidated_income: number;
  consolidated_expense: number;
  consolidated_net: number;
  elimination: ConsolidatedPLElimination;
  health_status: "strong" | "stable" | "watch" | "risk";
}

export async function getConsolidatedPL(
  holdingId: number,
  startDate: string,
  endDate: string,
): Promise<ConsolidatedPLResponse> {
  const params = new URLSearchParams({
    start_date: startDate,
    end_date: endDate,
  });
  return apiRequest<ConsolidatedPLResponse>(
    `/api/v1/holdings/${holdingId}/consolidated-pl?${params}`,
  );
}

// ── Sahne 4: Intercompany transfer (request + approve) ────────────────────

export interface IntercompanyTransferRead {
  id: number;
  holding_id: number;
  from_company: string;
  to_company: string;
  amount: number;
  currency: string;
  target_amount: number | null;
  fx_rate: number | null;
  description: string;
  requested_by: string;
  requested_at: number;
  approval_status: "pending" | "approved" | "rejected" | "completed";
  approved_by: string | null;
  approved_at: number | null;
  reject_reason: string | null;
  completed_at: number | null;
  ledger_entry_from_id: number | null;
  ledger_entry_to_id: number | null;
}

export interface IntercompanyTransferListResponse {
  total: number;
  transfers: IntercompanyTransferRead[];
}

export async function listPendingIntercompanyTransfers(
  holdingId: number,
): Promise<IntercompanyTransferListResponse> {
  return apiRequest<IntercompanyTransferListResponse>(
    `/api/v1/holdings/${holdingId}/intercompany-transfers/pending`,
  );
}

export async function approveIntercompanyTransfer(
  transferId: number,
  approverUserId: string,
): Promise<IntercompanyTransferRead> {
  return apiRequest<IntercompanyTransferRead>(
    `/api/v1/intercompany-transfers/${transferId}/approve`,
    {
      method: "POST",
      body: { approver_user_id: approverUserId },
    },
  );
}
