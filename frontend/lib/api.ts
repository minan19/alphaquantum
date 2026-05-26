/**
 * Alpha Quantum API client.
 * Single source of truth for talking to the FastAPI backend.
 *
 * Token storage: localStorage (browser only). Server components must pass
 * the token explicitly via the options arg if they need to hit the API.
 */

const TOKEN_KEY = "aq.access_token";

export function getApiBaseUrl(): string {
  return (
    process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
  );
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown, message?: string) {
    super(message ?? `API error: ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE" | "PUT";
  body?: unknown;
  /** Override token (e.g. SSR). Defaults to localStorage token. */
  token?: string | null;
  /** Add to query string. */
  params?: Record<string, string | number | boolean | undefined | null>;
}

export async function apiRequest<T = unknown>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { method = "GET", body, params } = options;
  const token = options.token ?? getToken();

  const url = new URL(path, getApiBaseUrl());
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null && v !== "") {
        url.searchParams.set(k, String(v));
      }
    }
  }

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(url.toString(), {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });

  if (!res.ok) {
    let detail: unknown = null;
    try {
      detail = await res.json();
    } catch {
      detail = await res.text();
    }
    throw new ApiError(res.status, detail);
  }

  // Some endpoints (PDF exports, etc.) return non-JSON. Detect that.
  const contentType = res.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    return (await res.blob()) as unknown as T;
  }
  return (await res.json()) as T;
}

// ── Domain helpers ───────────────────────────────────────────────────────────

export interface AuthLoginResponse {
  access_token: string;
  token_type: string;
  username?: string;
  permissions?: string[];
}

export async function login(
  username: string,
  password: string,
): Promise<AuthLoginResponse> {
  return apiRequest<AuthLoginResponse>("/api/v1/auth/login", {
    method: "POST",
    body: { username, password },
  });
}

export interface DashboardSignal {
  source: string;
  label: string;
  value: number | string | null;
  unit: string;
  status: "OK" | "WARN" | "ALERT";
  detail: string;
}

export interface DashboardLiveSignalsResponse {
  generated_at: string;
  company_scope: string | null;
  signals: DashboardSignal[];
  alert_count: number;
  warn_count: number;
}

export function fetchLiveSignals(
  company?: string,
): Promise<DashboardLiveSignalsResponse> {
  return apiRequest<DashboardLiveSignalsResponse>(
    "/api/v1/dashboard/live-signals",
    { params: { company } },
  );
}

export interface Customer {
  id: number;
  company: string;
  full_name: string;
  email: string;
  phone: string;
  sector: string;
  is_active: boolean;
  email_consent?: boolean;
  sms_consent?: boolean;
  whatsapp_consent?: boolean;
}

export interface CustomerListResponse {
  total: number;
  customers: Customer[];
}

export function fetchCustomers(
  company?: string,
): Promise<CustomerListResponse> {
  return apiRequest<CustomerListResponse>("/api/v1/crm/customers", {
    params: { company },
  });
}

export interface Invoice {
  id: number;
  company: string;
  customer_id: number | null;
  invoice_number: string;
  title: string;
  amount: number;
  paid_amount: number;
  currency: string;
  status: string;
  issue_date: string;
  due_date: string;
}

export interface InvoiceListResponse {
  total: number;
  invoices: Invoice[];
}

export function fetchInvoices(
  company?: string,
): Promise<InvoiceListResponse> {
  return apiRequest<InvoiceListResponse>("/api/v1/collections/invoices", {
    params: { company },
  });
}

export interface Company {
  name: string;
  balance: number;
}

export function fetchCompanies(): Promise<Company[]> {
  return apiRequest<Company[]>("/api/v1/companies");
}

// ── Notifications (S-334) ──────────────────────────────────────────────────

export interface Notification {
  id: number;
  company: string;
  kind: string;            // 'invoice_due_soon' | 'invoice_overdue' | ...
  severity: "info" | "warning" | "critical";
  subject_type: string;    // 'invoice'
  subject_id: number;
  window_key: string;      // 'T-3' | 'T-1' | 'T+1' | 'T+7' | 'T+14'
  title: string;
  message: string;
  is_read: boolean;
  created_at: number;
  updated_at: number;
}

export interface NotificationListResponse {
  total: number;
  unread_count: number;
  notifications: Notification[];
}

export interface NotificationSummary {
  company: string | null;
  total: number;
  unread: number;
  info: number;
  warning: number;
  critical: number;
}

export function fetchNotifications(opts?: {
  company?: string;
  severity?: "info" | "warning" | "critical";
  unread_only?: boolean;
}): Promise<NotificationListResponse> {
  return apiRequest<NotificationListResponse>("/api/v1/notifications", {
    params: {
      company: opts?.company,
      severity: opts?.severity,
      unread_only: opts?.unread_only,
    },
  });
}

export function fetchNotificationSummary(
  company?: string,
): Promise<NotificationSummary> {
  return apiRequest<NotificationSummary>("/api/v1/notifications/summary", {
    params: { company },
  });
}

export function markNotificationRead(id: number): Promise<Notification> {
  return apiRequest<Notification>(`/api/v1/notifications/${id}/read`, {
    method: "PATCH",
  });
}

// ── Cashflow projection (S-332) ────────────────────────────────────────────

export interface CashflowProjectionBucket {
  label: string;              // "0–30 gün", "31–60 gün", "61–90 gün"
  expected_income: number;
  expected_expense: number;
  net: number;
  invoice_count: number;
}

export interface CashflowProjectionResponse {
  company: string | null;
  as_of_date: string;
  buckets: CashflowProjectionBucket[];
  total_expected_income: number;
  total_expected_expense: number;
  total_net: number;
}

export function fetchCashflowProjection(
  company?: string,
): Promise<CashflowProjectionResponse> {
  return apiRequest<CashflowProjectionResponse>(
    "/api/v1/finance/cashflow-projection",
    { params: { company } },
  );
}

// ── Receivables summary + aging (S-331) ────────────────────────────────────

export interface AgingBucket {
  count: number;
  outstanding: number;
}

export interface ReceivablesAging {
  days_1_30: AgingBucket;
  days_31_60: AgingBucket;
  days_61_90: AgingBucket;
  days_90_plus: AgingBucket;
  total_overdue_count: number;
  total_overdue_outstanding: number;
}

export interface ReceivablesSummary {
  company: string | null;
  pending_count: number;
  partial_count: number;
  overdue_count: number;
  paid_count: number;
  pending_amount: number;
  partial_remaining: number;
  overdue_amount: number;
  paid_amount_total: number;
  total_outstanding: number;
  aging: ReceivablesAging;
}

export function fetchReceivablesSummary(
  company?: string,
): Promise<ReceivablesSummary> {
  return apiRequest<ReceivablesSummary>("/api/v1/collections/summary", {
    params: { company },
  });
}

// ── Customer risk score (S-333) ────────────────────────────────────────────

export interface CustomerRiskScore {
  customer_id: number;
  customer_name: string;
  company: string;
  score: number;              // 0-100
  risk_level: "LOW" | "MEDIUM" | "HIGH" | "NO_HISTORY";
  confidence: "LOW" | "MEDIUM" | "HIGH";
  invoice_count: number;
  paid_count: number;
  on_time_count: number;
  late_paid_count: number;
  active_overdue_count: number;
  avg_late_days: number;
  total_billed: number;
  total_outstanding: number;
  on_time_ratio: number;
  factors: string[];
}

export function fetchCustomerRiskScore(
  customerId: number,
): Promise<CustomerRiskScore> {
  return apiRequest<CustomerRiskScore>(
    `/api/v1/crm/customers/${customerId}/risk-score`,
  );
}

// ── FX summary (S-341) ─────────────────────────────────────────────────────

export interface FxCurrencyBucket {
  currency: string;
  count: number;
  outstanding: number;
  outstanding_try: number;
  fx_rate: number;
  pct_of_total: number;
}

export interface FxReceivablesSummary {
  company: string | null;
  total_outstanding_try: number;
  fx_exposure_pct: number;
  by_currency: FxCurrencyBucket[];
  as_of_date: string;
}

export function fetchFxSummary(
  company?: string,
): Promise<FxReceivablesSummary> {
  return apiRequest<FxReceivablesSummary>("/api/v1/collections/fx-summary", {
    params: { company },
  });
}
