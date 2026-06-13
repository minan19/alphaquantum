/**
 * WCAG rozet referans çözümleyici — `colors-panel`'in her token satırı için
 * doğru kontrast partneri + eşiği bulan saf fonksiyon.
 *
 * Bug fix: önceden TÜM rozetler `bg_primary`'ye karşı ölçülüyordu →
 *  - bg_primary kendi kendine: 1.00:1 FAIL (sıfır bilgi)
 *  - surface_01 vs bg_primary: ~1.22:1 FAIL (yanlış soru; ikisi de zemin)
 *  - cta_text vs bg_primary: ~18:1 AAA (yanlış soru; partner cta)
 *
 * Bu modül her token'ın ROLÜNE göre partneri seçer (key-first, sonra category)
 * ve uygun WCAG eşiğini döndürür. Referansı henüz anlamlı olmayan token'lar
 * için NÖTR ROZET döner — sahte oran üretmez.
 *
 * Kurallar ve karar tablosu PR fix/wcag-badge-reference açıklamasındadır.
 */

import { contrastRating, wcagContrast, type ContrastRating } from "@/lib/token-auto";
import type { Scope } from "@/lib/tokens";

export interface WcagInputToken {
  scope: Scope;
  key: string;
  value: string;
  category: string;
}

/** Bilgi-içeren rozet: gerçek oran + partner. */
export interface RatioBadge {
  mode: "ratio";
  ratio: number;
  rating: ContrastRating;
  /** WCAG eşik bandı — AA text (4.5) veya AA non-text/large (3.0). */
  threshold: 4.5 | 3.0;
  partnerKey: string;
  partnerValue: string;
  /** "vs --text-primary #E2E4E8" gibi tooltip metni. */
  tooltip: string;
}

/** Nötr rozet: referans bilinmiyor / Faz 7'ye bağlı / sayısal. */
export interface NeutralBadge {
  mode: "neutral";
  /** UI'da gri rozet metni ("light bağlam — Faz 7" gibi). */
  label: string;
  /** Tooltip için aynı metin. */
  tooltip: string;
}

export type WcagBadge = RatioBadge | NeutralBadge | null;

/** Kategori kümeleri — DRY. */
const SURFACE_CATEGORIES = new Set(["background", "surface"]);

function findToken(
  tokens: WcagInputToken[],
  scope: Scope,
  key: string,
): WcagInputToken | undefined {
  return tokens.find((t) => t.scope === scope && t.key === key);
}

/** "scope x" altında key varsa onu, yoksa core'da varsa core'u, yoksa undefined. */
function findScopedOrCore(
  tokens: WcagInputToken[],
  preferScope: Scope,
  key: string,
): WcagInputToken | undefined {
  return findToken(tokens, preferScope, key) ?? findToken(tokens, "core", key);
}

function makeRatio(
  fg: WcagInputToken,
  partner: WcagInputToken,
  threshold: 4.5 | 3.0,
): RatioBadge {
  const ratio = wcagContrast(fg.value, partner.value);
  return {
    mode: "ratio",
    ratio,
    rating: contrastRating(ratio),
    threshold,
    partnerKey: partner.key,
    partnerValue: partner.value,
    tooltip: `vs --${partner.key.replace(/_/g, "-")} ${partner.value}`,
  };
}

function neutral(label: string): NeutralBadge {
  return { mode: "neutral", label, tooltip: label };
}

const HEX_RE = /^#[0-9A-Fa-f]{6}$/;

/**
 * Bir token satırı için WCAG rozetini çöz.
 *
 * Karar sırası (ilk eşleşen kazanır):
 *  1. Sayısal token (cta_text_weight) → rozet yok (null).
 *  2. Geçersiz hex → rozet yok.
 *  3. text_inverse → nötr ("light bağlam — Faz 7").
 *  4. CTA/Brand dolgu (cta, cta_hover, brand, brand_hover) → cta_text (scope→core)
 *     yoksa on_brand, yoksa nötr. Eşik 4.5 (metin üstü).
 *  5. cta_text → aynı scope'taki cta (scope→core), yoksa nötr. Eşik 4.5.
 *  6. on_brand → aynı scope'taki brand, yoksa nötr. Eşik 4.5.
 *  7. *_surface (key suffix) → core text_primary. Eşik 4.5.
 *  8. category in {background, surface} → core text_primary. Eşik 4.5.
 *  9. category = text → core bg_primary. Eşik 4.5.
 *  10. accent_light özel → core text_primary (yumuşak yüzey). Eşik 4.5.
 *  11. link_back → core bg_primary. Eşik 4.5 (sekonder metin).
 *  12. category in {status, border, focus, accent} → core bg_primary. Eşik 3.0
 *      (status filled etiketler ve UI bileşenleri için non-text eşiği).
 *  13. Aksi durum → nötr ("kontrast referansı tanımsız").
 *
 * `activeScope` modül-scope'ta görüntülendiğinde partnerin tekil scope kuralını
 * etkiler (modül sekmesinde brand dolgusunun partneri aynı modülde on_brand).
 */
export function resolveWcagTarget(
  row: WcagInputToken,
  allTokens: WcagInputToken[],
  activeScope: Scope,
): WcagBadge {
  // 1, 2: sayısal / geçersiz
  if (row.key === "cta_text_weight") return null;
  if (!HEX_RE.test(row.value)) return null;

  // 3: text_inverse (light tema partneri Faz 7'de gelir)
  if (row.key === "text_inverse") {
    return neutral("light bağlam — Faz 7");
  }

  // 4: CTA / Brand dolgu
  if (row.key === "cta" || row.key === "cta_hover") {
    // Aktif modül scope'unda cta_text → core fallback → vazgeç (nötr)
    const scopeForPartner: Scope = row.scope === "core" ? activeScope : row.scope;
    const partner =
      findScopedOrCore(allTokens, scopeForPartner, "cta_text") ??
      findScopedOrCore(allTokens, scopeForPartner, "on_brand");
    if (partner) return makeRatio(row, partner, 4.5);
    return neutral("partner cta_text/on_brand henüz tanımlı değil");
  }
  if (row.key === "brand" || row.key === "brand_hover") {
    const scopeForPartner: Scope = row.scope === "core" ? activeScope : row.scope;
    const partner =
      findScopedOrCore(allTokens, scopeForPartner, "on_brand") ??
      findScopedOrCore(allTokens, scopeForPartner, "cta_text");
    if (partner) return makeRatio(row, partner, 4.5);
    return neutral("partner on_brand/cta_text henüz tanımlı değil");
  }

  // 5: CTA üstü metin
  if (row.key === "cta_text") {
    const scopeForPartner: Scope = row.scope === "core" ? activeScope : row.scope;
    const partner = findScopedOrCore(allTokens, scopeForPartner, "cta");
    if (partner) return makeRatio(row, partner, 4.5);
    return neutral("partner cta henüz tanımlı değil");
  }
  // 6: Brand üstü metin
  if (row.key === "on_brand") {
    const scopeForPartner: Scope = row.scope === "core" ? activeScope : row.scope;
    const partner = findScopedOrCore(allTokens, scopeForPartner, "brand");
    if (partner) return makeRatio(row, partner, 4.5);
    return neutral("partner brand henüz tanımlı değil");
  }

  // 7: *_surface — yumuşak yüzey
  if (row.key.endsWith("_surface")) {
    const partner = findToken(allTokens, "core", "text_primary");
    if (partner) return makeRatio(row, partner, 4.5);
    return neutral("text_primary tanımsız");
  }

  // 8: Zemin (background, surface)
  if (SURFACE_CATEGORIES.has(row.category)) {
    const partner = findToken(allTokens, "core", "text_primary");
    if (partner) return makeRatio(row, partner, 4.5);
    return neutral("text_primary tanımsız");
  }

  // 9: Metin
  if (row.category === "text") {
    const partner = findToken(allTokens, "core", "bg_primary");
    if (partner) return makeRatio(row, partner, 4.5);
    return neutral("bg_primary tanımsız");
  }

  // 10: accent_light — yumuşak yüzey (S1 onayı)
  if (row.key === "accent_light") {
    const partner = findToken(allTokens, "core", "text_primary");
    if (partner) return makeRatio(row, partner, 4.5);
    return neutral("text_primary tanımsız");
  }

  // 11: link_back — sekonder metin
  if (row.key === "link_back") {
    const partner = findToken(allTokens, "core", "bg_primary");
    if (partner) return makeRatio(row, partner, 4.5);
    return neutral("bg_primary tanımsız");
  }

  // 12: status (filled) + border + focus + accent — UI/non-text
  if (
    row.category === "status" ||
    row.category === "border" ||
    row.category === "focus" ||
    row.category === "accent"
  ) {
    const partner = findToken(allTokens, "core", "bg_primary");
    if (partner) return makeRatio(row, partner, 3.0);
    return neutral("bg_primary tanımsız");
  }

  // 13: bilinmeyen — sahte oran üretme.
  return neutral("kontrast referansı tanımsız");
}

/** Rozet eşik geçti mi? (ratio >= threshold) */
export function badgePasses(b: WcagBadge): boolean {
  return b !== null && b.mode === "ratio" && b.ratio >= b.threshold;
}
