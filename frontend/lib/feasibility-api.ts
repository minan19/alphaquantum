/**
 * M2 — Feasibility (GO/NO-GO) API client.
 * Backend: app/routers/procurement.py — /api/v1/feasibility/*
 */
import { apiRequest } from "@/lib/api";

export interface FeasibilityReport {
  id: number;
  company: string | null;
  title: string;
  sector: string | null;
  decision: "go" | "no_go" | "pending" | string;
  score: number | null;
  risk_level: string | null;
  estimated_capex: number | null;
  currency: string | null;
  notes: string | null;
  created_at: string;
  decided_at: string | null;
}

export interface FeasibilityReportListResponse {
  total: number;
  records: FeasibilityReport[];
}

export function listFeasibilityReports(params?: {
  sector?: string;
  company?: string;
  decision?: string;
  limit?: number;
}): Promise<FeasibilityReportListResponse> {
  return apiRequest<FeasibilityReportListResponse>("/api/v1/feasibility/reports", {
    params,
  });
}

export function getFeasibilityReport(id: number): Promise<FeasibilityReport> {
  return apiRequest<FeasibilityReport>(`/api/v1/feasibility/reports/${id}`);
}
