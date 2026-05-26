"use client";

import { Command } from "cmdk";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  LayoutDashboard,
  Users,
  Receipt,
  Bell,
  TrendingUp,
  Building2,
  Settings,
  LogOut,
  Search,
  ArrowRight,
  Moon,
  Sun,
} from "lucide-react";
import { useTheme } from "next-themes";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/cn";

type Action = {
  id: string;
  label: string;
  hint?: string;
  icon: typeof Search;
  perform: () => void;
  group: "Sayfalar" | "Eylemler" | "Tema";
};

export function CommandPalette({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const router = useRouter();
  const { logout } = useAuth();
  const { setTheme } = useTheme();
  const [value, setValue] = useState("");

  // Keyboard: ⌘K / Ctrl+K
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        onOpenChange(!open);
      }
      if (e.key === "Escape") onOpenChange(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onOpenChange]);

  const close = () => onOpenChange(false);

  const actions: Action[] = [
    { id: "go-dashboard",  label: "Gösterge Paneli", icon: LayoutDashboard, group: "Sayfalar", perform: () => { router.push("/dashboard"); close(); } },
    { id: "go-customers",  label: "Müşteriler",      icon: Users,           group: "Sayfalar", perform: () => { router.push("/customers"); close(); } },
    { id: "go-invoices",   label: "Faturalar",       icon: Receipt,         group: "Sayfalar", perform: () => { router.push("/invoices"); close(); } },
    { id: "go-cashflow",   label: "Nakit Akışı",     icon: TrendingUp,      group: "Sayfalar", perform: () => { router.push("/cashflow"); close(); } },
    { id: "go-notifications", label: "Bildirimler",  icon: Bell,            group: "Sayfalar", perform: () => { router.push("/notifications"); close(); } },
    { id: "go-companies",  label: "Şirketler",       icon: Building2,       group: "Sayfalar", perform: () => { router.push("/companies"); close(); } },
    { id: "go-settings",   label: "Ayarlar",         icon: Settings,        group: "Sayfalar", perform: () => { router.push("/settings"); close(); } },

    { id: "theme-dark",    label: "Karanlık tema",   icon: Moon,            group: "Tema", perform: () => { setTheme("dark");  close(); } },
    { id: "theme-light",   label: "Aydınlık tema",   icon: Sun,             group: "Tema", perform: () => { setTheme("light"); close(); } },
    { id: "theme-system",  label: "Sistem teması",   icon: Sun,             group: "Tema", perform: () => { setTheme("system"); close(); } },

    { id: "logout",        label: "Çıkış yap",       icon: LogOut, hint: "Tüm oturumu kapatır", group: "Eylemler", perform: () => { logout(); close(); router.push("/login"); } },
  ];

  const grouped = actions.reduce<Record<string, Action[]>>((acc, a) => {
    (acc[a.group] ??= []).push(a);
    return acc;
  }, {});

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          className="fixed inset-0 z-50 grid place-items-start pt-[12vh]"
        >
          {/* backdrop */}
          <div
            onClick={close}
            className="absolute inset-0 bg-aq-void/70 backdrop-blur-sm"
            aria-hidden="true"
          />
          {/* dialog */}
          <motion.div
            initial={{ opacity: 0, y: -8, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.98 }}
            transition={{ duration: 0.2, ease: [0.32, 0.72, 0, 1] }}
            className="relative z-10 w-full max-w-xl mx-auto px-4"
          >
            <Command
              className={cn(
                "overflow-hidden rounded-xl border border-aq-mist/60",
                "bg-aq-cosmos/95 shadow-quantum-lg backdrop-blur-2xl",
              )}
              loop
            >
              <div className="flex items-center gap-3 border-b border-aq-mist/40 px-4">
                <Search className="h-4 w-4 text-aq-dust" />
                <Command.Input
                  placeholder="Sayfa veya eylem ara…"
                  value={value}
                  onValueChange={setValue}
                  className="h-12 w-full bg-transparent text-sm text-foreground placeholder:text-aq-trace focus:outline-none"
                />
                <kbd className="rounded bg-aq-mist/60 px-1.5 py-0.5 font-mono text-[10px] text-aq-dust">
                  ESC
                </kbd>
              </div>

              <Command.List className="max-h-96 overflow-y-auto p-2">
                <Command.Empty className="py-6 text-center text-sm text-aq-dust">
                  Sonuç yok.
                </Command.Empty>

                {Object.entries(grouped).map(([groupName, items]) => (
                  <Command.Group
                    key={groupName}
                    heading={groupName}
                    className="
                      [&_[cmdk-group-heading]]:px-3
                      [&_[cmdk-group-heading]]:py-1.5
                      [&_[cmdk-group-heading]]:text-[10px]
                      [&_[cmdk-group-heading]]:font-medium
                      [&_[cmdk-group-heading]]:uppercase
                      [&_[cmdk-group-heading]]:tracking-wider
                      [&_[cmdk-group-heading]]:text-aq-trace
                    "
                  >
                    {items.map((a) => (
                      <Command.Item
                        key={a.id}
                        value={a.label}
                        onSelect={a.perform}
                        className={cn(
                          "group flex cursor-pointer items-center gap-3 rounded-md px-3 py-2",
                          "text-sm text-aq-dust transition-colors",
                          "data-[selected=true]:bg-aq-quantum/15 data-[selected=true]:text-foreground",
                          "aria-selected:bg-aq-quantum/15 aria-selected:text-foreground",
                        )}
                      >
                        <a.icon className="h-4 w-4 shrink-0" />
                        <span className="flex-1">{a.label}</span>
                        {a.hint && (
                          <span className="text-xs text-aq-trace">{a.hint}</span>
                        )}
                        <ArrowRight className="h-3 w-3 opacity-0 transition-opacity group-data-[selected=true]:opacity-100" />
                      </Command.Item>
                    ))}
                  </Command.Group>
                ))}
              </Command.List>

              <div className="flex items-center justify-between border-t border-aq-mist/40 px-4 py-2 text-[10px] font-mono text-aq-trace">
                <span>↑ ↓ gezin</span>
                <span>↵ seç</span>
                <span>⌘K aç/kapa</span>
              </div>
            </Command>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
