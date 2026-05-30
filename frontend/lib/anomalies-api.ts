/**
 * A2: Cross-Company Anomaly Detection — API client.
 *
 * Backend sözleşmesi:
 *   GET    /api/v1/anomalies             — listele (filter: severity, holding)
 *   POST   /api/v1/anomalies/run         — manuel detection trigger
 *   POST   /api/v1/anomalies/{id}/review — confirm / dismiss
 */
import { apiRequest } from "@/lib/api";

export type AnomalySeverity = "critical" | "high" | "medium" | "low";
export type AnomalyStatus = "open" | "confirmed" | "dismissed";
export type AnomalySignalType =
  | "intercompany_leakage"
  | "volume_spike"
  | "duplicate_payment"
  | "velocity_anomaly";

export interface AnomalySignal {
  id: number;
  holding_id: number | null;
  signal_type: AnomalySignalType | string;
  severity: AnomalySeverity;
  confidence_pct: number;
  modified_z: number;
  title: string;
  description: string;
  baseline: Record<string, unknown>;
  payload: Record<string, unknown>;
  detected_at: number;
  status: AnomalyStatus;
  reviewed_by: string | null;
  reviewed_at: number | null;
  review_note: string | null;
}

export interface AnomaliesListResponse {
  signals: AnomalySignal[];
  critical_count: number;
  high_count: number;
  medium_count: number;
  total_open: number;
  generated_at: number;
}

export interface AnomalyDetectionRunResponse {
  new_signals: number;
  detectors_run: string[];
  duration_ms: number;
  generated_at: number;
}

export async function fetchAnomalies(params?: {
  holdingId?: number;
  minSeverity?: AnomalySeverity;
  limit?: number;
}): Promise<AnomaliesListResponse> {
  const search = new URLSearchParams();
  if (params?.holdingId !== undefined) search.set("holding_id", String(params.holdingId));
  if (params?.minSeverity) search.set("min_severity", params.minSeverity);
  if (params?.limit) search.set("limit", String(params.limit));
  const qs = search.toString() ? `?${search.toString()}` : "";
  return apiRequest<AnomaliesListResponse>(`/api/v1/anomalies${qs}`);
}

export async function runAnomalyDetection(
  holdingId?: number,
): Promise<AnomalyDetectionRunResponse> {
  const qs = holdingId !== undefined ? `?holding_id=${holdingId}` : "";
  return apiRequest<AnomalyDetectionRunResponse>(
    `/api/v1/anomalies/run${qs}`,
    { method: "POST" },
  );
}

export async function reviewAnomaly(
  id: number,
  action: "confirm" | "dismiss",
  note?: string,
): Promise<AnomalySignal> {
  return apiRequest<AnomalySignal>(`/api/v1/anomalies/${id}/review`, {
    method: "POST",
    body: { action, note },
  });
}

// ── A2.1: Adaptive calibration ────────────────────────────────────────

export interface AnomalyDetectorMetric {
  confirmed: number;
  dismissed: number;
  total_reviews: number;
  measured_precision: number | null;
  threshold_offset: number;
  reliability: number;
}

export interface AnomalyCalibrationOverview {
  measured_precision: number | null;
  total_reviews: number;
  confirmed: number;
  dismissed: number;
  whitelisted_patterns: number;
  is_learned: boolean;
  per_detector: Record<string, AnomalyDetectorMetric>;
}

export async function fetchAnomalyCalibration(): Promise<AnomalyCalibrationOverview> {
  return apiRequest<AnomalyCalibrationOverview>("/api/v1/anomalies/calibration");
}

// ── Display helpers ────────────────────────────────────────────────────

export const SIGNAL_TYPE_LABEL: Record<string, string> = {
  intercompany_leakage: "Cross-Company Sızıntı",
  volume_spike: "Hacim Sıçraması",
  duplicate_payment: "Mükerrer Ödeme",
  velocity_anomaly: "Sıklık Anomalisi",
};

export const SEVERITY_LABEL: Record<AnomalySeverity, string> = {
  critical: "Kritik",
  high: "Yüksek",
  medium: "Orta",
  low: "Düşük",
};

export function severityTone(
  s: AnomalySeverity,
): "critical" | "warn" | "primary" | "neutral" {
  switch (s) {
    case "critical": return "critical";
    case "high":     return "warn";
    case "medium":   return "primary";
    default:         return "neutral";
  }
}
