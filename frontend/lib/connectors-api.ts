/**
 * I1: Logo Tiger ERP Connector — API client.
 */
import { apiRequest } from "@/lib/api";

export type ConnectorType = "logo_tiger" | string;
export type ConnectorMode = "xml" | "excel" | "web_service";
export type ImportStatus =
  | "pending"
  | "parsing"
  | "preview"
  | "committing"
  | "completed"
  | "failed"
  | "cancelled";

export interface ConnectorTypeInfo {
  connector_type: ConnectorType;
  label: string;
  supported_modes: ConnectorMode[];
}

export interface ConnectorImportError {
  row_index: number;
  record_type: string;
  error_code: string;
  error_message: string;
  raw_payload: string | null;
}

export interface ConnectorImportJob {
  id: number;
  user_id: string;
  connector_type: ConnectorType;
  mode: ConnectorMode;
  status: ImportStatus;
  source_filename: string | null;
  source_size_bytes: number;
  summary: Record<string, number | string>;
  preview: Array<{ type: string; data: Record<string, unknown> }>;
  error_message: string | null;
  started_at: number;
  finished_at: number | null;
  committed_at: number | null;
  errors: ConnectorImportError[];
}

export interface ConnectorImportList {
  jobs: ConnectorImportJob[];
  total: number;
}

export async function listConnectorTypes(): Promise<ConnectorTypeInfo[]> {
  return apiRequest<ConnectorTypeInfo[]>("/api/v1/connectors/types");
}

export async function listConnectorImports(limit = 20): Promise<ConnectorImportList> {
  return apiRequest<ConnectorImportList>(`/api/v1/connectors/imports?limit=${limit}`);
}

export async function getConnectorImport(id: number): Promise<ConnectorImportJob> {
  return apiRequest<ConnectorImportJob>(`/api/v1/connectors/imports/${id}`);
}

/**
 * Upload + parse + preview. Sunucu job 'preview' status'le yaratır.
 * Caller commit edene kadar veri DB'ye yazılmaz.
 */
export async function previewConnectorImport(
  connectorType: ConnectorType,
  file: File,
  mode: ConnectorMode = "xml",
): Promise<ConnectorImportJob> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("mode", mode);
  // apiRequest doesn't support FormData natively; fall back to raw fetch
  const url = `/api/v1/connectors/${connectorType}/preview`;
  const res = await fetch(url, {
    method: "POST",
    credentials: "include",
    body: fd,
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Upload başarısız (${res.status}): ${detail}`);
  }
  return res.json();
}

export async function commitConnectorImport(
  jobId: number,
  file: File,
): Promise<ConnectorImportJob> {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(`/api/v1/connectors/imports/${jobId}/commit`, {
    method: "POST",
    credentials: "include",
    body: fd,
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Onay başarısız (${res.status}): ${detail}`);
  }
  return res.json();
}

export async function cancelConnectorImport(
  jobId: number,
): Promise<{ cancelled: boolean }> {
  return apiRequest<{ cancelled: boolean }>(
    `/api/v1/connectors/imports/${jobId}/cancel`,
    { method: "POST" },
  );
}

// ── I2: Staging → CRM/Invoice/Ledger promotion ─────────────────────────

export type PromotionPolicy = "create_new" | "update_existing" | "skip";

export interface StagedRecord {
  signature_hash: string;
  payload: Record<string, unknown>;
  created_at: number;
}

export interface StagingList {
  customers: StagedRecord[];
  invoices: StagedRecord[];
  customer_count: number;
  invoice_count: number;
}

export interface PromotionPlanRecord {
  signature_hash: string;
  source_code: string | null;
  source_no: string | null;
  customer_source_code: string | null;
  name: string | null;
  tax_number: string | null;
  issue_date: string | null;
  amount: number | null;
  direction: string | null;
  existing_id: number | null;
  planned_action: string;
}

export interface PromotionPlan {
  new_customers: number;
  new_invoices: number;
  conflict_customers: number;
  conflict_invoices: number;
  already_promoted_customers: number;
  already_promoted_invoices: number;
  ledger_entries_to_create: number;
  customer_details: PromotionPlanRecord[];
  invoice_details: PromotionPlanRecord[];
}

export interface PromotionResult {
  customers_created: number;
  customers_updated: number;
  customers_skipped: number;
  invoices_created: number;
  invoices_skipped: number;
  ledger_entries_created: number;
  errors: string[];
}

export async function listStaging(limit = 200): Promise<StagingList> {
  return apiRequest<StagingList>(`/api/v1/connectors/staging?limit=${limit}`);
}

export async function previewStagingPromotion(
  companyName: string,
  policy: PromotionPolicy = "create_new",
): Promise<PromotionPlan> {
  return apiRequest<PromotionPlan>("/api/v1/connectors/staging/preview", {
    method: "POST",
    body: { company_name: companyName, policy },
  });
}

export async function promoteStaging(
  companyName: string,
  policy: PromotionPolicy = "create_new",
): Promise<PromotionResult> {
  return apiRequest<PromotionResult>("/api/v1/connectors/staging/promote", {
    method: "POST",
    body: { company_name: companyName, policy },
  });
}
