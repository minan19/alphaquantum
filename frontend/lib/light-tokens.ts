/**
 * Design Token Programı — Faz 7 · Light tema token üreticisi.
 *
 * Faz 3 motorunu (`buildCorePalette` / `buildModulePalette`) light anchor'larla
 * çalıştırır ve scope başına `{key: value}` sözlüklerini döndürür.
 *
 * KRİTİK: Bu modül DEĞER SAYI ÜRETMEZ — yalnız motoru çağırır. Foundation
 * kilidi (Faz 0 anchor'lar) tek doğruluk kaynağı. Elle uydurulan light değeri
 * YOKTUR; her değer hesaplanır.
 */
import {
  buildCorePalette,
  buildModulePalette,
  type CorePalette,
  type ModulePalette,
} from "@/lib/token-auto";
import type { Scope, ModuleScope } from "@/lib/tokens";

export type LightTokenMap = Record<string, string | number>;

function corePaletteToMap(palette: CorePalette): LightTokenMap {
  // CorePalette'in `theme` alanı CSS'e gitmez; geri kalan tüm string alanlar token.
  const { theme: _theme, ...tokens } = palette;
  return tokens as unknown as LightTokenMap;
}

function modulePaletteToMap(palette: ModulePalette): LightTokenMap {
  const { scope: _scope, link_back, cta_text_weight, on_brand, accent_light, ...rest } = palette;
  const out: LightTokenMap = { ...(rest as unknown as LightTokenMap) };
  if (link_back !== null && link_back !== undefined) out.link_back = link_back;
  if (typeof cta_text_weight === "number") out.cta_text_weight = cta_text_weight;
  if (typeof on_brand === "string") out.on_brand = on_brand;
  if (typeof accent_light === "string") out.accent_light = accent_light;
  return out;
}

/** Light core palette (Faz 3 motorundan). */
export function lightCoreTokens(): LightTokenMap {
  return corePaletteToMap(buildCorePalette("light"));
}

/** Light modül palette (verilen scope için). */
export function lightModuleTokens(scope: ModuleScope): LightTokenMap {
  const core = buildCorePalette("light");
  return modulePaletteToMap(buildModulePalette(scope, core, "light"));
}

/** Faz 2 ile uyumlu: scope'a göre döndürür (core ya da modül). */
export function lightTokensFor(scope: Scope): LightTokenMap {
  if (scope === "core") return lightCoreTokens();
  return lightModuleTokens(scope);
}
