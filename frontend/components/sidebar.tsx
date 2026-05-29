"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import {
  LayoutDashboard,
  Users,
  Receipt,
  Bell,
  TrendingUp,
  Building2,
  Settings,
  LogOut,
  ChevronsLeft,
  ChevronsRight,
  Command,
  HelpCircle,
} from "lucide-react";
import { useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { Logomark, Wordmark } from "@/components/brand/logomark";
import { Badge } from "@/components/ui/badge";
import { ThemeToggle } from "@/components/theme-toggle";
import { cn } from "@/lib/cn";

type NavItem = {
  href: string;
  label: string;
  icon: typeof LayoutDashboard;
  module?: "corpos" | "finos";
  badge?: string;
};

const NAV: { group: string; items: NavItem[] }[] = [
  {
    group: "Genel",
    items: [
      { href: "/dashboard",  label: "Gösterge Paneli", icon: LayoutDashboard },
    ],
  },
  {
    group: "CorpOS",
    items: [
      { href: "/customers",  label: "Müşteriler", icon: Users, module: "corpos" },
      { href: "/companies",  label: "Şirketler",  icon: Building2, module: "corpos" },
    ],
  },
  {
    group: "FinOS",
    items: [
      { href: "/invoices",     label: "Faturalar",     icon: Receipt, module: "finos" },
      { href: "/cashflow",     label: "Nakit Akışı",   icon: TrendingUp, module: "finos" },
      { href: "/notifications",label: "Bildirimler",   icon: Bell, module: "finos", badge: "yeni" },
    ],
  },
  {
    group: "Hesap",
    items: [
      { href: "/settings",     label: "Ayarlar",       icon: Settings },
    ],
  },
];

export function Sidebar({
  onOpenCommand,
}: {
  onOpenCommand?: () => void;
}) {
  const pathname = usePathname();
  const { logout } = useAuth();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      className={cn(
        "relative flex h-screen shrink-0 flex-col border-r border-aq-mist/60",
        "bg-aq-cosmos/40 backdrop-blur-2xl transition-[width] duration-300 ease-quantum",
        collapsed ? "w-[68px]" : "w-[248px]",
      )}
    >
      {/* Brand */}
      <div className={cn("flex items-center gap-3 px-4 py-5", collapsed && "justify-center px-2")}>
        <Logomark size={28} />
        {!collapsed && <Wordmark />}
      </div>

      {/* Command palette trigger */}
      {!collapsed && (
        <button
          onClick={onOpenCommand}
          className={cn(
            "mx-3 mb-3 flex items-center gap-2 rounded-md border border-aq-mist/40",
            "px-3 py-1.5 text-xs text-aq-dust hover:text-foreground",
            "hover:border-aq-quantum/40 hover:bg-aq-quantum/5 transition-all ease-quantum",
          )}
        >
          <Command className="h-3.5 w-3.5" />
          <span>Hızlı arama</span>
          <kbd className="ml-auto rounded bg-aq-mist/60 px-1.5 py-0.5 font-mono text-[10px]">
            ⌘K
          </kbd>
        </button>
      )}

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-2">
        {NAV.map((group) => (
          <div key={group.group} className="mb-4">
            {!collapsed && (
              <p className="px-3 pb-1.5 text-[10px] font-medium uppercase tracking-wider text-aq-trace">
                {group.group}
              </p>
            )}
            <ul className="space-y-0.5">
              {group.items.map((item) => {
                const active = pathname?.startsWith(item.href);
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      className={cn(
                        "group relative flex items-center gap-3 rounded-md px-3 py-2",
                        "text-sm transition-all duration-200 ease-quantum",
                        active
                          ? "bg-aq-quantum/15 text-aq-neutron"
                          : "text-aq-dust hover:bg-aq-mist/40 hover:text-foreground",
                        collapsed && "justify-center",
                      )}
                      title={collapsed ? item.label : undefined}
                    >
                      {active && (
                        <motion.span
                          layoutId="sidebar-active"
                          className="absolute inset-y-1 left-0 w-0.5 rounded-full bg-aq-quantum"
                          transition={{ duration: 0.35, ease: [0.32, 0.72, 0, 1] }}
                        />
                      )}
                      <item.icon
                        className={cn("h-4 w-4 shrink-0", active && "text-aq-quantum-2")}
                      />
                      {!collapsed && (
                        <>
                          <span className="flex-1">{item.label}</span>
                          {item.badge && (
                            <Badge tone="primary" className="px-1.5 py-0 text-[9px]">
                              {item.badge}
                            </Badge>
                          )}
                        </>
                      )}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div className="border-t border-aq-mist/40 p-2 space-y-0.5">
        {/* B5: Tema değiştirici (dashboard için) */}
        <div
          className={cn(
            "flex items-center px-3 py-2",
            collapsed ? "justify-center" : "justify-between",
          )}
        >
          {!collapsed && (
            <span className="text-xs text-aq-dust">Tema</span>
          )}
          <ThemeToggle />
        </div>
        <FooterItem icon={HelpCircle} label="Yardım" collapsed={collapsed} />
        <button
          onClick={logout}
          className={cn(
            "w-full flex items-center gap-3 rounded-md px-3 py-2 text-sm",
            "text-aq-dust hover:bg-aq-fission/10 hover:text-aq-fission transition-all",
            collapsed && "justify-center",
          )}
          title={collapsed ? "Çıkış" : undefined}
        >
          <LogOut className="h-4 w-4 shrink-0" />
          {!collapsed && <span>Çıkış yap</span>}
        </button>
      </div>

      {/* Collapse handle */}
      <button
        onClick={() => setCollapsed((c) => !c)}
        className={cn(
          "absolute -right-3 top-20 grid h-6 w-6 place-items-center",
          "rounded-full border border-aq-mist/60 bg-aq-cosmos text-aq-dust",
          "hover:text-foreground hover:border-aq-quantum/60 transition-all",
        )}
        aria-label={collapsed ? "Genişlet" : "Daralt"}
      >
        {collapsed ? <ChevronsRight className="h-3 w-3" /> : <ChevronsLeft className="h-3 w-3" />}
      </button>
    </aside>
  );
}

function FooterItem({
  icon: Icon,
  label,
  collapsed,
}: {
  icon: typeof Settings;
  label: string;
  collapsed: boolean;
}) {
  return (
    <button
      className={cn(
        "w-full flex items-center gap-3 rounded-md px-3 py-2 text-sm",
        "text-aq-dust hover:bg-aq-mist/40 hover:text-foreground transition-all",
        collapsed && "justify-center",
      )}
      title={collapsed ? label : undefined}
    >
      <Icon className="h-4 w-4 shrink-0" />
      {!collapsed && <span>{label}</span>}
    </button>
  );
}
