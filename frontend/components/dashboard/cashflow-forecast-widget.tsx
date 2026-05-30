"use client";

/**
 * A3: Cash Flow Forecast Widget — "yarın param yeter mi?" sorusunun
 * canlı görsel cevabı.
 *
 * Görsel hiyerarşi:
 *   1. Hero: 30g sonra net pozisyon + MAPE rozeti ("%X doğruluk")
 *   2. Line chart: cumulative cashflow projeksiyonu
 *      - Point estimate: ana çizgi (aq-mint)
 *      - CI80 band: %80 olası aralık (mint shadow)
 *      - CI95 band: %95 olası aralık (mint shadow daha açık)
 *   3. Horizon toggle: 30 / 60 / 90 gün
 *   4. Feedback row: "Doğru çıktı / Yanılttı" — model self-tune tetikler
 *
 * Trust-by-design:
 *   - MAPE açık şekilde gösterilir (low = elite, yüksek = "sistem öğreniyor")
 *   - Model parametreleri (α, β, γ) hover'da görünür (şeffaflık)
 *   - is_reliable=false → "yeterli veri yok, tahmin riski yüksek" uyarısı
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  Activity,
  CheckCircle2,
  Loader2,
  RefreshCw,
  Sparkles,
  TrendingDown,
  TrendingUp,
  XCircle,
} from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { toast } from "sonner";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import {
  fetchCashflowForecast,
  postForecastFeedback,
  type CashflowForecastResponse,
} from "@/lib/cashflow-forecast-api";


type Horizon = 30 | 60 | 90;
const HORIZONS: Horizon[] = [30, 60, 90];


export function CashflowForecastWidget({
  scope = "*",
  className,
}: {
  scope?: string;
  className?: string;
}) {
  const [horizon, setHorizon] = useState<Horizon>(30);
  const [data, setData] = useState<CashflowForecastResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [feedbackPending, setFeedbackPending] = useState(false);
  const [feedbackGiven, setFeedbackGiven] = useState<"accurate" | "misleading" | null>(null);

  const load = useCallback(
    async (force = false) => {
      setLoading(true);
      setError(null);
      try {
        const result = await fetchCashflowForecast({
          horizon, scope, forceRefresh: force,
        });
        setData(result);
        setFeedbackGiven(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Forecast yüklenemedi");
      } finally {
        setLoading(false);
      }
    },
    [horizon, scope],
  );

  useEffect(() => { void load(false); }, [load]);

  // Cumulative cashflow data for chart
  const chartData = useMemo(() => {
    if (!data || data.points.length === 0) return [];
    let cumPoint = 0;
    let cumLow80 = 0;
    let cumHigh80 = 0;
    let cumLow95 = 0;
    let cumHigh95 = 0;
    return data.points.map((p, i) => {
      cumPoint += p.point_estimate;
      cumLow80 += p.ci80_low;
      cumHigh80 += p.ci80_high;
      cumLow95 += p.ci95_low;
      cumHigh95 += p.ci95_high;
      return {
        day: `+${p.day_offset}g`,
        point: Math.round(cumPoint),
        low80: Math.round(cumLow80),
        high80: Math.round(cumHigh80),
        low95: Math.round(cumLow95),
        high95: Math.round(cumHigh95),
        // For Recharts stacked area band visualization we need band heights
        band80: Math.round(cumHigh80 - cumLow80),
        band95: Math.round(cumHigh95 - cumLow95),
        idx: i,
      };
    });
  }, [data]);

  const finalEstimate = chartData[chartData.length - 1]?.point ?? 0;
  const isPositive = finalEstimate >= 0;
  const mape = data?.mape;
  const mapeBadgeTone =
    mape == null ? "neutral"
    : mape < 15 ? "success"
    : mape < 30 ? "warn"
    : "critical";
  const mapeLabel =
    mape == null ? "öğreniyor"
    : mape < 15 ? "elit"
    : mape < 30 ? "iyi"
    : "geliştiriliyor";

  async function handleFeedback(action: "accurate" | "misleading") {
    if (!data || feedbackPending) return;
    setFeedbackPending(true);
    try {
      const today = new Date().toISOString().split("T")[0];
      await postForecastFeedback({
        snapshot_date: today,
        feedback: action,
        scope_key: scope,
      });
      setFeedbackGiven(action);
      toast.success(
        action === "accurate"
          ? "Teşekkürler — model güçleniyor"
          : "Geri bildirim alındı — model yeniden eğitilecek",
      );
      if (action === "misleading") {
        await load(true);
      }
    } catch (err) {
      toast.error("Geri bildirim kaydedilemedi", {
        description: err instanceof Error ? err.message : "Bilinmeyen hata",
      });
    } finally {
      setFeedbackPending(false);
    }
  }

  return (
    <Card className={cn("p-6", className)} variant="glass">
      <CardHeader className="p-0 pb-4 flex-row items-start justify-between gap-3">
        <div>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-aq-mint" />
            Nakit Akışı Tahmini
          </CardTitle>
          <CardDescription className="mt-1">
            Adaptive Holt-Winters · Trend + haftalık mevsim · Kendini eğitir.
          </CardDescription>
        </div>
        <div className="flex items-center gap-1.5">
          {HORIZONS.map((h) => (
            <button
              key={h}
              type="button"
              onClick={() => setHorizon(h)}
              className={cn(
                "px-2 py-1 text-[10px] uppercase font-mono rounded transition-colors",
                horizon === h
                  ? "bg-aq-mint/20 text-aq-mint border border-aq-mint/30"
                  : "text-aq-dust hover:text-foreground border border-transparent",
              )}
            >
              {h}g
            </button>
          ))}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => void load(true)}
            disabled={loading}
            title="Yeniden hesapla"
            className="ml-1"
          >
            {loading ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <RefreshCw className="h-3.5 w-3.5" />
            )}
          </Button>
        </div>
      </CardHeader>

      <CardContent className="p-0 space-y-4">
        {error && (
          <div className="rounded-md border border-aq-fission/40 bg-aq-fission/5 p-3 text-sm text-aq-fission">
            {error}
          </div>
        )}

        {loading && !data && (
          <div className="flex items-center justify-center py-10 text-aq-dust">
            <Loader2 className="h-5 w-5 animate-spin mr-2" />
            Model hazırlanıyor…
          </div>
        )}

        {data && !data.is_reliable && (
          <div className="rounded-md border border-aq-solar/40 bg-aq-solar/5 p-3 text-xs">
            <p className="font-medium text-aq-solar">
              Sistem öğreniyor — {data.history_used} günlük veri.
            </p>
            <p className="mt-1 text-aq-dust">
              En az 14 günlük gerçek hareket sonrası güvenli tahmin başlar.
              Ledger doldurdukça model şekillenir.
            </p>
          </div>
        )}

        {data && data.is_reliable && (
          <>
            {/* Hero */}
            <div className="flex items-end justify-between gap-3">
              <div>
                <div className="text-[10px] uppercase tracking-wider text-aq-trace mb-1">
                  {horizon} gün sonra net pozisyon
                </div>
                <div
                  className={cn(
                    "text-3xl font-bold num flex items-center gap-2",
                    isPositive ? "text-aq-mint" : "text-aq-fission",
                  )}
                >
                  {isPositive ? (
                    <TrendingUp className="h-6 w-6" />
                  ) : (
                    <TrendingDown className="h-6 w-6" />
                  )}
                  {isPositive ? "+" : ""}
                  {finalEstimate.toLocaleString("tr-TR")}
                  <span className="text-base font-normal text-aq-dust">₺</span>
                </div>
                <div className="text-xs text-aq-trace mt-1">
                  {data.history_used} günlük veri · {data.cached ? "cached" : "yeni"}
                </div>
              </div>
              <div className="text-right space-y-1">
                <Badge tone={mapeBadgeTone} withDot>
                  Doğruluk: {mapeLabel}
                </Badge>
                {mape != null && (
                  <div className="text-[10px] font-mono text-aq-trace">
                    MAPE: %{mape.toFixed(1)}
                  </div>
                )}
                {data.model && (
                  <div
                    className="text-[9px] font-mono text-aq-trace"
                    title={`α=${data.model.alpha.toFixed(2)} β=${data.model.beta.toFixed(2)} γ=${data.model.gamma.toFixed(2)}`}
                  >
                    α{data.model.alpha.toFixed(2)} β{data.model.beta.toFixed(2)} γ{data.model.gamma.toFixed(2)}
                  </div>
                )}
              </div>
            </div>

            {/* Chart */}
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="grad-forecast-point" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="rgb(34 197 94)" stopOpacity={0.6} />
                      <stop offset="100%" stopColor="rgb(34 197 94)" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="grad-forecast-ci80" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="rgb(34 197 94)" stopOpacity={0.18} />
                      <stop offset="100%" stopColor="rgb(34 197 94)" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.08)" />
                  <XAxis
                    dataKey="day"
                    stroke="rgb(148 163 184)"
                    fontSize={10}
                    tickLine={false}
                    axisLine={false}
                    interval={Math.max(1, Math.floor(horizon / 7))}
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
                      border: "1px solid rgb(34 197 94 / 0.3)",
                      borderRadius: "8px",
                      fontSize: "12px",
                    }}
                    labelStyle={{ color: "rgb(148 163 184)" }}
                    formatter={(v: number, name: string) => {
                      const label =
                        name === "point" ? "Tahmin"
                        : name === "high80" ? "%80 üst"
                        : name === "low80" ? "%80 alt"
                        : name;
                      return [`${v.toLocaleString("tr-TR")} ₺`, label];
                    }}
                  />
                  <ReferenceLine y={0} stroke="rgba(148,163,184,0.4)" strokeDasharray="2 4" />
                  {/* CI95 band — disable visually if too noisy on long horizons */}
                  <Area
                    type="monotone"
                    dataKey="high95"
                    stroke="none"
                    fill="rgb(34 197 94)"
                    fillOpacity={0.06}
                    isAnimationActive={false}
                  />
                  <Area
                    type="monotone"
                    dataKey="low95"
                    stroke="none"
                    fill="rgb(15 23 42)"
                    isAnimationActive={false}
                  />
                  {/* CI80 band */}
                  <Area
                    type="monotone"
                    dataKey="high80"
                    stroke="none"
                    fill="rgb(34 197 94)"
                    fillOpacity={0.14}
                    isAnimationActive={false}
                  />
                  <Area
                    type="monotone"
                    dataKey="low80"
                    stroke="none"
                    fill="rgb(15 23 42)"
                    isAnimationActive={false}
                  />
                  {/* Point estimate line */}
                  <Area
                    type="monotone"
                    dataKey="point"
                    stroke="rgb(34 197 94)"
                    strokeWidth={2}
                    fill="url(#grad-forecast-point)"
                    fillOpacity={0.25}
                    animationDuration={900}
                    animationEasing="ease-out"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>

            {/* Feedback row — A3 self-learning loop */}
            <motion.div
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4 }}
              className="flex items-center justify-between gap-2 pt-2 border-t border-aq-mist/30"
            >
              <span className="text-[11px] text-aq-trace flex items-center gap-1.5">
                <Activity className="h-3 w-3" />
                Tahmin doğru çıktı mı? Geri bildirimin modeli eğitir.
              </span>
              <div className="flex items-center gap-1.5">
                <Button
                  variant={feedbackGiven === "accurate" ? "primary" : "ghost"}
                  size="sm"
                  onClick={() => void handleFeedback("accurate")}
                  disabled={feedbackPending || feedbackGiven !== null}
                  className="h-7 px-2 text-[11px]"
                >
                  <CheckCircle2 className="h-3 w-3 mr-1" />
                  Doğru
                </Button>
                <Button
                  variant={feedbackGiven === "misleading" ? "primary" : "ghost"}
                  size="sm"
                  onClick={() => void handleFeedback("misleading")}
                  disabled={feedbackPending || feedbackGiven !== null}
                  className="h-7 px-2 text-[11px]"
                >
                  <XCircle className="h-3 w-3 mr-1" />
                  Yanılttı
                </Button>
              </div>
            </motion.div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
