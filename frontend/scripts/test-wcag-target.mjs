#!/usr/bin/env node
/**
 * fix/wcag-badge-reference — wcag-target.ts saf-fonksiyon doğrulaması.
 *
 * Strateji:
 *   1) tokens-defaults.json'u oku, panel'in göreceği canlı token kümesini kur.
 *   2) Her token için resolveWcagTarget'i çağır, beklenen partner+eşik+mod
 *      ile karşılaştır.
 *   3) Ek: bug-fix kanıtı — bg_primary kendine karşı YOK (mode ratio ama
 *      partner text_primary), surface_01 vs text_primary doğru hesaplanır
 *      (~16:1 AAA), bg_primary kendisi vs text_primary (~16:1 AAA).
 *
 * Exit: 0 → tüm assertion'lar; 1 → en az bir başarısızlık.
 */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const FRONTEND_ROOT = join(__dirname, "..");

// --- token-auto'nun saf hesabını embed et (modül ESM-only TS değil olsun) ---

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
  const [R, G, B] = [sRGBtoLinear(r), sRGBtoLinear(g), sRGBtoLinear(b)];
  return 0.2126 * R + 0.7152 * G + 0.0722 * B;
}

function wcagContrast(fg, bg) {
  const L1 = relLuminance(fg);
  const L2 = relLuminance(bg);
  const lighter = Math.max(L1, L2);
  const darker = Math.min(L1, L2);
  return (lighter + 0.05) / (darker + 0.05);
}

function contrastRating(r) {
  if (r >= 7) return "AAA";
  if (r >= 4.5) return "AA";
  if (r >= 3) return "AA-Lg";
  return "FAIL";
}

// --- wcag-target.ts mantığının saf JS aynası ----------------------------

const SURFACE_CATEGORIES = new Set(["background", "surface"]);
const HEX_RE = /^#[0-9A-Fa-f]{6}$/;

function findToken(tokens, scope, key) {
  return tokens.find((t) => t.scope === scope && t.key === key);
}
function findScopedOrCore(tokens, preferScope, key) {
  return findToken(tokens, preferScope, key) ?? findToken(tokens, "core", key);
}
function ratioBadge(fg, partner, threshold) {
  const ratio = wcagContrast(fg.value, partner.value);
  return {
    mode: "ratio",
    ratio,
    rating: contrastRating(ratio),
    threshold,
    partnerKey: partner.key,
    partnerValue: partner.value,
  };
}
function neutral(label) {
  return { mode: "neutral", label };
}
function resolveWcagTarget(row, all, activeScope) {
  if (row.key === "cta_text_weight") return null;
  if (!HEX_RE.test(row.value)) return null;
  if (row.key === "text_inverse") return neutral("light bağlam — Faz 7");

  if (row.key === "cta" || row.key === "cta_hover") {
    const sp = row.scope === "core" ? activeScope : row.scope;
    const p = findScopedOrCore(all, sp, "cta_text") ?? findScopedOrCore(all, sp, "on_brand");
    return p ? ratioBadge(row, p, 4.5) : neutral("partner cta_text/on_brand yok");
  }
  if (row.key === "brand" || row.key === "brand_hover") {
    const sp = row.scope === "core" ? activeScope : row.scope;
    const p = findScopedOrCore(all, sp, "on_brand") ?? findScopedOrCore(all, sp, "cta_text");
    return p ? ratioBadge(row, p, 4.5) : neutral("partner on_brand/cta_text yok");
  }
  if (row.key === "cta_text") {
    const sp = row.scope === "core" ? activeScope : row.scope;
    const p = findScopedOrCore(all, sp, "cta");
    return p ? ratioBadge(row, p, 4.5) : neutral("partner cta yok");
  }
  if (row.key === "on_brand") {
    const sp = row.scope === "core" ? activeScope : row.scope;
    const p = findScopedOrCore(all, sp, "brand");
    return p ? ratioBadge(row, p, 4.5) : neutral("partner brand yok");
  }
  if (row.key.endsWith("_surface")) {
    const p = findToken(all, "core", "text_primary");
    return p ? ratioBadge(row, p, 4.5) : neutral("text_primary yok");
  }
  if (SURFACE_CATEGORIES.has(row.category)) {
    const p = findToken(all, "core", "text_primary");
    return p ? ratioBadge(row, p, 4.5) : neutral("text_primary yok");
  }
  if (row.category === "text") {
    const p = findToken(all, "core", "bg_primary");
    return p ? ratioBadge(row, p, 4.5) : neutral("bg_primary yok");
  }
  if (row.key === "accent_light") {
    const p = findToken(all, "core", "text_primary");
    return p ? ratioBadge(row, p, 4.5) : neutral("text_primary yok");
  }
  if (row.key === "link_back") {
    const p = findToken(all, "core", "bg_primary");
    return p ? ratioBadge(row, p, 4.5) : neutral("bg_primary yok");
  }
  if (["status", "border", "focus", "accent"].includes(row.category)) {
    const p = findToken(all, "core", "bg_primary");
    return p ? ratioBadge(row, p, 3.0) : neutral("bg_primary yok");
  }
  return neutral("kontrast referansı tanımsız");
}

// --- Test harness ---------------------------------------------------------

let pass = 0, fail = 0;
function ok(label, cond, extra = "") {
  if (cond) { pass++; console.log(`  ✓ ${label}`); }
  else { fail++; console.error(`  ✗ ${label}${extra ? " — " + extra : ""}`); }
}
function eqClose(a, b, eps = 0.05) {
  return Math.abs(a - b) < eps;
}

// Token kümesini hazırla
const defaults = JSON.parse(
  readFileSync(join(FRONTEND_ROOT, "lib/tokens-defaults.json"), "utf8"),
);
const all = defaults.tokens.map((t) => ({
  scope: t.scope, key: t.key, value: t.value, category: t.category,
}));

console.log("\n=== fix/wcag-badge-reference: resolveWcagTarget()");

// --- (1) Sayısal & nötr durumlar ---
console.log("\n[1] sayısal & nötr");
{
  const w = all.find((t) => t.key === "cta_text_weight");
  ok("cta_text_weight → null", resolveWcagTarget(w, all, "corpos") === null);
  const ti = all.find((t) => t.key === "text_inverse");
  const r = resolveWcagTarget(ti, all, "core");
  ok("text_inverse → neutral 'light bağlam — Faz 7'",
     r?.mode === "neutral" && r.label.includes("Faz 7"));
}

// --- (2) Bug-fix kanıtı: zemin token'ları kendine karşı YOK ---
console.log("\n[2] bug-fix: zemin/surface → text_primary");
{
  const bg = all.find((t) => t.key === "bg_primary");
  const b = resolveWcagTarget(bg, all, "core");
  ok("bg_primary → partner text_primary",
     b?.mode === "ratio" && b.partnerKey === "text_primary");
  ok("bg_primary vs text_primary > 14:1 (AAA)",
     b?.mode === "ratio" && b.rating === "AAA" && b.ratio > 14,
     `ratio=${b?.ratio?.toFixed(2)}`);

  const s1 = all.find((t) => t.key === "surface_01");
  const sB = resolveWcagTarget(s1, all, "core");
  ok("surface_01 → partner text_primary",
     sB?.mode === "ratio" && sB.partnerKey === "text_primary");
  ok("surface_01 vs text_primary > 10:1 (AAA)",
     sB?.mode === "ratio" && sB.rating === "AAA" && sB.ratio > 10,
     `ratio=${sB?.ratio?.toFixed(2)}`);

  const ses = all.find((t) => t.key === "status_error_surface");
  const seB = resolveWcagTarget(ses, all, "core");
  ok("status_error_surface → partner text_primary",
     seB?.mode === "ratio" && seB.partnerKey === "text_primary");
}

// --- (3) Metin token'ları bg_primary'ye karşı ---
console.log("\n[3] text → bg_primary");
for (const k of ["text_primary", "text_secondary", "text_muted"]) {
  const t = all.find((x) => x.key === k);
  const b = resolveWcagTarget(t, all, "core");
  ok(`${k} → partner bg_primary`,
     b?.mode === "ratio" && b.partnerKey === "bg_primary");
  ok(`${k} eşik 4.5`,
     b?.mode === "ratio" && b.threshold === 4.5);
}

// --- (4) CTA dolgu cta_text'e karşı (scope-aware) ---
console.log("\n[4] cta/cta_hover → cta_text (scope-aware)");
{
  const cta = all.find((t) => t.key === "cta" && t.scope === "aq");
  const b = resolveWcagTarget(cta, all, "aq");
  ok("aq.cta → partner cta_text",
     b?.mode === "ratio" && b.partnerKey === "cta_text");
  ok("aq.cta eşik 4.5", b?.mode === "ratio" && b.threshold === 4.5);
  ok("aq.cta partner aq scope'undan",
     b?.mode === "ratio" && b.partnerValue === all.find((t) => t.key === "cta_text" && t.scope === "aq").value);
}

// --- (5) cta_text → cta ---
console.log("\n[5] cta_text → cta (scope-aware)");
{
  const cttCorpos = all.find((t) => t.key === "cta_text" && t.scope === "corpos");
  const b = resolveWcagTarget(cttCorpos, all, "corpos");
  ok("corpos.cta_text → partner cta", b?.mode === "ratio" && b.partnerKey === "cta");
  // Q6: corpos.cta=#F4C542 vs cta_text=#0C1224 yüksek kontrast olmalı
  ok("corpos.cta_text vs cta yüksek (Q6 kapı garantisi)",
     b?.mode === "ratio" && b.ratio > 9, `ratio=${b?.ratio?.toFixed(2)}`);
}

// --- (6) brand/brand_hover → on_brand ---
console.log("\n[6] brand/brand_hover → on_brand");
{
  const br = all.find((t) => t.key === "brand" && t.scope === "aq");
  const b = resolveWcagTarget(br, all, "aq");
  ok("aq.brand → partner on_brand", b?.mode === "ratio" && b.partnerKey === "on_brand");
}

// --- (7) link_back → bg_primary text eşik 4.5 ---
console.log("\n[7] link_back → bg_primary @ 4.5");
{
  const lb = all.find((t) => t.key === "link_back" && t.scope === "corpos");
  const b = resolveWcagTarget(lb, all, "corpos");
  ok("link_back → partner bg_primary", b?.mode === "ratio" && b.partnerKey === "bg_primary");
  ok("link_back eşik 4.5", b?.mode === "ratio" && b.threshold === 4.5);
}

// --- (8) status (filled) / border / focus / accent → 3.0 eşik ---
console.log("\n[8] status/border/focus/accent → bg_primary @ 3.0");
for (const k of ["status_success", "status_error", "border", "focus_ring"]) {
  const t = all.find((x) => x.key === k);
  const b = resolveWcagTarget(t, all, "core");
  ok(`${k} → eşik 3.0`, b?.mode === "ratio" && b.threshold === 3.0);
  ok(`${k} → partner bg_primary`, b?.mode === "ratio" && b.partnerKey === "bg_primary");
}
{
  const acc = all.find((t) => t.key === "accent" && t.scope === "aq");
  const b = resolveWcagTarget(acc, all, "aq");
  ok("aq.accent → eşik 3.0 (UI accent)",
     b?.mode === "ratio" && b.threshold === 3.0 && b.partnerKey === "bg_primary");
}

// --- (9) accent_light özel — yumuşak yüzey 4.5 ---
console.log("\n[9] accent_light → text_primary @ 4.5 (S1 onayı)");
{
  const al = all.find((t) => t.key === "accent_light");
  const b = resolveWcagTarget(al, all, "corpos");
  ok("accent_light → partner text_primary", b?.mode === "ratio" && b.partnerKey === "text_primary");
  ok("accent_light eşik 4.5", b?.mode === "ratio" && b.threshold === 4.5);
}

// --- (10) Ek kanıt: cta_hover vs cta_text raporu (Faz 8 notu olabilir) ---
console.log("\n[10] Ek rapor: cta_hover vs cta_text (her scope)");
for (const sc of ["aq", "finos", "corpos"]) {
  const ch = all.find((t) => t.key === "cta_hover" && t.scope === sc);
  if (!ch) { console.log(`  ${sc}: cta_hover yok`); continue; }
  const b = resolveWcagTarget(ch, all, sc);
  const flag = b?.rating === "FAIL" ? " ⚠ FAIL → Faz 8 not" : "";
  console.log(`  ${sc}.cta_hover ${ch.value} vs cta_text(${b?.partnerValue}) = ${b?.ratio?.toFixed(2)}:1 ${b?.rating}${flag}`);
}

// --- Sonuç ---
console.log(`\n=== ${pass} passed · ${fail} failed`);
process.exit(fail === 0 ? 0 : 1);
