/**
 * Design Token Programı — Faz 6 · CustomFont SSR fetch + URL helpers.
 *
 * SSR/RSC tarafında font listesini çeker (cache + 'design-tokens' tag'i ile
 * Faz 5 revalidateTag zinciri'ne dahil). Yardımcılar: Google Fonts CSS URL
 * inşası + format/MIME tablosu.
 *
 * Hata durumunda boş liste döner — fallback zinciri (var(--font-inter) →
 * 'Inter' → system-ui) bozulmaz.
 */
import { unstable_cache } from "next/cache";

import type { Scope } from "@/lib/tokens";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? process.env.AQ_BACKEND_URL ?? "http://127.0.0.1:8000";

export type FontSource = "google" | "upload";
export type FontFormat = "woff2" | "woff" | "ttf" | "otf";

export interface CustomFont {
  id: number;
  scope: Scope;
  family: string;
  source: FontSource;
  css_url: string | null;
  format: string | null;
  weight: string | null;
  style: string | null;
  is_default: boolean;
  created_at: number;
}

export interface CustomFontListResponse {
  scope_filter: Scope | null;
  fonts: CustomFont[];
}

async function fetchFontsRaw(): Promise<CustomFontListResponse> {
  try {
    const res = await fetch(`${API_URL}/api/v1/fonts`, { cache: "no-store" });
    if (!res.ok) return { scope_filter: null, fonts: [] };
    return (await res.json()) as CustomFontListResponse;
  } catch {
    // Backend ulaşılmazsa fallback zinciri ile çerçeve fontu kalır.
    return { scope_filter: null, fonts: [] };
  }
}

/** Cache'li font listesi (tag: 'design-tokens').
 *
 *  Dev: cache bypass — backend ekleme sonrası dev sunucusunun stale-state
 *  tutmasını engeller. Prod: unstable_cache aktif, revalidateTag(design-tokens)
 *  ile invalidate edilir (Faz 5 zinciri).
 */
export const getFonts =
  process.env.NODE_ENV === "production"
    ? unstable_cache(fetchFontsRaw, ["custom-fonts:v1"], { tags: ["design-tokens"] })
    : fetchFontsRaw;

/** CSS `font-format()` ifadesi. */
export function cssFormatHint(fmt: string | null): string {
  switch (fmt) {
    case "woff2":
      return "woff2";
    case "woff":
      return "woff";
    case "ttf":
      return "truetype";
    case "otf":
      return "opentype";
    default:
      return "";
  }
}

/** Google Fonts css2 URL inşası — display=swap ZORUNLU (FOIT yerine FOUT). */
export function buildGoogleFontUrl(
  family: string,
  weights: number[] = [400, 500, 600, 700],
): string {
  const fam = encodeURIComponent(family.trim()).replace(/%20/g, "+");
  const wghts = [...new Set(weights)]
    .sort((a, b) => a - b)
    .join(";");
  return `https://fonts.googleapis.com/css2?family=${fam}:wght@${wghts}&display=swap`;
}

/** Faz 1 valid scopes — server tarafında reuse. */
export const VALID_SCOPES = ["core", "aq", "finos", "corpos"] as const;
