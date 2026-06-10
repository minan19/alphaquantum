#!/usr/bin/env node
/**
 * Design Token Programı — Faz 1 · DEFAULT_TOKENS generator.
 *
 * Faz 0 wcag-report.json'u okur ve `frontend/lib/tokens-defaults.json`'u üretir.
 * Bu dosya `lib/tokens.ts` tarafından import edilir.
 *
 * GERÇEK DEĞERLER ELLE YAZILMAZ — yalnız bu script tarafından üretilir.
 * Çalıştırma:
 *   node frontend/scripts/generate-token-defaults.mjs
 *
 * Çıktı:
 *   frontend/lib/tokens-defaults.json
 *
 * Idempotent: aynı girdiden aynı çıktı.
 */
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..", "..");
const SRC = join(ROOT, "docs", "design-tokens", "wcag-report.json");
const OUT = join(ROOT, "frontend", "lib", "tokens-defaults.json");

// Meta haritası — backend `app/color_token_seed.py` ile birebir uyumlu.
// Sunum bilgisi (label/category/order); değerler kaynaktan gelir.
const CORE_META = {
  bg_primary:             ["Arkaplan — birincil",         "background", 10],
  bg_secondary:           ["Arkaplan — ikincil",          "background", 11],
  bg_tertiary:            ["Arkaplan — üçüncül",          "background", 12],
  surface_01:             ["Yüzey 01",                    "surface",    20],
  surface_02:             ["Yüzey 02",                    "surface",    21],
  surface_03:             ["Yüzey 03",                    "surface",    22],
  border:                 ["Kenarlık",                    "border",     30],
  text_primary:           ["Metin — birincil (~15:1)",    "text",       40],
  text_secondary:         ["Metin — ikincil (~8:1)",      "text",       41],
  text_muted:             ["Metin — soluk (~4.5:1)",      "text",       42],
  text_inverse:           ["Metin — ters",                "text",       43],
  status_success:         ["Durum — başarı",              "status",     50],
  status_success_surface: ["Durum — başarı yüzeyi",       "status",     51],
  status_warning:         ["Durum — uyarı",               "status",     52],
  status_warning_surface: ["Durum — uyarı yüzeyi",        "status",     53],
  status_error:           ["Durum — hata (= negatif)",    "status",     54],
  status_error_surface:   ["Durum — hata yüzeyi",         "status",     55],
  status_info:            ["Durum — bilgi",               "status",     56],
  status_info_surface:    ["Durum — bilgi yüzeyi",        "status",     57],
  focus_ring:             ["Focus halkası",               "focus",      60],
};

const MODULE_META = {
  brand:           ["Marka",                "brand",  10],
  brand_hover:     ["Marka — hover",        "brand",  11],
  cta:             ["CTA dolgu",            "cta",    20],
  cta_hover:       ["CTA — hover",          "cta",    21],
  cta_text:        ["CTA — metin rengi",    "cta",    22],
  cta_text_weight: ["CTA — metin ağırlığı", "cta",    23],
  on_brand:        ["Marka yüzeyi",         "brand",  30],
  accent:          ["Aksan (veri)",         "accent", 40],
  accent_light:    ["Aksan — açık",         "accent", 41],
  link_back:       ["Çatıya geri-dönüş",    "accent", 50],
};

function build() {
  const raw = readFileSync(SRC, "utf8");
  const report = JSON.parse(raw);

  const items = [];

  // core
  for (const [key, value] of Object.entries(report.core)) {
    if (key === "theme") continue;
    if (value === null || value === undefined) continue;
    const meta = CORE_META[key];
    if (!meta) {
      throw new Error(
        `core.${key} için meta tanımlı değil — generate-token-defaults.mjs güncellenmeli`,
      );
    }
    const [label, category, order] = meta;
    items.push({ scope: "core", key, value: String(value), label, category, order });
  }

  // modules
  for (const [scope, mod] of Object.entries(report.modules)) {
    if (!["aq", "finos", "corpos"].includes(scope)) {
      throw new Error(`beklenmeyen modül scope: ${scope}`);
    }
    for (const [key, value] of Object.entries(mod)) {
      if (key === "scope") continue;
      if (value === null || value === undefined) continue;
      const meta = MODULE_META[key];
      if (!meta) {
        throw new Error(
          `${scope}.${key} için meta tanımlı değil — generate-token-defaults.mjs güncellenmeli`,
        );
      }
      const [label, category, order] = meta;
      items.push({ scope, key, value: String(value), label, category, order });
    }
  }

  // deterministic sort
  items.sort((a, b) => {
    if (a.scope !== b.scope) return a.scope.localeCompare(b.scope);
    if (a.order !== b.order) return a.order - b.order;
    return a.key.localeCompare(b.key);
  });

  return {
    generated_from: "docs/design-tokens/wcag-report.json",
    foundation_version: report.foundation_version,
    theme: report.theme,
    tokens: items,
  };
}

const output = build();
writeFileSync(OUT, JSON.stringify(output, null, 2) + "\n", "utf8");
console.log(
  `wrote ${OUT} (${output.tokens.length} tokens from foundation ${output.foundation_version})`,
);
