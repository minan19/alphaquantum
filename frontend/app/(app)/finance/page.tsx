"use client";

/**
 * M2 — Finance ledger liste sayfası.
 * data-module="finos" (FinOS finans süreçleri).
 */
import { useCallback } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { ResourceListPage } from "@/components/module/ResourceListPage";
import { useResource } from "@/lib/use-resource";
import { listLedger, type LedgerEntry } from "@/lib/finance-api";
import type { ColumnDef } from "@/components/ui/data-table";

const COLUMNS: ColumnDef<LedgerEntry>[] = [
  {
    id: "id",
    label: "#",
    sortKey: (r) => r.id,
    cell: (r) => (
      <Link
        href={`/finance/${r.id}`}
        className="font-mono text-xs text-primary hover:underline"
      >
        #{r.id}
      </Link>
    ),
  },
  { id: "posted_at", label: "Tarih", sortKey: (r) => r.posted_at, cell: (r) => r.posted_at.slice(0, 10) },
  { id: "company", label: "Şirket", sortKey: (r) => r.company, cell: (r) => r.company },
  { id: "category", label: "Kategori", sortKey: (r) => r.category, cell: (r) => <Badge tone="neutral">{r.category}</Badge> },
  {
    id: "amount",
    label: "Tutar",
    sortKey: (r) => r.amount,
    cell: (r) => (
      <span className={r.amount < 0 ? "text-destructive" : "text-foreground"}>
        {r.currency} {r.amount.toLocaleString("tr-TR")}
      </span>
    ),
    className: "font-mono text-right tabular-nums",
  },
  { id: "counterparty", label: "Karşı taraf", sortKey: (r) => r.counterparty ?? "", cell: (r) => r.counterparty ?? null, defaultVisible: false },
];

export default function FinanceLedgerPage() {
  const fetcher = useCallback(
    () => listLedger({ limit: 500 }),
    [],
  );
  const resource = useResource(fetcher);

  return (
    <ResourceListPage
      title="Finans Defteri"
      description="Genel muhasebe kayıtları — gider, gelir, transfer. FinOS finans çekirdeği."
      columns={COLUMNS}
      rowId={(r) => String(r.id)}
      resource={resource}
      searchFields={(r) => `${r.company} ${r.category} ${r.counterparty ?? ""} ${r.notes ?? ""}`}
      searchPlaceholder="Şirket, kategori veya karşı tarafla ara…"
      emptyMessage="Henüz ledger kaydı yok."
      pageSize={50}
    />
  );
}
