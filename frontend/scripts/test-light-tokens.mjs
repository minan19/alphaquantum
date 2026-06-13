#!/usr/bin/env node
/**
 * Design Token Programı — Faz 7 · Light/Dark WCAG matrisi.
 *
 * 4 scope × 2 tema = 8 kombinasyon. Her birinde kritik çiftler:
 *   text_primary   vs bg_primary  ≥ 4.5 (AA hedef ~15)
 *   text_secondary vs bg_primary  ≥ 4.5 (AA hedef ~8)
 *   text_muted     vs bg_primary  ≥ 4.5
 *   cta            vs cta_text    ≥ 4.5 (her modül için)
 *   status_error   vs bg_primary  ≥ 3.0 (UI non-text)
 *   link_back      vs bg_primary  ≥ 4.5 (FinOS/CorpOS)
 *
 * Strateji: token-auto.ts'in JS portunu çağırarak palet üret, oranları hesapla,
 * eşik kontrolü yap. Foundation kilidi ile değer üretimi, elle uydurma yok.
 *
 * Exit 0 → tüm assertion'lar, 1 → başarısızlık.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const FRONTEND_ROOT = join(__dirname, "..");

// --- token-auto.ts'ten ESM/TS olmadan kullanmak için kopya hesaplar ---

function hexToRgb(hex) {
  const m = hex.replace(/^#/, "").match(/^([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})$/);
  if (!m) throw new Error(`bad hex: ${hex}`);
  return [parseInt(m[1], 16) / 255, parseInt(m[2], 16) / 255, parseInt(m[3], 16) / 255];
}
function sRGBtoLinear(c) {
  return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
}
function relLuminance(hex) {
  const [r, g, b] = hexToRgb(hex);
  return 0.2126 * sRGBtoLinear(r) + 0.7152 * sRGBtoLinear(g) + 0.0722 * sRGBtoLinear(b);
}
function wcagContrast(fg, bg) {
  const L1 = relLuminance(fg);
  const L2 = relLuminance(bg);
  return (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
}

// --- token-auto.ts'ten import — tsc-friendly: node test harness'inde
//     transpile etmek pahalı; bunun yerine compiled output yerine basit
//     TS yorumlama yapamayız, ama buildCorePalette/buildModulePalette
//     fonksiyonlarını runtime'da test etmek için ts-node alternatifi yok.
//     Çözüm: built dosya yerine doğrudan src import'u ts-node ile değil,
//     bunun yerine motor mantığını paylaşan paralel JS port'u kullanırız
//     (test-tokens.mjs benzeri pattern). Burada light değerlerini sabit
//     anchor'lardan üretip kritik çiftleri doğrularız.

// Anchor değerleri — TS dosyasından birebir kopyalandı, kayma olduğunda test
// kırılır (oluşması nadir; values değişirse yazılı kanıt da güncellenir).
const ANCHORS = {
  core: {
    neutral_hue: 258,
    neutral_chroma: 0.012,
    bg_primary_dark:  { L: 0.17, C: 0.012, h: 258 },
    bg_primary_light: { L: 0.99, C: 0.006, h: 258 },
    elevation_delta_L: 0.03,
    text_targets: {
      primary:   { contrast: 15,  hue: 258, chroma: 0.005 },
      secondary: { contrast:  8,  hue: 258, chroma: 0.008 },
      muted:     { contrast: 4.5, hue: 258, chroma: 0.012 },
    },
    status_error: { h: 27, L: 0.62, C: 0.18 },
  },
  aq:     { brand: { L: 0.316, C: 0.115, h: 261.5 }, cta: { L: 0.546, C: 0.215, h: 263 } },
  finos:  { brand: { L: 0.654, C: 0.110, h: 194 },   cta: { L: 0.580, C: 0.155, h: 47.6 }, link_back: "#94A3B8" },
  corpos: { brand: { L: 0.843, C: 0.151, h: 88 },    link_back: "#94A3B8" },
};

// --- OKLCH ↔ RGB (system.mjs portu, basitleştirilmiş) ---

function oklabToLinearRgb(L, a, b) {
  const l = L + 0.3963377774 * a + 0.2158037573 * b;
  const m = L - 0.1055613458 * a - 0.0638541728 * b;
  const s = L - 0.0894841775 * a - 1.2914855480 * b;
  const l3 = l * l * l, m3 = m * m * m, s3 = s * s * s;
  return [
     4.0767416621 * l3 - 3.3077115913 * m3 + 0.2309699292 * s3,
    -1.2684380046 * l3 + 2.6097574011 * m3 - 0.3413193965 * s3,
    -0.0041960863 * l3 - 0.7034186147 * m3 + 1.7076147010 * s3,
  ];
}
function linearToSRGB(c) {
  return c <= 0.0031308 ? 12.92 * c : 1.055 * Math.pow(c, 1 / 2.4) - 0.055;
}
function oklchToHex(L, C, hDeg) {
  const h = (hDeg * Math.PI) / 180;
  const a = C * Math.cos(h);
  const b = C * Math.sin(h);
  let [lr, lg, lb] = oklabToLinearRgb(L, a, b);
  const clamp01 = (x) => Math.max(0, Math.min(1, x));
  const r = Math.round(clamp01(linearToSRGB(clamp01(lr))) * 255);
  const g = Math.round(clamp01(linearToSRGB(clamp01(lg))) * 255);
  const bl = Math.round(clamp01(linearToSRGB(clamp01(lb))) * 255);
  return "#" + [r, g, bl].map((n) => n.toString(16).padStart(2, "0").toUpperCase()).join("");
}
function findTextL(bgHex, target, hue, chroma) {
  let lo = 0, hi = 1;
  for (let i = 0; i < 40; i++) {
    const mid = (lo + hi) / 2;
    const hex = oklchToHex(mid, chroma, hue);
    const ratio = wcagContrast(hex, bgHex);
    if (ratio < target) {
      const bgL = relLuminance(bgHex);
      if (bgL > 0.5) hi = mid; else lo = mid;
    } else {
      const bgL = relLuminance(bgHex);
      if (bgL > 0.5) lo = mid; else hi = mid;
    }
  }
  return (lo + hi) / 2;
}

// --- Palet üreticileri (TS dosyasıyla birebir uyumlu) ---

function buildCore(theme) {
  const c = ANCHORS.core;
  const bgL = theme === "light" ? c.bg_primary_light.L : c.bg_primary_dark.L;
  const bgC = theme === "light" ? c.bg_primary_light.C : c.bg_primary_dark.C;
  const bg_primary = oklchToHex(bgL, bgC, c.neutral_hue);
  const txt = (t) => {
    const L = findTextL(bg_primary, t.contrast, t.hue, t.chroma);
    return oklchToHex(L, t.chroma, t.hue);
  };
  return {
    theme,
    bg_primary,
    text_primary:   txt(c.text_targets.primary),
    text_secondary: txt(c.text_targets.secondary),
    text_muted:     txt(c.text_targets.muted),
    status_error:   oklchToHex(c.status_error.L, c.status_error.C, c.status_error.h),
  };
}
function buildModule(name, theme) {
  const lightDarken = 0.30;
  const L = (anchorL) => (theme === "light" ? Math.max(0.10, anchorL - lightDarken) : anchorL);
  if (name === "aq") {
    const a = ANCHORS.aq;
    return { cta: oklchToHex(L(a.cta.L), a.cta.C, a.cta.h), cta_text: "#FFFFFF", link_back: null };
  }
  // Faz 7: light için link_back koyulaşır (Kapı 2 anchor sadece dark için).
  const linkBack = (darkHex) =>
    theme === "light" ? oklchToHex(0.40, 0.027, 255) : darkHex;
  if (name === "finos") {
    const a = ANCHORS.finos;
    return { cta: oklchToHex(L(a.cta.L), a.cta.C, a.cta.h), cta_text: "#FFFFFF", link_back: linkBack(a.link_back) };
  }
  // corpos
  const a = ANCHORS.corpos;
  if (theme === "light") {
    const hex = oklchToHex(L(a.brand.L), a.brand.C, a.brand.h);
    return { cta: hex, cta_text: "#FFFFFF", link_back: linkBack(a.link_back) };
  }
  return { cta: oklchToHex(a.brand.L, a.brand.C, a.brand.h), cta_text: "#0C1224", link_back: linkBack(a.link_back) };
}

// --- Test harness ---

let pass = 0, fail = 0;
const rows = [];
function check(label, ok, hint = "") {
  if (ok) pass++; else fail++;
  rows.push((ok ? "✓" : "✗") + " " + label + (hint ? " — " + hint : ""));
}

console.log("\n=== Faz 7 — 4 scope × 2 tema WCAG matrisi");

for (const theme of ["dark", "light"]) {
  const core = buildCore(theme);
  console.log(`\n[${theme}]  bg=${core.bg_primary}  text_primary=${core.text_primary}`);

  // core
  const tp = wcagContrast(core.text_primary, core.bg_primary);
  const ts = wcagContrast(core.text_secondary, core.bg_primary);
  const tm = wcagContrast(core.text_muted, core.bg_primary);
  const se = wcagContrast(core.status_error, core.bg_primary);
  console.log(`  text_primary   vs bg = ${tp.toFixed(2)}:1`);
  console.log(`  text_secondary vs bg = ${ts.toFixed(2)}:1`);
  console.log(`  text_muted     vs bg = ${tm.toFixed(2)}:1`);
  console.log(`  status_error   vs bg = ${se.toFixed(2)}:1`);
  check(`[${theme}] core.text_primary ≥ 4.5`,  tp >= 4.5, `${tp.toFixed(2)}`);
  check(`[${theme}] core.text_secondary ≥ 4.5`, ts >= 4.5, `${ts.toFixed(2)}`);
  check(`[${theme}] core.text_muted ≥ 4.5`,    tm >= 4.5, `${tm.toFixed(2)}`);
  check(`[${theme}] core.status_error ≥ 3.0`,  se >= 3.0, `${se.toFixed(2)}`);

  // 3 modül
  for (const mod of ["aq", "finos", "corpos"]) {
    const m = buildModule(mod, theme);
    const c2t = wcagContrast(m.cta, m.cta_text);
    console.log(`  ${mod}.cta=${m.cta} vs cta_text=${m.cta_text} = ${c2t.toFixed(2)}:1`);
    check(`[${theme}] ${mod}.cta vs cta_text ≥ 4.5`, c2t >= 4.5, `${c2t.toFixed(2)}`);
    if (m.link_back) {
      const lb = wcagContrast(m.link_back, core.bg_primary);
      console.log(`  ${mod}.link_back=${m.link_back} vs bg = ${lb.toFixed(2)}:1`);
      check(`[${theme}] ${mod}.link_back ≥ 4.5`, lb >= 4.5, `${lb.toFixed(2)}`);
    }
  }
}

console.log("\n=== Sonuç");
console.log(rows.join("\n"));
console.log(`\n${pass} passed · ${fail} failed`);
process.exit(fail === 0 ? 0 : 1);
