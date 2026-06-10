/**
 * Design Token Programı — Faz 3 · OKLCH + WCAG motor (saf kütüphane).
 *
 * Faz 0 `docs/design-tokens/system.mjs` motorunun frontend tip-güvenli portu.
 * **Aynı matrisleri** kullanır (kopyalandı, yeniden türetilmedi). Hedef: panelin
 * canlı `✦ Otomatik` butonunun runtime'da hesaplayabileceği bir kütüphane sağlamak.
 *
 * - UI YOK (Faz 4)
 * - API YOK (yalnız frontend)
 * - DB YOK (yalnız hesap)
 *
 * Parite garantisi: bu modülün ürettiği değerler, `docs/design-tokens/wcag-report.json`
 * Faz 0 çıktısı ile **birebir aynı** olmalıdır (yuvarlama hariç).
 *
 * Governance: `computeAuto`, Faz 1 whitelist'ine uyar — modülde core-sahipli key
 * istenirse `assertGovernance` üzerinden `GovernanceViolationError` fırlar.
 */

import {
  assertGovernance,
  type ModuleScope,
  type Scope,
} from "./tokens";

// ============================================================================
// 1. OKLCH ↔ sRGB conversion (system.mjs BİREBİR port)
// Ref: Björn Ottosson, "A perceptual color space for image processing".
// ============================================================================

/** Linear-light sRGB → sRGB gamma (companding). */
function linearToSrgb(v: number): number {
  if (v < 0) return 0;
  if (v > 1) return 1;
  return v >= 0.0031308 ? 1.055 * Math.pow(v, 1 / 2.4) - 0.055 : 12.92 * v;
}

/** sRGB gamma → linear-light sRGB. */
function srgbToLinear(v: number): number {
  return v >= 0.04045 ? Math.pow((v + 0.055) / 1.055, 2.4) : v / 12.92;
}

/** OKLab → linear sRGB. */
function oklabToLinearSrgb(L: number, a: number, b: number): [number, number, number] {
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
function linearSrgbToOklab(r: number, g: number, b: number): [number, number, number] {
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

export interface OklchTuple {
  L: number;
  C: number;
  h: number;
}

export interface RgbTuple {
  r: number;
  g: number;
  b: number;
}

/** Hex `#RRGGBB` → {r, g, b} (0..255). */
export function hexToRgb(hex: string): RgbTuple {
  const clean = hex.startsWith("#") ? hex.slice(1) : hex;
  if (clean.length !== 6) {
    throw new Error(`hexToRgb: 6-haneli hex bekleniyor, alındı: ${hex}`);
  }
  return {
    r: parseInt(clean.slice(0, 2), 16),
    g: parseInt(clean.slice(2, 4), 16),
    b: parseInt(clean.slice(4, 6), 16),
  };
}

/** OKLCH → hex string `#RRGGBB`. Out-of-gamut clip ile. */
export function oklchToHex(L: number, C: number, hDeg: number): string {
  const h = (hDeg * Math.PI) / 180;
  const a = C * Math.cos(h);
  const b = C * Math.sin(h);
  const [lr, lg, lb] = oklabToLinearSrgb(L, a, b);
  const r = Math.round(255 * linearToSrgb(lr));
  const g = Math.round(255 * linearToSrgb(lg));
  const bl = Math.round(255 * linearToSrgb(lb));
  const clamp = (v: number) => Math.max(0, Math.min(255, v));
  return (
    "#" +
    clamp(r).toString(16).padStart(2, "0") +
    clamp(g).toString(16).padStart(2, "0") +
    clamp(bl).toString(16).padStart(2, "0")
  ).toUpperCase();
}

/** Hex `#RRGGBB` → OKLCH {L, C, h(°)}. */
export function hexToOklch(hex: string): OklchTuple {
  const { r, g, b } = hexToRgb(hex);
  const [lr, lg, lb] = [srgbToLinear(r / 255), srgbToLinear(g / 255), srgbToLinear(b / 255)];
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
function relLuminance(hex: string): number {
  const { r, g, b } = hexToRgb(hex);
  return (
    0.2126 * srgbToLinear(r / 255) +
    0.7152 * srgbToLinear(g / 255) +
    0.0722 * srgbToLinear(b / 255)
  );
}

/** WCAG 2.2 contrast ratio (1..21). */
export function wcagContrast(fgHex: string, bgHex: string): number {
  const L1 = relLuminance(fgHex);
  const L2 = relLuminance(bgHex);
  const lighter = Math.max(L1, L2);
  const darker = Math.min(L1, L2);
  return (lighter + 0.05) / (darker + 0.05);
}

export type ContrastRating = "AAA" | "AA" | "AA-Lg" | "FAIL";

/** WCAG kontrast oranını insan-okunur kategoriye eşle. */
export function contrastRating(r: number): ContrastRating {
  if (r >= 7) return "AAA";
  if (r >= 4.5) return "AA";
  if (r >= 3) return "AA-Lg";
  return "FAIL";
}

// ============================================================================
// 3. Binary-search text-level L (hedef kontrasta çöz)
// system.mjs ile birebir aynı algoritma.
// ============================================================================

/**
 * Verilen hue+chroma için, bg'ye karşı hedef kontrasta ulaşan L'i bul.
 * - Koyu bg'de yüksek L (light text), açık bg'de düşük L (dark text).
 * - 40 iterasyon yeterli (`2^-40` band).
 */
export function findTextL(
  bgHex: string,
  targetContrast: number,
  hue: number,
  chroma: number,
): number {
  const bgL = relLuminance(bgHex);
  const bgIsDark = bgL < 0.18; // perceptual heuristic, sabit
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
// 4. Faz 0 ANCHORS — foundation.md birebir kilitli
// system.mjs ile aynı değerler; tek bir kez tanımlanır, hem motor hem testler okur.
// ============================================================================

export const FAZ0_ANCHORS = {
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
      primary:   { contrast: 15,  hue: 258, chroma: 0.005 },
      secondary: { contrast:  8,  hue: 258, chroma: 0.008 },
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
    brand:     { L: 0.654, C: 0.110, h: 194,  hex: "#0EA5A4" },
    cta:       { L: 0.580, C: 0.155, h: 47.6, hex: "#CD4A00" },
    cta_text:  "#FFFFFF",
    link_back: "#94A3B8",
  },
  corpos: {
    brand:        { L: 0.843, C: 0.151, h: 88,  hex: "#F4C542" },
    accent:       { L: 0.446, C: 0.035, h: 257, hex: "#475569" },
    accent_light: { L: 0.711, C: 0.025, h: 257, hex: "#94A3B8" },
    cta_text_dark: "#0C1224",
    link_back:    "#94A3B8",
  },
} as const;

// ============================================================================
// 5. Palet üretimi — system.mjs `buildCorePalette` / `buildModulePalette` portu
// ============================================================================

export interface CorePalette {
  theme: "dark" | "light";
  bg_primary: string;
  bg_secondary: string;
  bg_tertiary: string;
  surface_01: string;
  surface_02: string;
  surface_03: string;
  border: string;
  text_primary: string;
  text_secondary: string;
  text_muted: string;
  text_inverse: string;
  status_success: string;
  status_success_surface: string;
  status_warning: string;
  status_warning_surface: string;
  status_error: string;
  status_error_surface: string;
  status_info: string;
  status_info_surface: string;
  focus_ring: string;
}

export interface ModulePalette {
  scope: ModuleScope;
  brand: string;
  brand_hover: string;
  cta: string;
  cta_hover: string;
  cta_text: string;
  /** corpos için: 500 (CorpOS altın CTA'nın koyu metin ağırlığı). */
  cta_text_weight?: number;
  /** aq'da: marka yüzeyi. */
  on_brand?: string;
  accent: string;
  /** corpos için ek aksan. */
  accent_light?: string;
  /** aq'da link_back null — çatı kendi içinde. */
  link_back: string | null;
}

/**
 * Core paleti deterministik üret. Foundation kilidi → değerler birebir Faz 0.
 */
export function buildCorePalette(theme: "dark" | "light" = "dark"): CorePalette {
  const c = FAZ0_ANCHORS.core;
  const bgL = theme === "light" ? c.bg_primary_light.L : c.bg_primary_dark.L;
  const bgC = theme === "light" ? c.bg_primary_light.C : c.bg_primary_dark.C;
  const sign = theme === "light" ? -1 : +1;

  const bg_primary = oklchToHex(bgL, bgC, c.neutral_hue);

  const elev = (n: number) =>
    oklchToHex(
      Math.max(0, Math.min(1, bgL + sign * c.elevation_delta_L * n)),
      bgC,
      c.neutral_hue,
    );

  const txt = (target: { contrast: number; hue: number; chroma: number }) => {
    const L = findTextL(bg_primary, target.contrast, target.hue, target.chroma);
    return oklchToHex(L, target.chroma, target.hue);
  };

  const statusHex: Record<string, string> = {};
  const statusSurfaceHex: Record<string, string> = {};
  for (const [k, v] of Object.entries(c.status)) {
    statusHex[k] = oklchToHex(v.L, v.C, v.h);
    const sL =
      theme === "light"
        ? Math.min(0.95, v.L + 0.18)
        : Math.max(0.18, v.L - 0.45);
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

/** Modül kimliği paleti üret (core'u baz alarak). */
export function buildModulePalette(
  name: ModuleScope,
  core: CorePalette,
): ModulePalette {
  if (name === "aq") {
    const a = FAZ0_ANCHORS.aq;
    return {
      scope: "aq",
      brand:        a.brand.hex,
      brand_hover:  oklchToHex(Math.max(0, a.brand.L - 0.14), a.brand.C, a.brand.h),
      cta:          a.cta.hex,
      cta_hover:    oklchToHex(Math.max(0, a.cta.L - 0.14), a.cta.C, a.cta.h),
      cta_text:     a.cta_text,
      on_brand:     a.on_brand.hex,
      accent:       a.cta.hex, // çatı: signature azure data accent
      link_back:    null,
    };
  }
  if (name === "finos") {
    const a = FAZ0_ANCHORS.finos;
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
  // corpos
  const a = FAZ0_ANCHORS.corpos;
  return {
    scope: "corpos",
    brand:        a.brand.hex,
    brand_hover:  oklchToHex(Math.max(0, a.brand.L - 0.10), a.brand.C, a.brand.h),
    cta:          a.brand.hex,
    cta_hover:    oklchToHex(Math.max(0, a.brand.L - 0.10), a.brand.C, a.brand.h),
    cta_text:     a.cta_text_dark,
    cta_text_weight: 500,
    accent:       a.accent.hex,
    accent_light: a.accent_light.hex,
    link_back:    a.link_back,
  };
}

// ============================================================================
// 6. computeAuto — Panel ✦ Otomatik butonun çağıracağı dispatch
// ============================================================================

/**
 * Bir token için "doğru" değeri üret. Anchor'lar `draft`'tan canlı okunur (örn.
 * bg-primary değiştirilmişse elevation ramp ona göre güncel kalır).
 *
 * Governance: scope/key Faz 1 whitelist'ine uygun olmalı. İhlalde `GovernanceViolationError`.
 *
 * Dönüş: yeni hex değeri (color category) veya number (font-weight gibi non-color).
 */
export interface DraftValues {
  /** Şu an düzenleniyor olan token sözlüğü (key → value). bg-primary, brand vb. */
  [key: string]: string | number;
}

export type ComputeAutoCategory =
  | "background"
  | "surface"
  | "border"
  | "text"
  | "status"
  | "focus"
  | "brand"
  | "cta"
  | "accent"
  | "font-family"
  | "font-size"
  | "font-weight"
  | "radius"
  | "shadow";

export interface ComputeAutoResult {
  value: string | number;
  /** Hesabın anchor / referans değerlerinin notu (debug + audit trail). */
  derivedFrom: string;
}

/**
 * Saf hesaplayıcı. UI'den bağımsız.
 * Panelden çağrılırken `draft = mevcut tüm token'lar` geçilir.
 */
export function computeAuto(
  scope: Scope,
  key: string,
  category: ComputeAutoCategory,
  draft: DraftValues,
): ComputeAutoResult {
  // Governance kapısı — modülde core-sahipli key istemek YASAK
  assertGovernance(scope, key);

  const core = FAZ0_ANCHORS.core;

  switch (category) {
    case "background": {
      // bg-primary ya direkt anchor (theme-dark) ya da draft'tan oku
      if (key === "bg_primary") {
        const a = core.bg_primary_dark;
        return {
          value: oklchToHex(a.L, a.C, a.h),
          derivedFrom: `dark anchor L=${a.L} C=${a.C} h=${a.h}`,
        };
      }
      // bg-secondary/tertiary → elevation ramp
      const levelMap: Record<string, number> = { bg_secondary: 1, bg_tertiary: 2 };
      const n = levelMap[key];
      if (n != null) {
        const bgPrimaryHex = (draft.bg_primary as string | undefined) ??
          oklchToHex(core.bg_primary_dark.L, core.bg_primary_dark.C, core.bg_primary_dark.h);
        const { L, C, h } = hexToOklch(bgPrimaryHex);
        return {
          value: oklchToHex(L + core.elevation_delta_L * n, C, h),
          derivedFrom: `elevation ramp +${core.elevation_delta_L * n}ΔL from bg_primary`,
        };
      }
      throw new Error(`computeAuto: bilinmeyen background key '${key}'`);
    }
    case "surface": {
      // surface-01/02/03 → bg-primary'den +3, +4, +5 ΔL
      const levelMap: Record<string, number> = { surface_01: 3, surface_02: 4, surface_03: 5 };
      const n = levelMap[key];
      if (n == null) throw new Error(`computeAuto: bilinmeyen surface key '${key}'`);
      const bgPrimaryHex = (draft.bg_primary as string | undefined) ??
        oklchToHex(core.bg_primary_dark.L, core.bg_primary_dark.C, core.bg_primary_dark.h);
      const { L, C, h } = hexToOklch(bgPrimaryHex);
      return {
        value: oklchToHex(L + core.elevation_delta_L * n, C, h),
        derivedFrom: `elevation ramp +${core.elevation_delta_L * n}ΔL from bg_primary`,
      };
    }
    case "border": {
      const bgPrimaryHex = (draft.bg_primary as string | undefined) ??
        oklchToHex(core.bg_primary_dark.L, core.bg_primary_dark.C, core.bg_primary_dark.h);
      const { L, C, h } = hexToOklch(bgPrimaryHex);
      return {
        value: oklchToHex(
          L + core.elevation_delta_L * 3,
          Math.min(0.02, C * 1.5),
          h,
        ),
        derivedFrom: `border = bg_primary + 3ΔL, chroma boosted to ≤0.02`,
      };
    }
    case "text": {
      const targets = core.text_targets;
      const target =
        key === "text_primary"   ? targets.primary :
        key === "text_secondary" ? targets.secondary :
        key === "text_muted"     ? targets.muted   : null;
      if (target == null) {
        if (key === "text_inverse") {
          return { value: "#0C1224", derivedFrom: "static dark inverse anchor" };
        }
        throw new Error(`computeAuto: bilinmeyen text key '${key}'`);
      }
      const bgPrimaryHex = (draft.bg_primary as string | undefined) ??
        oklchToHex(core.bg_primary_dark.L, core.bg_primary_dark.C, core.bg_primary_dark.h);
      const L = findTextL(bgPrimaryHex, target.contrast, target.hue, target.chroma);
      return {
        value: oklchToHex(L, target.chroma, target.hue),
        derivedFrom: `binary-search L for contrast ${target.contrast}:1 vs bg_primary`,
      };
    }
    case "status": {
      // status-success / -warning / -error / -info (+ -surface variantları)
      const statusMap: Record<string, keyof typeof core.status> = {
        status_success: "success", status_success_surface: "success",
        status_warning: "warning", status_warning_surface: "warning",
        status_error:   "error",   status_error_surface:   "error",
        status_info:    "info",    status_info_surface:    "info",
      };
      const which = statusMap[key];
      if (which == null) throw new Error(`computeAuto: bilinmeyen status key '${key}'`);
      const a = core.status[which];
      if (key.endsWith("_surface")) {
        const sL = Math.max(0.18, a.L - 0.45);
        const sC = Math.min(0.03, a.C * 0.18);
        return {
          value: oklchToHex(sL, sC, a.h),
          derivedFrom: `${which} surface = L-0.45, C×0.18 from base`,
        };
      }
      return {
        value: oklchToHex(a.L, a.C, a.h),
        derivedFrom: `${which} anchor L=${a.L} C=${a.C} h=${a.h}`,
      };
    }
    case "focus": {
      // focus_ring
      const f = core.focus_ring;
      return {
        value: oklchToHex(f.L, f.C, f.h),
        derivedFrom: `focus_ring anchor L=${f.L} C=${f.C} h=${f.h}`,
      };
    }
    case "brand": {
      // Modül scope'unun anchor brand'ı; hover = L - 0.14 (corpos için -0.10)
      if (scope === "core") {
        throw new Error("computeAuto: brand kategorisi core scope'unda olmaz");
      }
      const moduleA = FAZ0_ANCHORS[scope].brand;
      if (key === "brand")     return { value: moduleA.hex, derivedFrom: `${scope}.brand anchor` };
      const hoverDelta = scope === "corpos" ? 0.10 : 0.14;
      if (key === "brand_hover") {
        return {
          value: oklchToHex(Math.max(0, moduleA.L - hoverDelta), moduleA.C, moduleA.h),
          derivedFrom: `${scope}.brand L-${hoverDelta}`,
        };
      }
      if (key === "on_brand" && scope === "aq") {
        return { value: FAZ0_ANCHORS.aq.on_brand.hex, derivedFrom: "aq.on_brand anchor" };
      }
      throw new Error(`computeAuto: bilinmeyen brand key '${key}' in ${scope}`);
    }
    case "cta": {
      if (scope === "core") {
        throw new Error("computeAuto: cta kategorisi core scope'unda olmaz");
      }
      if (key === "cta_text") {
        return scope === "corpos"
          ? { value: FAZ0_ANCHORS.corpos.cta_text_dark, derivedFrom: "corpos altın CTA için dark text" }
          : { value: "#FFFFFF", derivedFrom: "azure/turuncu CTA üzerinde beyaz metin" };
      }
      if (key === "cta_text_weight") {
        return { value: 500, derivedFrom: "corpos altın CTA için medium weight" };
      }
      if (scope === "corpos") {
        const c = FAZ0_ANCHORS.corpos.brand;
        if (key === "cta") return { value: c.hex, derivedFrom: "corpos.cta = brand altın" };
        if (key === "cta_hover") {
          return {
            value: oklchToHex(Math.max(0, c.L - 0.10), c.C, c.h),
            derivedFrom: "corpos.cta_hover = brand L-0.10",
          };
        }
        throw new Error(`computeAuto: bilinmeyen corpos cta key '${key}'`);
      }
      // aq / finos
      const c = FAZ0_ANCHORS[scope].cta;
      if (key === "cta") {
        // Garanti: cta_text ile kontrast ≥ 4.5. Anchor zaten geçtiğinden direkt dön.
        return { value: c.hex, derivedFrom: `${scope}.cta anchor (Kapı 1 doğrulanmış)` };
      }
      if (key === "cta_hover") {
        return {
          value: oklchToHex(Math.max(0, c.L - 0.14), c.C, c.h),
          derivedFrom: `${scope}.cta L-0.14`,
        };
      }
      throw new Error(`computeAuto: bilinmeyen cta key '${key}' in ${scope}`);
    }
    case "accent": {
      if (scope === "core") {
        throw new Error("computeAuto: accent kategorisi core scope'unda olmaz");
      }
      if (key === "link_back") {
        if (scope === "aq") {
          throw new Error("computeAuto: aq'da link_back yok (çatı zaten root)");
        }
        const lb = scope === "finos" ? FAZ0_ANCHORS.finos.link_back : FAZ0_ANCHORS.corpos.link_back;
        return { value: lb, derivedFrom: `${scope}.link_back = silver #94A3B8 (Kapı 2)` };
      }
      if (scope === "aq" && key === "accent") {
        return { value: FAZ0_ANCHORS.aq.cta.hex, derivedFrom: "aq.accent = signature azure (çatı veri rengi)" };
      }
      if (scope === "finos" && key === "accent") {
        // status_info'yu draft'tan oku, yoksa anchor'dan üret
        const infoHex = (draft.status_info as string | undefined) ??
          oklchToHex(core.status.info.L, core.status.info.C, core.status.info.h);
        return { value: infoHex, derivedFrom: "finos.accent = core.status_info" };
      }
      if (scope === "corpos" && key === "accent") {
        return { value: FAZ0_ANCHORS.corpos.accent.hex, derivedFrom: "corpos.accent = slate (Kapı 4)" };
      }
      if (scope === "corpos" && key === "accent_light") {
        return { value: FAZ0_ANCHORS.corpos.accent_light.hex, derivedFrom: "corpos.accent_light" };
      }
      throw new Error(`computeAuto: bilinmeyen accent key '${key}' in ${scope}`);
    }
    // Non-color kategoriler — saf öneri (panel UX'i için)
    case "font-family": {
      return { value: "system-ui, -apple-system, sans-serif", derivedFrom: "system stack default" };
    }
    case "font-size": {
      // Modular scale (oran 1.2). key örn: "size_md" → derive
      const baseRem = 1.0;
      const ratio = 1.2;
      const stepMap: Record<string, number> = {
        size_xs: -2, size_sm: -1, size_md: 0, size_lg: 1, size_xl: 2, size_2xl: 3, size_3xl: 4,
      };
      const step = stepMap[key];
      if (step == null) throw new Error(`computeAuto: bilinmeyen font-size key '${key}'`);
      const val = baseRem * Math.pow(ratio, step);
      return { value: `${val.toFixed(3)}rem`, derivedFrom: `modular scale ratio ${ratio}^${step}` };
    }
    case "font-weight": {
      const weightMap: Record<string, number> = {
        weight_regular: 400, weight_medium: 500, weight_semibold: 600, weight_bold: 700,
      };
      const w = weightMap[key];
      if (w == null) throw new Error(`computeAuto: bilinmeyen font-weight key '${key}'`);
      return { value: w, derivedFrom: "static weight ramp" };
    }
    case "radius": {
      const rMap: Record<string, string> = {
        radius_sm: "4px", radius_md: "8px", radius_lg: "12px", radius_xl: "16px", radius_full: "9999px",
      };
      const r = rMap[key];
      if (r == null) throw new Error(`computeAuto: bilinmeyen radius key '${key}'`);
      return { value: r, derivedFrom: "consistent radius ramp" };
    }
    case "shadow": {
      const sMap: Record<string, string> = {
        shadow_sm: "0 1px 2px rgba(0,0,0,0.20)",
        shadow_md: "0 4px 12px rgba(0,0,0,0.30)",
        shadow_lg: "0 10px 30px -10px rgba(0,0,0,0.40)",
      };
      const s = sMap[key];
      if (s == null) throw new Error(`computeAuto: bilinmeyen shadow key '${key}'`);
      return { value: s, derivedFrom: "consistent shadow ramp" };
    }
  }
}
