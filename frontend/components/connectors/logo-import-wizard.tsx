"use client";

/**
 * I1: Logo Tiger Import Wizard — 3 step.
 *
 *   1. Mod seç (XML / Excel)
 *   2. Dosya yükle → preview
 *   3. Onayla → commit
 *
 * Trust by design: preview status'te kullanıcı tam olarak ne import
 * edeceğini görür; "Onayla" tuşuna basana kadar DB'ye hiçbir şey
 * yazılmaz. Hatalar şeffaf rapor edilir (row index + error code).
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  AlertTriangle,
  ArrowLeft,
  Check,
  CheckCircle2,
  FileSpreadsheet,
  FileText,
  Loader2,
  RotateCcw,
  Upload,
  X,
} from "lucide-react";
import { toast } from "sonner";
import {
  cancelConnectorImport,
  commitConnectorImport,
  previewConnectorImport,
  type ConnectorImportJob,
  type ConnectorMode,
} from "@/lib/connectors-api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/cn";


type Step = 1 | 2 | 3;


export function LogoImportWizard({
  onComplete,
  className,
}: {
  onComplete?: (job: ConnectorImportJob) => void;
  className?: string;
}) {
  const [step, setStep] = useState<Step>(1);
  const [mode, setMode] = useState<ConnectorMode>("xml");
  const [file, setFile] = useState<File | null>(null);
  const [job, setJob] = useState<ConnectorImportJob | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const reset = useCallback(() => {
    setStep(1);
    setMode("xml");
    setFile(null);
    setJob(null);
    setError(null);
    if (inputRef.current) inputRef.current.value = "";
  }, []);

  async function handleUpload() {
    if (!file) {
      setError("Dosya seç");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await previewConnectorImport("logo_tiger", file, mode);
      setJob(result);
      setStep(3);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Yükleme başarısız");
    } finally {
      setLoading(false);
    }
  }

  async function handleCommit() {
    if (!file || !job) return;
    setLoading(true);
    setError(null);
    try {
      const committed = await commitConnectorImport(job.id, file);
      setJob(committed);
      toast.success(
        `${committed.summary.committed_customers ?? 0} cari + ` +
        `${committed.summary.committed_invoices ?? 0} fatura import edildi 🎯`,
      );
      onComplete?.(committed);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Onay başarısız");
    } finally {
      setLoading(false);
    }
  }

  async function handleCancel() {
    if (!job) return reset();
    try {
      await cancelConnectorImport(job.id);
    } catch {
      /* ignore — UI reset olur */
    }
    reset();
  }

  return (
    <Card className={cn("p-6", className)} variant="glass">
      <CardHeader className="p-0 pb-4">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <FileSpreadsheet className="h-5 w-5 text-aq-quantum-2" />
            Logo Tiger İçe Aktar
          </CardTitle>
          <StepIndicator current={step} />
        </div>
        <CardDescription className="mt-1">
          Logo'dan dışa aktardığın XML veya Excel dosyasını yükle.
          Önce preview göreceksin, sonra onayla.
        </CardDescription>
      </CardHeader>

      <CardContent className="p-0">
        <AnimatePresence mode="wait">
          {step === 1 && (
            <motion.div
              key="step1"
              initial={{ opacity: 0, x: 12 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -12 }}
              transition={{ duration: 0.25 }}
              className="space-y-4"
            >
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <ModeCard
                  selected={mode === "xml"}
                  onClick={() => setMode("xml")}
                  icon={FileText}
                  title="XML Dosyası"
                  description="Logo'nun standart Veri Aktarımı > XML export'u"
                  badge="Önerilen"
                />
                <ModeCard
                  selected={mode === "excel"}
                  onClick={() => setMode("excel")}
                  icon={FileSpreadsheet}
                  title="Excel (.xlsx)"
                  description="Cariler ve Faturalar sheet'lerini içeren Excel"
                />
              </div>
              <div className="flex justify-end">
                <Button onClick={() => setStep(2)}>
                  İlerle →
                </Button>
              </div>
            </motion.div>
          )}

          {step === 2 && (
            <motion.div
              key="step2"
              initial={{ opacity: 0, x: 12 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -12 }}
              transition={{ duration: 0.25 }}
              className="space-y-4"
            >
              <div
                className={cn(
                  "rounded-lg border-2 border-dashed p-8 text-center transition-colors",
                  file
                    ? "border-aq-quantum/40 bg-aq-quantum/5"
                    : "border-aq-mist/40 bg-aq-cosmos/40 hover:border-aq-mist/60",
                )}
              >
                <Upload className="h-8 w-8 mx-auto mb-3 text-aq-dust" />
                {file ? (
                  <>
                    <p className="text-sm font-medium">{file.name}</p>
                    <p className="text-[10px] font-mono text-aq-trace mt-1">
                      {(file.size / 1024).toFixed(1)} KB · {mode.toUpperCase()}
                    </p>
                  </>
                ) : (
                  <>
                    <p className="text-sm text-foreground">
                      Dosyayı sürükle bırak veya tıkla
                    </p>
                    <p className="text-[10px] text-aq-trace mt-1">
                      Max 50 MB · {mode === "xml" ? ".xml" : ".xlsx"}
                    </p>
                  </>
                )}
                <input
                  ref={inputRef}
                  type="file"
                  accept={mode === "xml" ? ".xml,application/xml" : ".xlsx"}
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                  style={{ position: "absolute" }}
                />
              </div>
              <div className="flex justify-between gap-2">
                <Button variant="ghost" size="sm" onClick={() => setStep(1)}>
                  <ArrowLeft className="h-3.5 w-3.5 mr-1" />
                  Geri
                </Button>
                <Button
                  onClick={handleUpload}
                  disabled={!file || loading}
                >
                  {loading ? (
                    <>
                      <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                      Parse ediliyor…
                    </>
                  ) : (
                    "Önizle →"
                  )}
                </Button>
              </div>
              {error && (
                <div className="rounded-md border border-aq-fission/40 bg-aq-fission/5 p-3 text-sm text-aq-fission">
                  <AlertTriangle className="h-4 w-4 inline mr-1.5" />
                  {error}
                </div>
              )}
            </motion.div>
          )}

          {step === 3 && job && (
            <motion.div
              key="step3"
              initial={{ opacity: 0, x: 12 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -12 }}
              transition={{ duration: 0.25 }}
              className="space-y-4"
            >
              <PreviewSummary job={job} />
              {job.status === "completed" ? (
                <div className="text-center py-4">
                  <CheckCircle2 className="h-10 w-10 mx-auto text-aq-mint mb-2" />
                  <p className="text-sm font-medium text-aq-mint">
                    İçe aktarım tamamlandı
                  </p>
                  <Button
                    onClick={reset}
                    variant="ghost"
                    size="sm"
                    className="mt-3"
                  >
                    <RotateCcw className="h-3.5 w-3.5 mr-1.5" />
                    Yeni import başlat
                  </Button>
                </div>
              ) : (
                <div className="flex justify-between gap-2">
                  <Button variant="ghost" size="sm" onClick={handleCancel}>
                    <X className="h-3.5 w-3.5 mr-1" />
                    İptal
                  </Button>
                  <Button onClick={handleCommit} disabled={loading}>
                    {loading ? (
                      <>
                        <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                        Yazılıyor…
                      </>
                    ) : (
                      <>
                        <Check className="h-3.5 w-3.5 mr-1.5" />
                        Onayla ve İçe Aktar
                      </>
                    )}
                  </Button>
                </div>
              )}
              {error && (
                <div className="rounded-md border border-aq-fission/40 bg-aq-fission/5 p-3 text-sm text-aq-fission">
                  <AlertTriangle className="h-4 w-4 inline mr-1.5" />
                  {error}
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </CardContent>
    </Card>
  );
}


function StepIndicator({ current }: { current: Step }) {
  const labels = ["Mod", "Yükle", "Onayla"];
  return (
    <div className="flex items-center gap-1.5 text-[10px]">
      {labels.map((label, idx) => (
        <div key={label} className="flex items-center gap-1.5">
          <div
            className={cn(
              "h-1.5 w-1.5 rounded-full",
              idx + 1 <= current ? "bg-aq-quantum" : "bg-aq-mist/40",
            )}
          />
          <span
            className={cn(
              "uppercase tracking-wider",
              idx + 1 === current ? "text-aq-quantum-2" : "text-aq-trace",
            )}
          >
            {label}
          </span>
          {idx < labels.length - 1 && (
            <span className="text-aq-trace">·</span>
          )}
        </div>
      ))}
    </div>
  );
}


function ModeCard({
  selected,
  onClick,
  icon: Icon,
  title,
  description,
  badge,
}: {
  selected: boolean;
  onClick: () => void;
  icon: typeof FileText;
  title: string;
  description: string;
  badge?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "text-left rounded-lg border p-4 transition-colors",
        selected
          ? "border-aq-quantum/50 bg-aq-quantum/5"
          : "border-aq-mist/40 bg-aq-cosmos/40 hover:border-aq-mist/60",
      )}
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <Icon
          className={cn(
            "h-5 w-5",
            selected ? "text-aq-quantum-2" : "text-aq-dust",
          )}
        />
        {badge && <Badge tone="primary">{badge}</Badge>}
      </div>
      <p className="text-sm font-medium">{title}</p>
      <p className="text-[11px] text-aq-trace mt-1">{description}</p>
    </button>
  );
}


function PreviewSummary({ job }: { job: ConnectorImportJob }) {
  const summary = job.summary as Record<string, number>;
  const customerCount = Number(summary.customers ?? 0);
  const invoiceCount = Number(summary.invoices ?? 0);
  const errorCount = job.errors.length;
  return (
    <div className="rounded-lg border border-aq-mist/40 bg-aq-cosmos/40 p-4 space-y-3">
      <div className="grid grid-cols-3 gap-3 text-center">
        <Stat label="Cari" value={customerCount} tone="primary" />
        <Stat label="Fatura" value={invoiceCount} tone="primary" />
        <Stat
          label="Hata"
          value={errorCount}
          tone={errorCount > 0 ? "critical" : "neutral"}
        />
      </div>
      {job.preview.length > 0 && (
        <div className="border-t border-aq-mist/30 pt-3">
          <p className="text-[10px] uppercase tracking-wider text-aq-trace mb-2">
            İlk {job.preview.length} kayıt
          </p>
          <div className="space-y-1.5 max-h-48 overflow-y-auto">
            {job.preview.map((p, i) => (
              <PreviewRow key={i} type={p.type} data={p.data} />
            ))}
          </div>
        </div>
      )}
      {errorCount > 0 && (
        <div className="border-t border-aq-mist/30 pt-3">
          <p className="text-[10px] uppercase tracking-wider text-aq-fission mb-2">
            Hatalar
          </p>
          <div className="space-y-1 max-h-32 overflow-y-auto">
            {job.errors.slice(0, 5).map((e, i) => (
              <div key={i} className="text-[11px] text-aq-dust">
                <span className="font-mono text-aq-trace">
                  #{e.row_index} {e.record_type}
                </span>{" "}
                — {e.error_message}
              </div>
            ))}
            {errorCount > 5 && (
              <p className="text-[10px] text-aq-trace">
                ve {errorCount - 5} hata daha…
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}


function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "primary" | "critical" | "neutral";
}) {
  return (
    <div>
      <div
        className={cn(
          "text-2xl font-bold num",
          tone === "primary" && "text-aq-quantum-2",
          tone === "critical" && "text-aq-fission",
          tone === "neutral" && "text-foreground",
        )}
      >
        {value}
      </div>
      <div className="text-[10px] uppercase tracking-wider text-aq-trace mt-0.5">
        {label}
      </div>
    </div>
  );
}


function PreviewRow({
  type,
  data,
}: {
  type: string;
  data: Record<string, unknown>;
}) {
  const summary =
    type === "customer"
      ? `${data.source_code ?? "?"} · ${data.name ?? "—"}`
      : type === "invoice"
      ? `${data.source_no ?? "?"} · ${data.customer_source_code ?? "?"} · ${
          data.total_incl_tax ?? 0
        }`
      : "";
  const toneLabel: "primary" | "info" = type === "customer" ? "primary" : "info";
  return (
    <div className="flex items-center gap-2 text-xs">
      <Badge tone={toneLabel}>{type === "customer" ? "Cari" : "Fatura"}</Badge>
      <span className="text-aq-dust truncate">{summary}</span>
    </div>
  );
}
