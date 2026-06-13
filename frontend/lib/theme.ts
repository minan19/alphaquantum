/**
 * Design Token Programı — Faz 7 · Theme cookie helpers.
 *
 * Tema çereze yazılır (1 yıl, lax samesite). Layout SSR'da çerezi okuyup
 * `<html data-theme=...>` set eder → ilk boyamada doğru tema = NO-FLASH.
 *
 * Toggle'da hem çerez hem `document.documentElement.dataset.theme` güncellenir
 * (anlık görünüm). Hidrasyon snapshot'la senkron.
 */

export type Theme = "dark" | "light";

export const THEME_COOKIE = "aq.theme";
export const VALID_THEMES: readonly Theme[] = ["dark", "light"];

export function isValidTheme(v: unknown): v is Theme {
  return v === "dark" || v === "light";
}

/** Browser tarafında çerezi yaz + dataset'e bas. Server'da no-op. */
export function setThemeCookie(theme: Theme): void {
  if (typeof document === "undefined") return;
  // 1 yıl, Lax (CSRF güvenli, üçüncü-parti iframe'de değişmez).
  const oneYear = 60 * 60 * 24 * 365;
  document.cookie = `${THEME_COOKIE}=${theme}; Path=/; Max-Age=${oneYear}; SameSite=Lax`;
  document.documentElement.dataset.theme = theme;
  // shadcn .light class'ı uyumu — Tailwind dark variant'ı dark mod tabanlı.
  if (theme === "light") {
    document.documentElement.classList.add("light");
  } else {
    document.documentElement.classList.remove("light");
  }
}

/** Browser tarafında çerezi oku — yoksa null. */
export function readThemeCookieClient(): Theme | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(
    new RegExp(`(?:^|;\\s*)${THEME_COOKIE}=([^;]+)`),
  );
  if (!match) return null;
  return isValidTheme(match[1]) ? match[1] : null;
}

/**
 * Faz 7 — 3-state (light/dark/system) tema seçim tipi.
 * Cookie tek-kaynak; UI'lar için ortak yer.
 */
export type ThemeChoice = "light" | "dark" | "system";

/** Sistem teması (prefers-color-scheme). SSR/no-window → "dark" varsayılan. */
export function systemTheme(): Theme {
  if (typeof window === "undefined") return "dark";
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

export function resolveChoice(choice: ThemeChoice): Theme {
  return choice === "system" ? systemTheme() : choice;
}
