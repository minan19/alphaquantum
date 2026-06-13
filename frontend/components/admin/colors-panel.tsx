"use client";

/**
 * Faz 4 — Design Token Admin Panel.
 *
 * Özellikler:
 *  - Scope switcher tabs: Core / AlphaQ / FinOS / CorpOS
 *  - Token satırı: değer editörü + WCAG rozeti + ✦ Otomatik + ↩ Geri Al
 *  - Governance UI'da görünür: modül sekmesinde core token'lar READ-ONLY
 *  - Header: Kaydet (delta PATCH) + Fabrika (2 adımlı onay)
 *  - Draft state: kaydedilmemiş değişiklik sayacı, tab değişiminde uyarı
 *  - WCAG rozeti: çözümlenmiş zemine karşı canlı (scope-aware)
 *  - ✦ Tümünü Otomatik: kategori başına
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowDownToLine,
  Eye,
  History,
  Loader2,
  RotateCcw,
  Save,
  ShieldAlert,
  Sparkles,
  Undo2,
  Wand2,
} from "lucide-react";
import {
  fetchAllTokensClient,
  listSnapshots,
  patchTokens,
  resetScope,
  restoreSnapshot,
} from "@/lib/design-tokens-api";
import {
  VALID_SCOPES,
  type Scope,
  type Token,
  type ModuleScope,
} from "@/lib/tokens";
import {
  computeAuto,
  type ComputeAutoCategory,
  type DraftValues,
} from "@/lib/token-auto";
import {
  resolveWcagTarget,
  type WcagBadge,
  type WcagInputToken,
} from "@/lib/wcag-target";
import { SnapshotHistoryDrawer } from "@/components/admin/snapshot-history-drawer";
import { LivePreviewFrame } from "@/components/admin/live-preview-frame";
import { ImportExportDialog } from "@/components/admin/import-export-dialog";
import { TypographySection } from "@/components/admin/typography-section";

interface PanelToken extends Token {
  /** Kaydedilmiş (DB'deki) değer — ↩ Geri Al için referans. */
  savedValue: string;
}

const SCOPE_LABELS: Record<Scope, string> = {
  core:   "Core (ortak)",
  aq:     "AlphaQ (çatı)",
  finos:  "FinOS",
  corpos: "CorpOS",
};

const SCOPE_TONES: Record<Scope, string> = {
  core:   "#4CABFD",
  aq:     "#2563EB",
  finos:  "#0EA5A4",
  corpos: "#F4C542",
};

const HEX_RE = /^#[0-9A-Fa-f]{6}$/;

export function AdminColorsPanel() {
  const [tokens, setTokens] = useState<PanelToken[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeScope, setActiveScope] = useState<Scope>("core");
  const [saving, setSaving] = useState(false);
  const [factoryConfirmStep, setFactoryConfirmStep] = useState<0 | 1 | 2>(0);
  const [toast, setToast] = useState<{ kind: "success" | "error"; text: string } | null>(null);
  // Faz 5
  const [historyOpen, setHistoryOpen] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [revertingPrev, setRevertingPrev] = useState(false);
  const [importExportOpen, setImportExportOpen] = useState(false);

  // ---- load ---------------------------------------------------------------

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchAllTokensClient();
      const enriched: PanelToken[] = data.tokens.map((t) => ({
        scope: t.scope,
        key: t.key,
        value: t.value,
        label: t.label,
        category: t.category,
        order: t.order,
        savedValue: t.value,
      }));
      setTokens(enriched);
    } catch (e) {
      setToast({ kind: "error", text: e instanceof Error ? e.message : "Yüklenemedi" });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  // ---- derived ------------------------------------------------------------

  /** Aktif sekme için gösterilecek satırlar:
   *  - core sekmesi: yalnız core scope token'ları
   *  - modül sekmesi: core token'ları (READ-ONLY) + modül kimlik token'ları
   *  Governance UI'da GÖRÜNÜR — gizlenmez.
   */
  const visibleRows = useMemo(() => {
    if (activeScope === "core") {
      return tokens.filter((t) => t.scope === "core");
    }
    const core = tokens.filter((t) => t.scope === "core");
    const mod = tokens.filter((t) => t.scope === activeScope);
    return [...core, ...mod];
  }, [tokens, activeScope]);

  /** Scope için draft sözlüğü — Faz 3 computeAuto'ya verilir. */
  const draftForScope = useCallback(
    (scope: Scope): DraftValues => {
      const map: DraftValues = {};
      for (const t of tokens) {
        if (t.scope === "core" || t.scope === scope) {
          const num = Number(t.value);
          map[t.key] = Number.isFinite(num) && !t.value.startsWith("#") ? num : t.value;
        }
      }
      return map;
    },
    [tokens],
  );

  /** WCAG rozeti için sadeleştirilmiş token kümesi — resolveWcagTarget girdisi. */
  const wcagInputs = useMemo<WcagInputToken[]>(
    () =>
      tokens.map((t) => ({
        scope: t.scope,
        key: t.key,
        value: t.value,
        category: t.category,
      })),
    [tokens],
  );

  /** Draft (kaydedilmemiş) sayısı — yalnız aktif scope için. */
  const dirtyKeys = useMemo(() => {
    return tokens
      .filter((t) => t.scope === activeScope && t.value !== t.savedValue)
      .map((t) => t.key);
  }, [tokens, activeScope]);

  // ---- helpers ------------------------------------------------------------

  const isReadOnly = useCallback(
    (row: PanelToken) => activeScope !== "core" && row.scope === "core",
    [activeScope],
  );

  /** Token row için editör tipi: color (renk) veya number (cta_text_weight gibi). */
  const isNumericRow = (row: PanelToken) => row.key === "cta_text_weight";

  const updateValue = useCallback((scope: Scope, key: string, value: string) => {
    setTokens((prev) =>
      prev.map((t) =>
        t.scope === scope && t.key === key ? { ...t, value } : t,
      ),
    );
  }, []);

  const revertRow = useCallback((scope: Scope, key: string) => {
    setTokens((prev) =>
      prev.map((t) =>
        t.scope === scope && t.key === key ? { ...t, value: t.savedValue } : t,
      ),
    );
  }, []);

  const autoRow = useCallback(
    (row: PanelToken) => {
      try {
        const result = computeAuto(
          row.scope,
          row.key,
          row.category as ComputeAutoCategory,
          draftForScope(row.scope),
        );
        updateValue(row.scope, row.key, String(result.value));
      } catch (e) {
        setToast({
          kind: "error",
          text: e instanceof Error ? e.message : "Otomatik hesap başarısız",
        });
      }
    },
    [draftForScope, updateValue],
  );

  const autoCategory = useCallback(
    (category: string) => {
      const targets = visibleRows.filter(
        (r) => r.category === category && !isReadOnly(r),
      );
      for (const row of targets) autoRow(row);
    },
    [visibleRows, isReadOnly, autoRow],
  );

  // ---- save ---------------------------------------------------------------

  const handleSave = async () => {
    if (dirtyKeys.length === 0) return;
    setSaving(true);
    try {
      const changes: Record<string, string | number> = {};
      for (const t of tokens) {
        if (t.scope === activeScope && t.value !== t.savedValue) {
          changes[t.key] = isNumericRow(t) ? Number(t.value) : t.value;
        }
      }
      const res = await patchTokens(activeScope, changes);
      // Komite olarak savedValue'ları güncelle
      setTokens((prev) =>
        prev.map((t) =>
          t.scope === activeScope && res.updated.includes(t.key)
            ? { ...t, savedValue: t.value }
            : t,
        ),
      );
      setToast({
        kind: "success",
        text: `${res.updated_count} token kaydedildi — canlıya yansıdı`,
      });
    } catch (e) {
      setToast({ kind: "error", text: e instanceof Error ? e.message : "Kaydet başarısız" });
    } finally {
      setSaving(false);
    }
  };

  const handleFactoryReset = async () => {
    setSaving(true);
    try {
      await resetScope(activeScope);
      setToast({
        kind: "success",
        text: `${SCOPE_LABELS[activeScope]} fabrikaya döndürüldü`,
      });
      setFactoryConfirmStep(0);
      await loadAll();
    } catch (e) {
      setToast({ kind: "error", text: e instanceof Error ? e.message : "Reset başarısız" });
    } finally {
      setSaving(false);
    }
  };

  // ---- Faz 5: tek tık "Bir Önceki" --------------------------------------
  // En yakın pre_save/manual snapshot'a döner. UI'da kaybolan değişiklik yok
  // (her kayıt öncesi backend zaten snapshot bırakıyor).
  const handleRevertToPrevious = async () => {
    setRevertingPrev(true);
    try {
      const list = await listSnapshots(activeScope, 5);
      const previous = list.snapshots.find(
        (s) => s.source === "pre_save" || s.source === "manual",
      );
      if (!previous) {
        setToast({
          kind: "error",
          text: "Geri dönülecek önceki kayıt bulunamadı.",
        });
        return;
      }
      await restoreSnapshot(previous.id);
      setToast({
        kind: "success",
        text: `Önceki kayda dönüldü (#${previous.id} · ${previous.label})`,
      });
      await loadAll();
    } catch (e) {
      setToast({
        kind: "error",
        text: e instanceof Error ? e.message : "Geri sarma başarısız",
      });
    } finally {
      setRevertingPrev(false);
    }
  };

  // ---- tab change (draft uyarısı) ----------------------------------------

  const handleScopeChange = (next: Scope) => {
    if (dirtyKeys.length > 0) {
      const proceed = window.confirm(
        `${dirtyKeys.length} kaydedilmemiş değişiklik var. Sekme değiştirilirse kaybolur. Devam edilsin mi?`,
      );
      if (!proceed) return;
      // Geri yükle
      setTokens((prev) =>
        prev.map((t) =>
          t.scope === activeScope ? { ...t, value: t.savedValue } : t,
        ),
      );
    }
    setActiveScope(next);
  };

  // ---- toast auto-dismiss ------------------------------------------------

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(t);
  }, [toast]);

  // ---- render -------------------------------------------------------------

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-aq-dust">
        <Loader2 className="h-5 w-5 animate-spin" />
      </div>
    );
  }

  // Group rows by category for display
  const categorized = new Map<string, PanelToken[]>();
  for (const row of visibleRows) {
    const list = categorized.get(row.category) ?? [];
    list.push(row);
    categorized.set(row.category, list);
  }

  return (
    <div className="space-y-6 animate-fade-in p-1">
      {/* Header */}
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-aq-mist/40 pb-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Sparkles className="h-4 w-4 text-aq-quantum-2" />
            <span className="text-xs uppercase tracking-wider text-aq-trace">
              Faz 4 · Panel Çekirdeği
            </span>
          </div>
          <h1 className="text-2xl font-bold">Tasarım Tokenları</h1>
          <p className="text-sm text-aq-dust mt-1">
            Foundation kilidi: Faz 0 wcag-report.json. Modül cascade canlı uygulanır.
            Modül sekmesinde core token&apos;ları read-only (governance).
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-aq-dust">
            {dirtyKeys.length > 0
              ? `${dirtyKeys.length} değişiklik var`
              : "Senkron"}
          </span>
          <button
            onClick={handleSave}
            disabled={saving || dirtyKeys.length === 0}
            className="inline-flex items-center gap-2 rounded-md bg-aq-quantum px-4 py-2 text-sm font-medium text-white shadow-elevation-2 transition hover:bg-aq-quantum-2 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            Kaydet
          </button>

          {/* Faz 5: Bir Önceki */}
          <button
            onClick={handleRevertToPrevious}
            disabled={saving || revertingPrev}
            className="inline-flex items-center gap-2 rounded-md border border-aq-mist/40 px-3 py-2 text-xs text-aq-dust transition hover:border-aq-quantum/40 hover:text-aq-neutron disabled:opacity-40"
            title="En yakın önceki kayda dön"
          >
            {revertingPrev ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Undo2 className="h-3.5 w-3.5" />}
            Bir Önceki
          </button>

          {/* Faz 5: Geçmiş */}
          <button
            onClick={() => setHistoryOpen(true)}
            disabled={saving}
            className="inline-flex items-center gap-2 rounded-md border border-aq-mist/40 px-3 py-2 text-xs text-aq-dust transition hover:border-aq-quantum/40 hover:text-aq-neutron"
            title="Snapshot zinciri"
          >
            <History className="h-3.5 w-3.5" /> Geçmiş
          </button>

          {/* Faz 5: İçe / Dışa Aktar */}
          <button
            onClick={() => setImportExportOpen(true)}
            disabled={saving}
            className="inline-flex items-center gap-2 rounded-md border border-aq-mist/40 px-3 py-2 text-xs text-aq-dust transition hover:border-aq-quantum/40 hover:text-aq-neutron"
            title="JSON dışa / içe aktar"
          >
            <ArrowDownToLine className="h-3.5 w-3.5" /> İçe / Dışa Aktar
          </button>

          {/* Faz 5: Canlı Önizleme */}
          <button
            onClick={() => setPreviewOpen((v) => !v)}
            className={`inline-flex items-center gap-2 rounded-md border px-3 py-2 text-xs transition ${
              previewOpen
                ? "border-aq-quantum bg-aq-quantum/15 text-aq-neutron"
                : "border-aq-mist/40 text-aq-dust hover:border-aq-quantum/40 hover:text-aq-neutron"
            }`}
            title="Canlı önizleme penceresi"
          >
            <Eye className="h-3.5 w-3.5" />
            {previewOpen ? "Önizlemeyi Kapat" : "Canlı Önizleme"}
          </button>

          {/* Fabrika (2-step confirm) */}
          {factoryConfirmStep === 0 && (
            <button
              onClick={() => setFactoryConfirmStep(1)}
              disabled={saving}
              className="inline-flex items-center gap-2 rounded-md border border-aq-fission/40 px-3 py-2 text-sm text-aq-fission transition hover:bg-aq-fission/10"
              title={`${SCOPE_LABELS[activeScope]} → Faz 0 seed`}
            >
              <RotateCcw className="h-4 w-4" /> Fabrika
            </button>
          )}
          {factoryConfirmStep === 1 && (
            <button
              onClick={() => setFactoryConfirmStep(2)}
              className="inline-flex items-center gap-2 rounded-md bg-aq-fission/20 px-3 py-2 text-xs text-aq-fission ring-1 ring-aq-fission"
            >
              <ShieldAlert className="h-4 w-4" /> Emin misiniz? Devam et
            </button>
          )}
          {factoryConfirmStep === 2 && (
            <>
              <button
                onClick={() => setFactoryConfirmStep(0)}
                className="rounded-md px-3 py-2 text-xs text-aq-dust border border-aq-mist/40"
              >
                Vazgeç
              </button>
              <button
                onClick={handleFactoryReset}
                disabled={saving}
                className="inline-flex items-center gap-2 rounded-md bg-aq-fission px-3 py-2 text-xs font-semibold text-white"
              >
                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                FABRIKA RESET
              </button>
            </>
          )}
        </div>
      </header>

      {/* Scope tabs */}
      <nav className="flex flex-wrap gap-2" aria-label="Scope seçici">
        {VALID_SCOPES.map((scope) => (
          <button
            key={scope}
            onClick={() => handleScopeChange(scope)}
            className={`inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition ${
              activeScope === scope
                ? "bg-aq-orbital ring-1 ring-aq-quantum text-aq-neutron"
                : "text-aq-dust hover:bg-aq-mist/40"
            }`}
            style={{ borderLeft: `3px solid ${SCOPE_TONES[scope]}` }}
          >
            {SCOPE_LABELS[scope]}
            {tokens.filter((t) => t.scope === scope && t.value !== t.savedValue).length >
              0 && (
              <span className="text-[10px] text-aq-solar font-mono">●</span>
            )}
          </button>
        ))}
      </nav>

      {/* Categorized rows */}
      <div className="space-y-6">
        {[...categorized.entries()].map(([category, rows]) => (
          <section key={category} className="space-y-2">
            <header className="flex items-center justify-between border-b border-aq-mist/30 pb-2">
              <h2 className="text-xs uppercase tracking-wider text-aq-trace">
                {category}
              </h2>
              <button
                onClick={() => autoCategory(category)}
                disabled={saving}
                className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-aq-quantum-2 hover:bg-aq-quantum/10 transition"
                title={`${category}: tüm satırları otomatik hesapla (Faz 3 motoru)`}
              >
                <Wand2 className="h-3 w-3" /> Tümünü Otomatik
              </button>
            </header>

            <div className="space-y-1">
              {rows.map((row) => (
                <TokenRow
                  key={`${row.scope}:${row.key}`}
                  row={row}
                  readOnly={isReadOnly(row)}
                  isDirty={row.value !== row.savedValue}
                  badge={resolveWcagTarget(
                    { scope: row.scope, key: row.key, value: row.value, category: row.category },
                    wcagInputs,
                    activeScope,
                  )}
                  onChange={(v) => updateValue(row.scope, row.key, v)}
                  onRevert={() => revertRow(row.scope, row.key)}
                  onAuto={() => autoRow(row)}
                />
              ))}
            </div>
          </section>
        ))}
      </div>

      {/* Faz 6: Tipografi (dış font) bölümü — aktif scope'a göre */}
      <TypographySection
        scope={activeScope}
        onChanged={() => setToast({ kind: "success", text: "Font değişikliği uygulandı" })}
      />

      {/* Toast */}
      {toast && (
        <div
          role="status"
          className={`fixed bottom-6 right-6 z-50 max-w-md rounded-md px-4 py-3 text-sm shadow-elevation-3 ${
            toast.kind === "success"
              ? "bg-aq-fusion/20 text-aq-fusion ring-1 ring-aq-fusion/40"
              : "bg-aq-fission/20 text-aq-fission ring-1 ring-aq-fission/40"
          }`}
        >
          {toast.text}
        </div>
      )}

      {/* Faz 5: Snapshot Geçmişi */}
      <SnapshotHistoryDrawer
        scope={activeScope}
        open={historyOpen}
        onClose={() => setHistoryOpen(false)}
        onRestored={async () => {
          setToast({ kind: "success", text: "Snapshot restore edildi" });
          await loadAll();
        }}
      />

      {/* Faz 5: Canlı Önizleme (kaydetmeden uygulanır) */}
      <LivePreviewFrame
        activeScope={activeScope}
        draftTokens={tokens.map((t) => ({ scope: t.scope, key: t.key, value: t.value }))}
        open={previewOpen}
        onClose={() => setPreviewOpen(false)}
      />

      {/* Faz 5: İçe / Dışa Aktar */}
      <ImportExportDialog
        scope={activeScope}
        open={importExportOpen}
        onClose={() => setImportExportOpen(false)}
        onImported={async () => {
          setToast({ kind: "success", text: "İçe aktarma başarılı" });
          await loadAll();
        }}
      />
    </div>
  );
}

// ============================================================================
// Token row
// ============================================================================

function TokenRow({
  row,
  readOnly,
  isDirty,
  badge,
  onChange,
  onRevert,
  onAuto,
}: {
  row: PanelToken;
  readOnly: boolean;
  isDirty: boolean;
  badge: WcagBadge;
  onChange: (v: string) => void;
  onRevert: () => void;
  onAuto: () => void;
}) {
  const isNumeric = row.key === "cta_text_weight";
  const isValidHex = HEX_RE.test(row.value);
  const passing = badge?.mode === "ratio" && badge.ratio >= badge.threshold;

  return (
    <div
      className={`grid grid-cols-12 items-center gap-3 rounded-md border px-3 py-2 transition ${
        isDirty
          ? "border-aq-solar/40 bg-aq-solar/5"
          : "border-aq-mist/30 hover:border-aq-mist/60"
      } ${readOnly ? "opacity-70" : ""}`}
    >
      {/* Label */}
      <div className="col-span-3 min-w-0">
        <div className="font-mono text-xs text-aq-neutron truncate">--{row.key.replace(/_/g, "-")}</div>
        <div className="text-[11px] text-aq-dust truncate">{row.label}</div>
        {readOnly && (
          <span className="inline-block mt-1 text-[9px] uppercase tracking-wider text-aq-dust border border-aq-mist/60 rounded px-1 py-0.5">
            core · read-only (governance)
          </span>
        )}
      </div>

      {/* Value editor */}
      <div className="col-span-4 flex items-center gap-2">
        {isNumeric ? (
          <input
            type="number"
            value={row.value}
            disabled={readOnly}
            onChange={(e) => onChange(e.target.value)}
            className="w-24 rounded bg-aq-orbital/60 px-2 py-1 text-sm font-mono ring-1 ring-aq-mist/40 focus:outline-none focus:ring-aq-quantum"
          />
        ) : (
          <>
            <input
              type="color"
              value={isValidHex ? row.value : "#000000"}
              disabled={readOnly}
              onChange={(e) => onChange(e.target.value.toUpperCase())}
              className="h-7 w-10 cursor-pointer rounded border border-aq-mist/40 bg-transparent disabled:cursor-not-allowed"
            />
            <input
              type="text"
              value={row.value}
              disabled={readOnly}
              onChange={(e) => onChange(e.target.value)}
              className={`w-28 rounded bg-aq-orbital/60 px-2 py-1 text-xs font-mono ring-1 ring-aq-mist/40 focus:outline-none focus:ring-aq-quantum ${
                isValidHex ? "" : "ring-aq-fission/60 text-aq-fission"
              }`}
              maxLength={7}
            />
          </>
        )}
      </div>

      {/* WCAG badge */}
      <div className="col-span-3">
        {badge?.mode === "ratio" && (
          <span
            className={`inline-flex items-center gap-1 rounded px-2 py-1 text-[10px] font-mono ${
              badge.rating === "AAA"
                ? "bg-aq-fusion/20 text-aq-fusion"
                : badge.rating === "AA"
                  ? "bg-aq-fusion/15 text-aq-fusion"
                  : badge.rating === "AA-Lg"
                    ? passing
                      ? "bg-aq-fusion/15 text-aq-fusion"
                      : "bg-aq-solar/15 text-aq-solar"
                    : "bg-aq-fission/15 text-aq-fission"
            }`}
            title={`${badge.tooltip} · hedef ${badge.threshold}:1`}
          >
            {badge.ratio.toFixed(2)}:1 · {badge.rating}
          </span>
        )}
        {badge?.mode === "neutral" && (
          <span
            className="inline-flex items-center gap-1 rounded px-2 py-1 text-[10px] font-mono bg-aq-mist/20 text-aq-dust"
            title={badge.tooltip}
          >
            — {badge.label}
          </span>
        )}
      </div>

      {/* Actions */}
      <div className="col-span-2 flex items-center justify-end gap-1">
        <button
          onClick={onAuto}
          disabled={readOnly}
          title="✦ Otomatik (Faz 3 motoru)"
          className="rounded p-1.5 text-aq-quantum-2 hover:bg-aq-quantum/10 disabled:opacity-30 disabled:cursor-not-allowed transition"
        >
          <Sparkles className="h-3.5 w-3.5" />
        </button>
        <button
          onClick={onRevert}
          disabled={readOnly || !isDirty}
          title="↩ Geri Al"
          className="rounded p-1.5 text-aq-dust hover:bg-aq-mist/40 disabled:opacity-30 disabled:cursor-not-allowed transition"
        >
          <RotateCcw className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}

// Tip yardımcısı — VALID_SCOPES ile birlikte kullanılır (ts-only güvence için).
export type { ModuleScope };
