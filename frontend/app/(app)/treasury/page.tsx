"use client";

/**
 * Treasury Dashboard — T1: multi-bank konsolide bakiye.
 * Holding CFO için tüm hesapların tek ekrandan görünümü.
 * Backend: app/routers/treasury.py + TreasuryEngine.
 */

import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  Building2,
  Coins,
  Landmark,
  TrendingUp,
  Wallet,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  fetchTreasuryAccounts,
  fetchTreasurySummary,
  type TreasuryAccount,
  type TreasurySummary,
} from "@/lib/treasury-api";
import { ApiError } from "@/lib/api";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/cn";

function fmtTRY(n: number): string {
  return new Intl.NumberFormat("tr-TR", {
    style: "currency",
    currency: "TRY",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(n);
}

function fmtCurrency(n: number, ccy: string): string {
  try {
    return new Intl.NumberFormat("tr-TR", {
      style: "currency",
      currency: ccy,
      minimumFractionDigits: 0,
      maximumFractionDigits: 2,
    }).format(n);
  } catch {
    return `${n.toFixed(2)} ${ccy}`;
  }
}

const CURRENCY_COLORS: Record<string, string> = {
  TRY: "rgb(91 71 251)",
  USD: "rgb(6 182 212)",
  EUR: "rgb(245 158 11)",
  GBP: "rgb(124 96 255)",
  CHF: "rgb(34 197 94)",
};

const FALLBACK_COLORS = [
  "rgb(91 71 251)",
  "rgb(6 182 212)",
  "rgb(245 158 11)",
  "rgb(124 96 255)",
  "rgb(34 197 94)",
  "rgb(239 68 68)",
];

const ACCOUNT_TYPE_LABEL: Record<TreasuryAccount["account_type"], string> = {
  vadesiz: "Vadesiz",
  vadeli: "Vadeli",
  kredi: "Kredi",
  pos: "POS",
  doviz: "Döviz",
  diğer: "Diğer",
};

const ACCOUNT_TYPE_TONE: Record<
  TreasuryAccount["account_type"],
  "primary" | "info" | "success" | "warn" | "critical" | "neutral"
> = {
  vadesiz: "primary",
  vadeli: "info",
  kredi: "critical",
  pos: "neutral",
  doviz: "info",
  diğer: "neutral",
};

export default function TreasuryPage() {
  const [summary, setSummary] = useState<TreasurySummary | null>(null);
  const [accounts, setAccounts] = useState<TreasuryAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([fetchTreasurySummary(), fetchTreasuryAccounts()])
      .then(([s, a]) => {
        if (cancelled) return;
        setSummary(s);
        setAccounts(a);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        const msg =
          e instanceof ApiError
            ? `${e.status}: ${e.message}`
            : e instanceof Error
              ? e.message
              : "Bilinmeyen hata";
        setError(msg);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const currencyChartData = useMemo(() => {
    if (!summary) return [];
    return Object.entries(summary.by_currency)
      .map(([ccy, amount]) => ({
        name: ccy,
        value: amount,
        color: CURRENCY_COLORS[ccy] ?? FALLBACK_COLORS[0],
      }))
      .sort((a, b) => b.value - a.value);
  }, [summary]);

  const bankChartData = useMemo(() => {
    if (!summary) return [];
    return summary.by_bank.slice(0, 8).map((b, i) => ({
      bank: b.bank_name,
      bakiye: b.total_in_try,
      color: FALLBACK_COLORS[i % FALLBACK_COLORS.length],
    }));
  }, [summary]);

  // ---- error state ----------------------------------------------------------
  if (error) {
    return (
      <div className="p-6 space-y-4">
        <header>
          <h1 className="text-2xl font-display font-semibold">Treasury</h1>
          <p className="text-sm text-aq-dust">Multi-bank konsolide bakiye paneli</p>
        </header>
        <Card>
          <CardHeader>
            <CardTitle className="text-aq-fission">Veri yüklenemedi</CardTitle>
            <CardDescription>{error}</CardDescription>
          </CardHeader>
          <CardContent className="text-sm text-aq-dust">
            Backend bağlantınızı ve oturum tokenınızı kontrol edin. <br />
            <code className="text-xs">GET /api/v1/treasury/summary</code>
          </CardContent>
        </Card>
      </div>
    );
  }

  // ---- loading state --------------------------------------------------------
  if (loading || !summary) {
    return (
      <div className="p-6 space-y-6">
        <header>
          <Skeleton className="h-8 w-48" />
          <Skeleton className="mt-2 h-4 w-72" />
        </header>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
        <Skeleton className="h-80" />
        <Skeleton className="h-64" />
      </div>
    );
  }

  // ---- happy path -----------------------------------------------------------
  const totalAccounts = summary.account_count;
  const distinctCurrencies = Object.keys(summary.by_currency).length;
  const topBank = summary.by_bank[0];

  return (
    <div className="p-6 space-y-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-display font-semibold">Treasury</h1>
          <p className="text-sm text-aq-dust">
            Multi-bank konsolide bakiye · {totalAccounts} hesap ·{" "}
            {distinctCurrencies} para birimi
          </p>
        </div>
        {summary.last_synced_at && (
          <Badge tone="neutral" className="text-xs">
            Son senkron:{" "}
            {new Date(summary.last_synced_at * 1000).toLocaleString("tr-TR")}
          </Badge>
        )}
      </header>

      {/* KPI cards */}
      <motion.section
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4"
      >
        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="flex items-center gap-2">
              <Wallet className="h-4 w-4" />
              Toplam (TRY karşılığı)
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-display font-semibold">
              {fmtTRY(summary.total_in_try)}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="flex items-center gap-2">
              <Landmark className="h-4 w-4" />
              Hesap Sayısı
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-display font-semibold">
              {totalAccounts}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="flex items-center gap-2">
              <Coins className="h-4 w-4" />
              Para Birimi
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-display font-semibold">
              {distinctCurrencies}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="flex items-center gap-2">
              <Building2 className="h-4 w-4" />
              En Büyük Banka
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-base font-display font-semibold truncate">
              {topBank?.bank_name ?? "—"}
            </div>
            <div className="text-xs text-aq-dust mt-1">
              {topBank ? fmtTRY(topBank.total_in_try) : ""}
            </div>
          </CardContent>
        </Card>
      </motion.section>

      {/* Charts */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Para birimi dağılımı</CardTitle>
            <CardDescription>TRY karşılığına göre</CardDescription>
          </CardHeader>
          <CardContent className="h-64">
            {currencyChartData.length === 0 ? (
              <p className="text-sm text-aq-dust">Veri yok</p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={currencyChartData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={80}
                    innerRadius={50}
                    paddingAngle={2}
                  >
                    {currencyChartData.map((entry, i) => (
                      <Cell key={i} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(v: number) => fmtTRY(v)}
                    contentStyle={{
                      background: "rgb(var(--card))",
                      border: "1px solid rgb(var(--border))",
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Bankaya göre bakiye</CardTitle>
            <CardDescription>İlk 8 banka, TRY karşılığı</CardDescription>
          </CardHeader>
          <CardContent className="h-64">
            {bankChartData.length === 0 ? (
              <p className="text-sm text-aq-dust">Veri yok</p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={bankChartData} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                  <XAxis
                    type="number"
                    tickFormatter={(v) =>
                      new Intl.NumberFormat("tr-TR", {
                        notation: "compact",
                      }).format(v)
                    }
                    style={{ fontSize: 11 }}
                  />
                  <YAxis
                    type="category"
                    dataKey="bank"
                    width={100}
                    style={{ fontSize: 11 }}
                  />
                  <Tooltip
                    formatter={(v: number) => fmtTRY(v)}
                    contentStyle={{
                      background: "rgb(var(--card))",
                      border: "1px solid rgb(var(--border))",
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                  />
                  <Bar dataKey="bakiye" radius={[0, 4, 4, 0]}>
                    {bankChartData.map((entry, i) => (
                      <Cell key={i} fill={entry.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </section>

      {/* Accounts table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <TrendingUp className="h-4 w-4" />
            Hesap detayı
          </CardTitle>
          <CardDescription>{accounts.length} hesap listeleniyor</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {accounts.length === 0 ? (
            <p className="p-6 text-sm text-aq-dust">
              Henüz hesap eklenmemiş. CSV import ile başlayın:{" "}
              <code className="text-xs">
                POST /api/v1/treasury/accounts/{"{id}"}/import-csv
              </code>
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Şirket</TableHead>
                  <TableHead>Banka</TableHead>
                  <TableHead>Tip</TableHead>
                  <TableHead>Para</TableHead>
                  <TableHead className="text-right">Bakiye</TableHead>
                  <TableHead>Durum</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {accounts.map((a) => (
                  <TableRow
                    key={a.id}
                    className={cn(!a.is_active && "opacity-50")}
                  >
                    <TableCell className="font-medium">{a.company_name}</TableCell>
                    <TableCell>
                      <div>{a.bank_name}</div>
                      {a.branch && (
                        <div className="text-xs text-aq-dust">{a.branch}</div>
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge tone={ACCOUNT_TYPE_TONE[a.account_type]}>
                        {ACCOUNT_TYPE_LABEL[a.account_type]}
                      </Badge>
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {a.currency}
                    </TableCell>
                    <TableCell className="text-right font-mono tabular-nums">
                      {fmtCurrency(a.current_balance, a.currency)}
                    </TableCell>
                    <TableCell>
                      {a.is_active ? (
                        <Badge tone="success" className="text-xs">
                          Aktif
                        </Badge>
                      ) : (
                        <Badge tone="neutral" className="text-xs">
                          Pasif
                        </Badge>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
