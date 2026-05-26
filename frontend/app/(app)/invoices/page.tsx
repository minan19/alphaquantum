"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import {
  Calendar,
  CheckCircle2,
  Clock,
  Download,
  FileText,
  Plus,
  Receipt,
  Search,
  X,
} from "lucide-react";
import { ApiError, fetchCompanies, fetchInvoices, type Invoice } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/cn";

const STATUS_STYLE: Record<
  string,
  { tone: "success" | "warn" | "critical" | "primary" | "neutral"; label: string }
> = {
  paid:      { tone: "success",  label: "Ödendi"    },
  partial:   { tone: "warn",     label: "Kısmi"     },
  overdue:   { tone: "critical", label: "Gecikmiş"  },
  pending:   { tone: "primary",  label: "Bekliyor"  },
  cancelled: { tone: "neutral",  label: "İptal"     },
};

function fmt(n: number, ccy: string) {
  return new Intl.NumberFormat("tr-TR", {
    style: "currency",
    currency: ccy || "TRY",
    minimumFractionDigits: 2,
  }).format(n);
}

export default function InvoicesPage() {
  const router = useRouter();
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const companies = await fetchCompanies();
        const data = await fetchInvoices(companies[0]?.name);
        if (!cancelled) setInvoices(data.invoices);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? `API hatası (${err.status})` : "Yüklenemedi");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const filtered = useMemo(() => {
    const q = search.toLowerCase().trim();
    return invoices.filter((i) => {
      if (statusFilter !== "all" && i.status !== statusFilter) return false;
      if (!q) return true;
      return [i.invoice_number, i.title, i.currency]
        .join(" ").toLowerCase().includes(q);
    });
  }, [invoices, search, statusFilter]);

  // Stats
  const stats = useMemo(() => {
    const outstanding = invoices
      .filter((i) => !["paid", "cancelled"].includes(i.status))
      .reduce((s, i) => s + (i.amount - i.paid_amount), 0);
    const overdue = invoices.filter((i) => i.status === "overdue").length;
    const paid = invoices.filter((i) => i.status === "paid").length;
    return { outstanding, overdue, paid };
  }, [invoices]);

  return (
    <div className="space-y-6 animate-fade-in">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Badge tone="primary" withDot>FinOS</Badge>
            <span className="text-xs text-aq-trace font-mono">Collections</span>
          </div>
          <h1 className="text-3xl font-bold tracking-tight">Faturalar</h1>
          <p className="mt-1 text-sm text-aq-dust">
            {loading ? "Yükleniyor…" : `${filtered.length} kayıt`} · Açık bakiye {fmt(stats.outstanding, "TRY")}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary">
            <Download className="h-3.5 w-3.5" /> Dışa Aktar
          </Button>
          <Button>
            <Plus className="h-3.5 w-3.5" /> Yeni Fatura
          </Button>
        </div>
      </header>

      {/* Quick stats */}
      <section className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Toplam" value={invoices.length} icon={Receipt} />
        <Stat label="Bekleyen" value={invoices.filter(i => i.status === "pending").length} icon={Clock} tone="primary" />
        <Stat label="Gecikmiş" value={stats.overdue} icon={Clock} tone="alert" />
        <Stat label="Ödenen" value={stats.paid} icon={CheckCircle2} tone="ok" />
      </section>

      <Card className="overflow-hidden">
        {/* Toolbar */}
        <div className="flex flex-wrap items-center gap-2 border-b border-aq-mist/40 p-3">
          <div className="min-w-0 flex-1">
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Fatura no, başlık, para birimi…"
              leadingIcon={<Search className="h-4 w-4" />}
              trailingIcon={
                search ? (
                  <button onClick={() => setSearch("")} aria-label="Temizle">
                    <X className="h-4 w-4" />
                  </button>
                ) : null
              }
            />
          </div>
          {["all", "pending", "partial", "overdue", "paid"].map((k) => (
            <button
              key={k}
              onClick={() => setStatusFilter(k)}
              className={cn(
                "rounded-md px-3 py-1.5 text-xs font-medium transition-all",
                statusFilter === k
                  ? "bg-aq-quantum/20 text-aq-quantum-2 ring-1 ring-aq-quantum/40"
                  : "text-aq-dust hover:text-foreground hover:bg-aq-mist/40",
              )}
            >
              {k === "all" ? "Tümü" : STATUS_STYLE[k]?.label}
            </button>
          ))}
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-aq-mist/40 text-left text-[11px] font-medium uppercase tracking-wider text-aq-trace">
                <th className="px-4 py-3">Fatura</th>
                <th className="px-4 py-3 hidden md:table-cell">Vade</th>
                <th className="px-4 py-3 text-right">Tutar</th>
                <th className="px-4 py-3 text-right hidden lg:table-cell">Ödenen</th>
                <th className="px-4 py-3 text-right">Açık Bakiye</th>
                <th className="px-4 py-3">Durum</th>
              </tr>
            </thead>
            <tbody>
              {loading && [0, 1, 2, 3].map((i) => (
                <tr key={`s-${i}`} className="border-b border-aq-mist/30">
                  <td colSpan={6}><div className="m-3 h-8 rounded shimmer" /></td>
                </tr>
              ))}
              {!loading && filtered.length === 0 && (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-aq-dust">
                    <FileText className="mx-auto h-8 w-8 mb-2 opacity-40" />
                    Fatura bulunamadı.
                  </td>
                </tr>
              )}
              {!loading && filtered.map((inv, idx) => {
                const outstanding = inv.amount - inv.paid_amount;
                const meta = STATUS_STYLE[inv.status] ?? STATUS_STYLE.pending;
                const progress = inv.amount > 0 ? (inv.paid_amount / inv.amount) * 100 : 0;
                return (
                  <motion.tr
                    key={inv.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ duration: 0.3, delay: 0.02 * idx }}
                    onClick={() => router.push(`/invoices/${inv.id}`)}
                    className="border-b border-aq-mist/30 cursor-pointer transition-colors hover:bg-aq-quantum/5"
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <div className="grid h-9 w-9 place-items-center rounded-md bg-aq-orbital/60">
                          <Receipt className="h-4 w-4 text-aq-quantum-2" />
                        </div>
                        <div>
                          <div className="font-medium font-mono">
                            {inv.invoice_number || `#${inv.id}`}
                          </div>
                          <div className="text-xs text-aq-dust truncate max-w-[28ch]">
                            {inv.title}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 hidden md:table-cell">
                      <div className="flex items-center gap-1.5 text-xs text-aq-dust">
                        <Calendar className="h-3 w-3" /> {inv.due_date}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right tabular num">
                      {fmt(inv.amount, inv.currency)}
                    </td>
                    <td className="px-4 py-3 text-right hidden lg:table-cell">
                      <div className="space-y-1">
                        <div className="tabular num text-aq-dust text-xs">
                          {fmt(inv.paid_amount, inv.currency)}
                        </div>
                        <div className="h-1 w-20 ml-auto rounded-full bg-aq-mist overflow-hidden">
                          <div
                            className="h-full bg-gradient-to-r from-aq-quantum to-aq-plasma transition-all duration-700"
                            style={{ width: `${Math.min(progress, 100)}%` }}
                          />
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right tabular num font-medium">
                      {outstanding > 0
                        ? <span className="text-aq-fission">{fmt(outstanding, inv.currency)}</span>
                        : <span className="text-aq-fusion">—</span>}
                    </td>
                    <td className="px-4 py-3">
                      <Badge tone={meta.tone} withDot={meta.tone !== "neutral"}>
                        {meta.label}
                      </Badge>
                    </td>
                  </motion.tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      {error && (
        <Card className="border-aq-fission/40 bg-aq-fission/5 p-4">
          <div className="flex items-center gap-3 text-sm text-aq-fission">
            <Receipt className="h-4 w-4" />
            {error}
          </div>
        </Card>
      )}
    </div>
  );
}

function Stat({
  label, value, icon: Icon, tone = "neutral",
}: {
  label: string; value: number; icon: typeof Receipt;
  tone?: "neutral" | "primary" | "ok" | "alert";
}) {
  const toneClass = {
    neutral: "text-aq-dust ring-aq-mist/40",
    primary: "text-aq-quantum-2 ring-aq-quantum/30",
    ok:      "text-aq-fusion ring-aq-fusion/30",
    alert:   "text-aq-fission ring-aq-fission/30",
  }[tone];
  return (
    <div className={cn("flex items-center gap-3 rounded-lg bg-aq-orbital/40 px-4 py-3 ring-1", toneClass)}>
      <Icon className="h-4 w-4" />
      <div>
        <div className="text-xl font-bold tabular num">{value}</div>
        <div className="text-[10px] uppercase tracking-wider text-aq-trace">{label}</div>
      </div>
    </div>
  );
}
