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
    id: "expected_amount",
    label: "Beklenen Tutar",
    sortKey: (r) => r.expected_amount ?? 0,
    cell: (r) =>
      r.expected_amount !== null && r.expected_amount !== undefined
        ? `${r.currency ?? "₺"} ${r.expected_amount.toLocaleString("tr-TR")}`
        : null,
  },
  {
    id: "needed_by",
    label: "İhtiyaç Tarihi",
    sortKey: (r) => r.needed_by ?? "",
    cell: (r) => r.needed_by ?? null,
  },
  {
    id: "created_at",
    label: "Açılış",
    sortKey: (r) => r.created_at,
    cell: (r) => r.created_at.slice(0, 10),
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
