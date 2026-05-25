"use client";

import { useEffect, useState } from "react";
import {
  ApiError,
  fetchCompanies,
  fetchInvoices,
  type Invoice,
} from "@/lib/api";

const STATUS_COLOR: Record<string, string> = {
  paid: "bg-signal-ok/10 text-signal-ok",
  partial: "bg-signal-warn/10 text-signal-warn",
  overdue: "bg-signal-alert/10 text-signal-alert",
  pending: "bg-brand-100 text-brand-700",
  cancelled: "bg-gray-100 text-gray-500",
};

function formatMoney(amount: number, currency: string): string {
  return new Intl.NumberFormat("tr-TR", {
    style: "currency",
    currency: currency || "TRY",
    minimumFractionDigits: 2,
  }).format(amount);
}

export default function InvoicesPage() {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const companies = await fetchCompanies();
        const company = companies[0]?.name;
        const data = await fetchInvoices(company);
        if (!cancelled) setInvoices(data.invoices);
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof ApiError
              ? `API hatası (${err.status})`
              : "Yüklenemedi",
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const totalOutstanding = invoices
    .filter((i) => !["paid", "cancelled"].includes(i.status))
    .reduce((sum, i) => sum + (i.amount - i.paid_amount), 0);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-gray-900">Faturalar</h1>
        <p className="text-sm text-gray-500">
          Toplam: {invoices.length} fatura · Açık bakiye:{" "}
          {formatMoney(totalOutstanding, "TRY")}
        </p>
      </header>

      {loading && <div className="text-gray-400">Yükleniyor…</div>}
      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {!loading && !error && invoices.length === 0 && (
        <div className="rounded-md border border-gray-200 bg-white p-6 text-center text-sm text-gray-500">
          Henüz fatura yok.
        </div>
      )}

      {!loading && invoices.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  No
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Başlık
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
                  Tutar
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
                  Ödenen
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Vade
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Durum
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {invoices.map((inv) => (
                <tr key={inv.id}>
                  <td className="px-4 py-3 text-sm text-gray-900">
                    {inv.invoice_number || `#${inv.id}`}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-900">
                    {inv.title}
                  </td>
                  <td className="px-4 py-3 text-right text-sm text-gray-900">
                    {formatMoney(inv.amount, inv.currency)}
                  </td>
                  <td className="px-4 py-3 text-right text-sm text-gray-600">
                    {formatMoney(inv.paid_amount, inv.currency)}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {inv.due_date}
                  </td>
                  <td className="px-4 py-3 text-sm">
                    <span
                      className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${
                        STATUS_COLOR[inv.status] ?? "bg-gray-100 text-gray-600"
                      }`}
                    >
                      {inv.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
