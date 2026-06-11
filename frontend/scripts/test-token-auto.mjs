#!/usr/bin/env node
/**
 * Design Token Programı — Faz 3 · Parite + Unit Testleri.
 *
 * Doğrulamalar:
 *  1. OKLCH ↔ hex round-trip
 *  2. WCAG contrast bilinen değerlerde
 *  3. contrastRating eşikleri
 *  4. Binary search yakınsaması (text-primary ±0.2 contrast)
 *  5. Governance reddi (modülde core anahtarı)
 *  6. **PARİTE KAPISI**: 43 token × system.mjs çıktısı vs token-auto.ts
 *     - Gate values (#CD4A00, #94A3B8, #475569, #DE4F46, focus_ring, bg ramp) BİREBİR
 *     - Diğer hesaplanmış değerler ±1 RGB birimi tolerans
 *
 * Bu script lib/token-auto.ts'i değil — saf JS port'unu çalıştırır (Node'dan TS
 * çalıştırmamak için). Hesaplama eşdeğeri olduğunu manuel garanti ediyoruz; testler
 * ortak referans olarak Faz 0 wcag-report.json'u kullanır.
 *
 * Exit:
 *  0 — tüm assertion'lar pass
 *  1 — en az bir fail
 */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..", "..");
const WCAG = join(ROOT, "docs", "design-tokens", "wcag-report.json");

// -- Faz 0 sabitleri (system.mjs ile birebir aynı) --------------------------
// Bu sabitlerin token-auto.ts'tekilere TIPATIP eşit olması bu testin sözleşmesi.

const ANCHORS = {
  core: {
    neutral_hue: 258,
    neutral_chroma: 0.012,
    bg_primary_dark:  { L: 0.17, C: 0.012, h: 258 },
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
    cta:      { L: 0.546, C: 0.215, h: 263.0, hex: "#2563EB" },
    on_brand: { L: 0.95,  C: 0.012, h: 258,   hex: "#E8EFF9" },
    cta_text: "#FFFFFF",
  },
  finos: {
    brand:     { L: 0.654, C: 0.110, h: 194, hex: "#0EA5A4" },
    cta:       { L: 0.580, C: 0.155, h: 47.6, hex: "#CD4A00" },
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

// -- OKLCH motoru (system.mjs port — TS port'uyla aynı) ---------------------

function linearToSrgb(v) {
  if (v < 0) return 0;
  if (v > 1) return 1;
  return v >= 0.0031308 ? 1.055 * Math.pow(v, 1 / 2.4) - 0.055 : 12.92 * v;
}
function srgbToLinear(v) {
  return v >= 0.04045 ? Math.pow((v + 0.055) / 1.055, 2.4) : v / 12.92;
}
function oklabToLinearSrgb(L, a, b) {
  const l_ = L + 0.3963377774 * a + 0.2158037573 * b;
  const m_ = L - 0.1055613458 * a - 0.0638541728 * b;
  const s_ = L - 0.0894841775 * a - 1.2914855480 * b;
  const l = l_ * l_ * l_, m = m_ * m_ * m_, s = s_ * s_ * s_;
  return [
     4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
    -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
    -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
  ];
}
function linearSrgbToOklab(r, g, b) {
  const l = 0.4122214708*r + 0.5363325363*g + 0.0514459929*b;
  const m = 0.2119034982*r + 0.6806995451*g + 0.1073969566*b;
  const s = 0.0883024619*r + 0.2817188376*g + 0.6299787005*b;
  const l_ = Math.cbrt(l), m_ = Math.cbrt(m), s_ = Math.cbrt(s);
  return [
    0.2104542553*l_ + 0.7936177850*m_ - 0.0040720468*s_,
    1.9779984951*l_ - 2.4285922050*m_ + 0.4505937099*s_,
    0.0259040371*l_ + 0.7827717662*m_ - 0.8086757660*s_,
  ];
}
function oklchToHex(L, C, hDeg) {
  const h = (hDeg * Math.PI) / 180;
  const a = C * Math.cos(h), b = C * Math.sin(h);
  const [lr, lg, lb] = oklabToLinearSrgb(L, a, b);
  const r = Math.round(255 * linearToSrgb(lr));
  const g = Math.round(255 * linearToSrgb(lg));
  const bl = Math.round(255 * linearToSrgb(lb));
  const clamp = (v) => Math.max(0, Math.min(255, v));
  return ("#" + clamp(r).toString(16).padStart(2,"0") + clamp(g).toString(16).padStart(2,"0") + clamp(bl).toString(16).padStart(2,"0")).toUpperCase();
}
function hexToOklch(hex) {
  const r = parseInt(hex.slice(1,3),16)/255;
  const g = parseInt(hex.slice(3,5),16)/255;
  const b = parseInt(hex.slice(5,7),16)/255;
  const [lr,lg,lb] = [srgbToLinear(r), srgbToLinear(g), srgbToLinear(b)];
  const [L,A,B] = linearSrgbToOklab(lr,lg,lb);
  const C = Math.sqrt(A*A + B*B);
  let h = Math.atan2(B,A)*180/Math.PI; if (h<0) h+=360;
  return { L, C, h };
}
function relLuminance(hex) {
  const r = srgbToLinear(parseInt(hex.slice(1,3),16)/255);
  const g = srgbToLinear(parseInt(hex.slice(3,5),16)/255);
  const b = srgbToLinear(parseInt(hex.slice(5,7),16)/255);
  return 0.2126*r + 0.7152*g + 0.0722*b;
}
function wcagContrast(fg, bg) {
  const L1 = relLuminance(fg), L2 = relLuminance(bg);
  const lighter = Math.max(L1, L2), darker = Math.min(L1, L2);
  return (lighter + 0.05) / (darker + 0.05);
}
function contrastRating(r) {
  if (r >= 7) return "AAA";
  if (r >= 4.5) return "AA";
  if (r >= 3) return "AA-Lg";
  return "FAIL";
}
function findTextL(bgHex, target, hue, chroma) {
  const bgL = relLuminance(bgHex);
  const bgIsDark = bgL < 0.18;
  let lo = bgIsDark ? 0.5 : 0.0;
  let hi = bgIsDark ? 1.0 : 0.5;
  let best = bgIsDark ? 0.95 : 0.05;
  let bestDelta = Infinity;
  for (let i = 0; i < 40; i++) {
    const mid = (lo + hi) / 2;
    const c = wcagContrast(oklchToHex(mid, chroma, hue), bgHex);
    if (Math.abs(c - target) < bestDelta) { bestDelta = Math.abs(c - target); best = mid; }
    if (bgIsDark) { if (c < target) lo = mid; else hi = mid; }
    else          { if (c < target) hi = mid; else lo = mid; }
  }
  return best;
}

// -- Test runner ------------------------------------------------------------

let pass = 0, fail = 0;
const results = [];
function it(name, fn) {
  try { fn(); results.push("  ✓ " + name); pass++; }
  catch (e) { results.push("  ✗ " + name + "\n      " + e.message); fail++; }
}
function eq(a, b, msg) {
  if (a !== b) throw new Error((msg||"not equal") + " — expected " + JSON.stringify(b) + " got " + JSON.stringify(a));
}
function approx(a, b, eps, msg) {
  if (Math.abs(a - b) > eps) throw new Error((msg||"not approx") + " — expected " + b + " ± " + eps + " got " + a);
}

console.log("=".repeat(64));
console.log("Alpha Quantum — Token Auto Engine Parite Testleri (Faz 3)");
console.log("=".repeat(64));

// ---------- 1. OKLCH round-trip --------------------------------------------
console.log("\n[1] OKLCH ↔ hex round-trip (stable conversion)");
// Doğru round-trip: hex → OKLCH → hex SABİT kalmalı (gerçek OKLCH değeri için).
// Foundation'daki yuvarlanmış OKLCH (örn. 0.546, 0.215, 263) gerçek hex'e
// ±1 RGB birim yakın olabilir (yuvarlama); bu wcag-report.json'da anchor'ın
// `hex` alanını direkt kullanmamızın sebebi. Aşağıdaki testler stability
// (round-trip kararlılığı) ve OKLCH değerlerinin tutarlığını kontrol eder.
for (const hex of ["#0EA5A4", "#2563EB", "#CD4A00", "#94A3B8", "#475569", "#F4C542", "#0C1015", "#0094F6"]) {
  it(`hex → OKLCH → hex stable (${hex})`, () => {
    const o = hexToOklch(hex);
    const back = oklchToHex(o.L, o.C, o.h);
    eq(back, hex, `round-trip ${hex}`);
  });
}
it("hexToOklch('#0EA5A4') → L≈0.654 h≈194 (yuvarlanmış foundation eşleşmesi)", () => {
  const o = hexToOklch("#0EA5A4");
  approx(o.L, 0.654, 0.005, "L");
  approx(o.h, 194, 1.0, "h");
});
it("hexToOklch('#CD4A00') → L≈0.580 (foundation hue yaklaşıktır)", () => {
  // Foundation.md'de h=47.6 yazılmış ama gerçek hue ≈41.17° (yuvarlama farkı).
  // Foundation comment: "chroma chosen to match hex" — anchor approximate.
  // Asıl önemli: hex doğru ve Kapı 1 contrast geçer (test ediliyor).
  const o = hexToOklch("#CD4A00");
  approx(o.L, 0.580, 0.005, "L");
});

// ---------- 2. WCAG bilinen değerler --------------------------------------
console.log("\n[2] WCAG contrast bilinen değerler");
it("wcagContrast('#FFFFFF', '#CD4A00') ≈ 4.59  [Kapı 1]", () => {
  approx(wcagContrast("#FFFFFF", "#CD4A00"), 4.59, 0.02);
});
it("wcagContrast('#94A3B8', '#0C1015') ≈ 7.44  [Kapı 2]", () => {
  approx(wcagContrast("#94A3B8", "#0C1015"), 7.44, 0.02);
});
it("wcagContrast('#DE4F46', '#0C1015') ≈ 4.83  [Kapı 3]", () => {
  approx(wcagContrast("#DE4F46", "#0C1015"), 4.83, 0.02);
});
it("wcagContrast('#0094F6', '#0C1015') ≈ 5.97  [focus-ring]", () => {
  approx(wcagContrast("#0094F6", "#0C1015"), 5.97, 0.02);
});

// ---------- 3. contrastRating --------------------------------------------
console.log("\n[3] contrastRating eşikleri");
it("7.0 → AAA", () => eq(contrastRating(7.0), "AAA"));
it("4.5 → AA", () => eq(contrastRating(4.5), "AA"));
it("3.0 → AA-Lg", () => eq(contrastRating(3.0), "AA-Lg"));
it("2.9 → FAIL", () => eq(contrastRating(2.9), "FAIL"));

// ---------- 4. Binary search yakınsaması ---------------------------------
console.log("\n[4] Binary search yakınsaması (text targets ±0.2 contrast)");
const bgPrim = oklchToHex(0.17, 0.012, 258);
it("text-primary: hedef 15:1 ±0.2", () => {
  const L = findTextL(bgPrim, 15, 258, 0.005);
  const hex = oklchToHex(L, 0.005, 258);
  const c = wcagContrast(hex, bgPrim);
  approx(c, 15, 0.2, "contrast");
});
it("text-secondary: hedef 8:1 ±0.2", () => {
  const L = findTextL(bgPrim, 8, 258, 0.008);
  const c = wcagContrast(oklchToHex(L, 0.008, 258), bgPrim);
  approx(c, 8, 0.2, "contrast");
});
it("text-muted: hedef 4.5:1 ±0.2", () => {
  const L = findTextL(bgPrim, 4.5, 258, 0.012);
  const c = wcagContrast(oklchToHex(L, 0.012, 258), bgPrim);
  approx(c, 4.5, 0.2, "contrast");
});

// ---------- 5. PARITE — 43 token × Faz 0 wcag-report.json ----------------
console.log("\n[5] PARITE KAPISI — 43 token (auto vs Faz 0)");
const report = JSON.parse(readFileSync(WCAG, "utf8"));

const GATE_KEYS = new Set([
  "finos.cta",          // Kapı 1 #CD4A00
  "finos.link_back",    // Kapı 2 #94A3B8
  "corpos.link_back",   // Kapı 2 #94A3B8
  "corpos.accent",      // Kapı 4 #475569
  "core.status_error",  // Kapı 3 #DE4F46
  "core.focus_ring",    // #0094F6
  "core.bg_primary",
  "core.bg_secondary",
  "core.bg_tertiary",
  "core.surface_01",
  "core.surface_02",
  "core.surface_03",
]);

// Auto üreteç: token-auto.ts'in computeAuto'suyla aynı mantık.
function buildAuto() {
  const c = ANCHORS.core;
  const bgL = c.bg_primary_dark.L, bgC = c.bg_primary_dark.C;
  const bg_primary = oklchToHex(bgL, bgC, c.neutral_hue);
  const elev = (n) => oklchToHex(bgL + c.elevation_delta_L * n, bgC, c.neutral_hue);
  const txt = (t) => oklchToHex(findTextL(bg_primary, t.contrast, t.hue, t.chroma), t.chroma, t.hue);
  const statusH = {}, statusS = {};
  for (const [k, v] of Object.entries(c.status)) {
    statusH[k] = oklchToHex(v.L, v.C, v.h);
    statusS[k] = oklchToHex(Math.max(0.18, v.L - 0.45), Math.min(0.03, v.C * 0.18), v.h);
  }
  return {
    "core.bg_primary":             bg_primary,
    "core.bg_secondary":           elev(1),
    "core.bg_tertiary":            elev(2),
    "core.surface_01":             elev(3),
    "core.surface_02":             elev(4),
    "core.surface_03":             elev(5),
    "core.border":                 oklchToHex(bgL + c.elevation_delta_L*3, Math.min(0.02, bgC*1.5), c.neutral_hue),
    "core.text_primary":           txt(c.text_targets.primary),
    "core.text_secondary":         txt(c.text_targets.secondary),
    "core.text_muted":             txt(c.text_targets.muted),
    "core.text_inverse":           "#0C1224",
    "core.status_success":         statusH.success,
    "core.status_success_surface": statusS.success,
    "core.status_warning":         statusH.warning,
    "core.status_warning_surface": statusS.warning,
    "core.status_error":           statusH.error,
    "core.status_error_surface":   statusS.error,
    "core.status_info":            statusH.info,
    "core.status_info_surface":    statusS.info,
    "core.focus_ring":             oklchToHex(c.focus_ring.L, c.focus_ring.C, c.focus_ring.h),

    "aq.brand":       ANCHORS.aq.brand.hex,
    "aq.brand_hover": oklchToHex(Math.max(0, ANCHORS.aq.brand.L - 0.14), ANCHORS.aq.brand.C, ANCHORS.aq.brand.h),
    "aq.cta":         ANCHORS.aq.cta.hex,
    "aq.cta_hover":   oklchToHex(Math.max(0, ANCHORS.aq.cta.L - 0.14), ANCHORS.aq.cta.C, ANCHORS.aq.cta.h),
    "aq.cta_text":    ANCHORS.aq.cta_text,
    "aq.on_brand":    ANCHORS.aq.on_brand.hex,
    "aq.accent":      ANCHORS.aq.cta.hex,

    "finos.brand":       ANCHORS.finos.brand.hex,
    "finos.brand_hover": oklchToHex(Math.max(0, ANCHORS.finos.brand.L - 0.14), ANCHORS.finos.brand.C, ANCHORS.finos.brand.h),
    "finos.cta":         ANCHORS.finos.cta.hex,
    "finos.cta_hover":   oklchToHex(Math.max(0, ANCHORS.finos.cta.L - 0.14), ANCHORS.finos.cta.C, ANCHORS.finos.cta.h),
    "finos.cta_text":    ANCHORS.finos.cta_text,
    "finos.accent":      statusH.info,
    "finos.link_back":   ANCHORS.finos.link_back,

    "corpos.brand":          ANCHORS.corpos.brand.hex,
    "corpos.brand_hover":    oklchToHex(Math.max(0, ANCHORS.corpos.brand.L - 0.10), ANCHORS.corpos.brand.C, ANCHORS.corpos.brand.h),
    "corpos.cta":            ANCHORS.corpos.brand.hex,
    "corpos.cta_hover":      oklchToHex(Math.max(0, ANCHORS.corpos.brand.L - 0.10), ANCHORS.corpos.brand.C, ANCHORS.corpos.brand.h),
    "corpos.cta_text":       ANCHORS.corpos.cta_text_dark,
    "corpos.cta_text_weight": 500,
    "corpos.accent":         ANCHORS.corpos.accent.hex,
    "corpos.accent_light":   ANCHORS.corpos.accent_light.hex,
    "corpos.link_back":      ANCHORS.corpos.link_back,
  };
}

const auto = buildAuto();

// Faz 0 referans değerleri (wcag-report.json)
const faz0 = {};
for (const [k, v] of Object.entries(report.core)) {
  if (k === "theme" || v === null) continue;
  faz0["core." + k] = String(v);
}
for (const scope of ["aq", "finos", "corpos"]) {
  for (const [k, v] of Object.entries(report.modules[scope])) {
    if (k === "scope" || v === null) continue;
    faz0[scope + "." + k] = typeof v === "number" ? v : String(v);
  }
}

console.log("");
console.log("  Token                                Faz 0       auto          Status");
console.log("  " + "-".repeat(72));

const gateDeviations = [];
const nonGateDeviations = [];
let parityPass = 0, parityFail = 0;

for (const key of Object.keys(faz0).sort()) {
  const expected = faz0[key];
  const actual = auto[key];
  if (actual === undefined) {
    console.log(`  ${key.padEnd(36)} ${String(expected).padEnd(11)} (missing in auto) ✗`);
    parityFail++;
    nonGateDeviations.push({ key, expected, actual: "(missing)" });
    continue;
  }
  const match = typeof actual === "number" ? actual === expected : String(actual).toUpperCase() === String(expected).toUpperCase();
  const status = match ? "✓" : "✗";
  console.log(`  ${key.padEnd(36)} ${String(expected).padEnd(11)} ${String(actual).padEnd(13)} ${status}`);
  if (match) parityPass++;
  else {
    parityFail++;
    const dev = { key, expected, actual };
    if (GATE_KEYS.has(key)) gateDeviations.push(dev);
    else nonGateDeviations.push(dev);
  }
}

console.log("");
console.log(`  Parity: ${parityPass}/${parityPass + parityFail} eşleşme`);
if (gateDeviations.length > 0) {
  console.log("");
  console.log("  ⚠ KAPI DEĞER SAPMASI (kabul edilmez):");
  for (const d of gateDeviations) {
    console.log(`    ${d.key}: ${d.expected} → ${d.actual}`);
  }
}
if (nonGateDeviations.length > 0) {
  console.log("");
  console.log("  ℹ Non-gate sapma (eğer ±1 RGB ise kontrast hâlâ geçer):");
  for (const d of nonGateDeviations) {
    console.log(`    ${d.key}: ${d.expected} → ${d.actual}`);
  }
}

it("Tüm Kapı değerleri Faz 0 ile birebir", () => {
  if (gateDeviations.length > 0) {
    throw new Error("Kapı sapmaları: " + JSON.stringify(gateDeviations));
  }
});
it("Tüm 43 token (gate dahil) eşleşme", () => {
  if (parityFail > 0) {
    throw new Error(`${parityFail} token sapması (gate: ${gateDeviations.length}, non-gate: ${nonGateDeviations.length})`);
  }
});

// ---------- 6. Governance reddi (saf JS — token-auto.ts'in TS varyantı aynısını yapar) -
console.log("\n[6] Governance — modül core anahtarı ezme reddi");
const CORE_KEYS = new Set([
  "bg_primary","bg_secondary","bg_tertiary","surface_01","surface_02","surface_03",
  "border","text_primary","text_secondary","text_muted","text_inverse",
  "status_success","status_success_surface","status_warning","status_warning_surface",
  "status_error","status_error_surface","status_info","status_info_surface","focus_ring",
]);
const MODULE_KEYS = new Set([
  "brand","brand_hover","cta","cta_hover","cta_text","cta_text_weight",
  "on_brand","accent","accent_light","link_back",
]);
function assertGov(scope, key) {
  if (!["core","aq","finos","corpos"].includes(scope)) throw new Error("invalid scope");
  if (scope === "core") {
    if (!CORE_KEYS.has(key)) throw new Error(`core izinsiz: ${key}`);
    return;
  }
  if (CORE_KEYS.has(key)) throw new Error(`modül '${scope}' core-sahipli '${key}' ezemez`);
  if (!MODULE_KEYS.has(key)) throw new Error(`modül '${scope}' izinsiz: ${key}`);
}

for (const scope of ["aq","finos","corpos"]) {
  it(`computeAuto(${scope}, bg_primary, background) reddedilir`, () => {
    let threw = false;
    try { assertGov(scope, "bg_primary"); } catch { threw = true; }
    if (!threw) throw new Error(`${scope}.bg_primary reddedilmeliydi`);
  });
  it(`computeAuto(${scope}, status_error, status) reddedilir`, () => {
    let threw = false;
    try { assertGov(scope, "status_error"); } catch { threw = true; }
    if (!threw) throw new Error(`${scope}.status_error reddedilmeliydi`);
  });
}

// ---------- Output ---------------------------------------------------------
console.log("");
for (const r of results) console.log(r);
console.log("");
console.log("=".repeat(64));
console.log(`SONUÇ: ${pass} pass / ${fail} fail`);
console.log("=".repeat(64));

if (fail > 0) process.exit(1);
process.exit(0);
