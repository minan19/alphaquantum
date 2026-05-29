"use client";

/**
 * A2: Anomaly Signals Widget — dashboard'daki "sızıntı dedektörü".
 *
 * Sadece kritik + yüksek tier sinyaller gösterilir (false-positive
 * yorgunluğu sıfır). Her kart: severity badge, confidence%, başlık,
 * Türkçe açıklama, Onayla / Yanlış-alarm aksiyonları.
 *
 * Güven katmanı görsel hiyerarşisi:
 *   * critical → aq-fission (kırmızı), pulsing dot, prominent
 *   * high     → aq-amber (sarı), normal
 *   * (lower tiers backend zaten filtreliyor)
 */
import { useCallback, useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  AlertTriangle,
  Check,
  ChevronRight,
  Loader2,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  X,
} from "lucide-react";
import { toast } from "sonner";
import {
  fetchAnomalies,
  fetchAnomalyCalibration,
  reviewAnomaly,
  runAnomalyDetection,
  severityTone,
  SEVERITY_LABEL,
  SIGNAL_TYPE_LABEL,
  type AnomaliesListResponse,
  type AnomalyCalibrationOverview,
  type AnomalySignal,
} from "@/lib/anomalies-api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/cn";


export function AnomalySignalsWidget({
  holdingId,
  className,
}: {
  holdingId?: number;
  className?: string;
}) {
  const [data, setData] = useState<AnomaliesListResponse | null>(null);
  const [calibration, setCalibration] = useState<AnomalyCalibrationOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [reviewing, setReviewing] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [signals, calib] = await Promise.all([
        fetchAnomalies({ holdingId, minSeverity: "high", limit: 10 }),
        fetchAnomalyCalibration().catch(() => null),
      ]);
      setData(signals);
      setCalibration(calib);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [holdingId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleRun() {
    setRunning(true);
    try {
      const result = await runAnomalyDetection(holdingId);
      toast.success(
        result.new_signals > 0
          ? `${result.new_signals} yeni sinyal yakalandı 🎯`
          : "Tarama tamamlandı — yeni anomali yok",
        { description: `${result.detectors_run.length} dedektör · ${result.duration_ms}ms` },
      );
      await load();
    } catch (err) {
      toast.error("Tarama başarısız", {
        description: err instanceof Error ? err.message : "Bilinmeyen hata",
      });
    } finally {
      setRunning(false);
    }
  }

  async function handleReview(
    signal: AnomalySignal,
    action: "confirm" | "dismiss",
  ) {
    setReviewing(signal.id);
    try {
      await reviewAnomaly(signal.id, action);
      toast.success(
        action === "confirm"
          ? "Onaylandı — sinyal kapatıldı"
          : "Yanlış alarm olarak işaretlendi",
      );
      // Optimistic: listeden çıkar
      setData((prev) =>
        prev
          ? {
              ...prev,
              signals: prev.signals.filter((s) => s.id !== signal.id),
              total_open: Math.max(0, prev.total_open - 1),
              [action === "confirm" ? "critical_count" : "high_count"]:
                Math.max(
                  0,
                  (action === "confirm"
                    ? prev.critical_count
                    : prev.high_count) - 1,
                ),
            }
          : prev,
      );
    } catch (err) {
      toast.error("İşlem başarısız", {
        description: err instanceof Error ? err.message : "Bilinmeyen hata",
      });
    } finally {
      setReviewing(null);
    }
  }

  return (
    <Card className={cn("p-6", className)} variant="glass">
      <CardHeader className="p-0 pb-4 flex-row items-start justify-between gap-3">
        <div>
          <CardTitle className="flex items-center gap-2">
            <ShieldAlert className="h-4 w-4 text-aq-fission" />
            Çapraz-şirket Anomali Dedektörü
          </CardTitle>
          <CardDescription className="mt-1">
            %99+ güven katmanlı sinyaller — yorgunluğunu çürütmüyoruz, sadece
            önemli olanı gösteriyoruz.
          </CardDescription>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={handleRun}
          disabled={running || loading}
          title="Tarama tekrar başlat"
        >
          {running ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <RefreshCw className="h-3.5 w-3.5" />
          )}
          <span className="ml-1.5">Tara</span>
        </Button>
      </CardHeader>

      <CardContent className="p-0 space-y-3">
        {/* A2.1: Self-learning precision KPI */}
        {calibration && (
          <CalibrationBanner overview={calibration} />
        )}

        {/* Summary strip */}
        {data && (
          <div className="flex items-center gap-2 text-xs">
            {data.critical_count > 0 && (
              <Badge tone="critical" withDot>
                {data.critical_count} kritik
              </Badge>
            )}
            {data.high_count > 0 && (
              <Badge tone="warn" withDot>
                {data.high_count} yüksek
              </Badge>
            )}
            {data.critical_count === 0 && data.high_count === 0 && (
              <Badge tone="success" withDot>
                Tüm sistemler normal
              </Badge>
            )}
            <span className="text-aq-trace ml-auto">
              Güncellendi: {new Date(data.generated_at * 1000).toLocaleTimeString("tr-TR")}
            </span>
          </div>
        )}

        {loading && (
          <div className="flex items-center justify-center py-8 text-aq-dust">
            <Loader2 className="h-4 w-4 animate-spin mr-2" />
            Sinyaller taranıyor…
          </div>
        )}

        {error && (
          <div className="rounded-md border border-aq-fission/40 bg-aq-fission/5 p-3 flex items-center gap-2 text-sm text-aq-fission">
            <AlertTriangle className="h-4 w-4" />
            {error}
          </div>
        )}

        {data && !loading && data.signals.length === 0 && (
          <div className="rounded-md border border-aq-mist/30 bg-aq-cosmos/40 p-4 text-center text-sm">
            <ShieldCheck className="h-5 w-5 mx-auto mb-2 text-aq-mint" />
            <p className="text-foreground">Şu an yüksek-güvenli anomali yok.</p>
            <p className="mt-1 text-xs text-aq-trace">
              4 dedektör arka planda 7/24 çalışır. Yeni sinyal çıkarsa burada belirir.
            </p>
          </div>
        )}

        <AnimatePresence initial={false}>
          {data?.signals.map((s) => (
            <AnomalyCard
              key={s.id}
              signal={s}
              onConfirm={() => handleReview(s, "confirm")}
              onDismiss={() => handleReview(s, "dismiss")}
              reviewing={reviewing === s.id}
            />
          ))}
        </AnimatePresence>
      </CardContent>
    </Card>
  );
}


function CalibrationBanner({
  overview,
}: {
  overview: AnomalyCalibrationOverview;
}) {
  if (!overview.is_learned) {
    return (
      <div className="rounded-md border border-aq-mist/40 bg-aq-cosmos/40 px-3 py-2 text-[11px] flex items-center gap-2">
        <span className="inline-block h-1.5 w-1.5 rounded-full bg-aq-trace animate-pulse" />
        <span className="text-aq-dust">
          Sistem öğreniyor — {overview.total_reviews} review.
          <span className="text-aq-trace ml-1">
            (5+ feedback sonrası kalibrasyon başlar)
          </span>
        </span>
      </div>
    );
  }
  const pct = ((overview.measured_precision ?? 0) * 100).toFixed(1);
  const numPct = parseFloat(pct);
  const isElite = numPct >= 95;
  return (
    <div
      className={cn(
        "rounded-md border px-3 py-2 text-[11px]",
        isElite
          ? "border-aq-mint/40 bg-aq-mint/5"
          : "border-aq-solar/40 bg-aq-solar/5",
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className={cn(
            "inline-block h-1.5 w-1.5 rounded-full",
            isElite ? "bg-aq-mint" : "bg-aq-solar",
          )} />
          <span className={cn(
            "font-medium",
            isElite ? "text-aq-mint" : "text-aq-solar",
          )}>
            Ölçülmüş doğruluk: %{pct}
          </span>
          <span className="text-aq-trace">
            · {overview.total_reviews} review
          </span>
        </div>
        <span className="text-[10px] text-aq-trace">
          {overview.whitelisted_patterns > 0 && (
            <>{overview.whitelisted_patterns} pattern öğrenildi · </>
          )}
          Her review'ün doğruluğu yükseltir
        </span>
      </div>
      {/* Precision bar */}
      <div className="mt-1.5 h-1 w-full rounded-full bg-aq-mist/20 overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${numPct}%` }}
          transition={{ duration: 0.8, ease: [0.32, 0.72, 0, 1] }}
          className={cn(
            "h-full rounded-full",
            isElite ? "bg-aq-mint" : "bg-aq-solar",
          )}
        />
      </div>
    </div>
  );
}


function AnomalyCard({
  signal,
  onConfirm,
  onDismiss,
  reviewing,
}: {
  signal: AnomalySignal;
  onConfirm: () => void;
  onDismiss: () => void;
  reviewing: boolean;
}) {
  const tone = severityTone(signal.severity);
  const typeLabel = SIGNAL_TYPE_LABEL[signal.signal_type] ?? signal.signal_type;
  const [expanded, setExpanded] = useState(false);

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, x: 20 }}
      transition={{ duration: 0.25, ease: [0.32, 0.72, 0, 1] }}
      className={cn(
        "rounded-lg border bg-aq-orbital/60 p-3.5",
        signal.severity === "critical"
          ? "border-aq-fission/50 shadow-[0_0_24px_-12px_rgba(239,68,68,0.5)]"
          : "border-aq-solar/40",
      )}
    >
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <Badge tone={tone} withDot>
              {SEVERITY_LABEL[signal.severity]}
            </Badge>
            <span className="text-[10px] uppercase tracking-wider text-aq-trace">
              {typeLabel}
            </span>
            <span className="font-mono text-[10px] text-aq-trace ml-auto">
              %{signal.confidence_pct.toFixed(1)} güven
            </span>
          </div>
          <h4 className="text-sm font-medium text-foreground truncate">
            {signal.title}
          </h4>
          <p
            className={cn(
              "mt-1 text-xs text-aq-dust",
              !expanded && "line-clamp-2",
            )}
          >
            {signal.description}
          </p>
          {signal.description.length > 120 && (
            <button
              type="button"
              onClick={() => setExpanded((v) => !v)}
              className="mt-1 text-[10px] text-aq-quantum-2 hover:underline inline-flex items-center gap-0.5"
            >
              {expanded ? "Daha az" : "Detay"}
              <ChevronRight
                className={cn(
                  "h-3 w-3 transition-transform",
                  expanded && "rotate-90",
                )}
              />
            </button>
          )}
        </div>

        <div className="flex flex-col gap-1">
          <button
            type="button"
            onClick={onConfirm}
            disabled={reviewing}
            aria-label="Onayla — sinyal gerçek"
            className="grid h-7 w-7 place-items-center rounded text-aq-dust hover:text-aq-mint hover:bg-aq-mint/10 disabled:opacity-50 transition-colors"
            title="Onayla"
          >
            {reviewing ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Check className="h-3.5 w-3.5" />
            )}
          </button>
          <button
            type="button"
            onClick={onDismiss}
            disabled={reviewing}
            aria-label="Yanlış alarm"
            className="grid h-7 w-7 place-items-center rounded text-aq-dust hover:text-aq-fission hover:bg-aq-fission/10 disabled:opacity-50 transition-colors"
            title="Yanlış alarm"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </motion.div>
  );
}
