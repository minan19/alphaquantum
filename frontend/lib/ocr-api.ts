/**
 * A4: AI Invoice OCR API client.
 */
import { apiRequest } from "@/lib/api";

export type OcrStatus =
  | "pending" | "processing" | "extracted"
  | "confirmed" | "failed" | "cancelled";

export interface OcrExtract {
  vendor_name?: string | null;
  vendor_tax_number?: string | null;
  invoice_no?: string | null;
  issue_date?: string | null;
  total_amount?: number | null;
  currency?: string | null;
  direction?: "outgoing" | "incoming" | null;
  category?: string | null;
  confidence_pct?: number | null;
  notes?: string | null;
}

export interface OcrJob {
  id: number;
  user_id: string;
  source_filename: string | null;
  status: OcrStatus;
  extract: OcrExtract;
  confidence_pct: number;
  ledger_entry_id: number | null;
  error_message: string | null;
  created_at: number;
  extracted_at: number | null;
  confirmed_at: number | null;
}

export interface OcrJobList {
  jobs: OcrJob[];
  total: number;
}

export async function uploadInvoiceImage(file: File): Promise<OcrJob> {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch("/api/v1/ocr/invoice", {
    method: "POST",
    credentials: "include",
    body: fd,
  });
  if (!res.ok) {
    throw new Error(`Yükleme başarısız (${res.status}): ${await res.text()}`);
  }
  return res.json();
}

export async function confirmOcrJob(
  jobId: number,
  payload: {
    company_name: string;
    vendor_name?: string;
    invoice_no?: string;
    issue_date?: string;
    total_amount?: number;
    direction?: "outgoing" | "incoming";
    category?: string;
  },
): Promise<OcrJob> {
  return apiRequest<OcrJob>(`/api/v1/ocr/invoice/${jobId}/confirm`, {
    method: "POST",
    body: payload,
  });
}

export async function listOcrJobs(limit = 20): Promise<OcrJobList> {
  return apiRequest<OcrJobList>(`/api/v1/ocr/jobs?limit=${limit}`);
}
