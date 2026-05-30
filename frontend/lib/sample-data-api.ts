/**
 * OBS1: Sample data API client.
 */
import { apiRequest } from "@/lib/api";

export interface SampleDataStatus {
  has_sample_data: boolean;
}

export interface SampleDataSeedResult {
  customers_created: number;
  invoices_created: number;
  ledger_entries_created: number;
  anomaly_signals_created: number;
  already_seeded: boolean;
}

export interface SampleDataClearResult {
  customers_deleted: number;
  invoices_deleted: number;
  ledger_entries_deleted: number;
  anomalies_deleted: number;
}

export async function getSampleDataStatus(): Promise<SampleDataStatus> {
  return apiRequest<SampleDataStatus>("/api/v1/sample-data/status");
}

export async function seedSampleData(
  companyName?: string,
): Promise<SampleDataSeedResult> {
  return apiRequest<SampleDataSeedResult>("/api/v1/sample-data/seed", {
    method: "POST",
    body: { company_name: companyName ?? null },
  });
}

export async function clearSampleData(): Promise<SampleDataClearResult> {
  return apiRequest<SampleDataClearResult>("/api/v1/sample-data", {
    method: "DELETE",
  });
}
