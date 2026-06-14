"use client";

/**
 * M2 — Feasibility rapor detayı.
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
import { getFeasibilityReport } from "@/lib/feasibility-api";

const TONES: Record<string, "success" | "critical" | "warn" | "neutral"> = {
  go: "success",
  no_go: "critical",
  pending: "warn",
};

export default function FeasibilityDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id: idStr } = use(params);
  const id = Number(idStr);
  const fetcher = useCallback(() => getFeasibilityReport(id), [id]);
  const r = useResource(fetcher);

  if (r.loading) return <Skeleton className="h-64 w-full" />;
  if (r.error || !r.data) return <ResourceDetailNotFound resourceLabel="Fizibilite raporu" backHref="/feasibility" />;
  const f = r.data;

  return (
    <div className="space-y-6 animate-fade-in">
      <ResourceDetailHeader
        backHref="/feasibility"
        title={f.title}
        subtitle={`${f.company ?? "—"} · ${f.sector ?? "—"}`}
        actions={
          <Badge tone={TONES[f.decision] ?? "neutral"}>
            {f.decision.toUpperCase().replace("_", "-")}
          </Badge>
        }
      />

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Genel</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-3 text-sm">
            <Field label="Skor" value={f.score !== null ? f.score.toFixed(2) : "—"} />
            <Field label="Risk" value={f.risk_level ?? "—"} />
            <Field label="Tahmini CAPEX" value={
              f.estimated_capex !== null && f.estimated_capex !== undefined
                ? `${f.currency ?? "₺"} ${f.estimated_capex.toLocaleString("tr-TR")}`
                : "—"
            } />
            <Field label="Karar tarihi" value={f.decided_at?.slice(0, 10) ?? "—"} />
            {f.notes && <Field label="Notlar" value={f.notes} className="col-span-2" />}
            <Field label="Oluşturulma" value={f.created_at} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Karar paneli</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="text-center">
              <Badge tone={TONES[f.decision] ?? "neutral"} className="text-base px-3 py-1">
                {f.decision.toUpperCase().replace("_", "-")}
              </Badge>
            </div>
            {f.score !== null && (
              <div>
                <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Skor (0-10)</div>
                <div className="mt-1 h-2 w-full rounded-full bg-muted">
                  <div
                    className="h-2 rounded-full bg-primary"
                    style={{ width: `${Math.min(100, Math.max(0, (f.score / 10) * 100))}%` }}
                  />
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
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
