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
