"use client";

/**
 * M2 — Procurement detay sayfası (RFQ → Quote → PO görünümü).
 */
import { useCallback } from "react";
import { use } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  ResourceDetailHeader,
  ResourceDetailNotFound,
} from "@/components/module/ResourceDetailHeader";
import { Skeleton } from "@/components/ui/skeleton";
import { useResource } from "@/lib/use-resource";
import {
  getProcurementRequest,
  listQuotes,
  listPurchaseOrders,
} from "@/lib/procurement-api";

export default function ProcurementDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id: idStr } = use(params);
  const id = Number(idStr);

  const reqFetcher = useCallback(() => getProcurementRequest(id), [id]);
  const quotesFetcher = useCallback(() => listQuotes(id), [id]);
  const posFetcher = useCallback(() => listPurchaseOrders(id), [id]);
  const req = useResource(reqFetcher);
  const quotes = useResource(quotesFetcher);
  const pos = useResource(posFetcher);

  if (req.loading) {
    return <Skeleton className="h-64 w-full" />;
  }
  if (req.error || !req.data) {
    return <ResourceDetailNotFound resourceLabel="RFQ" backHref="/procurement" />;
  }
  const r = req.data;

  return (
    <div className="space-y-6 animate-fade-in">
      <ResourceDetailHeader
        backHref="/procurement"
        title={r.title}
        subtitle={`${r.company ?? "—"} · #${r.id}`}
        actions={<Badge tone="info">{r.status}</Badge>}
      />

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Genel bilgi</CardTitle>
            <CardDescription>Talep özeti</CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-3 text-sm">
            <Field label="Bütçe limiti" value={r.budget_limit !== null ? `${r.currency ?? "₺"} ${r.budget_limit.toLocaleString("tr-TR")}` : "—"} />
            <Field label="Strateji" value={r.strategy} />
            <Field label="İhale referansı" value={r.tender_reference ?? "—"} />
            <Field label="Açılış" value={new Date(r.created_at * 1000).toLocaleDateString("tr-TR")} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Özet</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <SummaryRow label="Teklif sayısı" value={quotes.data?.length ?? 0} />
            <SummaryRow label="Sipariş sayısı" value={pos.data?.length ?? 0} />
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="quotes">
        <TabsList>
          <TabsTrigger value="quotes">Teklifler ({quotes.data?.length ?? 0})</TabsTrigger>
          <TabsTrigger value="pos">Sipariş ({pos.data?.length ?? 0})</TabsTrigger>
        </TabsList>
        <TabsContent value="quotes">
          {quotes.loading && <Skeleton className="h-24 w-full" />}
          {!quotes.loading && (quotes.data?.length ?? 0) === 0 && (
            <p className="text-sm text-muted-foreground">Bu talep için henüz teklif yok.</p>
          )}
          {!quotes.loading && (quotes.data?.length ?? 0) > 0 && (
            <Card>
              <CardContent className="divide-y divide-border p-0">
                {quotes.data?.map((q) => (
                  <div key={q.id} className="flex flex-wrap items-center justify-between gap-2 p-3 text-sm">
                    <div>
                      <div className="font-medium text-foreground">{q.vendor}</div>
                      <div className="text-xs text-muted-foreground">
                        Hazırlık {q.lead_time_days ?? "—"} gün
                      </div>
                    </div>
                    <div className="font-mono">{q.currency} {q.amount.toLocaleString("tr-TR")}</div>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}
        </TabsContent>
        <TabsContent value="pos">
          {pos.loading && <Skeleton className="h-24 w-full" />}
          {!pos.loading && (pos.data?.length ?? 0) === 0 && (
            <p className="text-sm text-muted-foreground">Bu talep için henüz sipariş yok.</p>
          )}
          {!pos.loading && (pos.data?.length ?? 0) > 0 && (
            <Card>
              <CardContent className="divide-y divide-border p-0">
                {pos.data?.map((p) => (
                  <div key={p.id} className="flex flex-wrap items-center justify-between gap-2 p-3 text-sm">
                    <div>
                      <div className="font-medium text-foreground">{p.vendor}</div>
                      <Badge tone="success">{p.status}</Badge>
                    </div>
                    <div className="font-mono">{p.currency} {p.amount.toLocaleString("tr-TR")}</div>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

function Field({ label, value, className = "" }: { label: string; value: string; className?: string }) {
  return (
    <div className={className}>
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-0.5 text-foreground">{value}</div>
    </div>
  );
}

function SummaryRow({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-mono font-semibold text-foreground">{value}</span>
    </div>
  );
}
