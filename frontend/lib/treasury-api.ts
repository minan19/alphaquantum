/**
 * Treasury API client — T1: Multi-bank Treasury Dashboard.
 * Backend: app/routers/treasury.py
 */
import { apiRequest } from "@/lib/api";

export interface TreasuryAccount {
  id: number;
  user_id: string;
  company_name: string;
  bank_name: string;
  branch: string | null;
  iban: string | null;
  account_no: string | null;
  account_type: "vadesiz" | "vadeli" | "kredi" | "pos" | "doviz" | "diğer";
  currency: string;
  current_balance: number;
  last_synced_at: number | null;
  is_active: boolean;
  notes: string | null;
}

export interface TreasuryByBankEntry {
  bank_name: string;
  total_in_try: number;
  account_count: number;
}

export interface TreasuryByCompanyEntry {
  company_name: string;
  total_in_try: number;
  account_count: number;
}

export interface TreasurySummary {
  total_in_try: number;
  by_currency: Record<string, number>;
  by_bank: TreasuryByBankEntry[];
  by_company: TreasuryByCompanyEntry[];
  account_count: number;
  last_synced_at: number | null;
}

export interface TreasuryHistoryEntry {
  snapshot_date: string;
  balance: number;
  snapshot_source: string;
}

export interface TreasuryHistoryResponse {
  entries: TreasuryHistoryEntry[];
}

export function fetchTreasuryAccounts(): Promise<TreasuryAccount[]> {
  return apiRequest<TreasuryAccount[]>("/api/v1/treasury/accounts");
}

export function fetchTreasurySummary(): Promise<TreasurySummary> {
  return apiRequest<TreasurySummary>("/api/v1/treasury/summary");
}

export function fetchTreasuryHistory(
  accountId: number,
): Promise<TreasuryHistoryResponse> {
  return apiRequest<TreasuryHistoryResponse>(
    `/api/v1/treasury/accounts/${accountId}/history`,
  );
}
