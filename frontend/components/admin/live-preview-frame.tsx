"use client";

/**
 * Faz 5 — Canlı Önizleme iframe.
 *
 * Aktif modül scope'una göre `/tokens-cascade-{scope}` rotasını iframe içinde
 * gösterir. Panel'deki draft (kaydedilmemiş) değerler iframe'e `postMessage`
 * ile yollanır — kaydetmeden de cascade canlı görünür.
 *
 * Core sekmesinde her üç modül (aq/finos/corpos) için sekmeli önizleme.
 * Mobil/desktop genişlik toggle.
 *
 * Iframe tarafındaki dinleyici: cascade-probe sayfası (Faz 5 ek):
 *   window.addEventListener("message", ev => ev.data?.type === "aq:draft-tokens" → apply)
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { Monitor, Smartphone, X } from "lucide-react";
import type { Scope } from "@/lib/tokens";

type PreviewScope = Exclude<Scope, "core">;
const PREVIEW_SCOPES: PreviewScope[] = ["aq", "finos", "corpos"];

const PREVIEW_LABELS: Record<PreviewScope, string> = {
  aq: "AlphaQ",
  finos: "FinOS",
  corpos: "CorpOS",
};

interface DraftToken {
  scope: Scope;
  key: string;
  value: string;
}

export function LivePreviewFrame({
  activeScope,
  draftTokens,
  open,
  onClose,
}: {
  activeScope: Scope;
  draftTokens: DraftToken[];
  open: boolean;
  onClose: () => void;
}) {
  // Core sekmesindeyse default önizleme aq; modüldeysek modül.
  const initialPreview: PreviewScope = activeScope === "core" ? "aq" : activeScope;
  const [previewScope, setPreviewScope] = useState<PreviewScope>(initialPreview);
  const [viewport, setViewport] = useState<"desktop" | "mobile">("desktop");
  const [iframeReady, setIframeReady] = useState(false);
  const iframeRef = useRef<HTMLIFrameElement>(null);

  // Aktif scope değişirse önizlemeyi senkronla.
  useEffect(() => {
    if (activeScope !== "core") {
      setPreviewScope(activeScope);
    }
  }, [activeScope]);

  // Iframe hazır olduğunda VE draft her değiştiğinde postMessage gönder.
  useEffect(() => {
    if (!open || !iframeReady) return;
    const win = iframeRef.current?.contentWindow;
    if (!win) return;
    win.postMessage(
      { type: "aq:draft-tokens", tokens: draftTokens },
      window.location.origin,
    );
  }, [open, iframeReady, draftTokens, previewScope]);

  // Iframe yüklenir yüklenmez "hazır" eventi dinle.
  useEffect(() => {
    if (!open) return;
    function onMessage(ev: MessageEvent) {
      if (ev.origin !== window.location.origin) return;
      if ((ev.data as { type?: string })?.type === "aq:preview-ready") {
        setIframeReady(true);
      }
    }
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [open]);

  // Önizleme scope'u değişince iframe yeniden yüklenir → hazır olmadan
  // bekle.
  useEffect(() => {
    setIframeReady(false);
  }, [previewScope]);

  const iframeUrl = useMemo(() => `/tokens-cascade-${previewScope}?preview=1`, [previewScope]);
  const frameWidth = viewport === "mobile" ? 380 : "100%";

  if (!open) return null;

  return (
    <aside
      className="fixed top-0 right-0 z-30 h-screen w-full max-w-2xl overflow-hidden border-l border-aq-mist/40 bg-aq-cosmos shadow-elevation-3 flex flex-col"
      role="region"
      aria-label="Canlı önizleme"
    >
      <header className="flex items-center justify-between gap-3 border-b border-aq-mist/40 px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="text-xs uppercase tracking-wider text-aq-trace">
            Faz 5 · Canlı Önizleme
          </span>
          <span className="text-[10px] text-aq-dust">
            kaydetmeden uygulanır
          </span>
        </div>
        <button
          onClick={onClose}
          className="rounded p-1.5 text-aq-dust hover:bg-aq-mist/40"
          aria-label="Kapat"
        >
          <X className="h-4 w-4" />
        </button>
      </header>

      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-aq-mist/40 px-4 py-2">
        <div className="flex flex-wrap gap-1" role="tablist" aria-label="Modül seç">
          {PREVIEW_SCOPES.map((sc) => (
            <button
              key={sc}
              role="tab"
              aria-selected={previewScope === sc}
              onClick={() => setPreviewScope(sc)}
              className={`rounded-md px-2.5 py-1 text-xs transition ${
                previewScope === sc
                  ? "bg-aq-orbital ring-1 ring-aq-quantum text-aq-neutron"
                  : "text-aq-dust hover:bg-aq-mist/40"
              }`}
            >
              {PREVIEW_LABELS[sc]}
            </button>
          ))}
        </div>
        <div className="flex gap-1">
          <button
            onClick={() => setViewport("desktop")}
            className={`rounded p-1.5 transition ${
              viewport === "desktop"
                ? "bg-aq-orbital ring-1 ring-aq-quantum"
                : "text-aq-dust hover:bg-aq-mist/40"
            }`}
            aria-label="Masaüstü genişlik"
            title="Masaüstü"
          >
            <Monitor className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={() => setViewport("mobile")}
            className={`rounded p-1.5 transition ${
              viewport === "mobile"
                ? "bg-aq-orbital ring-1 ring-aq-quantum"
                : "text-aq-dust hover:bg-aq-mist/40"
            }`}
            aria-label="Mobil genişlik"
            title="Mobil (380px)"
          >
            <Smartphone className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-auto bg-aq-orbital/30 p-3">
        <div className="mx-auto" style={{ width: frameWidth, maxWidth: "100%" }}>
          <iframe
            ref={iframeRef}
            src={iframeUrl}
            title={`Önizleme: ${PREVIEW_LABELS[previewScope]}`}
            className="block h-[calc(100vh-160px)] w-full rounded-md border border-aq-mist/30 bg-white"
            // Iframe yüklendiğinde fallback olarak da postMessage tetikle —
            // hedef sayfa preview-ready göndermezse bile draftler düşer.
            onLoad={() => {
              const win = iframeRef.current?.contentWindow;
              if (!win) return;
              win.postMessage(
                { type: "aq:draft-tokens", tokens: draftTokens },
                window.location.origin,
              );
            }}
          />
        </div>
      </div>
    </aside>
  );
}
