/**
 * M2 — Procurement API client.
 * Backend: app/routers/procurement.py
 */
import { apiRequest } from "@/lib/api";

export interface ProcurementRequest {
  id: number;
  company: string | null;
  title: string;
  description: string | null;
  status: string;
  priority: string | null;
  expected_amount: number | null;
  currency: string | null;
  needed_by: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface ProcurementRequestListResponse {
  total: number;
  records: ProcurementRequest[];
}

export interface Quote {
  id: number;
  request_id: number;
  vendor: string;
  amount: number;
  currency: string;
  lead_time_days: number | null;
  notes: string | null;
  created_at: string;
}

export interface PurchaseOrder {
  id: number;
  request_id: number;
  vendor: string;
  amount: number;
  currency: string;
  status: string;
  created_at: string;
}

export function listProcurementRequests(params?: {
  status?: string;
  company?: string;
  limit?: number;
}): Promise<ProcurementRequestListResponse> {
  return apiRequest<ProcurementRequestListResponse>("/api/v1/procurement/requests", {
    params,
  });
}

export function getProcurementRequest(id: number): Promise<ProcurementRequest> {
  return apiRequest<ProcurementRequest>(`/api/v1/procurement/requests/${id}`);
}

export function listQuotes(requestId: number): Promise<Quote[]> {
  return apiRequest<Quote[]>(`/api/v1/procurement/requests/${requestId}/quotes`);
}

export function listPurchaseOrders(requestId: number): Promise<PurchaseOrder[]> {
  return apiRequest<PurchaseOrder[]>(
    `/api/v1/procurement/requests/${requestId}/purchase-orders`,
  );
}
