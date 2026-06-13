"use client";

/**
 * Faz 5 — Import/Export Dialog.
 *
 * İki sekme:
 *  - "Dışa Aktar": tek tıkla `<scope>-tokens.json` indir (sayfa içinde gösterim de var).
 *  - "İçe Aktar": JSON yapıştır VEYA .json dosya seç → preview → onayla.
 *
 * Backend sıkı validasyon yapar (governance + hex format + scope match).
 * Hata sebebi UI'da gösterilir; başarı sonrası snapshot zincirine
 * "İçe aktarma öncesi (N alan)" otomatik kayıt eklenir.
 */
import { useCallback, useEffect, useState } from "react";
import { Download, Loader2, Upload, X } from "lucide-react";
import {
  exportScope,
  importScope,
  type ExportItem,
  type ExportResponse,
} from "@/lib/design-tokens-api";
import type { Scope } from "@/lib/tokens";

type Tab = "export" | "import";

export function ImportExportDialog({
  scope,
  open,
  onClose,
  onImported,
}: {
  scope: Scope;
  open: boolean;
  onClose: () => void;
  onImported: () => void;
}) {
  const [tab, setTab] = useState<Tab>("export");
  const [exportData, setExportData] = useState<ExportResponse | null>(null);
  const [exportLoading, setExportLoading] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  const [importText, setImportText] = useState("");
  const [importBusy, setImportBusy] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<string | null>(null);

  // Dialog açılınca export'u arka planda çek (kullanıcı sekmeye geçince hazır olsun).
  const loadExport = useCallback(async () => {
    setExportLoading(true);
    setExportError(null);
    try {
      const res = await exportScope(scope);
      setExportData(res);
    } catch (e) {
      setExportError(e instanceof Error ? e.message : "Dışa aktarma başarısız");
    } finally {
      setExportLoading(false);
    }
  }, [scope]);

  useEffect(() => {
    if (!open) return;
    setTab("export");
    setImportText("");
    setImportError(null);
    setImportResult(null);
    void loadExport();
  }, [open, loadExport]);

  const handleDownload = () => {
    if (!exportData) return;
    const json = JSON.stringify(exportData, null, 2);
    const blob = new Blob([json], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${scope}-tokens.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleFileSelected = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => setImportText(String(reader.result ?? ""));
    reader.onerror = () => setImportError("Dosya okunamadı");
    reader.readAsText(file);
  };

  /** Yapıştırılan veya yüklenen JSON'u parse et — toleranslı:
   *  - {tokens: [...]} (export çıktısı) VEYA
   *  - [...] (yalın array) kabul.
   *  Backend tekil item'ı yine sıkı doğrular; bu sadece basit format desteği.
   */
  const parsePayload = (raw: string): ExportItem[] => {
    const trimmed = raw.trim();
    if (!trimmed) throw new Error("Boş içerik");
    let parsed: unknown;
    try {
      parsed = JSON.parse(trimmed);
    } catch (e) {
      throw new Error(
        `Geçersiz JSON: ${e instanceof Error ? e.message : "parse hatası"}`,
      );
    }
    if (Array.isArray(parsed)) return parsed as ExportItem[];
    if (parsed && typeof parsed === "object" && Array.isArray((parsed as { tokens?: unknown }).tokens)) {
      return (parsed as { tokens: ExportItem[] }).tokens;
    }
    throw new Error("Beklenen şema: { tokens: [...] } veya doğrudan [...]");
  };

  const handleImport = async () => {
    setImportBusy(true);
    setImportError(null);
    setImportResult(null);
    try {
      const payload = parsePayload(importText);
      const res = await importScope(scope, payload);
      setImportResult(
        `${res.imported_count} alan yüklendi · pre-import snapshot #${res.pre_import_snapshot_id}`,
      );
      onImported();
    } catch (e) {
      // Backend 422 detail bazen dict (errors listesi) olabilir — JSON yap.
      const msg =
        e instanceof Error
          ? e.message
          : typeof e === "object"
            ? JSON.stringify(e)
            : String(e);
      setImportError(msg);
    } finally {
      setImportBusy(false);
    }
  };

  if (!open) return null;

  return (
    <>
      <div
        className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden
      />
      <div
        className="fixed left-1/2 top-1/2 z-50 w-full max-w-2xl -translate-x-1/2 -translate-y-1/2 rounded-md border border-aq-mist/40 bg-aq-cosmos shadow-elevation-3"
        role="dialog"
        aria-label="Dışa / İçe Aktar"
      >
        <header className="flex items-center justify-between border-b border-aq-mist/40 px-5 py-3">
          <div>
            <div className="text-xs uppercase tracking-wider text-aq-trace">
              Faz 5 · {scope.toUpperCase()} scope
            </div>
            <h2 className="mt-0.5 text-base font-semibold">Dışa / İçe Aktar</h2>
          </div>
          <button
            onClick={onClose}
            className="rounded p-1.5 text-aq-dust hover:bg-aq-mist/40"
            aria-label="Kapat"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="border-b border-aq-mist/40 px-5 pt-2">
          <div role="tablist" className="flex gap-1">
            <button
              role="tab"
              aria-selected={tab === "export"}
              onClick={() => setTab("export")}
              className={`inline-flex items-center gap-1 rounded-t-md px-3 py-2 text-sm transition ${
                tab === "export"
                  ? "bg-aq-orbital text-aq-neutron ring-1 ring-aq-quantum/40 ring-b-0"
                  : "text-aq-dust hover:bg-aq-mist/40"
              }`}
            >
              <Download className="h-3.5 w-3.5" /> Dışa Aktar
            </button>
            <button
              role="tab"
              aria-selected={tab === "import"}
              onClick={() => setTab("import")}
              className={`inline-flex items-center gap-1 rounded-t-md px-3 py-2 text-sm transition ${
                tab === "import"
                  ? "bg-aq-orbital text-aq-neutron ring-1 ring-aq-quantum/40 ring-b-0"
                  : "text-aq-dust hover:bg-aq-mist/40"
              }`}
            >
              <Upload className="h-3.5 w-3.5" /> İçe Aktar
            </button>
          </div>
        </div>

        <div className="max-h-[60vh] overflow-y-auto p-5">
          {tab === "export" && (
            <div className="space-y-3">
              <p className="text-xs text-aq-dust">
                Aşağıdaki JSON&apos;u indir veya kopyala. Round-trip uyumlu — aynı
                yapı İçe Aktar sekmesine yapıştırılabilir.
              </p>
              {exportLoading && (
                <div className="flex items-center gap-2 text-sm text-aq-dust">
                  <Loader2 className="h-4 w-4 animate-spin" /> Yükleniyor…
                </div>
              )}
              {exportError && (
                <div className="rounded-md border border-aq-fission/40 bg-aq-fission/10 px-3 py-2 text-xs text-aq-fission">
                  {exportError}
                </div>
              )}
              {exportData && (
                <>
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-[11px] text-aq-trace">
                      {exportData.tokens.length} alan · şema v{exportData.version}
                    </div>
                    <button
                      onClick={handleDownload}
                      className="inline-flex items-center gap-2 rounded-md bg-aq-quantum px-3 py-1.5 text-xs font-medium text-white hover:bg-aq-quantum-2"
                    >
                      <Download className="h-3.5 w-3.5" /> {scope}-tokens.json indir
                    </button>
                  </div>
                  <textarea
                    readOnly
                    value={JSON.stringify(exportData, null, 2)}
                    className="block h-72 w-full resize-none rounded bg-aq-orbital/40 p-3 font-mono text-[11px] text-aq-neutron ring-1 ring-aq-mist/40 focus:outline-none focus:ring-aq-quantum"
                  />
                </>
              )}
            </div>
          )}

          {tab === "import" && (
            <div className="space-y-3">
              <p className="text-xs text-aq-dust">
                JSON&apos;u yapıştır veya .json dosyası seç. Bilinmeyen anahtar,
                yanlış hex veya scope uyumsuzluğu reddedilir; başarısızlıkta hiçbir
                yazım yapılmaz (atomic).
              </p>
              <label className="inline-flex items-center gap-2 rounded-md border border-aq-mist/40 px-3 py-1.5 text-xs text-aq-dust hover:border-aq-quantum/40 hover:text-aq-neutron cursor-pointer">
                <Upload className="h-3.5 w-3.5" />
                Dosya seç (.json)
                <input
                  type="file"
                  accept="application/json,.json"
                  className="hidden"
                  onChange={handleFileSelected}
                />
              </label>
              <textarea
                placeholder={'{ "scope": "finos", "tokens": [...] }  veya  [...]'}
                value={importText}
                onChange={(e) => setImportText(e.target.value)}
                className="block h-56 w-full resize-none rounded bg-aq-orbital/40 p-3 font-mono text-[11px] text-aq-neutron ring-1 ring-aq-mist/40 focus:outline-none focus:ring-aq-quantum"
              />
              {importError && (
                <div className="rounded-md border border-aq-fission/40 bg-aq-fission/10 px-3 py-2 text-xs text-aq-fission whitespace-pre-wrap">
                  {importError}
                </div>
              )}
              {importResult && (
                <div className="rounded-md border border-aq-fusion/40 bg-aq-fusion/10 px-3 py-2 text-xs text-aq-fusion">
                  {importResult}
                </div>
              )}
              <div className="flex justify-end gap-2">
                <button
                  onClick={onClose}
                  className="rounded-md px-3 py-2 text-xs text-aq-dust border border-aq-mist/40"
                >
                  Kapat
                </button>
                <button
                  onClick={handleImport}
                  disabled={importBusy || !importText.trim()}
                  className="inline-flex items-center gap-2 rounded-md bg-aq-quantum px-3 py-2 text-xs font-medium text-white hover:bg-aq-quantum-2 disabled:opacity-40"
                >
                  {importBusy ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Upload className="h-3.5 w-3.5" />
                  )}
                  İçe Aktar
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
