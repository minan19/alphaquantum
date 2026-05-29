"use client";

/**
 * OBS1: Yeni kullanıcı için "Demo veriyi yükle" CTA banner.
 *
 * Dashboard üstünde gösterilir, sample yüklendiğinde "Demo verisi
 * aktif — temizle" haline geçer. Kullanıcı kendi verisini girince
 * tek tıkla temizler.
 */
import { useCallback, useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Loader2, Sparkles, Trash2, X } from "lucide-react";
import { toast } from "sonner";
import {
  clearSampleData,
  getSampleDataStatus,
  seedSampleData,
} from "@/lib/sample-data-api";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";


export function SampleDataBanner({
  className,
  onChange,
}: {
  className?: string;
  onChange?: () => void;
}) {
  const [hasSampleData, setHasSampleData] = useState<boolean | null>(null);
  const [working, setWorking] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const result = await getSampleDataStatus();
      setHasSampleData(result.has_sample_data);
    } catch {
      setHasSampleData(null);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  async function handleSeed() {
    setWorking(true);
    try {
      const result = await seedSampleData();
      if (result.already_seeded) {
        toast.info("Demo verisi zaten mevcut");
      } else {
        toast.success(
          `Demo verisi yüklendi 🎯`,
          {
            description:
              `${result.customers_created} cari · ` +
              `${result.invoices_created} fatura · ` +
              `${result.ledger_entries_created} nakit hareketi · ` +
              `${result.anomaly_signals_created} anomali`,
          },
        );
      }
      await refresh();
      onChange?.();
    } catch (err) {
      toast.error("Demo verisi yüklenemedi", {
        description: err instanceof Error ? err.message : "Bilinmeyen hata",
      });
    } finally {
      setWorking(false);
    }
  }

  async function handleClear() {
    setWorking(true);
    try {
      const result = await clearSampleData();
      toast.success("Demo verisi temizlendi", {
        description:
          `${result.customers_deleted} cari + ${result.invoices_deleted} fatura silindi`,
      });
      await refresh();
      onChange?.();
    } catch (err) {
      toast.error("Temizlik başarısız", {
        description: err instanceof Error ? err.message : "Bilinmeyen hata",
      });
    } finally {
      setWorking(false);
    }
  }

  if (hasSampleData === null || dismissed) return null;

  return (
    <AnimatePresence>
      <motion.div
        layout
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -8 }}
        transition={{ duration: 0.3 }}
        className={cn(
          "rounded-lg border p-3 flex items-center gap-3",
          hasSampleData
            ? "border-aq-mint/40 bg-aq-mint/5"
            : "border-aq-quantum/40 bg-aq-quantum/5",
          className,
        )}
      >
        <div className={cn(
          "shrink-0 h-8 w-8 rounded-md grid place-items-center",
          hasSampleData ? "bg-aq-mint/10 text-aq-mint" : "bg-aq-quantum/10 text-aq-quantum-2",
        )}>
          <Sparkles className="h-4 w-4" />
        </div>
        <div className="flex-1 min-w-0">
          {hasSampleData ? (
            <>
              <p className="text-sm font-medium text-foreground">
                Demo verisi aktif
              </p>
              <p className="text-[11px] text-aq-dust mt-0.5">
                Tüm rakamlar örnektir. Kendi verilerini eklediğinde demo'yu
                temizleyebilirsin.
              </p>
            </>
          ) : (
            <>
              <p className="text-sm font-medium text-foreground">
                Platformu canlı görmek ister misin?
              </p>
              <p className="text-[11px] text-aq-dust mt-0.5">
                Tek tıkla 8 cari, 12 fatura, 90 günlük nakit akışı ve
                anomali sinyalleri ile demo ortamı yüklenir.
              </p>
            </>
          )}
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          {hasSampleData ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleClear}
              disabled={working}
              className="h-7 text-xs"
            >
              {working ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <Trash2 className="h-3 w-3" />
              )}
              <span className="ml-1">Temizle</span>
            </Button>
          ) : (
            <Button
              size="sm"
              onClick={handleSeed}
              disabled={working}
              className="h-7 text-xs"
            >
              {working ? (
                <Loader2 className="h-3 w-3 mr-1 animate-spin" />
              ) : (
                <Sparkles className="h-3 w-3 mr-1" />
              )}
              Demo yükle
            </Button>
          )}
          <button
            type="button"
            onClick={() => setDismissed(true)}
            aria-label="Kapat"
            className="grid h-6 w-6 place-items-center rounded text-aq-dust hover:text-foreground"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
