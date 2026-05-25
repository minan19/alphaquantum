"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

const NAV = [
  { href: "/dashboard", label: "Gösterge Paneli" },
  { href: "/customers", label: "Müşteriler" },
  { href: "/invoices", label: "Faturalar" },
];

export function Sidebar() {
  const pathname = usePathname();
  const { logout } = useAuth();

  return (
    <aside className="flex h-screen w-56 flex-col bg-brand-700 text-white">
      <div className="border-b border-brand-600 px-6 py-4">
        <h1 className="text-lg font-bold">Alpha Quantum</h1>
        <p className="text-xs text-brand-100">CorpOS · FinOS</p>
      </div>

      <nav className="flex-1 space-y-1 px-3 py-4">
        {NAV.map((item) => {
          const active = pathname?.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={[
                "block rounded-md px-3 py-2 text-sm transition-colors",
                active
                  ? "bg-brand-600 font-medium"
                  : "text-brand-100 hover:bg-brand-600 hover:text-white",
              ].join(" ")}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>

      <button
        onClick={logout}
        className="border-t border-brand-600 px-6 py-3 text-left text-sm text-brand-100 hover:bg-brand-600 hover:text-white"
      >
        Çıkış yap
      </button>
    </aside>
  );
}
