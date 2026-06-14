/**
 * M2 — Finance ledger + budget API client.
 * Backend: app/routers/finance.py — prefix /api/v1/finance-engine
 */
import { apiRequest } from "@/lib/api";

export interface LedgerEntry {
  id: number;
  company: string;
  posted_at: string;
  amount: number;
  currency: string;
  category: string;
  account: string | null;
  counterparty: string | null;
  intercompany_flag: number | null;
  notes: string | null;
  created_at: string;
}

export interface LedgerListResponse {
  total: number;
  records: LedgerEntry[];
}

export interface Budget {
  id: number;
  company: string;
  year: number;
  month: number;
  category: string;
  planned_amount: number;
  currency: string;
  created_at: string;
}

export interface BudgetVsActual {
  company: string;
  year: number;
  month: number;
  category: string;
  planned: number;
  actual: number;
  variance: number;
  variance_pct: number;
}

export function listLedger(params?: {
  start_date?: string;
  end_date?: string;
  company?: string;
  category?: string;
  limit?: number;
}): Promise<LedgerListResponse> {
  return apiRequest<LedgerListResponse>("/api/v1/finance-engine/ledger", { params });
}

export function getLedgerEntry(id: number): Promise<LedgerEntry> {
  // Bireysel detay ucu yok — listeden filtre ile çekeriz.
  return apiRequest<LedgerListResponse>("/api/v1/finance-engine/ledger", {
    params: { limit: 1000 },
  }).then((r) => {
    const found = r.records.find((e) => e.id === id);
    if (!found) throw new Error(`Ledger entry ${id} bulunamadı`);
    return found;
  });
}

export function listBudgets(params?: {
  company?: string;
  year?: number;
  month?: number;
}): Promise<Budget[]> {
  return apiRequest<Budget[]>("/api/v1/finance-engine/budgets", { params });
}

export function getBudgetVsActual(params?: {
  company?: string;
  year?: number;
  month?: number;
}): Promise<BudgetVsActual[]> {
  return apiRequest<BudgetVsActual[]>("/api/v1/finance-engine/budget-vs-actual", {
    params,
  });
}
