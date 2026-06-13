"use client";

/**
 * Faz 7: Cookie-tabanlı tema sağlayıcısı (pass-through).
 *
 * Tek-kaynak çerez. SSR: layout cookie'yi okur, <html data-theme + class>
 * set eder. Client: ilk render'da DOM zaten doğru; ThemeToggle çerez +
 * dataset günceller (anlık CSS variable swap, no-flash, no-jank).
 */
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
