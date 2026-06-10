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

  useEffect(() => {
    const html = document.documentElement;
    setDocModule(html.getAttribute("data-module") ?? "");

    const cs = window.getComputedStyle(html);
    const out: Record<string, string> = {};
    for (const probe of PROBES) {
      const raw = cs.getPropertyValue(probe.cssVar).trim();
      out[probe.cssVar] = raw ? normalizeColor(raw) : "(unset)";
    }
    setComputed(out);
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
