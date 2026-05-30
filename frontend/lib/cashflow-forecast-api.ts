/**
 * A3: Cash Flow Forecasting — API client.
 */
import { apiRequest } from "@/lib/api";

export interface CashflowForecastPoint {
  day_offset: number;
  point_estimate: number;
  ci80_low: number;
  ci80_high: number;
  ci95_low: number;
  ci95_high: number;
}

export interface CashflowForecastModelMeta {
  alpha: number;
  beta: number;
  gamma: number;
  period_days: number;
  level: number;
  trend: number;
}

export interface CashflowForecastResponse {
  horizon_days: number;
  points: CashflowForecastPoint[];
  history_used: number;
  mape: number | null;
  rmse: number | null;
  is_reliable: boolean;
  model: CashflowForecastModelMeta | null;
  generated_at: number;
  cached: boolean;
  unreliable_reason: string | null;
  narrative: string | null;
}

export async function fetchCashflowForecast(params?: {
  horizon?: number;
  scope?: string;
  forceRefresh?: boolean;
}): Promise<CashflowForecastResponse> {
  const search = new URLSearchParams();
  if (params?.horizon) search.set("horizon", String(params.horizon));
  if (params?.scope) search.set("scope", params.scope);
  if (params?.forceRefresh) search.set("force_refresh", "true");
  const qs = search.toString() ? `?${search.toString()}` : "";
  return apiRequest<CashflowForecastResponse>(`/api/v1/cashflow/forecast${qs}`);
}

export interface CashflowAccuracyEntry {
  snapshot_date: string;
  mape: number;
  rmse: number;
  test_size: number;
  user_feedback: string | null;
  user_feedback_at: number | null;
}

export interface CashflowAccuracyHistoryResponse {
  entries: CashflowAccuracyEntry[];
  median_mape_last_30d: number | null;
  feedback_accuracy_ratio: number | null;
}

export async function fetchCashflowForecastAccuracy(
  scope: string = "*",
  limit: number = 30,
): Promise<CashflowAccuracyHistoryResponse> {
  const qs = `?scope=${encodeURIComponent(scope)}&limit=${limit}`;
  return apiRequest<CashflowAccuracyHistoryResponse>(
    `/api/v1/cashflow/forecast/accuracy${qs}`,
  );
}

export async function postForecastFeedback(payload: {
  snapshot_date: string;
  feedback: "accurate" | "misleading";
  scope_key?: string;
}): Promise<{ recorded: boolean }> {
  return apiRequest<{ recorded: boolean }>(
    "/api/v1/cashflow/forecast/feedback",
    {
      method: "POST",
      body: {
        snapshot_date: payload.snapshot_date,
        feedback: payload.feedback,
        scope_key: payload.scope_key ?? "*",
      },
    },
  );
}
