"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Building2,
  ChevronRight,
  Package,
  Wallet,
} from "lucide-react";
import { ApiError, fetchCompanies, type Company } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";

function fmt(n: number) {
  return new Intl.NumberFormat("tr-TR", {
    style: "currency", currency: "TRY", minimumFractionDigits: 0,
  }).format(n);
}

export default function CompaniesPage() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const list = await fetchCompanies();
        if (!cancelled) setCompanies(list);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? `API hatası (${err.status})` : "Yüklenemedi");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const totalBalance = companies.reduce((s, c) => s + c.balance, 0);

  return (
    <div className="space-y-6 animate-fade-in">
      <header>
        <div className="flex items-center gap-2 mb-2">
          <Badge tone="primary" withDot>CorpOS</Badge>
          <span className="text-xs text-aq-trace font-mono">Multi-Company Portfolio</span>
        </div>
        <h1 className="text-3xl font-bold tracking-tight">Şirket Portföyü</h1>
        <p className="mt-1 text-sm text-aq-dust">
          {companies.length} şirket · Toplam bakiye{" "}
          <span className="font-medium text-foreground tabular num">{fmt(totalBalance)}</span>
        </p>
      </header>

      {loading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-44 rounded-lg shimmer" />
          ))}
        </div>
      ) : error ? (
        <Card className="border-aq-fission/40 bg-aq-fission/5 p-4 text-sm text-aq-fission">
          {error}
        </Card>
      ) : (
        <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {companies.map((c, i) => {
            const isNegative = c.balance < 0;
            const isHigh = c.balance > 100_000;
            return (
              <motion.div
                key={c.name}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: i * 0.05, ease: [0.32, 0.72, 0, 1] }}
              >
                <Card
                  variant="default"
                  className={cn(
                    "group p-5 cursor-pointer relative overflow-hidden",
                    isNegative && "ring-1 ring-aq-fission/30",
                    isHigh && "ring-1 ring-aq-fusion/30",
                  )}
                >
                  {/* Top status gradient */}
                  <div
                    className={cn(
                      "absolute -right-12 -top-12 h-36 w-36 rounded-full blur-3xl opacity-50",
                      isNegative ? "bg-aq-fission" : isHigh ? "bg-aq-fusion" : "bg-aq-quantum",
                    )}
                  />

                  <div className="relative space-y-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-center gap-3">
                        <div className="grid h-10 w-10 place-items-center rounded-lg bg-gradient-to-br from-aq-quantum/15 to-aq-plasma/15 ring-1 ring-aq-quantum/25">
                          <Building2 className="h-5 w-5 text-aq-quantum-2" />
                        </div>
                        <div>
                          <h3 className="font-semibold leading-tight">{c.name}</h3>
                          <p className="text-[10px] uppercase tracking-wider text-aq-trace mt-0.5">
                            Holding üyesi
                          </p>
                        </div>
                      </div>
                      <Badge
                        tone={isNegative ? "critical" : isHigh ? "success" : "primary"}
                        withDot
                      >
                        {isNegative ? "Risk" : isHigh ? "Sağlam" : "Aktif"}
                      </Badge>
                    </div>

                    <div>
                      <div className="text-[10px] uppercase tracking-wider text-aq-trace">
                        Bakiye
                      </div>
                      <div className={cn(
                        "text-2xl font-bold tabular num mt-0.5",
                        isNegative && "text-aq-fission",
                        isHigh && "text-aq-fusion",
                      )}>
                        {fmt(c.balance)}
                      </div>
                    </div>

                    <div className="flex items-center justify-between text-xs">
                      <div className="flex items-center gap-1.5 text-aq-dust">
                        <Package className="h-3 w-3" />
                        <span>Envanter</span>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        Detay <ChevronRight className="h-3 w-3" />
                      </Button>
                    </div>

                    {/* Mini sparkline placeholder */}
                    <div className="flex items-end gap-0.5 h-6">
                      {Array.from({ length: 14 }).map((_, idx) => {
                        // Deterministic noise (sin-based) for SSR/CSR consistency.
                        const noise = Math.abs((Math.sin((idx + i) * 12.9898) * 43758.5453) % 1);
                        const h = 30 + Math.sin((idx + i) / 2) * 25 + noise * 20;
                        return (
                          <div
                            key={idx}
                            className={cn(
                              "flex-1 rounded-sm transition-all duration-500",
                              "group-hover:scale-y-110 origin-bottom",
                              isNegative
                                ? "bg-aq-fission/40 group-hover:bg-aq-fission/70"
                                : isHigh
                                ? "bg-aq-fusion/40 group-hover:bg-aq-fusion/70"
                                : "bg-aq-quantum/40 group-hover:bg-aq-quantum/70",
                            )}
                            style={{ height: `${h}%` }}
                          />
                        );
                      })}
                    </div>
                  </div>
                </Card>
              </motion.div>
            );
          })}
        </section>
      )}

      {/* Footer hint */}
      <div className="flex items-center gap-2 text-xs text-aq-trace font-mono">
        <Wallet className="h-3 w-3 text-aq-quantum-2" />
        {`Şirket karşılaştırma paneli için ComparisonEngine'a bağlanacak (S-313)`}
      </div>
    </div>
  );
}
