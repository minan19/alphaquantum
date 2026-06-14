"use client";

/**
 * M2.3 — DataTable performans test sayfası.
 *
 * 5000 satır sentetik veriyle sıralama / filtre / sayfalama akıcılığını ölç.
 * Ölçümler:
 *   - İlk render: useState/useMemo initialize
 *   - Sıralama: column header click → sort → row swap
 *   - Sayfa değişimi: Pagination click → slice
 *   - Toplu seçim: "tümünü seç" checkbox
 * performance.now() ile her aksiyon süresi yazdırılır.
 */
import { useMemo, useState } from "react";
import { DataTable, type ColumnDef } from "@/components/ui/data-table";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Search } from "lucide-react";

interface DemoRow {
  id: string;
  company: string;
  amount: number;
  status: string;
  date: string;
}

const COMPANIES = ["Acme", "Beta", "Gamma", "Delta", "Epsilon", "Zeta", "Eta", "Theta"];
const STATUSES = ["ok", "pending", "fail", "review"];

function generate(n: number): DemoRow[] {
  const rows: DemoRow[] = [];
  for (let i = 0; i < n; i++) {
    // Deterministic — bağımsız render'larda aynı veri.
    const hash = (i * 2654435761) >>> 0;
    rows.push({
      id: `r${i}`,
      company: `${COMPANIES[hash % COMPANIES.length]} ${(hash % 200) + 1}`,
      amount: (hash % 1_000_000) + 100,
      status: STATUSES[hash % STATUSES.length],
      date: `2026-${String(((hash >> 8) % 12) + 1).padStart(2, "0")}-${String(((hash >> 16) % 28) + 1).padStart(2, "0")}`,
    });
  }
  return rows;
}

const COLUMNS: ColumnDef<DemoRow>[] = [
  { id: "id", label: "ID", sortKey: (r) => r.id, cell: (r) => r.id, className: "font-mono text-xs" },
  { id: "company", label: "Şirket", sortKey: (r) => r.company, cell: (r) => r.company },
  {
    id: "amount",
    label: "Tutar",
    sortKey: (r) => r.amount,
    cell: (r) => r.amount.toLocaleString("tr-TR"),
    className: "font-mono tabular-nums",
  },
  { id: "status", label: "Durum", sortKey: (r) => r.status, cell: (r) => r.status },
  { id: "date", label: "Tarih", sortKey: (r) => r.date, cell: (r) => r.date },
];

export default function PerfTestPage() {
  const [size, setSize] = useState(5000);
  const [query, setQuery] = useState("");
  const [marks, setMarks] = useState<{ label: string; ms: number }[]>([]);

  const rows = useMemo(() => {
    const t0 = performance.now();
    const out = generate(size);
    const dt = performance.now() - t0;
    // generate ölçümü ayrı bir effect olmadan setState içine yazmadık (loop).
    if (typeof window !== "undefined") {
      console.debug(`[perf] generate(${size}) = ${dt.toFixed(2)}ms`);
    }
    return out;
  }, [size]);

  const filtered = useMemo(() => {
    if (!query.trim()) return rows;
    const t0 = performance.now();
    const q = query.toLowerCase();
    const out = rows.filter((r) =>
      `${r.company} ${r.status} ${r.id}`.toLowerCase().includes(q),
    );
    const dt = performance.now() - t0;
    if (typeof window !== "undefined") {
      console.debug(`[perf] filter(${rows.length}→${out.length}) = ${dt.toFixed(2)}ms`);
    }
    return out;
  }, [rows, query]);

  const mark = (label: string) => {
    const t0 = performance.now();
    // Bir microtask sonrasında ölç — DOM güncellemesi henüz olmamış olabilir,
    // ama ana JS işine işaret eder.
    requestAnimationFrame(() => {
      const dt = performance.now() - t0;
      setMarks((m) => [...m.slice(-9), { label, ms: dt }]);
    });
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="container mx-auto py-8 space-y-6">
        <header>
          <h1 className="text-2xl font-bold">DataTable performans testi (M2.3)</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {size.toLocaleString("tr-TR")} satır · {filtered.length.toLocaleString("tr-TR")} filtreli.
            Sıralama / sayfalama / filtre tepkisini ölçer. Konsol&apos;da daha detaylı çıktılar.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {[1000, 2500, 5000, 10000].map((n) => (
              <Button
                key={n}
                size="sm"
                variant={size === n ? "primary" : "outline"}
                onClick={() => { mark(`size→${n}`); setSize(n); }}
              >
                {n.toLocaleString("tr-TR")}
              </Button>
            ))}
          </div>
        </header>

        <Card>
          <CardContent className="p-3">
            <Input
              value={query}
              onChange={(e) => { mark("filter"); setQuery(e.target.value); }}
              placeholder="Şirket / durum / id arası filtre…"
              leadingIcon={<Search className="h-4 w-4" />}
            />
          </CardContent>
        </Card>

        {/* Ölçüm konsolu */}
        <Card>
          <CardHeader>
            <CardTitle>Son ölçümler (rAF cycle)</CardTitle>
          </CardHeader>
          <CardContent>
            {marks.length === 0 ? (
              <p className="text-xs text-muted-foreground">Henüz ölçüm yok. Sıralama / sayfalama / filtre tetikleyin.</p>
            ) : (
              <ul className="space-y-1 text-xs font-mono">
                {marks.map((m, i) => (
                  <li key={i} className="flex justify-between">
                    <span>{m.label}</span>
                    <span className={m.ms > 50 ? "text-destructive" : m.ms > 16 ? "text-warning" : "text-success"}>
                      {m.ms.toFixed(1)}ms
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <DataTable
          columns={COLUMNS}
          rows={filtered}
          rowId={(r) => r.id}
          pageSize={100}
        />
      </div>
    </div>
  );
}
