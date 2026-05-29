"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { History, Loader2, RefreshCw } from "lucide-react";
import {
  listConnectorImports,
  type ConnectorImportJob,
} from "@/lib/connectors-api";
import { LogoImportWizard } from "@/components/connectors/logo-import-wizard";
import { StagingReview } from "@/components/connectors/staging-review";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";


const STATUS_TONE: Record<string, "primary" | "warn" | "critical" | "success" | "neutral"> = {
  pending:    "neutral",
  parsing:    "primary",
  preview:    "warn",
  committing: "primary",
  completed:  "success",
  failed:     "critical",
  cancelled:  "neutral",
};


export default function ConnectorsPage() {
  const [jobs, setJobs] = useState<ConnectorImportJob[]>([]);
  const [loading, setLoading] = useState(true);

  async function refresh() {
    setLoading(true);
    try {
      const result = await listConnectorImports(15);
      setJobs(result.jobs);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void refresh(); }, []);

  return (
    <div className="space-y-6 animate-fade-in">
      <motion.header
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <Badge tone="primary" withDot>ERP Bağlantıları</Badge>
        <h1 className="text-2xl font-bold mt-2">
          Veri kaynaklarını <span className="bg-gradient-to-r from-aq-quantum-2 to-aq-plasma bg-clip-text text-transparent">bağla</span>
        </h1>
        <p className="text-sm text-aq-dust mt-1">
          Logo Tiger ve diğer ERP'lerden veri import et — XML veya Excel.
          Onay öncesi her şeyi preview'de görürsün.
        </p>
      </motion.header>

      <ErpWizardTabs onComplete={() => void refresh()} />

      <StagingReview />

      <Card className="p-6" variant="glass">
        <CardHeader className="p-0 pb-3 flex-row items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <History className="h-4 w-4 text-aq-dust" />
              Son İmportlar
            </CardTitle>
            <CardDescription className="mt-1">
              Önceki import job'larını gör.
            </CardDescription>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => void refresh()}
            disabled={loading}
          >
            {loading ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <RefreshCw className="h-3.5 w-3.5" />
            )}
          </Button>
        </CardHeader>
        <CardContent className="p-0">
          {jobs.length === 0 && !loading && (
            <p className="text-sm text-aq-dust text-center py-6">
              Henüz import yapılmadı.
            </p>
          )}
          <div className="space-y-2">
            {jobs.map((j) => (
              <div
                key={j.id}
                className="flex items-center justify-between gap-3 rounded-md border border-aq-mist/40 bg-aq-orbital/40 p-3"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <Badge tone={STATUS_TONE[j.status] ?? "neutral"} withDot>
                      {j.status}
                    </Badge>
                    <span className="text-xs font-mono text-aq-trace">
                      #{j.id} · {j.connector_type} · {j.mode}
                    </span>
                  </div>
                  <p className="text-xs text-aq-dust mt-1 truncate">
                    {j.source_filename || "—"} ·{" "}
                    {(j.source_size_bytes / 1024).toFixed(1)} KB
                  </p>
                  {j.summary && Object.keys(j.summary).length > 0 && (
                    <p className="text-[10px] font-mono text-aq-trace mt-0.5">
                      {Object.entries(j.summary)
                        .filter(([k]) => k !== "errors" || Number(j.summary[k]) > 0)
                        .map(([k, v]) => `${k}: ${v}`)
                        .join(" · ")}
                    </p>
                  )}
                </div>
                <div className="text-right text-[10px] text-aq-trace shrink-0">
                  {new Date(j.started_at * 1000).toLocaleString("tr-TR")}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}


function ErpWizardTabs({ onComplete }: { onComplete: () => void }) {
  const [active, setActive] = useState<"logo_tiger" | "mikro">("logo_tiger");
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => setActive("logo_tiger")}
          className={
            "px-3 py-1.5 rounded-full text-xs transition-colors " +
            (active === "logo_tiger"
              ? "bg-aq-quantum/20 text-aq-quantum-2 border border-aq-quantum/30"
              : "bg-aq-orbital/40 text-aq-dust border border-aq-mist/30 hover:border-aq-mist/60")
          }
        >
          Logo Tiger
        </button>
        <button
          type="button"
          onClick={() => setActive("mikro")}
          className={
            "px-3 py-1.5 rounded-full text-xs transition-colors " +
            (active === "mikro"
              ? "bg-aq-quantum/20 text-aq-quantum-2 border border-aq-quantum/30"
              : "bg-aq-orbital/40 text-aq-dust border border-aq-mist/30 hover:border-aq-mist/60")
          }
        >
          Mikro ERP
        </button>
        <span className="text-[10px] text-aq-trace ml-auto">
          Daha fazla ERP yakında
        </span>
      </div>
      <LogoImportWizard
        key={active}
        connectorType={active}
        title={
          active === "logo_tiger" ? "Logo Tiger İçe Aktar" : "Mikro ERP İçe Aktar"
        }
        onComplete={onComplete}
      />
    </div>
  );
}
