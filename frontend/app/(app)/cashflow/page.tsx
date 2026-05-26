"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Globe2,
  Layers,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  fetchCashflowProjection,
  fetchCompanies,
  fetchFxSummary,
  fetchReceivablesSummary,
  type CashflowProjectionResponse,
  type FxReceivablesSummary,
  type ReceivablesSummary,
} from "@/lib/api";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/cn";

function fmtTRY(n: number): string {
  return new Intl.NumberFormat("tr-TR", {
    style: "currency", currency: "TRY", minimumFractionDigits: 0,
  }).format(n);
}

const PIE_COLORS = [
  "rgb(91 71 251)",   // quantum
  "rgb(6 182 212)",   // plasma
  "rgb(245 158 11)",  // solar
  "rgb(239 68 68)",   // fission
  "rgb(34 197 94)",   // fusion
  "rgb(124 96 255)",  // quantum-2
];

export default function CashflowPage() {
  const [projection, setProjection] = useState<CashflowProjectionResponse | null>(null);
  const [aging, setAging] = useState<ReceivablesSummary | null>(null);
  const [fx, setFx] = useState<FxReceivablesSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const companies = await fetchCompanies();
        const company = companies[0]?.name;
        const [p, a, f] = await Promise.all([
          fetchCashflowProjection(company).catch(() => null),
          fetchReceivablesSummary(company).catch(() => null),
          fetchFxSummary(company).catch(() => null),
        ]);
        if (!cancelled) {
          setProjection(p);
          setAging(a);
          setFx(f);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  return (
    <div className="space-y-6 animate-fade-in">
      <header>
        <div className="flex items-center gap-2 mb-2">
          <Badge tone="primary" withDot>FinOS</Badge>
          <span className="text-xs text-aq-trace font-mono">Cashflow Intelligence · S-331 + S-332 + S-341</span>
        </div>
        <h1 className="text-3xl font-bold tracking-tight">
          <span className="bg-gradient-to-r from-aq-quantum-2 to-aq-plasma bg-clip-text text-transparent">
            Nakit Akışı
          </span>{" "}
          Zekası
        </h1>
        <p className="mt-1 text-sm text-aq-dust">
          30/60/90 gün projeksiyon · alacak yaşlandırma · FX exposure
        </p>
      </header>

      {/* Projection chart */}
      <motion.section
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.55, ease: [0.32, 0.72, 0, 1] }}
      >
        <Card className="p-6">
          <CardHeader className="p-0 pb-4 flex-row items-start justify-between">
            <div>
              <CardTitle>30-60-90 Gün Projeksiyon</CardTitle>
              <CardDescription>
                Bekleyen + kısmi faturalar (gelir) + tekrarlayan giderler
              </CardDescription>
            </div>
            {projection && (
              <div className="text-right">
                <div className="text-[10px] uppercase tracking-wider text-aq-trace">90 Gün Net</div>
                <div className={cn(
                  "text-2xl font-bold tabular num",
                  projection.total_net >= 0 ? "text-aq-fusion" : "text-aq-fission",
                )}>
                  {projection.total_net >= 0 ? "+" : ""}{fmtTRY(projection.total_net)}
                </div>
              </div>
            )}
          </CardHeader>
          <CardContent className="p-0">
            {loading || !projection ? (
              <div className="h-72 shimmer rounded" />
            ) : (
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={projection.buckets} barGap={8}>
                    <defs>
                      <linearGradient id="gIncome" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="rgb(34 197 94)" stopOpacity={0.85} />
                        <stop offset="100%" stopColor="rgb(34 197 94)" stopOpacity={0.25} />
                      </linearGradient>
                      <linearGradient id="gExpense" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="rgb(239 68 68)" stopOpacity={0.85} />
                        <stop offset="100%" stopColor="rgb(239 68 68)" stopOpacity={0.25} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.08)" />
                    <XAxis
                      dataKey="label"
                      stroke="rgb(148 163 184)"
                      fontSize={11}
                      tickLine={false}
                      axisLine={false}
                    />
                    <YAxis
                      stroke="rgb(148 163 184)"
                      fontSize={10}
                      tickLine={false}
                      axisLine={false}
                      tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
                    />
                    <Tooltip
                      contentStyle={{
                        background: "rgb(20 32 58 / 0.95)",
                        border: "1px solid rgb(91 71 251 / 0.3)",
                        borderRadius: "8px",
                        fontSize: "12px",
                      }}
                      formatter={(v: number) => fmtTRY(v)}
                    />
                    <Bar dataKey="expected_income"  fill="url(#gIncome)"  radius={[6, 6, 0, 0]} name="Gelir" />
                    <Bar dataKey="expected_expense" fill="url(#gExpense)" radius={[6, 6, 0, 0]} name="Gider" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>
      </motion.section>

      {/* Aging + FX side by side */}
      <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Aging breakdown */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, delay: 0.1 }}
        >
          <Card className="p-6 h-full">
            <CardHeader className="p-0 pb-4">
              <CardTitle className="flex items-center gap-2">
                <Layers className="h-4 w-4 text-aq-solar" />
                Alacak Yaşlandırma
              </CardTitle>
              <CardDescription>Vadesi geçmiş alacakların dilim dağılımı (S-331)</CardDescription>
            </CardHeader>
            <CardContent className="p-0 space-y-3">
              {loading || !aging ? (
                <div className="h-48 shimmer rounded" />
              ) : (
                <>
                  <AgingRow label="1-30 gün"   bucket={aging.aging.days_1_30}   total={aging.aging.total_overdue_outstanding} tone="primary" />
                  <AgingRow label="31-60 gün"  bucket={aging.aging.days_31_60}  total={aging.aging.total_overdue_outstanding} tone="warn" />
                  <AgingRow label="61-90 gün"  bucket={aging.aging.days_61_90}  total={aging.aging.total_overdue_outstanding} tone="critical" />
                  <AgingRow label="90+ gün"    bucket={aging.aging.days_90_plus} total={aging.aging.total_overdue_outstanding} tone="critical" />
                  <div className="mt-4 pt-4 border-t border-aq-mist/40 flex justify-between text-sm">
                    <span className="text-aq-dust">Toplam vadesi geçmiş</span>
                    <span className="font-bold tabular num text-aq-fission">
                      {fmtTRY(aging.aging.total_overdue_outstanding)}
                    </span>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </motion.div>

        {/* FX Exposure */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, delay: 0.15 }}
        >
          <Card className="p-6 h-full">
            <CardHeader className="p-0 pb-4">
              <CardTitle className="flex items-center gap-2">
                <Globe2 className="h-4 w-4 text-aq-plasma" />
                FX Exposure
              </CardTitle>
              <CardDescription>Çok para birimi pozisyonu (S-341)</CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              {loading || !fx ? (
                <div className="h-48 shimmer rounded" />
              ) : fx.by_currency.length === 0 ? (
                <div className="py-12 text-center text-sm text-aq-dust">
                  Henüz açık alacak yok.
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-6 items-center">
                  <div className="h-44">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={fx.by_currency}
                          dataKey="outstanding_try"
                          nameKey="currency"
                          innerRadius="55%"
                          outerRadius="85%"
                          paddingAngle={2}
                          stroke="rgb(10 18 38)"
                          strokeWidth={2}
                        >
                          {fx.by_currency.map((_, i) => (
                            <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                          ))}
                        </Pie>
                        <Tooltip
                          contentStyle={{
                            background: "rgb(20 32 58 / 0.95)",
                            border: "1px solid rgb(91 71 251 / 0.3)",
                            borderRadius: "8px",
                            fontSize: "12px",
                          }}
                          formatter={(v: number) => fmtTRY(v)}
                        />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="space-y-2">
                    {fx.by_currency.slice(0, 5).map((c, i) => (
                      <div key={c.currency} className="flex items-center gap-2 text-xs">
                        <div
                          className="h-2 w-2 rounded-full shrink-0"
                          style={{ background: PIE_COLORS[i % PIE_COLORS.length] }}
                        />
                        <span className="font-mono font-medium">{c.currency}</span>
                        <span className="flex-1 text-right tabular num text-aq-dust">
                          {c.pct_of_total.toFixed(0)}%
                        </span>
                      </div>
                    ))}
                    <div className="pt-2 mt-2 border-t border-aq-mist/40">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-aq-trace uppercase tracking-wider">FX Riski</span>
                        <Badge
                          tone={fx.fx_exposure_pct > 50 ? "critical" : fx.fx_exposure_pct > 20 ? "warn" : "success"}
                          className="px-1.5 py-0 text-[10px]"
                        >
                          %{fx.fx_exposure_pct.toFixed(1)}
                        </Badge>
                      </div>
                      <div className="mt-2 text-xs text-aq-dust">
                        Toplam: <span className="tabular num font-medium text-foreground">
                          {fmtTRY(fx.total_outstanding_try)}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>
      </section>
    </div>
  );
}

function AgingRow({
  label, bucket, total, tone,
}: {
  label: string;
  bucket: { count: number; outstanding: number };
  total: number;
  tone: "primary" | "warn" | "critical";
}) {
  const pct = total > 0 ? (bucket.outstanding / total) * 100 : 0;
  const barClass = {
    primary:  "bg-gradient-to-r from-aq-quantum to-aq-quantum-2",
    warn:     "bg-gradient-to-r from-aq-solar to-aq-solar/60",
    critical: "bg-gradient-to-r from-aq-fission to-aq-fission/60",
  }[tone];
  return (
    <div>
      <div className="flex items-baseline justify-between mb-1.5">
        <div className="text-sm">
          <span className="font-medium">{label}</span>
          <span className="ml-2 text-xs text-aq-trace tabular num">({bucket.count} fatura)</span>
        </div>
        <span className="text-sm font-medium tabular num">{fmtTRY(bucket.outstanding)}</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-aq-mist">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.8, ease: [0.32, 0.72, 0, 1] }}
          className={cn("h-full", barClass)}
        />
      </div>
    </div>
  );
}
