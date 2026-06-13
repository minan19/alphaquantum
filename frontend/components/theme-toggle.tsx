"use client";

/**
 * B5: Dark/Light mode toggle.
 *
 * next-themes wrapper. UX kararları:
 *  - Smooth sun ↔ moon ikon morph (Framer Motion)
 *  - System preference takip seçeneği (3-state: light/dark/system)
 *  - Premium hover state (border accent + subtle glow)
 *  - a11y: aria-label, focus-visible ring
 *  - SSR-safe: mounted guard ile hydration mismatch önleme
 *
 * Tasarım doc'undaki "Dark/Light Mode Geçiş Animasyonu" (K9.3) hayata geçer:
 *   - Toggle'a tıkla → tema yumuşak geçer (CSS variables transition)
 *   - İkon morph (güneş ↔ ay) Framer Motion ile
 *   - prefers-reduced-motion: instant geçiş (animation kapalı)
 */
import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Moon, Sun, Monitor } from "lucide-react";
import { cn } from "@/lib/cn";
import { readThemeCookieClient, setThemeCookie, type Theme as AqTheme } from "@/lib/theme";

type ThemeChoice = "light" | "dark" | "system";

/** Sistem teması (prefers-color-scheme). SSR'da yok → "dark" varsayılan. */
function systemTheme(): AqTheme {
  if (typeof window === "undefined") return "dark";
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

function resolveChoice(choice: ThemeChoice): AqTheme {
  return choice === "system" ? systemTheme() : choice;
}

interface ThemeToggleProps {
  className?: string;
  /** Compact: sadece toggle (sistem yok). False: 3-state segmented control. */
  compact?: boolean;
}

export function ThemeToggle({ className, compact = true }: ThemeToggleProps) {
  // Faz 7: cookie tek-kaynak. SSR'da hangi tema set'lendi → o.
  const [mounted, setMounted] = useState(false);
  const [choice, setChoice] = useState<ThemeChoice>("dark");

  useEffect(() => {
    setMounted(true);
    // Çerez varsa onu kullan; yoksa dark default.
    const fromCookie = readThemeCookieClient();
    setChoice(fromCookie ?? "dark");
  }, []);

  const apply = (next: ThemeChoice) => {
    setChoice(next);
    setThemeCookie(resolveChoice(next));
  };

  // SSR placeholder: hydration mismatch önle
  if (!mounted) {
    return (
      <div
        className={cn(
          "h-9 w-9 rounded-full border border-aq-mist/40 bg-aq-orbital/40",
          className,
        )}
        aria-hidden="true"
      />
    );
  }

  if (compact) {
    // Compact: single toggle between light ↔ dark, ignoring system
    const isDark = resolveChoice(choice) === "dark";
    const nextLabel = isDark ? "Açık temaya geç" : "Koyu temaya geç";

    return (
      <button
        type="button"
        onClick={() => apply(isDark ? "light" : "dark")}
        aria-label={nextLabel}
        title={nextLabel}
        className={cn(
          "relative inline-flex h-9 w-9 items-center justify-center rounded-full",
          "border border-aq-mist/40 bg-aq-orbital/40 backdrop-blur-sm",
          "text-aq-dust transition-all duration-300",
          "hover:border-aq-quantum/40 hover:text-foreground hover:shadow-quantum",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-aq-quantum focus-visible:ring-offset-2 focus-visible:ring-offset-aq-void",
          className,
        )}
      >
        <AnimatePresence mode="wait" initial={false}>
          {isDark ? (
            <motion.span
              key="moon"
              initial={{ opacity: 0, rotate: -90, scale: 0.8 }}
              animate={{ opacity: 1, rotate: 0, scale: 1 }}
              exit={{ opacity: 0, rotate: 90, scale: 0.8 }}
              transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
              className="absolute inset-0 flex items-center justify-center"
            >
              <Moon className="h-4 w-4" />
            </motion.span>
          ) : (
            <motion.span
              key="sun"
              initial={{ opacity: 0, rotate: 90, scale: 0.8 }}
              animate={{ opacity: 1, rotate: 0, scale: 1 }}
              exit={{ opacity: 0, rotate: -90, scale: 0.8 }}
              transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
              className="absolute inset-0 flex items-center justify-center"
            >
              <Sun className="h-4 w-4" />
            </motion.span>
          )}
        </AnimatePresence>
      </button>
    );
  }

  // 3-state segmented control: Light | System | Dark
  type ThemeOption = "light" | "system" | "dark";
  const options: { value: ThemeOption; label: string; icon: typeof Sun }[] = [
    { value: "light", label: "Açık", icon: Sun },
    { value: "system", label: "Sistem", icon: Monitor },
    { value: "dark", label: "Koyu", icon: Moon },
  ];

  return (
    <div
      role="radiogroup"
      aria-label="Tema seçimi"
      className={cn(
        "inline-flex items-center gap-0.5 rounded-full border border-aq-mist/40 bg-aq-orbital/40 backdrop-blur-sm p-0.5",
        className,
      )}
    >
      {options.map((opt) => {
        const Icon = opt.icon;
        const active = choice === opt.value;
        return (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => apply(opt.value)}
            className={cn(
              "relative inline-flex items-center gap-1.5 rounded-full px-2.5 py-1.5",
              "text-xs font-medium transition-colors duration-200",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-aq-quantum focus-visible:ring-offset-1 focus-visible:ring-offset-aq-void",
              active
                ? "text-foreground"
                : "text-aq-dust hover:text-foreground",
            )}
          >
            {active && (
              <motion.span
                layoutId="theme-toggle-active"
                className="absolute inset-0 rounded-full bg-aq-quantum/20 ring-1 ring-aq-quantum/40"
                transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
              />
            )}
            <Icon className="relative h-3.5 w-3.5" />
            <span className="relative">{opt.label}</span>
          </button>
        );
      })}
    </div>
  );
}
