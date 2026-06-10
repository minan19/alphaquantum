#!/usr/bin/env node
/* eslint-disable */
/**
 * Alpha Quantum Design Token Engine — Faz 0 system.mjs
 *
 * Saf JS (sıfır npm bağımlılığı). Çalıştırma:
 *   node docs/design-tokens/system.mjs
 *
 * Çıktılar (docs/design-tokens/ içine):
 *   wcag-report.md     ← insan-okunur rapor (6 kapı sonucu)
 *   wcag-report.json   ← makine-okunur (CI gate için)
 *   preview.html       ← 4 palet statik önizleme
 *
 * Exit code:
 *   0 — 6 kapı geçti
 *   1 — 1+ kapı düştü (raporda detay)
 */

import { writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUT_DIR = __dirname;

// ============================================================================
// 1. OKLCH ↔ sRGB conversion
// Ref: Björn Ottosson, "A perceptual color space for image processing" (Oklab).
// ============================================================================

/** Linear-light sRGB → sRGB gamma (companding). */
function linearToSrgb(v) {
  if (v < 0) return 0;
  if (v > 1) return 1;
  return v >= 0.0031308 ? 1.055 * Math.pow(v, 1 / 2.4) - 0.055 : 12.92 * v;
}

/** sRGB gamma → linear-light sRGB. */
function srgbToLinear(v) {
  return v >= 0.04045 ? Math.pow((v + 0.055) / 1.055, 2.4) : v / 12.92;
}

/** OKLab → linear sRGB. */
function oklabToLinearSrgb(L, a, b) {
  const l_ = L + 0.3963377774 * a + 0.2158037573 * b;
  const m_ = L - 0.1055613458 * a - 0.0638541728 * b;
  const s_ = L - 0.0894841775 * a - 1.2914855480 * b;
  const l = l_ * l_ * l_;
  const m = m_ * m_ * m_;
  const s = s_ * s_ * s_;
  return [
     4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
    -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
    -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
  ];
}

/** Linear sRGB → OKLab. */
function linearSrgbToOklab(r, g, b) {
  const l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b;
  const m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b;
  const s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b;
  const l_ = Math.cbrt(l);
  const m_ = Math.cbrt(m);
  const s_ = Math.cbrt(s);
  return [
    0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
    1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
    0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
  ];
}

/** OKLCH → hex string `#RRGGBB`. Out-of-gamut clamps via simple clip. */
export function oklchToHex(L, C, hDeg) {
  const h = (hDeg * Math.PI) / 180;
  const a = C * Math.cos(h);
  const b = C * Math.sin(h);
  const [lr, lg, lb] = oklabToLinearSrgb(L, a, b);
  const r = Math.round(255 * linearToSrgb(lr));
  const g = Math.round(255 * linearToSrgb(lg));
  const bl = Math.round(255 * linearToSrgb(lb));
  const clamp = (v) => Math.max(0, Math.min(255, v));
  return (
    "#" +
    clamp(r).toString(16).padStart(2, "0") +
    clamp(g).toString(16).padStart(2, "0") +
    clamp(bl).toString(16).padStart(2, "0")
  ).toUpperCase();
}

/** Hex `#RRGGBB` → OKLCH {L,C,h}. */
export function hexToOklch(hex) {
  const r = parseInt(hex.slice(1, 3), 16) / 255;
  const g = parseInt(hex.slice(3, 5), 16) / 255;
  const b = parseInt(hex.slice(5, 7), 16) / 255;
  const [lr, lg, lb] = [srgbToLinear(r), srgbToLinear(g), srgbToLinear(b)];
  const [L, A, B] = linearSrgbToOklab(lr, lg, lb);
  const C = Math.sqrt(A * A + B * B);
  let h = (Math.atan2(B, A) * 180) / Math.PI;
  if (h < 0) h += 360;
  return { L, C, h };
}

// ============================================================================
// 2. WCAG 2.2 contrast
// ============================================================================

/** Relative luminance per WCAG. */
function relLuminance(hex) {
  const r = srgbToLinear(parseInt(hex.slice(1, 3), 16) / 255);
  const g = srgbToLinear(parseInt(hex.slice(3, 5), 16) / 255);
  const b = srgbToLinear(parseInt(hex.slice(5, 7), 16) / 255);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/** WCAG 2.2 contrast ratio (1..21). */
export function wcagContrast(fgHex, bgHex) {
  const L1 = relLuminance(fgHex);
  const L2 = relLuminance(bgHex);
  const lighter = Math.max(L1, L2);
  const darker = Math.min(L1, L2);
  return (lighter + 0.05) / (darker + 0.05);
}

/** AAA / AA / AA-Large / FAIL. */
export function contrastRating(r) {
  if (r >= 7) return "AAA";
  if (r >= 4.5) return "AA";
  if (r >= 3) return "AA-Lg";
  return "FAIL";
}

// ============================================================================
// 3. Binary-search text level L for a target contrast against bg.
// ============================================================================

/** Find L (in OKLCH) for given hue+chroma that lands at target contrast against bg. */
function findTextL(bgHex, targetContrast, hue, chroma, prefer = "light") {
  const bgL = relLuminance(bgHex);
  // Direction: if bg is dark → text should be light (L high); else dark (L low).
  const bgIsDark = bgL < 0.18; // perceptual heuristic
  let lo = bgIsDark ? 0.5 : 0.0;
  let hi = bgIsDark ? 1.0 : 0.5;
  let best = bgIsDark ? 0.95 : 0.05;
  let bestDelta = Infinity;
  for (let i = 0; i < 40; i++) {
    const mid = (lo + hi) / 2;
    const hex = oklchToHex(mid, chroma, hue);
    const c = wcagContrast(hex, bgHex);
    const delta = c - targetContrast;
    if (Math.abs(delta) < bestDelta) {
      bestDelta = Math.abs(delta);
      best = mid;
    }
    // Higher L on dark bg → higher contrast. Lower L on light bg → higher contrast.
    if (bgIsDark) {
      if (c < targetContrast) lo = mid;
      else hi = mid;
    } else {
      if (c < targetContrast) hi = mid;
      else lo = mid;
    }
  }
  return best;
}

// ============================================================================
// 4. FAZ 0 anchors (from foundation.md — KILITLI)
// ============================================================================

const ANCHORS = {
  core: {
    neutral_hue: 258,
    neutral_chroma: 0.012,
    bg_primary_dark:  { L: 0.17, C: 0.012, h: 258 },
    bg_primary_light: { L: 0.99, C: 0.006, h: 258 },
    elevation_delta_L: 0.03,
    status: {
      success: { h: 150, L: 0.72, C: 0.13 },
      warning: { h:  80, L: 0.78, C: 0.16 },
      error:   { h:  27, L: 0.62, C: 0.18 },
      info:    { h: 248, L: 0.72, C: 0.15 },
    },
    focus_ring: { h: 248, L: 0.65, C: 0.18 },
    text_targets: {
      primary:   { contrast: 15, hue: 258, chroma: 0.005 },
      secondary: { contrast:  8, hue: 258, chroma: 0.008 },
      muted:     { contrast: 4.5, hue: 258, chroma: 0.012 },
    },
  },
  aq: {
    brand:    { L: 0.316, C: 0.115, h: 261.5, hex: "#0C2D6B" },
    cta:      { L: 0.546, C: 0.215, h: 263.0, hex: "#2563EB", roof_locked: true },
    on_brand: { L: 0.95,  C: 0.012, h: 258,   hex: "#E8EFF9" },
    cta_text: "#FFFFFF",
  },
  finos: {
    brand:     { L: 0.654, C: 0.110, h: 194, hex: "#0EA5A4" },
    cta:       { L: 0.580, C: 0.155, h: 47.6, hex: "#CD4A00" }, // chroma chosen to match hex
    cta_text:  "#FFFFFF",
    link_back: "#94A3B8",
  },
  corpos: {
    brand:        { L: 0.843, C: 0.151, h: 88, hex: "#F4C542" },
    accent:       { L: 0.446, C: 0.035, h: 257, hex: "#475569" },
    accent_light: { L: 0.711, C: 0.025, h: 257, hex: "#94A3B8" },
    cta_text_dark: "#0C1224",
    link_back:    "#94A3B8",
  },
};

// ============================================================================
// 5. Palette builder
// ============================================================================

function buildCorePalette(theme = "dark") {
  const c = ANCHORS.core;
  const bgL = theme === "light" ? c.bg_primary_light.L : c.bg_primary_dark.L;
  const bgC = theme === "light" ? c.bg_primary_light.C : c.bg_primary_dark.C;
  const sign = theme === "light" ? -1 : +1;

  const bg_primary = oklchToHex(bgL, bgC, c.neutral_hue);

  // Elevation ramp (+0.03 ΔL each step in dark, -0.03 each step in light).
  const elev = (n) =>
    oklchToHex(
      Math.max(0, Math.min(1, bgL + sign * c.elevation_delta_L * n)),
      bgC,
      c.neutral_hue,
    );

  // Text levels via binary search (against bg_primary).
  const txt = (target) => {
    const L = findTextL(
      bg_primary,
      target.contrast,
      target.hue,
      target.chroma,
    );
    return oklchToHex(L, target.chroma, target.hue);
  };

  // Status anchors → hex (raw, no contrast tuning — used in badges/highlights).
  const statusHex = {};
  const statusSurfaceHex = {};
  for (const [k, v] of Object.entries(c.status)) {
    statusHex[k] = oklchToHex(v.L, v.C, v.h);
    // Surface: low chroma, dark bg-adapted L for dark theme.
    const sL = theme === "light" ? Math.min(0.95, v.L + 0.18) : Math.max(0.18, v.L - 0.45);
    const sC = Math.min(0.03, v.C * 0.18);
    statusSurfaceHex[k] = oklchToHex(sL, sC, v.h);
  }

  return {
    theme,
    bg_primary,
    bg_secondary: elev(1),
    bg_tertiary:  elev(2),
    surface_01:   elev(3),
    surface_02:   elev(4),
    surface_03:   elev(5),
    border: oklchToHex(
      Math.max(0, Math.min(1, bgL + sign * c.elevation_delta_L * 3)),
      Math.min(0.02, bgC * 1.5),
      c.neutral_hue,
    ),
    text_primary:   txt(c.text_targets.primary),
    text_secondary: txt(c.text_targets.secondary),
    text_muted:     txt(c.text_targets.muted),
    text_inverse:   theme === "light" ? "#FFFFFF" : "#0C1224",
    status_success:         statusHex.success,
    status_success_surface: statusSurfaceHex.success,
    status_warning:         statusHex.warning,
    status_warning_surface: statusSurfaceHex.warning,
    status_error:           statusHex.error,
    status_error_surface:   statusSurfaceHex.error,
    status_info:            statusHex.info,
    status_info_surface:    statusSurfaceHex.info,
    focus_ring: oklchToHex(c.focus_ring.L, c.focus_ring.C, c.focus_ring.h),
  };
}

function buildModulePalette(name, core) {
  const a = ANCHORS[name];
  if (name === "aq") {
    return {
      scope: "aq",
      brand:        a.brand.hex,
      brand_hover:  oklchToHex(Math.max(0, a.brand.L - 0.14), a.brand.C, a.brand.h),
      cta:          a.cta.hex,
      cta_hover:    oklchToHex(Math.max(0, a.cta.L - 0.14), a.cta.C, a.cta.h),
      cta_text:     a.cta_text,
      on_brand:     a.on_brand.hex,
      accent:       a.cta.hex, // çatı için signature azure data accent
      link_back:    null,      // çatı kendi içinde, geri-link yok
    };
  }
  if (name === "finos") {
    return {
      scope: "finos",
      brand:        a.brand.hex,
      brand_hover:  oklchToHex(Math.max(0, a.brand.L - 0.14), a.brand.C, a.brand.h),
      cta:          a.cta.hex,
      cta_hover:    oklchToHex(Math.max(0, a.cta.L - 0.14), a.cta.C, a.cta.h),
      cta_text:     a.cta_text,
      accent:       core.status_info,
      link_back:    a.link_back,
    };
  }
  if (name === "corpos") {
    return {
      scope: "corpos",
      brand:        a.brand.hex,
      brand_hover:  oklchToHex(Math.max(0, a.brand.L - 0.10), a.brand.C, a.brand.h),
      cta:          a.brand.hex, // CTA = altın dolgu
      cta_hover:    oklchToHex(Math.max(0, a.brand.L - 0.10), a.brand.C, a.brand.h),
      cta_text:     a.cta_text_dark,
      cta_text_weight: 500,
      accent:       a.accent.hex,
      accent_light: a.accent_light.hex,
      link_back:    a.link_back,
    };
  }
  throw new Error(`Unknown scope: ${name}`);
}

// ============================================================================
// 6. WCAG gate verification
// ============================================================================

function verifyGates(core, palettes) {
  const checks = [];

  // GATE 1 — FinOS CTA over white text ≥ 4.5
  const g1 = wcagContrast(palettes.finos.cta_text, palettes.finos.cta);
  checks.push({
    id: 1,
    name: "FinOS CTA × white text ≥ 4.5:1",
    target: 4.5,
    measured: g1,
    pass: g1 >= 4.5,
    detail: `cta=${palettes.finos.cta} text=${palettes.finos.cta_text} → ${g1.toFixed(2)}:1`,
  });

  // GATE 2 — link-back over dark surface ≥ 4.5 (both finos + corpos)
  const g2a = wcagContrast(palettes.finos.link_back, core.bg_primary);
  const g2b = wcagContrast(palettes.corpos.link_back, core.bg_primary);
  checks.push({
    id: 2,
    name: "FinOS link-back × bg-primary(dark) ≥ 4.5:1",
    target: 4.5,
    measured: g2a,
    pass: g2a >= 4.5,
    detail: `link_back=${palettes.finos.link_back} bg=${core.bg_primary} → ${g2a.toFixed(2)}:1`,
  });
  checks.push({
    id: 2,
    name: "CorpOS link-back × bg-primary(dark) ≥ 4.5:1",
    target: 4.5,
    measured: g2b,
    pass: g2b >= 4.5,
    detail: `link_back=${palettes.corpos.link_back} bg=${core.bg_primary} → ${g2b.toFixed(2)}:1`,
  });

  // GATE 3 — negative/loss color defined (core.status_error)
  const errExists = !!core.status_error;
  const errContrast = errExists
    ? wcagContrast(core.status_error, core.bg_primary)
    : 0;
  checks.push({
    id: 3,
    name: "Negatif renk (status-error) tanımlı + okunabilir",
    target: 3.0, // accent için AA-Lg yeterli (icon + sayı)
    measured: errContrast,
    pass: errExists && errContrast >= 3.0,
    detail: `status_error=${core.status_error} bg=${core.bg_primary} → ${errContrast.toFixed(2)}:1`,
  });

  // GATE 4 — FinOS vs CorpOS NOT same teal: hue dissimilarity check
  const finosBrandOklch = hexToOklch(palettes.finos.brand);
  const corposAccentOklch = hexToOklch(palettes.corpos.accent);
  const hueDelta = Math.abs(finosBrandOklch.h - corposAccentOklch.h);
  const hueDeltaWrapped = Math.min(hueDelta, 360 - hueDelta);
  // CorpOS accent must NOT be teal (hue ≈ 180-200). Slate hue ~257 expected.
  const corposIsTeal = corposAccentOklch.h >= 170 && corposAccentOklch.h <= 210;
  checks.push({
    id: 4,
    name: "FinOS (teal) ≠ CorpOS accent (slate, teal değil)",
    target: "CorpOS accent hue ∉ [170, 210]",
    measured: `Δh = ${hueDeltaWrapped.toFixed(1)}°, CorpOS hue = ${corposAccentOklch.h.toFixed(1)}°`,
    pass: !corposIsTeal && hueDeltaWrapped > 40,
    detail: `finos.brand hue=${finosBrandOklch.h.toFixed(1)}, corpos.accent hue=${corposAccentOklch.h.toFixed(1)}`,
  });

  // GATE 5 — Common semantic layer (status) defined in core, not in modules
  const allFourStatus =
    !!core.status_success &&
    !!core.status_warning &&
    !!core.status_error &&
    !!core.status_info;
  checks.push({
    id: 5,
    name: "Ortak semantik katman (success/warning/error/info) çekirdekte",
    target: "4/4 status token core scope'unda",
    measured: `success=${!!core.status_success} warning=${!!core.status_warning} error=${!!core.status_error} info=${!!core.status_info}`,
    pass: allFourStatus,
    detail: "Modüller status token'larını ezemez (governance).",
  });

  // GATE 6 — focus-ring defined + visible (≥ 3:1 against bg)
  const focusContrast = wcagContrast(core.focus_ring, core.bg_primary);
  checks.push({
    id: 6,
    name: "focus-ring tanımlı + bg-primary üzerinde görünür ≥ 3:1",
    target: 3.0,
    measured: focusContrast,
    pass: !!core.focus_ring && focusContrast >= 3.0,
    detail: `focus_ring=${core.focus_ring} bg=${core.bg_primary} → ${focusContrast.toFixed(2)}:1`,
  });

  return checks;
}

// ============================================================================
// 7. Text contrast diagnostics (informational)
// ============================================================================

function buildTextContrastTable(core) {
  return [
    {
      pair: "text_primary × bg_primary",
      contrast: wcagContrast(core.text_primary, core.bg_primary),
      rating: () => {},
    },
    {
      pair: "text_secondary × bg_primary",
      contrast: wcagContrast(core.text_secondary, core.bg_primary),
    },
    {
      pair: "text_muted × bg_primary",
      contrast: wcagContrast(core.text_muted, core.bg_primary),
    },
  ].map((r) => ({ ...r, rating: contrastRating(r.contrast) }));
}

// ============================================================================
// 8. Report writers
// ============================================================================

function writeJsonReport(report) {
  writeFileSync(
    join(OUT_DIR, "wcag-report.json"),
    JSON.stringify(report, null, 2) + "\n",
    "utf8",
  );
}

function writeMarkdownReport(core, modules, gates, textTable) {
  const lines = [];
  const stamp = "10 Haziran 2026"; // intentional fixed date — script is deterministic
  const passCount = gates.filter((g) => g.pass).length;
  const totalCount = gates.length;
  const allPass = passCount === totalCount;

  lines.push("# Alpha Quantum — Design Token WCAG Raporu");
  lines.push(`### Faz 0 · Otomatik üretildi (${stamp})`);
  lines.push("");
  lines.push(`> Bu rapor \`docs/design-tokens/system.mjs\` tarafından mekanik olarak`);
  lines.push(`> üretilmiştir. Manuel değiştirme YASAK. Yeniden üretim: \`node docs/design-tokens/system.mjs\`.`);
  lines.push("");
  lines.push(`## Özet: ${allPass ? "✅ TÜM KAPILAR GEÇTİ" : "❌ EN AZ 1 KAPI DÜŞTÜ"}`);
  lines.push(``);
  lines.push(`**Kapı sonucu:** ${passCount}/${totalCount} pass`);
  lines.push("");

  // Gates table
  lines.push("## 6 Pazarlıksız Kapı");
  lines.push("");
  lines.push("| # | Kapı | Hedef | Ölçülen | Sonuç |");
  lines.push("|---|------|-------|---------|-------|");
  for (const g of gates) {
    const icon = g.pass ? "✅" : "❌";
    const measured =
      typeof g.measured === "number" ? g.measured.toFixed(2) : g.measured;
    lines.push(`| ${g.id} | ${g.name} | ${g.target} | ${measured} | ${icon} |`);
  }
  lines.push("");
  lines.push("### Detaylar");
  lines.push("");
  for (const g of gates) {
    lines.push(`- **Kapı ${g.id} — ${g.name}**`);
    lines.push(`  - ${g.detail}`);
    lines.push(`  - ${g.pass ? "✅ PASS" : "❌ FAIL"}`);
  }
  lines.push("");

  // Core palette
  lines.push("## CORE palet");
  lines.push("");
  lines.push("### Dark teması");
  lines.push("| Token | Hex |");
  lines.push("|---|---|");
  for (const [k, v] of Object.entries(core)) {
    if (k === "theme") continue;
    lines.push(`| \`${k}\` | \`${v}\` |`);
  }
  lines.push("");

  // Text contrast table
  lines.push("### Metin kontrastları (bg_primary'ye karşı)");
  lines.push("");
  lines.push("| Çift | Kontrast | Derece |");
  lines.push("|---|---|---|");
  for (const r of textTable) {
    lines.push(`| ${r.pair} | ${r.contrast.toFixed(2)}:1 | ${r.rating} |`);
  }
  lines.push("");

  // Module palettes
  for (const [name, p] of Object.entries(modules)) {
    lines.push(`## ${name.toUpperCase()} kimlik tokenları`);
    lines.push("");
    lines.push("| Token | Değer |");
    lines.push("|---|---|");
    for (const [k, v] of Object.entries(p)) {
      if (v === null || v === undefined) continue;
      lines.push(`| \`${k}\` | \`${v}\` |`);
    }
    lines.push("");

    // Module-specific contrast diagnostics
    const diag = [];
    if (p.cta && p.cta_text) {
      diag.push({
        pair: `${name}.cta × ${name}.cta_text`,
        c: wcagContrast(p.cta, p.cta_text),
      });
    }
    if (p.link_back) {
      diag.push({
        pair: `${name}.link_back × core.bg_primary`,
        c: wcagContrast(p.link_back, core.bg_primary),
      });
    }
    if (p.brand) {
      diag.push({
        pair: `${name}.brand × core.bg_primary`,
        c: wcagContrast(p.brand, core.bg_primary),
      });
    }
    if (diag.length) {
      lines.push("### Kritik kontrastlar");
      lines.push("");
      lines.push("| Çift | Kontrast | Derece |");
      lines.push("|---|---|---|");
      for (const d of diag) {
        lines.push(`| ${d.pair} | ${d.c.toFixed(2)}:1 | ${contrastRating(d.c)} |`);
      }
      lines.push("");
    }
  }

  // Color-blind / dissimilarity check
  lines.push("## Modül ayırt edilebilirlik (renk körlüğü dayanıklılığı)");
  lines.push("");
  lines.push(
    "Kapı #4'ün ötesi: FinOS ve CorpOS kimlik token'larının hue uzayında",
  );
  lines.push("yeterli uzaklıkta olması — protan/deutan körlüğüne karşı dayanıklılık.");
  lines.push("");

  writeFileSync(join(OUT_DIR, "wcag-report.md"), lines.join("\n") + "\n", "utf8");
}

// ============================================================================
// 9. Preview HTML (4 palet, self-contained)
// ============================================================================

function writePreviewHtml(coreDark, modules) {
  const palette = (name, p) => {
    const isCore = name === "core";
    const brand = isCore ? coreDark.bg_secondary : p.brand;
    const cta = isCore ? coreDark.status_info : p.cta;
    const ctaText = isCore ? coreDark.text_primary : p.cta_text;
    const accent = isCore ? coreDark.status_info : p.accent;
    const linkBack = isCore ? null : p.link_back;
    const moduleLabel =
      { aq: "AlphaQ (çatı)", finos: "FinOS", corpos: "CorpOS" }[name] ?? "Core";

    const css = `
      --bg-primary: ${coreDark.bg_primary};
      --bg-secondary: ${coreDark.bg_secondary};
      --bg-tertiary: ${coreDark.bg_tertiary};
      --surface-01: ${coreDark.surface_01};
      --border: ${coreDark.border};
      --text-primary: ${coreDark.text_primary};
      --text-secondary: ${coreDark.text_secondary};
      --text-muted: ${coreDark.text_muted};
      --text-inverse: ${coreDark.text_inverse};
      --status-success: ${coreDark.status_success};
      --status-warning: ${coreDark.status_warning};
      --status-error: ${coreDark.status_error};
      --status-info: ${coreDark.status_info};
      --focus-ring: ${coreDark.focus_ring};
      --brand: ${brand};
      --cta: ${cta};
      --cta-text: ${ctaText};
      --accent: ${accent};
      --link-back: ${linkBack ?? "transparent"};
    `;

    return `
    <section class="palette-card" style="${css}">
      <header class="ph">
        <div class="ph-brand">
          <div class="logo-dot" style="background:${brand}"></div>
          <strong>${moduleLabel}</strong>
        </div>
        ${linkBack ? `<a class="back" href="#" style="color:${linkBack}">← Çatı'ya dön</a>` : `<span class="back" style="opacity:.4">root</span>`}
      </header>
      <div class="hero">
        <h2>${moduleLabel} ana ekranı</h2>
        <p>Tek paragraflık tanıtım metni — secondary text tonunda.</p>
        <div class="hero-actions">
          <button class="cta" style="background:${cta}; color:${ctaText};">Hemen başla</button>
          <button class="ghost">İncele</button>
        </div>
      </div>
      <div class="card">
        <div class="card-h">
          <strong>Aylık özet</strong>
          <span class="muted">Haziran 2026</span>
        </div>
        <div class="kpi-row">
          <div class="kpi">
            <span class="muted">Net akış</span>
            <strong class="up">+₺128.450</strong>
          </div>
          <div class="kpi">
            <span class="muted">Risk müşterisi</span>
            <strong class="down">−₺47.200</strong>
          </div>
          <div class="kpi">
            <span class="muted">Aktif hesap</span>
            <strong>${name === "core" ? 14 : 23 + name.length}</strong>
          </div>
        </div>
      </div>
      <div class="badges">
        <span class="b b-success">başarı</span>
        <span class="b b-warning">uyarı</span>
        <span class="b b-error">hata</span>
        <span class="b b-info">bilgi</span>
      </div>
      <div class="swatches">
        ${[
          { label: "brand", v: brand },
          { label: "cta", v: cta },
          { label: "accent", v: accent },
          { label: "bg-primary", v: coreDark.bg_primary },
          { label: "surface-01", v: coreDark.surface_01 },
          { label: "border", v: coreDark.border },
        ]
          .map(
            (s) =>
              `<div class="sw"><div class="sw-c" style="background:${s.v}"></div><code>${s.label}</code><code class="muted">${s.v}</code></div>`,
          )
          .join("")}
      </div>
    </section>`;
  };

  const html = `<!doctype html>
<html lang="tr" data-theme="dark">
<head>
<meta charset="utf-8">
<title>Alpha Quantum — Design Token Önizleme (Faz 0)</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  :root {
    --bg-page: ${coreDark.bg_primary};
    --bg-card: ${coreDark.bg_secondary};
    --border: ${coreDark.border};
    color-scheme: dark;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; }
  body {
    background: var(--bg-page);
    color: ${coreDark.text_primary};
    font-family: -apple-system, "SF Pro Text", "Inter", Segoe UI, Roboto, sans-serif;
    line-height: 1.5;
    padding: 32px 24px 80px;
  }
  .container { max-width: 1280px; margin: 0 auto; }
  .top {
    display: flex; justify-content: space-between; align-items: flex-end;
    margin-bottom: 28px; border-bottom: 1px solid var(--border); padding-bottom: 16px;
  }
  .top h1 { margin: 0; font-size: 22px; }
  .top .meta { color: ${coreDark.text_muted}; font-size: 13px; }
  .grid { display: grid; gap: 24px; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); }

  .palette-card {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
    color: var(--text-primary);
  }
  .ph {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 16px; padding-bottom: 12px;
    border-bottom: 1px solid var(--border);
  }
  .ph-brand { display: flex; align-items: center; gap: 10px; font-size: 13px; }
  .logo-dot { width: 16px; height: 16px; border-radius: 50%; }
  .back { font-size: 12px; text-decoration: none; }

  .hero h2 { margin: 0 0 4px; font-size: 18px; }
  .hero p { margin: 0 0 12px; color: var(--text-secondary); font-size: 13px; }
  .hero-actions { display: flex; gap: 8px; }
  button.cta, button.ghost {
    font: inherit; padding: 8px 14px; border-radius: 6px; border: none;
    cursor: pointer; font-weight: 500; font-size: 13px;
  }
  button.ghost {
    background: transparent; color: var(--text-secondary);
    border: 1px solid var(--border);
  }
  button.cta { box-shadow: 0 1px 0 rgba(255,255,255,.08) inset; }
  button:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 2px; }

  .card {
    margin-top: 16px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 14px;
  }
  .card-h { display: flex; justify-content: space-between; font-size: 13px; margin-bottom: 10px; }
  .muted { color: var(--text-muted); font-size: 12px; }

  .kpi-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
  .kpi { display: flex; flex-direction: column; gap: 4px; }
  .kpi strong { font-variant-numeric: tabular-nums; font-size: 16px; }
  .up { color: var(--status-success); }
  .down { color: var(--status-error); }

  .badges { display: flex; gap: 8px; margin-top: 14px; flex-wrap: wrap; }
  .b {
    padding: 3px 10px; border-radius: 999px; font-size: 11px; font-weight: 500;
    border: 1px solid transparent;
  }
  .b-success { color: var(--status-success); background: ${coreDark.status_success_surface}; border-color: var(--status-success); }
  .b-warning { color: var(--status-warning); background: ${coreDark.status_warning_surface}; border-color: var(--status-warning); }
  .b-error   { color: var(--status-error);   background: ${coreDark.status_error_surface};   border-color: var(--status-error);   }
  .b-info    { color: var(--status-info);    background: ${coreDark.status_info_surface};    border-color: var(--status-info);    }

  .swatches {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
    gap: 8px; margin-top: 16px;
  }
  .sw {
    display: flex; flex-direction: column; gap: 2px; align-items: flex-start;
    font-size: 10px;
  }
  .sw-c { width: 100%; height: 38px; border-radius: 6px; border: 1px solid var(--border); }
  .sw code { font-size: 10px; }
  .legend {
    margin-top: 28px; padding: 14px;
    background: ${coreDark.bg_secondary}; border: 1px solid ${coreDark.border};
    border-radius: 10px; font-size: 12px; color: ${coreDark.text_secondary};
  }
  .legend strong { color: ${coreDark.text_primary}; }
</style>
</head>
<body>
<div class="container">
  <div class="top">
    <h1>Alpha Quantum — Design Token Önizleme</h1>
    <div class="meta">Faz 0 · Foundation kilidi · 10 Haziran 2026</div>
  </div>
  <div class="grid">
    ${palette("core", null)}
    ${palette("aq", modules.aq)}
    ${palette("finos", modules.finos)}
    ${palette("corpos", modules.corpos)}
  </div>
  <div class="legend">
    <strong>Kapı doğrulamaları:</strong> Bu sayfa <code>system.mjs</code> tarafından
    üretilmiştir. WCAG kontrast oranları, hue dissimilarity, status renk varlığı —
    hepsi raporda mekanik olarak doğrulanmıştır. Detay için
    <code>docs/design-tokens/wcag-report.md</code>.
  </div>
</div>
</body>
</html>
`;
  writeFileSync(join(OUT_DIR, "preview.html"), html, "utf8");
}

// ============================================================================
// 10. Main
// ============================================================================

function main() {
  // Ensure out dir exists.
  mkdirSync(OUT_DIR, { recursive: true });

  // Build dark palette (Faz 0 deliverable; light is Faz 7).
  const core = buildCorePalette("dark");

  const modules = {
    aq:     buildModulePalette("aq", core),
    finos:  buildModulePalette("finos", core),
    corpos: buildModulePalette("corpos", core),
  };

  const gates = verifyGates(core, modules);
  const textTable = buildTextContrastTable(core);

  const allPass = gates.every((g) => g.pass);

  // Serialize results.
  const json = {
    generated_at: "2026-06-10",
    foundation_version: "1.0.0",
    theme: "dark",
    core,
    modules,
    gates,
    text_contrast: textTable,
    pass_count: gates.filter((g) => g.pass).length,
    gate_count: gates.length,
    all_gates_pass: allPass,
  };
  writeJsonReport(json);
  writeMarkdownReport(core, modules, gates, textTable);
  writePreviewHtml(core, modules);

  // Console summary.
  console.log("=".repeat(64));
  console.log("Alpha Quantum — Design Token Foundation (Faz 0)");
  console.log("=".repeat(64));
  console.log(`Theme: dark`);
  console.log("");
  console.log(`Core palette (${Object.keys(core).length} token):`);
  console.log(`  bg_primary=${core.bg_primary}  border=${core.border}`);
  console.log(`  text_primary=${core.text_primary}`);
  console.log("");
  console.log("Module identity:");
  for (const [k, v] of Object.entries(modules)) {
    console.log(`  ${k.padEnd(7)} brand=${v.brand} cta=${v.cta} cta_text=${v.cta_text}`);
  }
  console.log("");
  console.log(`PAZARLIKSIZ KAPILAR: ${gates.filter((g) => g.pass).length}/${gates.length} pass`);
  console.log("");
  for (const g of gates) {
    const icon = g.pass ? "✓" : "✗";
    const measured =
      typeof g.measured === "number" ? g.measured.toFixed(2) : g.measured;
    console.log(`  ${icon} Kapı ${g.id}: ${g.name}`);
    console.log(`     ${measured}`);
  }
  console.log("");
  console.log(`Çıktılar:`);
  console.log(`  - ${join(OUT_DIR, "wcag-report.md")}`);
  console.log(`  - ${join(OUT_DIR, "wcag-report.json")}`);
  console.log(`  - ${join(OUT_DIR, "preview.html")}`);
  console.log("=".repeat(64));

  if (!allPass) {
    console.error("❌ EN AZ 1 KAPI DÜŞTÜ. system.mjs anchor'larını gözden geçir.");
    process.exit(1);
  }
  console.log("✅ TÜM 6 KAPI GEÇTİ.");
  process.exit(0);
}

main();
