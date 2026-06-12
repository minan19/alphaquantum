/**
 * Design Token Programı — Faz 2 cascade probe.
 *
 * Sayfada `var(--bg-primary)`, `var(--cta)`, `var(--brand)`, `var(--accent)` gibi
 * Faz 1 token'larını OKUYAN element'ler basar. Her demo route farklı `data-module`
 * altında render edildiğinde aynı `var(--cta)` farklı renge çözülür → cascade
 * görsel olarak kanıtlanmış olur.
 *
 * Ayrıca client-side `getComputedStyle()` ile gerçek hesaplanmış değerleri okur ve
 * yazdırır (kanıt çıktısı).
 */
"use client";

import { useEffect, useState } from "react";

interface Probe {
  cssVar: string;
  label: string;
  expectedAq?: string;
  expectedFinos?: string;
  expectedCorpos?: string;
}

const PROBES: Probe[] = [
  { cssVar: "--bg-primary",   label: "bg-primary (core — 3 modülde de aynı)",     expectedAq: "#0C1015", expectedFinos: "#0C1015", expectedCorpos: "#0C1015" },
  { cssVar: "--text-primary", label: "text-primary (core)",                       expectedAq: "#E2E4E8", expectedFinos: "#E2E4E8", expectedCorpos: "#E2E4E8" },
  { cssVar: "--status-error", label: "status-error (core — Kapı 3 negatif renk)", expectedAq: "#DE4F46", expectedFinos: "#DE4F46", expectedCorpos: "#DE4F46" },
  { cssVar: "--focus-ring",   label: "focus-ring (core)",                         expectedAq: "#0094F6", expectedFinos: "#0094F6", expectedCorpos: "#0094F6" },
  { cssVar: "--brand",        label: "brand (modül kimliği)",                     expectedAq: "#0C2D6B", expectedFinos: "#0EA5A4", expectedCorpos: "#F4C542" },
  { cssVar: "--cta",          label: "cta (modül kimliği — Kapı 1 FinOS=#CD4A00)", expectedAq: "#2563EB", expectedFinos: "#CD4A00", expectedCorpos: "#F4C542" },
  { cssVar: "--cta-text",     label: "cta-text (Q6 çift — CorpOS=#0C1224 koyu)",   expectedAq: "#FFFFFF", expectedFinos: "#FFFFFF", expectedCorpos: "#0C1224" },
  { cssVar: "--accent",       label: "accent (Kapı 4 CorpOS=slate #475569)",      expectedAq: "#2563EB", expectedFinos: "#4CABFD", expectedCorpos: "#475569" },
  { cssVar: "--link-back",    label: "link-back (Kapı 2 — silver #94A3B8)",       expectedAq: undefined, expectedFinos: "#94A3B8", expectedCorpos: "#94A3B8" },
];

type Module = "aq" | "finos" | "corpos";

/** Hex normalizer: "#cd4a00" → "#CD4A00", "rgb(205, 74, 0)" → "#CD4A00" */
function normalizeColor(value: string): string {
  const trimmed = value.trim();
  if (trimmed.startsWith("#")) return trimmed.toUpperCase();
  const m = trimmed.match(/rgb\((\d+)[,\s]+(\d+)[,\s]+(\d+)\)/i);
  if (m) {
    const [, r, g, b] = m;
    return (
      "#" +
      [r, g, b]
        .map((n) => parseInt(n, 10).toString(16).padStart(2, "0"))
        .join("")
        .toUpperCase()
    );
  }
  return trimmed.toUpperCase();
}

export function CascadeProbe({ expectedModule }: { expectedModule: Module }) {
  const [computed, setComputed] = useState<Record<string, string>>({});
  const [docModule, setDocModule] = useState<string>("");

  function refreshComputed() {
    const html = document.documentElement;
    setDocModule(html.getAttribute("data-module") ?? "");
    const cs = window.getComputedStyle(html);
    const out: Record<string, string> = {};
    for (const probe of PROBES) {
      const raw = cs.getPropertyValue(probe.cssVar).trim();
      out[probe.cssVar] = raw ? normalizeColor(raw) : "(unset)";
    }
    setComputed(out);
  }

  useEffect(() => {
    refreshComputed();
  }, []);

  // Faz 5 — Live preview: parent panel postMessage ile draft token gönderir.
  // Inline <style id="aq-draft-overlay"> bloğu ile en yüksek specificity'de
  // override edilir (SSR base + module cascade + draft overlay).
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!window.parent || window.parent === window) return;
    function applyDraft(tokens: Array<{ scope: string; key: string; value: string }>) {
      const byScope: Record<string, string[]> = {};
      for (const t of tokens) {
        if (typeof t.value !== "string") continue;
        const cssKey = `--${t.key.replace(/_/g, "-")}: ${t.value};`;
        let cssKeyRgb = "";
        const hex = t.value.match(/^#([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})$/);
        if (hex) {
          cssKeyRgb = `--${t.key.replace(/_/g, "-")}-rgb: ${parseInt(hex[1], 16)} ${parseInt(hex[2], 16)} ${parseInt(hex[3], 16)};`;
        }
        (byScope[t.scope] ??= []).push(cssKey + cssKeyRgb);
      }
      const segments: string[] = [];
      if (byScope.core) segments.push(`:root{${byScope.core.join("")}}`);
      for (const mod of ["aq", "finos", "corpos"] as const) {
        if (byScope[mod]) {
          segments.push(`html[data-module='${mod}']{${byScope[mod].join("")}}`);
        }
      }
      const css = segments.join("");
      let el = document.getElementById("aq-draft-overlay") as HTMLStyleElement | null;
      if (!el) {
        el = document.createElement("style");
        el.id = "aq-draft-overlay";
        document.head.appendChild(el);
      }
      el.textContent = css;
      requestAnimationFrame(refreshComputed);
    }
    function onMessage(ev: MessageEvent) {
      if (ev.origin !== window.location.origin) return;
      const data = ev.data as { type?: string; tokens?: unknown };
      if (data?.type !== "aq:draft-tokens" || !Array.isArray(data.tokens)) return;
      applyDraft(data.tokens as Array<{ scope: string; key: string; value: string }>);
    }
    window.addEventListener("message", onMessage);
    window.parent.postMessage({ type: "aq:preview-ready" }, window.location.origin);
    return () => window.removeEventListener("message", onMessage);
  }, []);

  const moduleColors: Record<Module, { bg: string; border: string; label: string }> = {
    aq:     { bg: "rgba(37, 99, 235, 0.08)",  border: "#2563EB", label: "AlphaQ (çatı)" },
    finos:  { bg: "rgba(14, 165, 164, 0.08)", border: "#0EA5A4", label: "FinOS" },
    corpos: { bg: "rgba(244, 197, 66, 0.10)", border: "#F4C542", label: "CorpOS" },
  };
  const c = moduleColors[expectedModule];
  const moduleMatchesDom = docModule === expectedModule;

  return (
    <main
      id="main"
      style={{
        minHeight: "100vh",
        background: "var(--bg-primary, #0a0a0a)",
        color: "var(--text-primary, #fafafa)",
        padding: "32px 24px",
        fontFamily: "system-ui, -apple-system, sans-serif",
      }}
    >
      <header style={{ marginBottom: 24, borderBottom: "1px solid var(--border)", paddingBottom: 16 }}>
        <h1 style={{ fontSize: 24, margin: 0 }}>
          Design Token Cascade Proof — <span style={{ color: c.border }}>{c.label}</span>
        </h1>
        <p style={{ marginTop: 8, color: "var(--text-secondary)", fontSize: 14 }}>
          Sayfa <code>{`<html data-module="${docModule || "?"}">`}</code> altında render edildi.
          {moduleMatchesDom ? (
            <span style={{ color: "var(--status-success)", marginLeft: 8 }}>
              ✓ Beklenen <code>{expectedModule}</code> ile eşleşti.
            </span>
          ) : (
            <span style={{ color: "var(--status-error)", marginLeft: 8 }}>
              ✗ MISMATCH! Beklenen: {expectedModule}
            </span>
          )}
        </p>
      </header>

      {/* Kimlik vurgu: var(--cta) ve var(--brand) ile boyalı kartlar.
          Bu kartlar AYNI HTML — yalnız CSS cascade ile renkleri değişiyor. */}
      <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 16, marginBottom: 28 }}>
        <div style={{ padding: 20, borderRadius: 10, background: c.bg, border: `1px solid ${c.border}` }}>
          <div style={{ height: 64, borderRadius: 6, background: "var(--cta)", marginBottom: 12 }} />
          <div style={{ fontSize: 12, color: "var(--text-muted)" }}>background: var(--cta)</div>
          <div style={{ fontSize: 16, fontWeight: 600, color: "var(--cta-text, white)" }}>
            <span style={{ background: "var(--cta)", padding: "4px 12px", borderRadius: 4 }}>
              Hemen başla
            </span>
          </div>
        </div>
        <div style={{ padding: 20, borderRadius: 10, background: c.bg, border: `1px solid ${c.border}` }}>
          <div style={{ height: 64, borderRadius: 6, background: "var(--brand)", marginBottom: 12 }} />
          <div style={{ fontSize: 12, color: "var(--text-muted)" }}>background: var(--brand)</div>
        </div>
        <div style={{ padding: 20, borderRadius: 10, background: c.bg, border: `1px solid ${c.border}` }}>
          <div style={{ height: 64, borderRadius: 6, background: "var(--accent)", marginBottom: 12 }} />
          <div style={{ fontSize: 12, color: "var(--text-muted)" }}>background: var(--accent)</div>
        </div>
        <div style={{ padding: 20, borderRadius: 10, background: c.bg, border: `1px solid ${c.border}` }}>
          <div style={{ height: 64, borderRadius: 6, background: "var(--bg-secondary)", border: "1px solid var(--border)", marginBottom: 12 }} />
          <div style={{ fontSize: 12, color: "var(--text-muted)" }}>background: var(--bg-secondary) (core)</div>
        </div>
      </section>

      {/* Faz 3.5: Alias Bridge — Tailwind shadcn class'larıyla aynı kimliği iddia.
          bg-primary text-primary-foreground → alias bridge → var(--cta-rgb) + var(--cta-text-rgb)
          → cascade modül scope'undan çözer. Üç route'ta üç farklı renge dönüşür. */}
      <section style={{ marginTop: 24, padding: 16, background: "var(--bg-secondary)", border: "1px solid var(--border)", borderRadius: 10 }}>
        <h2 style={{ fontSize: 14, margin: 0, marginBottom: 4 }}>Alias Bridge Kanıtı — Tailwind shadcn class&apos;ları</h2>
        <p style={{ fontSize: 11, color: "var(--text-muted)", margin: 0, marginBottom: 14 }}>
          Bu öğeler CSS değişkenlerini DOĞRUDAN kullanmıyor; Tailwind shadcn utility class&apos;ları
          (bg-primary, text-primary-foreground, bg-card, vb.) kullanıyor. Alias bridge devredeyken
          modül cascade&apos;inden geçerek modüle özel renkler alır.
        </p>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
          <button
            className="bg-primary text-primary-foreground px-4 py-2 rounded-md font-medium"
          >
            Hemen başla
          </button>
          <button
            className="bg-secondary text-secondary-foreground px-4 py-2 rounded-md"
          >
            İkincil
          </button>
          <button
            className="bg-destructive text-destructive-foreground px-4 py-2 rounded-md"
          >
            Sil
          </button>
          <div className="bg-accent text-accent-foreground px-4 py-2 rounded-md">
            Aksan
          </div>
          <div className="bg-card border-border border px-4 py-2 rounded-md text-foreground">
            Kart yüzeyi
          </div>
        </div>
        <div style={{ marginTop: 10, fontSize: 10, color: "var(--text-muted)" }}>
          <code>className=&quot;bg-primary text-primary-foreground&quot;</code> →
          alias: <code>--primary: var(--cta-rgb)</code>,
          <code> --primary-foreground: var(--cta-text-rgb)</code> →
          cascade: <code>html[data-module=&apos;{expectedModule}&apos;]</code>
        </div>
      </section>

      {/* Computed values — gerçek tarayıcı çıktısı. Sayfa yüklendikten sonra useEffect doldurur. */}
      <section style={{ background: "var(--bg-secondary)", border: "1px solid var(--border)", borderRadius: 10, padding: 20 }}>
        <h2 style={{ fontSize: 16, margin: 0, marginBottom: 12 }}>Computed CSS değerleri (tarayıcı)</h2>
        <p style={{ fontSize: 12, color: "var(--text-muted)", margin: 0, marginBottom: 16 }}>
          <code>getComputedStyle(document.documentElement).getPropertyValue(...)</code>
        </p>
        <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: "ui-monospace, monospace", fontSize: 12 }}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border)", textAlign: "left" }}>
              <th style={{ padding: "6px 8px", color: "var(--text-muted)" }}>CSS var</th>
              <th style={{ padding: "6px 8px", color: "var(--text-muted)" }}>Computed</th>
              <th style={{ padding: "6px 8px", color: "var(--text-muted)" }}>Expected ({expectedModule})</th>
              <th style={{ padding: "6px 8px", color: "var(--text-muted)" }}>Status</th>
              <th style={{ padding: "6px 8px", color: "var(--text-muted)" }}>Swatch</th>
            </tr>
          </thead>
          <tbody>
            {PROBES.map((probe) => {
              const got = computed[probe.cssVar] ?? "...";
              const expected = (probe[`expected${expectedModule.charAt(0).toUpperCase() + expectedModule.slice(1)}` as keyof Probe] as string | undefined);
              const match = !expected ? null : got.toUpperCase() === expected.toUpperCase();
              return (
                <tr key={probe.cssVar} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td style={{ padding: "8px 8px" }}>
                    <code>{probe.cssVar}</code>
                    <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 2 }}>{probe.label}</div>
                  </td>
                  <td style={{ padding: "8px 8px", fontWeight: 600 }}>{got}</td>
                  <td style={{ padding: "8px 8px" }}>{expected ?? "—"}</td>
                  <td style={{ padding: "8px 8px" }}>
                    {match === null && <span style={{ color: "var(--text-muted)" }}>n/a</span>}
                    {match === true && <span style={{ color: "var(--status-success)" }}>✓</span>}
                    {match === false && <span style={{ color: "var(--status-error)" }}>✗</span>}
                  </td>
                  <td style={{ padding: "8px 8px" }}>
                    <span
                      style={{
                        display: "inline-block",
                        width: 28,
                        height: 16,
                        borderRadius: 3,
                        background: got !== "..." && got !== "(unset)" ? got : "transparent",
                        border: "1px solid var(--border)",
                      }}
                    />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>

      <footer style={{ marginTop: 24, fontSize: 11, color: "var(--text-muted)" }}>
        Sayfa SSR&apos;da render edildi · <code>{`<html data-module="${docModule}">`}</code> ·{" "}
        ThemeTokens 5 style bloğu (core + aq + finos + corpos + theme scaffold) basıldı.
        Specificity: <code>html[data-module=&apos;X&apos;] (0,1,1) &gt; :root (0,1,0)</code>.
      </footer>
    </main>
  );
}
