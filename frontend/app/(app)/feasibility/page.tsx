"use client";

/**
 * M2 — Feasibility (GO/NO-GO) raporları listesi.
 * data-module="corpos" (üst yönetim karar süreçleri).
 */
import { useCallback } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { ResourceListPage } from "@/components/module/ResourceListPage";
import { useResource } from "@/lib/use-resource";
import {
  listFeasibilityReports,
  type FeasibilityReport,
} from "@/lib/feasibility-api";
import type { ColumnDef } from "@/components/ui/data-table";

const DECISION_TONES: Record<string, "success" | "critical" | "warn" | "neutral"> = {
  go: "success",
  no_go: "critical",
  pending: "warn",
};

const COLUMNS: ColumnDef<FeasibilityReport>[] = [
  {
    id: "title",
    label: "Proje",
    sortKey: (r) => r.title,
    cell: (r) => (
      <Link
        href={`/feasibility/${r.id}`}
        className="font-medium text-foreground hover:text-primary transition-colors"
      >
        {r.title}
      </Link>
    ),
  },
  { id: "company", label: "Şirket", sortKey: (r) => r.company ?? "", cell: (r) => r.company ?? "—" },
  { id: "sector", label: "Sektör", sortKey: (r) => r.sector ?? "", cell: (r) => r.sector ?? "—" },
  {
    id: "decision",
    label: "Karar",
    sortKey: (r) => r.decision,
    cell: (r) => (
      <Badge tone={DECISION_TONES[r.decision] ?? "neutral"}>{r.decision.toUpperCase().replace("_", "-")}</Badge>
    ),
  },
  {
    id: "score",
    label: "Skor",
    sortKey: (r) => r.score ?? 0,
    cell: (r) => (r.score !== null ? r.score.toFixed(2) : null),
    className: "font-mono tabular-nums",
  },
  {
    id: "estimated_capex",
    label: "Tahmini CAPEX",
    sortKey: (r) => r.estimated_capex ?? 0,
    cell: (r) =>
      r.estimated_capex !== null && r.estimated_capex !== undefined
        ? `${r.currency ?? "₺"} ${r.estimated_capex.toLocaleString("tr-TR")}`
        : null,
  },
  { id: "risk_level", label: "Risk", sortKey: (r) => r.risk_level ?? "", cell: (r) => r.risk_level ?? "—", defaultVisible: false },
];

export default function FeasibilityListPage() {
  const fetcher = useCallback(() => listFeasibilityReports({ limit: 500 }), []);
  const resource = useResource(fetcher);

  return (
    <ResourceListPage
      title="Fizibilite Raporları"
      description="GO / NO-GO karar belgeleri — yatırım/strateji yüzeyi. CorpOS karar dosyası."
      columns={COLUMNS}
      rowId={(r) => String(r.id)}
      resource={resource}
      searchFields={(r) => `${r.title} ${r.company ?? ""} ${r.sector ?? ""}`}
      searchPlaceholder="Proje, şirket veya sektörle ara…"
      emptyMessage="Henüz fizibilite raporu yok."
      pageSize={25}
    />
  );
}
