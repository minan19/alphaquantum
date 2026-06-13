"use client";

/**
 * Faz 7 — Cookie-tabanlı useTheme hook'u.
 *
 * Tek-kaynak: çerez. Mount sonrası çerezi okur; setTheme cookie + dataset +
 * class günceller. SSR'da choice "system" döner (layout zaten data-theme'i
 * çerezden set ettiği için ilk boyamada doğru tema).
 */
import { useEffect, useState } from "react";

import {
  isValidTheme,
  readThemeCookieClient,
  resolveChoice,
  setThemeCookie,
  systemTheme,
  type Theme,
  type ThemeChoice,
} from "@/lib/theme";

export interface UseThemeReturn {
  /** Kullanıcı seçimi (light/dark/system). Mount edilmeden önce SSR-güvenli: "system". */
  theme: ThemeChoice;
  /** Çözümlenmiş tema (system → matchMedia). Render kararı için kullan. */
  resolvedTheme: Theme;
  /** Cookie + dataset + class günceller. */
  setTheme: (next: ThemeChoice) => void;
  /** Hidrasyon tamamlandı mı (SSR placeholder UI'ları için). */
  mounted: boolean;
}

export function useTheme(): UseThemeReturn {
  const [mounted, setMounted] = useState(false);
  const [choice, setChoice] = useState<ThemeChoice>("system");

  useEffect(() => {
    setMounted(true);
    const fromCookie = readThemeCookieClient();
    setChoice(fromCookie ?? "dark");
  }, []);

  const setTheme = (next: ThemeChoice) => {
    setChoice(next);
    setThemeCookie(resolveChoice(next));
  };

  const resolvedTheme: Theme =
    mounted
      ? resolveChoice(choice)
      : // SSR/pre-mount: pessimistic "dark" — layout zaten cookie ile gerçeği basıyor.
        "dark";

  return { theme: choice, resolvedTheme, setTheme, mounted };
}

// Yardımcı re-export'lar — useTheme + helpers tek dosyadan.
export { isValidTheme, resolveChoice, setThemeCookie, systemTheme };
export type { Theme, ThemeChoice };
