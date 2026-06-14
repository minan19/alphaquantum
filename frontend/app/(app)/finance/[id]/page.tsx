"use client";

/**
 * M2 — Finance ledger entry detayı.
 */
import { useCallback, use } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ResourceDetailHeader,
  ResourceDetailNotFound,
} from "@/components/module/ResourceDetailHeader";
import { useResource } from "@/lib/use-resource";
import { getLedgerEntry } from "@/lib/finance-api";

export default function LedgerDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id: idStr } = use(params);
  const id = Number(idStr);
  const fetcher = useCallback(() => getLedgerEntry(id), [id]);
  const r = useResource(fetcher);

  if (r.loading) return <Skeleton className="h-64 w-full" />;
  if (r.error || !r.data) return <ResourceDetailNotFound resourceLabel="Ledger entry" backHref="/finance" />;
  const e = r.data;

  return (
    <div className="space-y-6 animate-fade-in">
      <ResourceDetailHeader
        backHref="/finance"
        title={`Defter kaydı #${e.id}`}
        subtitle={`${e.company} · ${e.posted_at.slice(0, 10)}`}
        actions={<Badge tone="neutral">{e.category}</Badge>}
      />

      <Card>
        <CardHeader>
          <CardTitle>Detay</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-3 text-sm">
          <Field label="Tutar" value={
            <span className={e.amount < 0 ? "text-destructive" : "text-foreground"}>
              {e.currency} {e.amount.toLocaleString("tr-TR")}
            </span>
          } />
          <Field label="Hesap" value={e.account ?? "—"} />
          <Field label="Karşı taraf" value={e.counterparty ?? "—"} />
          <Field label="Inter-co" value={e.intercompany_flag ? "Evet" : "Hayır"} />
          {e.notes && <Field label="Notlar" value={e.notes} className="col-span-2" />}
          <Field label="Oluşturulma" value={e.created_at} />
        </CardContent>
      </Card>
    </div>
  );
}

function Field({ label, value, className = "" }: { label: string; value: React.ReactNode; className?: string }) {
  return (
    <div className={className}>
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-0.5 text-foreground">{value}</div>
    </div>
  );
}
