/**
 * Design Token Programı — Faz 1 · Token mimarisi (data layer).
 *
 * Sorumluluklar:
 *   1. Scope tip sistemi (core / aq / finos / corpos).
 *   2. `DEFAULT_TOKENS` — Faz 0 wcag-report.json'dan üretilen seed
 *      (frontend/lib/tokens-defaults.json, `scripts/generate-token-defaults.mjs`
 *      üreticisi).
 *   3. Governance whitelist — modüller core-sahipli anahtarları EZEMEZ.
 *      İhlal `GovernanceViolationError` fırlatır.
 *   4. `getTokens(scope?)` — DB'den okur (yoksa DEFAULT_TOKENS), `unstable_cache`
 *      ile tag'lendirilir.
 *   5. `resolveTokens(module)` — core + modül override'ı birleştirir.
 *   6. `tokensToCss(tokens, selector)` — CSS custom property bloğu üretir.
 *   7. İki-katman destek: token `value` ya hex'tir ya da `var(--key)` referansıdır
 *      (semantic → primitive remap'i ileride bu sayede çalışacak).
 *
 * Faz 0 kilitlidir. Foundation değerlerini bu dosyada hand-edit ETMEYİN —
 * `docs/design-tokens/foundation.md` + `wcag-report.json` güncellenir,
 * `node frontend/scripts/generate-token-defaults.mjs` yeniden çalıştırılır.
 */

import { unstable_cache } from "next/cache";

import tokensDefaultsRaw from "./tokens-defaults.json";

// ============================================================================
// 1. Types
// ============================================================================

export const VALID_SCOPES = ["core", "aq", "finos", "corpos"] as const;
export type Scope = (typeof VALID_SCOPES)[number];

export type ModuleScope = Exclude<Scope, "core">;

export type TokenCategory =
  // semantic color categories (core sahipli)
  | "background"
  | "surface"
  | "border"
  | "text"
  | "status"
  | "focus"
  // identity color categories (modül sahipli)
  | "brand"
  | "cta"
  | "accent"
  // tipografi + form (Faz 6'da genişler)
  | "font-family"
  | "font-size"
  | "font-weight"
  | "radius"
  | "shadow";

export interface Token {
  scope: Scope;
  key: string;
  value: string; // hex, sayı string'i veya `var(--ref)` (iki-katman desteği)
  label: string;
  category: TokenCategory;
  order: number;
}

// ============================================================================
// 2. Defaults — Faz 0'dan üretilmiş seed
// ============================================================================

interface TokensDefaultsFile {
  generated_from: string;
  foundation_version: string;
  theme: string;
  tokens: Token[];
}

const tokensDefaults = tokensDefaultsRaw as TokensDefaultsFile;

/**
 * Foundation seed'i — `frontend/lib/tokens-defaults.json` (build artifact).
 * Foundation versiyonu değiştiyse generator'ı yeniden çalıştır.
 */
export const DEFAULT_TOKENS: readonly Token[] = Object.freeze(
  tokensDefaults.tokens.map((t) => Object.freeze({ ...t })) as Token[],
);

export const FOUNDATION_VERSION: string = tokensDefaults.foundation_version;

// ============================================================================
// 3. Governance — modüller core-sahipli anahtarları EZEMEZ
// ============================================================================

/** core scope'unda izinli anahtarlar (sabit). */
export const CORE_ALLOWED_KEYS: ReadonlySet<string> = new Set([
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

/** Modül scope'larında izinli kimlik anahtarları (sabit). */
export const MODULE_ALLOWED_KEYS: ReadonlySet<string> = new Set([
  "brand", "brand_hover",
  "cta", "cta_hover", "cta_text", "cta_text_weight",
  "on_brand",
  "accent", "accent_light",
  "link_back",
]);

export class GovernanceViolationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "GovernanceViolationError";
  }
}

/**
 * Token (scope, key) çifti governance'ı geçer mi?
 *
 * @throws `GovernanceViolationError` modül core-sahipli anahtarı ezerse
 * @throws `Error` scope geçersizse
 */
export function assertGovernance(scope: string, key: string): void {
  if (!VALID_SCOPES.includes(scope as Scope)) {
    throw new Error(`Geçersiz scope: ${scope}. İzinli: ${VALID_SCOPES.join(", ")}`);
  }
  if (scope === "core") {
    if (!CORE_ALLOWED_KEYS.has(key)) {
      throw new GovernanceViolationError(
        `core scope'unda izinsiz anahtar: ${key}`,
      );
    }
    return;
  }
  // modül scope'u — core anahtarı ezmek YASAK
  if (CORE_ALLOWED_KEYS.has(key)) {
    throw new GovernanceViolationError(
      `Modül '${scope}' core-sahipli anahtar '${key}' ezemez. ` +
      "Core token'ları (bg/surface/border/text/status/focus) yalnız core scope'unda tanımlanır.",
    );
  }
  if (!MODULE_ALLOWED_KEYS.has(key)) {
    throw new GovernanceViolationError(
      `Modül '${scope}' için izinsiz anahtar: ${key}`,
    );
  }
}

/** Verilen liste hepsi governance'ı geçiyor mu? İhlal varsa ilk hatayı fırlatır. */
export function assertAllGovernance(tokens: readonly Token[]): void {
  for (const t of tokens) {
    assertGovernance(t.scope, t.key);
  }
}

// Build-time assertion: DEFAULT_TOKENS governance temiz.
// (Test framework'siz statik garanti — modül import edildiğinde fırlatır.)
assertAllGovernance(DEFAULT_TOKENS);

// ============================================================================
// 4. getTokens — DB'den oku, yoksa DEFAULT_TOKENS fallback (unstable_cache wrap)
// ============================================================================

interface DesignTokensApiResponse {
  tokens: Array<{
    scope: Scope;
    key: string;
    value: string;
    label: string;
    category: TokenCategory;
    order: number;
    updated_at: number;
  }>;
  scope_filter: Scope | null;
  seeded_at: number | null;
}

const BACKEND_URL =
  process.env.NEXT_PUBLIC_API_URL ?? process.env.AQ_BACKEND_URL ?? "http://127.0.0.1:8000";

/**
 * Backend'den token'ları çek. Başarısızlıkta DEFAULT_TOKENS'a düş.
 * `unstable_cache` ile sarılmış: revalidation `revalidateTag('design-tokens')`.
 */
async function fetchTokensImpl(scope?: Scope): Promise<Token[]> {
  const qs = scope ? `?scope=${encodeURIComponent(scope)}` : "";
  try {
    const res = await fetch(`${BACKEND_URL}/api/v1/design-tokens${qs}`, {
      // Server-side fetch; FETCH cache deferred to unstable_cache wrapping.
      cache: "no-store",
    });
    if (!res.ok) {
      return filterDefaults(scope);
    }
    const payload = (await res.json()) as DesignTokensApiResponse;
    // Backend boş veya hatalı dönerse fallback
    if (!Array.isArray(payload.tokens) || payload.tokens.length === 0) {
      return filterDefaults(scope);
    }
    return payload.tokens.map((t) => ({
      scope: t.scope,
      key: t.key,
      value: t.value,
      label: t.label,
      category: t.category,
      order: t.order,
    }));
  } catch {
    return filterDefaults(scope);
  }
}

function filterDefaults(scope?: Scope): Token[] {
  return scope
    ? DEFAULT_TOKENS.filter((t) => t.scope === scope).map((t) => ({ ...t }))
    : DEFAULT_TOKENS.map((t) => ({ ...t }));
}

/**
 * Token'ları getir (cache'li). Faz 4'te admin panel `revalidateTag('design-tokens')`
 * çağırarak anında yenileyebilir.
 */
export const getTokens = unstable_cache(
  async (scope?: Scope) => fetchTokensImpl(scope),
  ["design-tokens-v1"],
  { tags: ["design-tokens"] },
);

// ============================================================================
// 5. resolveTokens — core + modül override merge
// ============================================================================

/**
 * Belirli bir modül için nihai token sözlüğünü döndürür: core + modül override'ı.
 *
 * - core token'ları taban olarak gelir
 * - modül token'ları kendi izinli kimlik anahtarlarını ekler/ezer
 * - `assertGovernance` zaten tek tek validate eder; burada sadece merge
 *
 * Çıktı: `{ [key]: { scope, key, value, ... } }` sözlüğü. Aynı `key`
 * hem core'da hem modülde bulunamaz (governance bunu garanti eder) — bu
 * yüzden çakışma yoktur.
 */
export async function resolveTokens(
  module: ModuleScope,
): Promise<Record<string, Token>> {
  const [coreTokens, moduleTokens] = await Promise.all([
    getTokens("core"),
    getTokens(module),
  ]);

  const resolved: Record<string, Token> = {};
  for (const t of coreTokens) resolved[t.key] = t;
  for (const t of moduleTokens) {
    // governance gereği bu noktada hiç core anahtarı olmamalı; defansif:
    if (CORE_ALLOWED_KEYS.has(t.key)) continue; // sessizce yok say
    resolved[t.key] = t;
  }
  return resolved;
}

/** Senkron varyant — DEFAULT_TOKENS üzerinden, test/SSR-deterministic kullanım için. */
export function resolveTokensSync(module: ModuleScope): Record<string, Token> {
  const resolved: Record<string, Token> = {};
  for (const t of DEFAULT_TOKENS) {
    if (t.scope === "core") resolved[t.key] = t;
  }
  for (const t of DEFAULT_TOKENS) {
    if (t.scope !== module) continue;
    if (CORE_ALLOWED_KEYS.has(t.key)) continue; // defansif governance
    resolved[t.key] = t;
  }
  return resolved;
}

// ============================================================================
// 6. tokensToCss — CSS custom property emitter
// ============================================================================

/**
 * Token sözlüğünü CSS değişken bloğu olarak yazar.
 *
 *   tokensToCss({ bg_primary: {...} }, ":root")
 *   → ":root { --bg-primary: #0C1015; }"
 *
 * Anahtar→CSS değişken adı dönüşümü: `bg_primary` → `--bg-primary`.
 * Faz 2 SSR enjeksiyonu bunu kullanacak.
 */
export function tokensToCss(
  tokens: Record<string, Token> | readonly Token[],
  selector: string,
): string {
  const list = Array.isArray(tokens)
    ? (tokens as readonly Token[])
    : Object.values(tokens as Record<string, Token>);

  const declarations = list
    .slice()
    .sort((a, b) => {
      if (a.order !== b.order) return a.order - b.order;
      return a.key.localeCompare(b.key);
    })
    .map((t) => `  --${keyToCssVar(t.key)}: ${t.value};`)
    .join("\n");

  return `${selector} {\n${declarations}\n}`;
}

/** `bg_primary` → `bg-primary` (CSS değişken adı konvensiyonu). */
export function keyToCssVar(key: string): string {
  return key.replace(/_/g, "-");
}

// ============================================================================
// 7. Pathname → Module detection (Faz 2 SSR cascade)
// ============================================================================

/**
 * URL pathname'inden modül kimliğini tespit eder. Root layout `data-module`
 * attribute'una bu değeri yazar; cascade `html[data-module='<scope>']`
 * selectoru ile devreye girer.
 *
 * Kurallar (tutarlı + öngörülebilir):
 *  - `/cashflow`, `/treasury`, `/invoices`, `/notifications` → FinOS
 *  - `/customers`, `/companies` → CorpOS
 *  - `/tokens-cascade-finos*`, `/tokens-cascade-corpos*` → demo override
 *  - Diğer her şey (root, dashboard, settings, login, vs.) → AlphaQ çatı
 *
 * Core hiçbir zaman tek başına kimlik DEĞİL; her zaman bir modül seçilir.
 */
export function detectModuleFromPathname(pathname: string): ModuleScope {
  // Demo route'lar — explicit override (test/proof için)
  if (/^\/(tokens-cascade-finos)(\/|$)/.test(pathname)) return "finos";
  if (/^\/(tokens-cascade-corpos)(\/|$)/.test(pathname)) return "corpos";
  if (/^\/(tokens-cascade-aq)(\/|$)/.test(pathname)) return "aq";

  // FinOS modülünün gerçek route'ları
  if (/^\/(cashflow|treasury|invoices|notifications|finance)(\/|$)/.test(pathname)) {
    return "finos";
  }

  // CorpOS modülünün gerçek route'ları
  if (/^\/(customers|companies|procurement|feasibility)(\/|$)/.test(pathname)) {
    return "corpos";
  }

  // Default: çatı (AlphaQ)
  return "aq";
}

