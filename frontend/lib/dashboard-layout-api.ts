/**
 * F4: Dashboard layout API client.
 *
 * Backend ile sözleşme:
 *   GET    /api/v1/dashboard/layout
 *   PUT    /api/v1/dashboard/layout
 *   DELETE /api/v1/dashboard/layout
 */
import { apiRequest } from "@/lib/api";

export type WidgetSize = "sm" | "md" | "lg";

export type KnownWidgetId =
  | "balance"
  | "fx_position"
  | "consolidated_pl"
  | "pending_transfers"
  | "exec_summary"
  | "aging_analysis"
  | "cashflow_projection"
  | "recent_invoices";

export interface DashboardWidgetConfig {
  widget_id: KnownWidgetId | string;
  size: WidgetSize;
  hidden: boolean;
  order: number;
}

export interface DashboardLayoutResponse {
  user_id: string;
  widgets: DashboardWidgetConfig[];
  is_default: boolean;
  updated_at: number;
}

export async function getDashboardLayout(): Promise<DashboardLayoutResponse> {
  return apiRequest<DashboardLayoutResponse>("/api/v1/dashboard/layout");
}

export async function saveDashboardLayout(
  widgets: DashboardWidgetConfig[],
): Promise<DashboardLayoutResponse> {
  return apiRequest<DashboardLayoutResponse>("/api/v1/dashboard/layout", {
    method: "PUT",
    body: { widgets },
  });
}

export async function resetDashboardLayout(): Promise<DashboardLayoutResponse> {
  return apiRequest<DashboardLayoutResponse>("/api/v1/dashboard/layout", {
    method: "DELETE",
  });
}

// Widget metadata (görsel etiket + ikon mapping frontend tarafı)
export interface WidgetMeta {
  id: KnownWidgetId;
  label: string;
  description: string;
  category: "corpos" | "finos" | "shared";
}

export const WIDGET_CATALOG: WidgetMeta[] = [
  {
    id: "balance",
    label: "Konsolide Bakiye",
    description: "Tüm şirketlerin ledger-derived toplam bakiyesi",
    category: "shared",
  },
  {
    id: "fx_position",
    label: "FX Net Pozisyon",
    description: "Multi-currency net pozisyon + sensitivity scenarios",
    category: "corpos",
  },
  {
    id: "consolidated_pl",
    label: "Konsolide P&L",
    description: "Holding P&L (intercompany eliminasyonlu)",
    category: "corpos",
  },
  {
    id: "pending_transfers",
    label: "Onay Kuyruğu",
    description: "4-eyes onay bekleyen intercompany transferler",
    category: "corpos",
  },
  {
    id: "exec_summary",
    label: "AI Yönetici Özeti",
    description: "Claude LLM ile günlük Türkçe rapor",
    category: "shared",
  },
  {
    id: "aging_analysis",
    label: "Alacak Yaşlandırma",
    description: "30/60/90+ gün bucket breakdown",
    category: "finos",
  },
  {
    id: "cashflow_projection",
    label: "Nakit Akışı Projeksiyonu",
    description: "30 günlük ileriye dönük tahmin",
    category: "finos",
  },
  {
    id: "recent_invoices",
    label: "Son Faturalar",
    description: "Son 7 günde oluşturulan faturalar",
    category: "finos",
  },
];
