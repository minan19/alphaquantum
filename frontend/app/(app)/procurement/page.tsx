"use client";

/**
 * M2 — Procurement (RFQ / teklif / PO) liste sayfası.
 * data-module="corpos" (CorpOS satın alma süreçleri).
 */
import { useCallback } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { ResourceListPage } from "@/components/module/ResourceListPage";
import { useResource } from "@/lib/use-resource";
import {
  listProcurementRequests,
  type ProcurementRequest,
} from "@/lib/procurement-api";
import type { ColumnDef } from "@/components/ui/data-table";

const STATUS_TONES: Record<string, "neutral" | "success" | "warn" | "critical" | "info" | "primary"> = {
  draft: "neutral",
  open: "info",
  in_review: "warn",
  awarded: "success",
  cancelled: "critical",
  closed: "neutral",
};

const COLUMNS: ColumnDef<ProcurementRequest>[] = [
  {
    id: "title",
    label: "Başlık",
    sortKey: (r) => r.title,
    cell: (r) => (
      <Link
        href={`/procurement/${r.id}`}
        className="font-medium text-foreground hover:text-primary transition-colors"
      >
        {r.title}
      </Link>
    ),
  },
  { id: "company", label: "Şirket", sortKey: (r) => r.company ?? "", cell: (r) => r.company ?? "—" },
  {
    id: "status",
    label: "Durum",
    sortKey: (r) => r.status,
    cell: (r) => (
      <Badge tone={STATUS_TONES[r.status] ?? "neutral"}>{r.status}</Badge>
    ),
  },
  {
    id: "budget_limit",
    label: "Bütçe Limiti",
    sortKey: (r) => r.budget_limit ?? 0,
    cell: (r) =>
      r.budget_limit !== null && r.budget_limit !== undefined
        ? `${r.currency ?? "₺"} ${r.budget_limit.toLocaleString("tr-TR")}`
        : null,
    className: "font-mono tabular-nums",
  },
  {
    id: "strategy",
    label: "Strateji",
    sortKey: (r) => r.strategy,
    cell: (r) => <Badge tone="neutral">{r.strategy}</Badge>,
  },
  {
    id: "created_at",
    label: "Açılış",
    sortKey: (r) => r.created_at,
    cell: (r) => new Date(r.created_at * 1000).toLocaleDateString("tr-TR"),
    defaultVisible: false,
  },
];

export default function ProcurementListPage() {
  const fetcher = useCallback(
    () => listProcurementRequests({ limit: 500 }),
    [],
  );
  const resource = useResource(fetcher);

  return (
    <ResourceListPage
      title="Satın Alma Talepleri"
      description="RFQ → teklif değerlendirme → Purchase Order zinciri. CorpOS satın alma süreçleri."
      columns={COLUMNS}
      rowId={(r) => String(r.id)}
      resource={resource}
      searchFields={(r) => `${r.title} ${r.company ?? ""} ${r.status}`}
      searchPlaceholder="Başlık, şirket veya durumla ara…"
      emptyMessage="Henüz satın alma talebi yok."
      pageSize={25}
    />
  );
}
