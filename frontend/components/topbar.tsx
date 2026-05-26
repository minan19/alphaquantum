"use client";

import { Bell, Command, Moon, Sun, Monitor } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/cn";

export function Topbar({ onOpenCommand }: { onOpenCommand: () => void }) {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  const cycleTheme = () => {
    setTheme(theme === "dark" ? "light" : theme === "light" ? "system" : "dark");
  };

  const ThemeIcon = !mounted
    ? Monitor
    : theme === "dark" ? Moon : theme === "light" ? Sun : Monitor;

  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-aq-mist/40 bg-aq-cosmos/30 px-6 backdrop-blur-xl">
      {/* Breadcrumb space (per-page can portal here) */}
      <div className="flex-1" id="topbar-breadcrumb-slot" />

      {/* Quick search trigger */}
      <button
        onClick={onOpenCommand}
        className={cn(
          "hidden sm:flex items-center gap-2 rounded-md border border-aq-mist/40 bg-aq-orbital/40",
          "px-3 py-1.5 text-xs text-aq-dust hover:text-foreground hover:border-aq-quantum/40",
          "transition-all ease-quantum",
        )}
      >
        <Command className="h-3.5 w-3.5" />
        <span>Hızlı arama…</span>
        <kbd className="ml-2 rounded bg-aq-mist/60 px-1.5 py-0.5 font-mono text-[10px]">⌘K</kbd>
      </button>

      {/* Notifications */}
      <Button variant="ghost" size="icon" className="relative" aria-label="Bildirimler">
        <Bell className="h-4 w-4" />
        <span className="absolute right-2 top-2 h-1.5 w-1.5 rounded-full bg-aq-fission shadow-[0_0_8px_currentColor] animate-pulse" />
      </Button>

      {/* Theme switcher */}
      <Button
        variant="ghost"
        size="icon"
        onClick={cycleTheme}
        aria-label={`Tema: ${theme}`}
        title={`Tema: ${theme ?? "system"}`}
      >
        <ThemeIcon className="h-4 w-4" />
      </Button>

      {/* Profile chip */}
      <div className="flex items-center gap-2 rounded-md border border-aq-mist/40 bg-aq-orbital/40 px-2 py-1">
        <div className="grid h-7 w-7 place-items-center rounded-full bg-gradient-to-br from-aq-quantum to-aq-plasma text-xs font-semibold text-white">
          AD
        </div>
        <div className="hidden sm:flex flex-col leading-tight">
          <span className="text-xs font-medium">Yönetici</span>
          <Badge tone="primary" className="px-1.5 py-0 text-[9px] font-mono" withDot>
            admin
          </Badge>
        </div>
      </div>
    </header>
  );
}
