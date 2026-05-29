/**
 * SEC1: Admin audit + KVKK API client.
 */
import { apiRequest } from "@/lib/api";

export interface AuditLogEntry {
  id: number;
  request_id: string;
  username: string | null;
  role: string | null;
  method: string;
  path: string;
  status_code: number;
  ip_address: string | null;
  user_agent: string | null;
  duration_ms: number;
  created_at: number;
  event_type: string | null;
  event_detail: Record<string, unknown> | null;
}

export interface AuditSummary {
  window_hours: number;
  total_events: number;
  error_count: number;
  error_rate_pct: number;
  events_by_method: Array<{ method: string; count: number }>;
  events_by_user: Array<{ username: string; count: number }>;
  slow_routes: Array<{
    path: string;
    avg_duration_ms: number;
    request_count: number;
  }>;
}

export interface AuditSearchFilters {
  username?: string;
  method?: string;
  pathContains?: string;
  statusCodeMin?: number;
  statusCodeMax?: number;
  fromHoursAgo?: number;
  eventType?: string;
  limit?: number;
}

export async function searchAuditLogs(
  filters: AuditSearchFilters,
): Promise<AuditLogEntry[]> {
  const search = new URLSearchParams();
  if (filters.username) search.set("username", filters.username);
  if (filters.method) search.set("method", filters.method);
  if (filters.pathContains) search.set("path_contains", filters.pathContains);
  if (filters.statusCodeMin !== undefined) search.set("status_code_min", String(filters.statusCodeMin));
  if (filters.statusCodeMax !== undefined) search.set("status_code_max", String(filters.statusCodeMax));
  if (filters.fromHoursAgo !== undefined) search.set("from_hours_ago", String(filters.fromHoursAgo));
  if (filters.eventType) search.set("event_type", filters.eventType);
  if (filters.limit) search.set("limit", String(filters.limit));
  const qs = search.toString() ? `?${search.toString()}` : "";
  return apiRequest<AuditLogEntry[]>(`/api/v1/admin/audit/search${qs}`);
}

export async function fetchAuditSummary(
  windowHours: number = 24,
): Promise<AuditSummary> {
  return apiRequest<AuditSummary>(
    `/api/v1/admin/audit/summary?window_hours=${windowHours}`,
  );
}

// ── KVKK admin ─────────────────────────────────────────────────────────

export interface KvkkDeletionRequest {
  id: number;
  user_id: string;
  reason: string | null;
  status: string;
  created_at: number;
  reviewed_at: number | null;
  reviewed_by: string | null;
}

export interface KvkkIncident {
  id: number;
  incident_type: string;
  severity: string;
  affected_user_id: string | null;
  affected_record_count: number;
  description: string;
  reported_by: string;
  reported_at: number;
  notification_required: number;
  status: string;
  created_at: number;
}

export async function listKvkkDeletionRequests(): Promise<KvkkDeletionRequest[]> {
  return apiRequest<KvkkDeletionRequest[]>(
    "/api/v1/admin/kvkk/deletion-requests",
  );
}

export async function listKvkkIncidents(): Promise<KvkkIncident[]> {
  return apiRequest<KvkkIncident[]>("/api/v1/admin/kvkk/incidents");
}
