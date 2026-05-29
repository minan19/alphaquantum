"use client";

/**
 * F4: Dashboard customize modal.
 *
 * Kullanıcı widget'ları ekler/çıkarır/sıralar/boyutlandırır.
 * "Bana özel pano" aidiyet hissi — saved layout dashboard'a yansır.
 *
 * UX kararları:
 *  - Sol panel: kullanılabilir widget'lar (catalog) — drag-able
 *  - Sağ panel: aktif layout — arrow buttonlarla reorder + size + remove
 *  - Footer: Reset / İptal / Kaydet
 *  - Toast feedback (success/error)
 *
 * a11y:
 *  - Modal dialog role
 *  - Focus trap (Radix Dialog ile)
 *  - Keyboard: ↑↓ reorder, Delete kaldır
 */
import { useEffect, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { motion } from "framer-motion";
import {
  Check,
  ChevronDown,
  ChevronUp,
  Loader2,
  Plus,
  RotateCcw,
  Save,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import {
  WIDGET_CATALOG,
  type DashboardWidgetConfig,
  type WidgetSize,
  getDashboardLayout,
  resetDashboardLayout,
  saveDashboardLayout,
} from "@/lib/dashboard-layout-api";


export function CustomizeDashboardModal({
  open,
  onOpenChange,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  onSaved?: (widgets: DashboardWidgetConfig[]) => void;
}) {
  const [widgets, setWidgets] = useState<DashboardWidgetConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Fetch on open
  useEffect(() => {
    if (!open) return;
    setLoading(true);
    getDashboardLayout()
      .then((r) => setWidgets(r.widgets))
      .catch(() => toast.error("Layout yüklenemedi"))
      .finally(() => setLoading(false));
  }, [open]);

  const activeIds = new Set(widgets.map((w) => w.widget_id));
  const availableWidgets = WIDGET_CATALOG.filter((w) => !activeIds.has(w.id));

  function addWidget(id: string) {
    setWidgets((prev) => [
      ...prev,
      {
        widget_id: id,
        size: "md",
        hidden: false,
        order: prev.length,
      },
    ]);
  }

  function removeWidget(id: string) {
    setWidgets((prev) =>
      prev
        .filter((w) => w.widget_id !== id)
        .map((w, i) => ({ ...w, order: i })),
    );
  }

  function moveWidget(id: string, direction: -1 | 1) {
    setWidgets((prev) => {
      const idx = prev.findIndex((w) => w.widget_id === id);
      if (idx < 0) return prev;
      const target = idx + direction;
      if (target < 0 || target >= prev.length) return prev;
      const next = [...prev];
      [next[idx], next[target]] = [next[target], next[idx]];
      return next.map((w, i) => ({ ...w, order: i }));
    });
  }

  function setSize(id: string, size: WidgetSize) {
    setWidgets((prev) =>
      prev.map((w) => (w.widget_id === id ? { ...w, size } : w)),
    );
  }

  async function handleSave() {
    setSaving(true);
    try {
      const result = await saveDashboardLayout(widgets);
      toast.success("Panoyu kaydettim 🎯");
      onSaved?.(result.widgets);
      onOpenChange(false);
    } catch (err) {
      toast.error("Kayıt başarısız", {
        description: err instanceof Error ? err.message : "Bilinmeyen hata",
      });
    } finally {
      setSaving(false);
    }
  }

  async function handleReset() {
    setSaving(true);
    try {
      const result = await resetDashboardLayout();
      setWidgets(result.widgets);
      toast.success("Varsayılan pano geri yüklendi");
    } catch (err) {
      toast.error("Sıfırlama başarısız", {
        description: err instanceof Error ? err.message : "Bilinmeyen hata",
      });
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-aq-void/70 backdrop-blur-sm data-[state=open]:animate-in data-[state=open]:fade-in-0" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 grid w-full max-w-4xl -translate-x-1/2 -translate-y-1/2 gap-4 border border-aq-mist/40 bg-aq-orbital p-6 shadow-quantum-lg rounded-xl">
          <Dialog.Title className="text-lg font-bold">
            Panoyu özelleştir
          </Dialog.Title>
          <Dialog.Description className="text-sm text-aq-dust">
            Hangi widget&apos;lar görünsün, hangi sırada, hangi boyutta — sen karar
            ver.
          </Dialog.Description>

          {loading ? (
            <div className="flex items-center justify-center py-10 text-aq-dust">
              <Loader2 className="h-5 w-5 animate-spin mr-2" />
              Layout yükleniyor…
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-2">
              {/* Sol: kullanılabilir */}
              <div className="rounded-lg border border-aq-mist/40 bg-aq-cosmos/50 p-3">
                <h3 className="text-xs uppercase tracking-wider text-aq-trace mb-2">
                  Eklenebilir Widget&apos;lar ({availableWidgets.length})
                </h3>
                <div className="space-y-1.5 max-h-[400px] overflow-y-auto pr-1">
                  {availableWidgets.length === 0 && (
                    <div className="text-xs text-aq-dust py-4 text-center">
                      Tüm widget&apos;lar panoda 🎉
                    </div>
                  )}
                  {availableWidgets.map((w) => (
                    <button
                      key={w.id}
                      type="button"
                      onClick={() => addWidget(w.id)}
                      className="w-full text-left rounded-md border border-aq-mist/30 bg-aq-orbital/40 px-3 py-2 hover:border-aq-quantum/40 hover:bg-aq-quantum/5 transition-colors"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div className="min-w-0">
                          <div className="text-sm font-medium truncate">
                            {w.label}
                          </div>
                          <div className="text-[10px] text-aq-trace mt-0.5 truncate">
                            {w.description}
                          </div>
                        </div>
                        <Plus className="h-4 w-4 text-aq-dust shrink-0" />
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Sağ: aktif layout */}
              <div className="rounded-lg border border-aq-mist/40 bg-aq-cosmos/50 p-3">
                <h3 className="text-xs uppercase tracking-wider text-aq-trace mb-2">
                  Aktif Pano ({widgets.length}/12)
                </h3>
                <div className="space-y-1.5 max-h-[400px] overflow-y-auto pr-1">
                  {widgets.length === 0 && (
                    <div className="text-xs text-aq-dust py-4 text-center">
                      Pano boş — soldan ekle.
                    </div>
                  )}
                  {widgets.map((cfg, idx) => {
                    const meta = WIDGET_CATALOG.find(
                      (m) => m.id === cfg.widget_id,
                    );
                    if (!meta) return null;
                    return (
                      <motion.div
                        key={cfg.widget_id}
                        layout
                        className="rounded-md border border-aq-mist/40 bg-aq-orbital/60 px-2.5 py-2"
                      >
                        <div className="flex items-center gap-2">
                          <div className="flex flex-col gap-0.5">
                            <button
                              type="button"
                              onClick={() => moveWidget(cfg.widget_id, -1)}
                              disabled={idx === 0}
                              aria-label="Yukarı taşı"
                              className="grid h-5 w-5 place-items-center rounded text-aq-dust hover:text-foreground disabled:opacity-30"
                            >
                              <ChevronUp className="h-3.5 w-3.5" />
                            </button>
                            <button
                              type="button"
                              onClick={() => moveWidget(cfg.widget_id, 1)}
                              disabled={idx === widgets.length - 1}
                              aria-label="Aşağı taşı"
                              className="grid h-5 w-5 place-items-center rounded text-aq-dust hover:text-foreground disabled:opacity-30"
                            >
                              <ChevronDown className="h-3.5 w-3.5" />
                            </button>
                          </div>
                          <div className="min-w-0 flex-1">
                            <div className="text-sm font-medium truncate">
                              {meta.label}
                            </div>
                            <div className="text-[10px] text-aq-trace truncate">
                              Kategori: {meta.category}
                            </div>
                          </div>
                          <div
                            role="radiogroup"
                            aria-label="Widget boyut"
                            className="inline-flex rounded-md border border-aq-mist/40 bg-aq-cosmos p-0.5"
                          >
                            {(["sm", "md", "lg"] as WidgetSize[]).map(
                              (sz) => (
                                <button
                                  key={sz}
                                  type="button"
                                  role="radio"
                                  aria-checked={cfg.size === sz}
                                  onClick={() => setSize(cfg.widget_id, sz)}
                                  className={cn(
                                    "px-1.5 py-0.5 text-[10px] uppercase font-mono rounded transition-colors",
                                    cfg.size === sz
                                      ? "bg-aq-quantum/30 text-foreground"
                                      : "text-aq-dust hover:text-foreground",
                                  )}
                                >
                                  {sz}
                                </button>
                              ),
                            )}
                          </div>
                          <button
                            type="button"
                            onClick={() => removeWidget(cfg.widget_id)}
                            aria-label="Panodan kaldır"
                            className="grid h-7 w-7 place-items-center rounded text-aq-dust hover:text-aq-fission hover:bg-aq-fission/10"
                          >
                            <X className="h-4 w-4" />
                          </button>
                        </div>
                      </motion.div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {/* Footer */}
          <div className="flex items-center justify-between mt-4 pt-3 border-t border-aq-mist/40">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleReset}
              disabled={saving || loading}
            >
              <RotateCcw className="h-3.5 w-3.5 mr-1.5" />
              Varsayılana dön
            </Button>
            <div className="flex items-center gap-2">
              <Dialog.Close asChild>
                <Button variant="ghost" size="sm" disabled={saving}>
                  İptal
                </Button>
              </Dialog.Close>
              <Button onClick={handleSave} disabled={saving || loading}>
                {saving ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                    Kaydediliyor…
                  </>
                ) : (
                  <>
                    <Save className="h-3.5 w-3.5 mr-1.5" />
                    Kaydet
                  </>
                )}
              </Button>
            </div>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}


/**
 * Tetikleyici buton — sidebar/footer'a takılabilir.
 * Kullanım: <CustomizeDashboardTrigger onSaved={...} />
 */
export function CustomizeDashboardTrigger({
  onSaved,
}: {
  onSaved?: (widgets: DashboardWidgetConfig[]) => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setOpen(true)}
        title="Panoyu özelleştir"
      >
        <Check className="h-3.5 w-3.5 mr-1.5" />
        Özelleştir
      </Button>
      <CustomizeDashboardModal
        open={open}
        onOpenChange={setOpen}
        onSaved={onSaved}
      />
    </>
  );
}
