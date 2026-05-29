"use client";

/**
 * I2: Staging Review — Logo'dan stage edilen kayıtları gerçek
 * tablolara (customers + invoices + finance_ledger) aktarım UI'ı.
 *
 * Akış:
 *   1. Şirket seç (hangi customer/ledger'a bağlanacak)
 *   2. Conflict politikası seç (create_new / update_existing / skip)
 *   3. Preview → plan göster
 *   4. Onayla → promote (idempotent, tekrar tetiklemek güvenli)
 */
import { useCallback, useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  ArrowRightCircle,
  CheckCircle2,
  Database,
  Loader2,
  Plus,
  RefreshCw,
  ShieldAlert,
} from "lucide-react";
import { toast } from "sonner";
import {
  listStaging,
  previewStagingPromotion,
  promoteStaging,
  type PromotionPlan,
  type PromotionPolicy,
  type StagingList,
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


const POLICIES: Array<{ value: PromotionPolicy; label: string; description: string }> = [
  { value: "create_new", label: "Yeni kayıt aç", description: "Mevcut bir kayıtla eşleşse bile her zaman yeni satır oluşturur" },
  { value: "update_existing", label: "Mevcuti güncelle", description: "VKN eşleşmesinde mevcut customer'ı Logo verisiyle günceller" },
  { value: "skip", label: "Çatışma olursa atla", description: "Mevcut kayıt varsa Logo verisi göz ardı edilir" },
];


export function StagingReview({
  className,
  defaultCompanyName,
}: {
  className?: string;
  defaultCompanyName?: string;
}) {
  const [staging, setStaging] = useState<StagingList | null>(null);
  const [companyName, setCompanyName] = useState(defaultCompanyName ?? "");
  const [policy, setPolicy] = useState<PromotionPolicy>("create_new");
  const [plan, setPlan] = useState<PromotionPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [previewing, setPreviewing] = useState(false);
  const [promoting, setPromoting] = useState(false);

  const loadStaging = useCallback(async () => {
    setLoading(true);
    try {
      const result = await listStaging(500);
      setStaging(result);
    } catch (err) {
      toast.error("Staging yüklenemedi", {
        description: err instanceof Error ? err.message : "Bilinmeyen hata",
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void loadStaging(); }, [loadStaging]);

  async function handlePreview() {
    if (!companyName.trim()) {
      toast.error("Şirket adı gerekli");
      return;
    }
    setPreviewing(true);
    try {
      const result = await previewStagingPromotion(companyName.trim(), policy);
      setPlan(result);
    } catch (err) {
      toast.error("Önizleme başarısız", {
        description: err instanceof Error ? err.message : "Bilinmeyen hata",
      });
    } finally {
      setPreviewing(false);
    }
  }

  async function handlePromote() {
    if (!plan || !companyName.trim()) return;
    setPromoting(true);
    try {
      const result = await promoteStaging(companyName.trim(), policy);
      const total =
        result.customers_created +
        result.customers_updated +
        result.invoices_created +
        result.ledger_entries_created;
      toast.success(
        `${total} kayıt CRM ve finans modüllerine aktarıldı 🎯`,
        {
          description:
            `${result.customers_created} yeni cari · ` +
            `${result.invoices_created} fatura · ` +
            `${result.ledger_entries_created} ledger entry`,
        },
      );
      setPlan(null);
      await loadStaging();
    } catch (err) {
      toast.error("Aktarım başarısız", {
        description: err instanceof Error ? err.message : "Bilinmeyen hata",
      });
    } finally {
      setPromoting(false);
    }
  }

  const hasStaged =
    (staging?.customer_count ?? 0) > 0 || (staging?.invoice_count ?? 0) > 0;

  return (
    <Card className={cn("p-6", className)} variant="glass">
      <CardHeader className="p-0 pb-4 flex-row items-start justify-between gap-3">
        <div>
          <CardTitle className="flex items-center gap-2">
            <Database className="h-4 w-4 text-aq-quantum-2" />
            Staging → CRM & Fatura Aktarımı
          </CardTitle>
          <CardDescription className="mt-1">
            Logo'dan import edilen kayıtları gerçek CRM, fatura ve nakit
            akışı tablolarına aktar. Idempotent — tekrar tetiklemek
            güvenli.
          </CardDescription>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => void loadStaging()}
          disabled={loading}
          title="Yenile"
        >
          {loading ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <RefreshCw className="h-3.5 w-3.5" />
          )}
        </Button>
      </CardHeader>

      <CardContent className="p-0 space-y-4">
        {/* Staging summary */}
        {staging && (
          <div className="flex items-center gap-3 text-xs">
            <Badge tone="primary" withDot>
              {staging.customer_count} stage cari
            </Badge>
            <Badge tone="info" withDot>
              {staging.invoice_count} stage fatura
            </Badge>
            {!hasStaged && (
              <span className="text-aq-trace">
                Logo'dan import yaparak staging'i doldurun
              </span>
            )}
          </div>
        )}

        {hasStaged && (
          <>
            {/* Company + policy form */}
            <div className="space-y-3 rounded-lg border border-aq-mist/40 bg-aq-cosmos/40 p-3">
              <div>
                <label className="text-[10px] uppercase tracking-wider text-aq-trace block mb-1">
                  Hedef şirket
                </label>
                <input
                  type="text"
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                  placeholder="örn. AcmeHolding"
                  className="w-full rounded-md border border-aq-mist/40 bg-aq-orbital/60 px-2.5 py-1.5 text-sm text-foreground focus:outline-none focus:border-aq-quantum/40"
                />
                <p className="text-[10px] text-aq-trace mt-1">
                  Logo verileri bu şirketin CRM ve finans kayıtlarına eklenecek
                </p>
              </div>
              <div>
                <label className="text-[10px] uppercase tracking-wider text-aq-trace block mb-1.5">
                  Çatışma politikası
                </label>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                  {POLICIES.map((p) => (
                    <button
                      key={p.value}
                      type="button"
                      onClick={() => setPolicy(p.value)}
                      className={cn(
                        "text-left rounded-md border p-2 transition-colors",
                        policy === p.value
                          ? "border-aq-quantum/40 bg-aq-quantum/5"
                          : "border-aq-mist/30 bg-aq-orbital/40 hover:border-aq-mist/50",
                      )}
                    >
                      <p className="text-xs font-medium">{p.label}</p>
                      <p className="text-[10px] text-aq-trace mt-0.5">
                        {p.description}
                      </p>
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex justify-end gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handlePreview}
                  disabled={previewing || !companyName.trim()}
                >
                  {previewing ? (
                    <>
                      <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                      Hesaplanıyor…
                    </>
                  ) : (
                    "Önizle"
                  )}
                </Button>
              </div>
            </div>

            {/* Plan preview */}
            {plan && (
              <motion.div
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                className="space-y-3 rounded-lg border border-aq-mint/30 bg-aq-mint/5 p-3"
              >
                <div className="flex items-center gap-2 text-sm">
                  <ArrowRightCircle className="h-4 w-4 text-aq-mint" />
                  <span className="font-medium">Aktarım planı</span>
                </div>
                <div className="grid grid-cols-3 gap-3 text-center">
                  <PlanStat
                    icon={Plus}
                    label="Yeni cari"
                    value={plan.new_customers}
                    tone="mint"
                  />
                  <PlanStat
                    icon={Plus}
                    label="Yeni fatura"
                    value={plan.new_invoices}
                    tone="mint"
                  />
                  <PlanStat
                    icon={Database}
                    label="Ledger entry"
                    value={plan.ledger_entries_to_create}
                    tone="primary"
                  />
                </div>
                {(plan.conflict_customers > 0 || plan.conflict_invoices > 0) && (
                  <div className="rounded-md border border-aq-solar/40 bg-aq-solar/5 p-2 text-xs">
                    <div className="flex items-center gap-1.5 text-aq-solar">
                      <ShieldAlert className="h-3.5 w-3.5" />
                      <span className="font-medium">
                        Çatışma: {plan.conflict_customers} cari ·{" "}
                        {plan.conflict_invoices} fatura
                      </span>
                    </div>
                    <p className="text-[11px] text-aq-dust mt-1">
                      Politikanız: <strong>{policy}</strong> — kararı
                      uygulayacak.
                    </p>
                  </div>
                )}
                {(plan.already_promoted_customers > 0 ||
                  plan.already_promoted_invoices > 0) && (
                  <div className="text-[11px] text-aq-trace">
                    Önceden aktarılmış:{" "}
                    {plan.already_promoted_customers} cari ·{" "}
                    {plan.already_promoted_invoices} fatura — atlanacak.
                  </div>
                )}
                <div className="flex justify-end">
                  <Button
                    onClick={handlePromote}
                    disabled={promoting}
                    size="sm"
                  >
                    {promoting ? (
                      <>
                        <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                        Aktarılıyor…
                      </>
                    ) : (
                      <>
                        <CheckCircle2 className="h-3.5 w-3.5 mr-1.5" />
                        Onayla ve Aktar
                      </>
                    )}
                  </Button>
                </div>
              </motion.div>
            )}
          </>
        )}

        {!hasStaged && !loading && (
          <div className="rounded-md border border-aq-mist/30 bg-aq-cosmos/40 p-4 text-center text-xs">
            <AlertTriangle className="h-4 w-4 mx-auto mb-2 text-aq-dust" />
            Staging boş. Önce Logo'dan import yaparak veri ekleyin.
          </div>
        )}
      </CardContent>
    </Card>
  );
}


function PlanStat({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: typeof Plus;
  label: string;
  value: number;
  tone: "mint" | "primary";
}) {
  return (
    <div>
      <div
        className={cn(
          "text-2xl font-bold num flex items-center justify-center gap-1",
          tone === "mint" ? "text-aq-mint" : "text-aq-quantum-2",
        )}
      >
        <Icon className="h-4 w-4" />
        {value}
      </div>
      <div className="text-[10px] uppercase tracking-wider text-aq-trace mt-0.5">
        {label}
      </div>
    </div>
  );
}
