"use client";

import { useEffect, useState } from "react";
import {
  ApiError,
  fetchLiveSignals,
  type DashboardLiveSignalsResponse,
  type DashboardSignal,
} from "@/lib/api";

const STATUS_STYLES: Record<DashboardSignal["status"], string> = {
  OK: "border-signal-ok/30 bg-signal-ok/5 text-signal-ok",
  WARN: "border-signal-warn/30 bg-signal-warn/5 text-signal-warn",
  ALERT: "border-signal-alert/30 bg-signal-alert/5 text-signal-alert",
};

export default function DashboardPage() {
  const [data, setData] = useState<DashboardLiveSignalsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const result = await fetchLiveSignals();
        if (!cancelled) setData(result);
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof ApiError
              ? `API hatası (${err.status})`
              : "Yüklenemedi",
          );
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return (
      <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        {error}
      </div>
    );
  }
  if (!data) {
    return <div className="text-gray-400">Sinyaller yükleniyor…</div>;
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-gray-900">Gösterge Paneli</h1>
        <p className="text-sm text-gray-500">
          {data.alert_count} alarm · {data.warn_count} uyarı ·{" "}
          {new Date(data.generated_at).toLocaleString("tr-TR")}
        </p>
      </header>

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {data.signals.map((s, idx) => (
          <article
            key={`${s.source}-${s.label}-${idx}`}
            className={`rounded-lg border p-4 ${STATUS_STYLES[s.status]}`}
          >
            <div className="text-xs uppercase tracking-wider opacity-70">
              {s.source}
            </div>
            <div className="mt-1 text-sm font-medium">{s.label}</div>
            <div className="mt-2 text-2xl font-bold">
              {s.value === null ? "—" : String(s.value)}
              {s.unit && (
                <span className="ml-1 text-sm font-normal opacity-70">
                  {s.unit}
                </span>
              )}
            </div>
            {s.detail && (
              <div className="mt-2 text-xs opacity-80">{s.detail}</div>
            )}
          </article>
        ))}
      </section>
    </div>
  );
}
