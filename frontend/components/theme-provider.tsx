"use client";

/**
 * Faz 7: Cookie-tabanlı tema sağlayıcısı.
 *
 * next-themes'i KULLANMIYORUZ — mount'unda localStorage'a bakıp SSR'da
 * cookie'den okunan değeri eziyordu (FLASH). Tek-kaynak: çerez.
 *
 * SSR: layout cookie'yi okur, <html data-theme + class={'light'}> set eder.
 * Client: ilk render'da DOM zaten doğru. ThemeToggle setThemeCookie ile çerez
 * + dataset günceller; layout sayfayı yeniden render etmez ama dataset/class
 * değişimi anlık CSS variable swap'ı tetikler (no-flash, no-jank).
 */
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
