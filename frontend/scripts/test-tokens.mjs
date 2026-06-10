#!/usr/bin/env node
/**
 * Design Token Programı — Faz 1 · Frontend doğrulama scripti.
 *
 * `lib/tokens.ts` ile aynı governance + resolve mantığını çalıştırır,
 * `tokens-defaults.json`'u `docs/design-tokens/wcag-report.json` ile karşılaştırır.
 *
 * Yürütme:
 *   node frontend/scripts/test-tokens.mjs
 *
 * Exit:
 *   0  — tüm assertion'lar geçti
 *   1  — en az bir assertion düştü
 */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..", "..");
const WCAG = join(ROOT, "docs", "design-tokens", "wcag-report.json");
const DEFAULTS = join(ROOT, "frontend", "lib", "tokens-defaults.json");

const wcag = JSON.parse(readFileSync(WCAG, "utf8"));
const defaults = JSON.parse(readFileSync(DEFAULTS, "utf8"));

// ---- Governance whitelist (lib/tokens.ts ile birebir) ----
const CORE_ALLOWED_KEYS = new Set([
  "bg_primary", "bg_secondary", "bg_tertiary",
  "surface_01", "surface_02", "surface_03",
  "border",
  "text_primary", "text_secondary", "text_muted", "text_inverse",
  "status_success", "status_success_surface",
  "status_warning", "status_warning_surface",
  "status_error", "status_error_surface",
  "status_info", "status_info_surface",
  "focus_ring",
]);
const MODULE_ALLOWED_KEYS = new Set([
  "brand", "brand_hover",
  "cta", "cta_hover", "cta_text", "cta_text_weight",
  "on_brand",
  "accent", "accent_light",
  "link_back",
]);
const VALID_SCOPES = ["core", "aq", "finos", "corpos"];

function assertGovernance(scope, key) {
  if (!VALID_SCOPES.includes(scope)) {
    throw new Error(`invalid scope: ${scope}`);
  }
  if (scope === "core") {
    if (!CORE_ALLOWED_KEYS.has(key)) {
      throw new Error(`core core'da izinsiz anahtar: ${key}`);
    }
    return;
  }
  if (CORE_ALLOWED_KEYS.has(key)) {
    throw new Error(`Modül '${scope}' core-sahipli anahtar '${key}' ezemez`);
  }
  if (!MODULE_ALLOWED_KEYS.has(key)) {
    throw new Error(`Modül '${scope}' için izinsiz anahtar: ${key}`);
  }
}

function resolveTokens(module, allTokens) {
  const resolved = {};
  for (const t of allTokens) {
    if (t.scope === "core") resolved[t.key] = t;
  }
  for (const t of allTokens) {
    if (t.scope !== module) continue;
    if (CORE_ALLOWED_KEYS.has(t.key)) continue;
    resolved[t.key] = t;
  }
  return resolved;
}

// ============================================================================
// Assertions
// ============================================================================

let passed = 0;
let failed = 0;
const results = [];

function it(name, fn) {
  try {
    fn();
    results.push(`  ✓ ${name}`);
    passed++;
  } catch (err) {
    results.push(`  ✗ ${name}\n      ${err.message}`);
    failed++;
  }
}

function assertEq(a, b, msg) {
  if (a !== b) {
    throw new Error(`${msg || "not equal"} — expected ${JSON.stringify(b)}, got ${JSON.stringify(a)}`);
  }
}

function assertThrows(fn, msg) {
  let threw = false;
  try { fn(); } catch { threw = true; }
  if (!threw) throw new Error(msg || "expected throw");
}

console.log("=".repeat(64));
console.log("Alpha Quantum — Design Token Faz 1 frontend doğrulama");
console.log("=".repeat(64));

console.log("\n[Section 1] Governance whitelist");
it("core izinli anahtarlar passes", () => {
  for (const k of CORE_ALLOWED_KEYS) assertGovernance("core", k);
});
it("module izinli anahtarlar passes", () => {
  for (const scope of ["aq", "finos", "corpos"]) {
    for (const k of MODULE_ALLOWED_KEYS) assertGovernance(scope, k);
  }
});
it("core'da brand anahtarı reddedilir", () => {
  assertThrows(() => assertGovernance("core", "brand"));
});
it("modülün core anahtarını ezme denemesi reddedilir (bg_primary)", () => {
  for (const scope of ["aq", "finos", "corpos"]) {
    assertThrows(
      () => assertGovernance(scope, "bg_primary"),
      `${scope}.bg_primary reddedilmeliydi`,
    );
  }
});
it("modülün core anahtarını ezme denemesi reddedilir (status_error)", () => {
  for (const scope of ["aq", "finos", "corpos"]) {
    assertThrows(() => assertGovernance(scope, "status_error"));
  }
});
it("invalid scope reddedilir", () => {
  assertThrows(() => assertGovernance("foo", "brand"));
});

console.log("\n[Section 2] DEFAULT_TOKENS governance temiz");
it("tokens-defaults.json'daki her item governance geçer", () => {
  for (const t of defaults.tokens) assertGovernance(t.scope, t.key);
});

console.log("\n[Section 3] DEFAULT_TOKENS ↔ wcag-report.json birebir eşleşme");
it("core değerleri birebir", () => {
  const coreMap = Object.fromEntries(
    defaults.tokens.filter((t) => t.scope === "core").map((t) => [t.key, t.value]),
  );
  for (const [k, v] of Object.entries(wcag.core)) {
    if (k === "theme" || v === null) continue;
    assertEq(coreMap[k], String(v), `core.${k}`);
  }
});
it("aq değerleri birebir", () => {
  const mod = Object.fromEntries(
    defaults.tokens.filter((t) => t.scope === "aq").map((t) => [t.key, t.value]),
  );
  for (const [k, v] of Object.entries(wcag.modules.aq)) {
    if (k === "scope" || v === null) continue;
    assertEq(mod[k], String(v), `aq.${k}`);
  }
});
it("finos değerleri birebir (Kapı 1: cta=#CD4A00, Kapı 2: link_back=#94A3B8)", () => {
  const mod = Object.fromEntries(
    defaults.tokens.filter((t) => t.scope === "finos").map((t) => [t.key, t.value]),
  );
  for (const [k, v] of Object.entries(wcag.modules.finos)) {
    if (k === "scope" || v === null) continue;
    assertEq(mod[k], String(v), `finos.${k}`);
  }
  assertEq(mod.cta, "#CD4A00", "Kapı 1 — FinOS CTA");
  assertEq(mod.link_back, "#94A3B8", "Kapı 2 — FinOS link-back");
});
it("corpos değerleri birebir (Kapı 4: accent=#475569 slate, teal değil)", () => {
  const mod = Object.fromEntries(
    defaults.tokens.filter((t) => t.scope === "corpos").map((t) => [t.key, t.value]),
  );
  for (const [k, v] of Object.entries(wcag.modules.corpos)) {
    if (k === "scope" || v === null) continue;
    assertEq(mod[k], String(v), `corpos.${k}`);
  }
  assertEq(mod.accent, "#475569", "Kapı 4 — CorpOS accent slate");
});

console.log("\n[Section 4] resolveTokens(module) = core + module override");
it("resolveTokens('finos') core + finos = beklenen kümede", () => {
  const finos = resolveTokens("finos", defaults.tokens);
  // Core token'ları mevcut
  assertEq(finos.bg_primary?.value, wcag.core.bg_primary, "core.bg_primary kalır");
  assertEq(finos.status_error?.value, wcag.core.status_error, "core.status_error kalır");
  assertEq(finos.focus_ring?.value, wcag.core.focus_ring, "core.focus_ring kalır");
  // Module identity token'ları
  assertEq(finos.brand?.value, "#0EA5A4", "finos.brand turkuaz");
  assertEq(finos.cta?.value, "#CD4A00", "finos.cta turuncu");
  assertEq(finos.cta_text?.value, "#FFFFFF", "finos.cta_text beyaz");
  assertEq(finos.link_back?.value, "#94A3B8", "finos.link_back silver");
});
it("resolveTokens('corpos') core + corpos = beklenen kümede", () => {
  const corpos = resolveTokens("corpos", defaults.tokens);
  assertEq(corpos.bg_primary?.value, wcag.core.bg_primary, "core korunur");
  assertEq(corpos.brand?.value, "#F4C542", "corpos.brand altın");
  assertEq(corpos.accent?.value, "#475569", "corpos.accent slate (teal değil)");
  assertEq(corpos.link_back?.value, "#94A3B8", "corpos.link_back silver");
});
it("resolveTokens('aq') core + aq", () => {
  const aq = resolveTokens("aq", defaults.tokens);
  assertEq(aq.brand?.value, "#0C2D6B", "aq.brand safir");
  assertEq(aq.cta?.value, "#2563EB", "aq.cta azure (çatıya kilitli)");
  assertEq(aq.on_brand?.value, "#E8EFF9", "aq.on_brand");
});

console.log("\n[Section 5] Anahtar dağılımı");
it("toplam 43 token (20 core + 23 modül)", () => {
  assertEq(defaults.tokens.length, 43);
  assertEq(defaults.tokens.filter((t) => t.scope === "core").length, 20);
  const moduleTotal = defaults.tokens.filter((t) => t.scope !== "core").length;
  assertEq(moduleTotal, 23);
});

// ============================================================================
// Output
// ============================================================================
console.log("");
for (const r of results) console.log(r);
console.log("");
console.log("=".repeat(64));
console.log(`SONUÇ: ${passed} pass / ${failed} fail`);
console.log("=".repeat(64));

if (failed > 0) process.exit(1);
process.exit(0);
