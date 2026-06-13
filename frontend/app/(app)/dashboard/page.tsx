"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  Banknote,
  Bell,
  CheckCircle2,
  Coins,
  Package,
  Receipt,
  TrendingUp,
  Wallet,
  Zap,
} from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ApiError, fetchLiveSignals, type DashboardLiveSignalsResponse, type DashboardSignal } from "@/lib/api";
import {
  fetchCashflowForecast,
  type CashflowForecastResponse,
} from "@/lib/cashflow-forecast-api";
import { StatCard } from "@/components/dashboard/stat-card";
import { CustomizeDashboardTrigger } from "@/components/dashboard/customize-modal";
import { AnomalySignalsWidget } from "@/components/dashboard/anomaly-signals-widget";
import { CashflowForecastWidget } from "@/components/dashboard/cashflow-forecast-widget";
import { SampleDataBanner } from "@/components/sample-data-banner";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useSpotlight } from "@/lib/use-spotlight";

// B8: Cashflow chart now bound to real A3 forecast API.
// Fallback (used while loading or on API failure) — deterministic sin-based,
// keeps SSR + client renders identical so React doesn't hydrate mismatch.
const FALLBACK_CASHFLOW = Array.from({ length: 30 }).map((_, i) => {
  const day = i + 1;
  const noise1 = (Math.sin(i * 12.9898) * 43758.5453) % 1;
  const inflow = 12_000 + Math.sin(i / 3) * 4_000 + Math.abs(noise1) * 3_000;
  return {
    day: `+${day}g`,
    net: Math.round(inflow * 0.3),
    ci80_low: Math.round(inflow * 0.2),
    ci80_high: Math.round(inflow * 0.4),
  };
});

/** Forecast API → chart row. Maps day_offset → "+Ng" label + bands. */
function forecastToChartData(
  fc: CashflowForecastResponse | null,
): Array<{ day: string; net: number; ci80_low: number; ci80_high: number }> {
  if (!fc || fc.points.length === 0) return FALLBACK_CASHFLOW;
  return fc.points.map((p) => ({
    day: `+${p.day_offset}g`,
    net: Math.round(p.point_estimate),
    ci80_low: Math.round(p.ci80_low),
    ci80_high: Math.round(p.ci80_high),
  }));
}

// Map API signal source → icon + tone
const SIGNAL_MAP: Record<string, { icon: typeof Activity; tone: "primary"|"ok"|"warn"|"alert"|"neutral"; label: string }> = {
  finance:       { icon: Wallet,       tone: "primary", label: "Finans" },
  inventory:     { icon: Package,      tone: "warn",    label: "Stok" },
  procurement:   { icon: Receipt,      tone: "neutral", label: "Tedarik" },
  feasibility:   { icon: CheckCircle2, tone: "neutral", label: "Fizibilite" },
  market:        { icon: TrendingUp,   tone: "primary", label: "Piyasa" },
  tasks:         { icon: Zap,          tone: "warn",    label: "Görevler" },
  notifications: { icon: Bell,         tone: "alert",   label: "Bildirimler" },
};

export default function DashboardPage() {
  const [data, setData] = useState<DashboardLiveSignalsResponse | null>(null);
  const [forecast, setForecast] = useState<CashflowForecastResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    // Faz 8 §4.3: cold-start race için 1 sessiz retry (250ms), sonra graceful
    // empty state. Kullanıcıya 'API hatası (404)' yerine boş/yükleniyor UI.
    (async () => {
      const tryOnce = async () => {
        const result = await fetchLiveSignals();
        if (!cancelled) setData(result);
      };
      try {
        await tryOnce();
      } catch (err1) {
        if (cancelled) return;
        await new Promise((r) => setTimeout(r, 250));
        if (cancelled) return;
        try {
          await tryOnce();
        } catch (err2) {
          if (cancelled) return;
          // Sessiz drop: data null kalır → UI fallback ("Bağlanılıyor…" / empty).
          // Yalnız geliştirici için console.debug (kullanıcıya yansımaz).
          if (typeof console !== "undefined") {
            console.debug("[dashboard/live-signals] retry failed:", err2);
          }
          // ApiError 4xx ise üst görsel hatayı yine bastır — empty state daha iyi.
          if (!(err2 instanceof ApiError)) {
            setError("Yüklenemedi");
          }
        }
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // B8: Real cashflow forecast (A3 engine, scope=* = all companies, 30-day horizon).
  // Fallback chart renders during load + on API failure.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const fc = await fetchCashflowForecast({ horizon: 30, scope: "*" });
        if (!cancelled) setForecast(fc);
      } catch {
        // Silent: chart falls back to deterministic shape.
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const cashflowChartData = forecastToChartData(forecast);

  return (
    <div className="space-y-6 animate-fade-in">
      {/* OBS1: Sample data banner — yeni kullanıcı için demo CTA */}
      <SampleDataBanner />

      {/* Hero header */}
      <motion.header
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.32, 0.72, 0, 1] }}
        className="flex flex-wrap items-end justify-between gap-4"
      >
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Badge tone="primary" withDot>Canlı veri</Badge>
            {data && (
              <span className="font-mono text-[10px] text-aq-trace">
                Güncellendi: {new Date(data.generated_at).toLocaleTimeString("tr-TR")}
              </span>
            )}
          </div>
          <h1 className="text-3xl font-bold tracking-tight">
            İyi günler, <span className="bg-gradient-to-r from-aq-quantum-2 to-aq-plasma bg-clip-text text-transparent">Yönetici</span>
          </h1>
          <p className="mt-1 text-sm text-aq-dust">
            {data ? (
              <>
                {data.alert_count} kritik · {data.warn_count} uyarı ·{" "}
                tüm sinyaller işlendi.
              </>
            ) : (
              <>Sinyaller yükleniyor…</>
            )}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <CustomizeDashboardTrigger />
          <Button variant="secondary" size="sm">
            <Activity className="h-3.5 w-3.5" /> Rapor üret
          </Button>
          <Button size="sm">
            <Bell className="h-3.5 w-3.5" /> Bildirim oluştur
          </Button>
        </div>
      </motion.header>

      {/* KPI Grid */}
      <section
        aria-label="Anahtar metrikler"
        className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4"
      >
        <StatCard
          label="Toplam Bakiye"
          value="847.230"
          unit="₺"
          delta={12.4}
          tone="primary"
          icon={Wallet}
          hint="Tüm şirketler"
          index={0}
        />
        <StatCard
          label="Açık Alacak"
          value="125.430"
          unit="₺"
          delta={-3.2}
          tone="warn"
          icon={Coins}
          hint="32 fatura · 4 gecikmiş"
          index={1}
        />
        <StatCard
          label="30g Net Akış"
          value="+45.200"
          unit="₺"
          delta={8.7}
          tone="ok"
          icon={TrendingUp}
          hint="Geçen 30 günde"
          index={2}
        />
        <StatCard
          label="Aktif Müşteri"
          value="248"
          delta={5.1}
          tone="primary"
          icon={Banknote}
          hint="Bu ay 12 yeni"
          index={3}
        />
      </section>

      {/* Anomaly Detection + Cashflow Forecast — CorpOS + FinOS pillars */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <motion.section
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, delay: 0.1, ease: [0.32, 0.72, 0, 1] }}
          aria-label="Anomali sinyalleri"
        >
          <AnomalySignalsWidget />
        </motion.section>
        <motion.section
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, delay: 0.15, ease: [0.32, 0.72, 0, 1] }}
          aria-label="Nakit akışı tahmini"
        >
          <CashflowForecastWidget />
        </motion.section>
      </div>

      {/* Cashflow Chart */}
      <motion.section
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.2, ease: [0.32, 0.72, 0, 1] }}
      >
        <Card className="p-6">
          <CardHeader className="p-0 pb-4 flex-row items-start justify-between">
            <div>
              <CardTitle>Nakit Akışı Tahmini</CardTitle>
              <CardDescription>
                {forecast
                  ? `Önümüzdeki ${forecast.horizon_days} gün · A3 adaptif tahmin${forecast.cached ? " (cache)" : ""}`
                  : "Önümüzdeki 30 gün · Yükleniyor…"}
              </CardDescription>
            </div>
            <div className="flex gap-1.5 items-center">
              {forecast && (
                <Badge
                  tone={forecast.is_reliable ? "success" : "warn"}
                  withDot
                >
                  {forecast.is_reliable
                    ? forecast.mape != null
                      ? `MAPE %${forecast.mape.toFixed(1)}`
                      : "Güvenilir"
                    : "Düşük güven"}
                </Badge>
              )}
              <Badge tone="primary" withDot>Net</Badge>
              <Badge tone="neutral" withDot>%80 güven</Badge>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={cashflowChartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="grad-gelir" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%"  stopColor="rgb(34 197 94)" stopOpacity={0.5} />
                      <stop offset="100%" stopColor="rgb(34 197 94)" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="grad-gider" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%"  stopColor="rgb(239 68 68)" stopOpacity={0.4} />
                      <stop offset="100%" stopColor="rgb(239 68 68)" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="grad-net" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%"  stopColor="rgb(91 71 251)" stopOpacity={0.6} />
                      <stop offset="100%" stopColor="rgb(91 71 251)" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.08)" />
                  <XAxis
                    dataKey="day"
                    stroke="rgb(148 163 184)"
                    fontSize={10}
                    tickLine={false}
                    axisLine={false}
                    interval={4}
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
                    labelStyle={{ color: "rgb(148 163 184)" }}
                    formatter={(v: number) => [
                      `${v.toLocaleString("tr-TR")} ₺`,
                      undefined,
                    ]}
                  />
                  {/* Confidence band: ci80_high then ci80_low (high painted first, low painted second to "cut out") */}
                  <Area
                    type="monotone"
                    dataKey="ci80_high"
                    stroke="rgb(34 197 94)"
                    strokeWidth={0}
                    fill="url(#grad-gelir)"
                    fillOpacity={0.35}
                    animationDuration={1200}
                    animationEasing="ease-out"
                  />
                  <Area
                    type="monotone"
                    dataKey="ci80_low"
                    stroke="rgb(239 68 68)"
                    strokeWidth={0}
                    fill="url(#grad-gider)"
                    fillOpacity={0.35}
                    animationDuration={1200}
                    animationBegin={150}
                    animationEasing="ease-out"
                  />
                  {/* Point estimate (net) — on top */}
                  <Area
                    type="monotone"
                    dataKey="net"
                    stroke="rgb(91 71 251)"
                    strokeWidth={2.5}
                    fill="url(#grad-net)"
                    fillOpacity={0.5}
                    animationDuration={1400}
                    animationBegin={300}
                    animationEasing="ease-out"
                  />
                  {forecast?.unreliable_reason && (
                    <text
                      x="50%" y="20" textAnchor="middle"
                      fill="rgb(245 158 11)" fontSize={10}
                    >
                      {forecast.unreliable_reason}
                    </text>
                  )}
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </motion.section>

      {/* Live Signals Grid */}
      <section aria-label="Canlı sinyaller" className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold tracking-tight">Canlı Sinyaller</h2>
          {data && (
            <div className="flex items-center gap-2 text-xs text-aq-dust">
              {data.alert_count > 0 && (
                <Badge tone="critical" withDot>{data.alert_count} kritik</Badge>
              )}
              {data.warn_count > 0 && (
                <Badge tone="warn" withDot>{data.warn_count} uyarı</Badge>
              )}
              {data.alert_count === 0 && data.warn_count === 0 && (
                <Badge tone="success" withDot>Tüm sistemler normal</Badge>
              )}
            </div>
          )}
        </div>

        {error && (
          <Card className="border-aq-fission/40 bg-aq-fission/5 p-4">
            <div className="flex items-center gap-3 text-sm text-aq-fission">
              <AlertTriangle className="h-4 w-4" />
              {error}
            </div>
          </Card>
        )}

        {data && (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {data.signals.map((s, i) => (
              <SignalCard key={`${s.source}-${s.label}-${i}`} signal={s} index={i} />
            ))}
          </div>
        )}

        {!data && !error && (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {[0, 1, 2, 3, 4, 5].map((i) => (
              <div
                key={i}
                className="h-28 rounded-lg border border-aq-mist/40 bg-aq-orbital/40 shimmer"
              />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────────── */

function SignalCard({ signal, index }: { signal: DashboardSignal; index: number }) {
  const meta = SIGNAL_MAP[signal.source] ?? SIGNAL_MAP.market;
  const Icon = meta.icon;
  const tone =
    signal.status === "ALERT" ? "alert" :
    signal.status === "WARN"  ? "warn"  :
    "ok";
  const { ref, onMouseMove } = useSpotlight<HTMLDivElement>();

  return (
    <motion.div
      ref={ref}
      onMouseMove={onMouseMove}
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.35, delay: 0.04 * index, ease: [0.32, 0.72, 0, 1] }}
      className="spotlight-card rounded-lg"
    >
      <Card variant="glass" className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-1">
            <div className="flex items-center gap-2 text-[10px] uppercase tracking-wider text-aq-trace">
              <Icon className="h-3 w-3" />
              {meta.label}
            </div>
            <p className="text-sm font-medium">{signal.label}</p>
            <p className="text-2xl font-bold num">
              {signal.value ?? "—"}
              {signal.unit && (
                <span className="ml-1 text-xs font-normal text-aq-dust">{signal.unit}</span>
              )}
            </p>
          </div>
          <Badge
            tone={tone === "alert" ? "critical" : tone === "warn" ? "warn" : "success"}
            withDot
          >
            {signal.status}
          </Badge>
        </div>
        {signal.detail && (
          <p className="mt-2 text-[11px] text-aq-trace">{signal.detail}</p>
        )}
      </Card>
    </motion.div>
  );
}
