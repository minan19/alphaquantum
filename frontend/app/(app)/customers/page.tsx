"use client";

import { useEffect, useState } from "react";
import {
  ApiError,
  fetchCompanies,
  fetchCustomers,
  type Customer,
} from "@/lib/api";

export default function CustomersPage() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        // Need a company name first — admin always sees the first company.
        const companies = await fetchCompanies();
        const company = companies[0]?.name;
        const data = await fetchCustomers(company);
        if (!cancelled) setCustomers(data.customers);
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

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-gray-900">Müşteriler</h1>
        <p className="text-sm text-gray-500">
          Toplam: {customers.length} müşteri
        </p>
      </header>

      {loading && <div className="text-gray-400">Yükleniyor…</div>}
      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {!loading && !error && customers.length === 0 && (
        <div className="rounded-md border border-gray-200 bg-white p-6 text-center text-sm text-gray-500">
          Henüz müşteri yok.
        </div>
      )}

      {!loading && customers.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Ad
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  E-posta
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Telefon
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Sektör
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  KVKK Onayı
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {customers.map((c) => (
                <tr key={c.id}>
                  <td className="px-4 py-3 text-sm font-medium text-gray-900">
                    {c.full_name}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {c.email || "—"}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {c.phone || "—"}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {c.sector}
                  </td>
                  <td className="px-4 py-3 text-xs">
                    {c.email_consent && (
                      <span className="mr-1 inline-block rounded bg-signal-ok/10 px-2 py-0.5 text-signal-ok">
                        E-posta
                      </span>
                    )}
                    {c.sms_consent && (
                      <span className="mr-1 inline-block rounded bg-signal-ok/10 px-2 py-0.5 text-signal-ok">
                        SMS
                      </span>
                    )}
                    {c.whatsapp_consent && (
                      <span className="mr-1 inline-block rounded bg-signal-ok/10 px-2 py-0.5 text-signal-ok">
                        WhatsApp
                      </span>
                    )}
                    {!c.email_consent &&
                      !c.sms_consent &&
                      !c.whatsapp_consent && (
                        <span className="text-gray-400">Yok</span>
                      )}
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
