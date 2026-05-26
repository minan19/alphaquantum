"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import {
  ArrowUpDown,
  Filter,
  Mail,
  Phone,
  Plus,
  Search,
  Users,
  X,
} from "lucide-react";
import {
  ApiError,
  fetchCompanies,
  fetchCustomers,
  type Customer,
} from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/cn";

type SortKey = "name" | "sector" | "consent";
type SortDir = "asc" | "desc";

export default function CustomersPage() {
  const router = useRouter();
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("name");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [selected, setSelected] = useState<Customer | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const companies = await fetchCompanies();
        const data = await fetchCustomers(companies[0]?.name);
        if (!cancelled) setCustomers(data.customers);
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
    let list = !q
      ? customers
      : customers.filter((c) =>
          [c.full_name, c.email, c.phone, c.sector]
            .join(" ")
            .toLowerCase()
            .includes(q),
        );
    list = [...list].sort((a, b) => {
      const dir = sortDir === "asc" ? 1 : -1;
      if (sortKey === "name") return a.full_name.localeCompare(b.full_name, "tr") * dir;
      if (sortKey === "sector") return a.sector.localeCompare(b.sector, "tr") * dir;
      if (sortKey === "consent") {
        const consentCount = (c: Customer) =>
          Number(c.email_consent) + Number(c.sms_consent) + Number(c.whatsapp_consent);
        return (consentCount(a) - consentCount(b)) * dir;
      }
      return 0;
    });
    return list;
  }, [customers, search, sortKey, sortDir]);

  const toggleSort = (k: SortKey) => {
    if (sortKey === k) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSortKey(k); setSortDir("asc"); }
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Badge tone="primary" withDot>CorpOS</Badge>
            <span className="text-xs text-aq-trace font-mono">CRM</span>
          </div>
          <h1 className="text-3xl font-bold tracking-tight">Müşteriler</h1>
          <p className="mt-1 text-sm text-aq-dust">
            {loading ? "Yükleniyor…" : `${filtered.length} kayıt`} · KVKK onayları gizli kalır
          </p>
        </div>
        <Button>
          <Plus className="h-4 w-4" /> Yeni Müşteri
        </Button>
      </header>

      <Card className="overflow-hidden">
        {/* Toolbar */}
        <div className="flex flex-wrap items-center gap-2 border-b border-aq-mist/40 p-3">
          <div className="min-w-0 flex-1">
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Ad, e-posta, telefon veya sektör ara…"
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
          <Button variant="outline" size="sm">
            <Filter className="h-3.5 w-3.5" /> Filtre
          </Button>
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-aq-mist/40 text-left text-[11px] font-medium uppercase tracking-wider text-aq-trace">
                <Th onClick={() => toggleSort("name")} active={sortKey === "name"}>
                  Müşteri
                </Th>
                <th className="px-4 py-3 hidden md:table-cell">İletişim</th>
                <Th onClick={() => toggleSort("sector")} active={sortKey === "sector"}>
                  Sektör
                </Th>
                <Th onClick={() => toggleSort("consent")} active={sortKey === "consent"}>
                  KVKK
                </Th>
                <th className="px-4 py-3 text-right">Durum</th>
              </tr>
            </thead>
            <tbody>
              {loading && [0, 1, 2, 3, 4].map((i) => (
                <tr key={`s-${i}`} className="border-b border-aq-mist/30">
                  <td colSpan={5}><div className="m-3 h-8 rounded shimmer" /></td>
                </tr>
              ))}
              {!loading && filtered.length === 0 && !error && (
                <tr>
                  <td colSpan={5} className="py-12 text-center text-aq-dust">
                    <Users className="mx-auto h-8 w-8 mb-2 opacity-40" />
                    Müşteri bulunamadı.
                  </td>
                </tr>
              )}
              {!loading && filtered.map((c, idx) => (
                <motion.tr
                  key={c.id}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ duration: 0.3, delay: 0.02 * idx }}
                  onClick={() => setSelected(c)}
                  className="border-b border-aq-mist/30 cursor-pointer transition-colors hover:bg-aq-quantum/5"
                >
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <div className="grid h-9 w-9 place-items-center rounded-md bg-gradient-to-br from-aq-quantum/20 to-aq-plasma/20 ring-1 ring-aq-quantum/30 text-xs font-semibold uppercase">
                        {c.full_name.split(" ").map(s => s[0]).slice(0, 2).join("")}
                      </div>
                      <div>
                        <div className="font-medium">{c.full_name}</div>
                        <div className="text-xs text-aq-trace md:hidden">{c.email || c.phone || "—"}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3 hidden md:table-cell">
                    <div className="flex flex-col gap-0.5">
                      {c.email && (
                        <span className="flex items-center gap-1.5 text-xs text-aq-dust">
                          <Mail className="h-3 w-3" /> {c.email}
                        </span>
                      )}
                      {c.phone && (
                        <span className="flex items-center gap-1.5 text-xs text-aq-dust">
                          <Phone className="h-3 w-3" /> {c.phone}
                        </span>
                      )}
                      {!c.email && !c.phone && <span className="text-xs text-aq-trace">—</span>}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone="neutral">{c.sector}</Badge>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {c.email_consent && <Badge tone="success" className="px-1.5 py-0 text-[9px]">E-posta</Badge>}
                      {c.sms_consent && <Badge tone="success" className="px-1.5 py-0 text-[9px]">SMS</Badge>}
                      {c.whatsapp_consent && <Badge tone="success" className="px-1.5 py-0 text-[9px]">WhatsApp</Badge>}
                      {!c.email_consent && !c.sms_consent && !c.whatsapp_consent && (
                        <span className="text-xs text-aq-trace">Yok</span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right">
                    {c.is_active ? (
                      <Badge tone="success" withDot>Aktif</Badge>
                    ) : (
                      <Badge tone="neutral">Pasif</Badge>
                    )}
                  </td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Detail drawer */}
      {selected && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-40"
        >
          <div onClick={() => setSelected(null)} className="absolute inset-0 bg-aq-void/60 backdrop-blur-sm" />
          <motion.aside
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            transition={{ duration: 0.35, ease: [0.32, 0.72, 0, 1] }}
            className="absolute inset-y-0 right-0 w-full max-w-md border-l border-aq-mist/60 bg-aq-cosmos shadow-2xl p-6 overflow-y-auto"
          >
            <div className="flex items-start justify-between gap-3 mb-6">
              <div className="flex items-center gap-3">
                <div className="grid h-12 w-12 place-items-center rounded-lg bg-gradient-to-br from-aq-quantum to-aq-plasma text-white text-sm font-semibold">
                  {selected.full_name.split(" ").map(s => s[0]).slice(0, 2).join("")}
                </div>
                <div>
                  <h3 className="text-lg font-semibold">{selected.full_name}</h3>
                  <p className="text-xs text-aq-dust">ID #{selected.id} · {selected.sector}</p>
                </div>
              </div>
              <button onClick={() => setSelected(null)} aria-label="Kapat">
                <X className="h-5 w-5 text-aq-dust hover:text-foreground transition-colors" />
              </button>
            </div>

            <div className="space-y-5">
              <Section title="İletişim">
                <Field label="E-posta" value={selected.email || "—"} icon={<Mail className="h-3.5 w-3.5" />} />
                <Field label="Telefon" value={selected.phone || "—"} icon={<Phone className="h-3.5 w-3.5" />} />
              </Section>

              <Section title="KVKK Onayları">
                <ConsentRow label="E-posta" granted={selected.email_consent ?? false} />
                <ConsentRow label="SMS" granted={selected.sms_consent ?? false} />
                <ConsentRow label="WhatsApp" granted={selected.whatsapp_consent ?? false} />
              </Section>

              <Section title="Risk Skoru">
                <RiskScorePreview customerId={selected.id} />
              </Section>

              <div className="flex gap-2 pt-2">
                <Button variant="secondary" className="flex-1">Düzenle</Button>
                <Button
                  className="flex-1"
                  onClick={() => router.push(`/customers/${selected.id}`)}
                >
                  Müşteri 360 Görünümü
                </Button>
              </div>
            </div>
          </motion.aside>
        </motion.div>
      )}
    </div>
  );
}

function Th({
  children, onClick, active,
}: { children: React.ReactNode; onClick: () => void; active: boolean }) {
  return (
    <th className="px-4 py-3">
      <button
        onClick={onClick}
        className={cn(
          "flex items-center gap-1 transition-colors",
          active ? "text-aq-quantum-2" : "hover:text-foreground",
        )}
      >
        {children}
        <ArrowUpDown className="h-3 w-3 opacity-60" />
      </button>
    </th>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h4 className="text-[10px] font-medium uppercase tracking-wider text-aq-trace mb-2">{title}</h4>
      <div className="space-y-2">{children}</div>
    </div>
  );
}

function Field({ label, value, icon }: { label: string; value: string; icon?: React.ReactNode }) {
  return (
    <div className="flex items-start gap-3 rounded-md bg-aq-orbital/40 px-3 py-2">
      <div className="text-aq-dust mt-0.5">{icon}</div>
      <div className="flex-1">
        <div className="text-[10px] uppercase tracking-wider text-aq-trace">{label}</div>
        <div className="text-sm">{value}</div>
      </div>
    </div>
  );
}

function ConsentRow({ label, granted }: { label: string; granted: boolean }) {
  return (
    <div className="flex items-center justify-between rounded-md bg-aq-orbital/40 px-3 py-2">
      <span className="text-sm">{label}</span>
      {granted ? (
        <Badge tone="success" withDot>İzin verildi</Badge>
      ) : (
        <Badge tone="neutral">Yok</Badge>
      )}
    </div>
  );
}

function RiskScorePreview({ customerId }: { customerId: number }) {
  // Placeholder mock — replace with real GET /api/v1/crm/customers/{id}/risk-score
  const score = 50 + ((customerId * 13) % 50);
  const tone = score >= 75 ? "success" : score >= 40 ? "warn" : "critical";
  const label = score >= 75 ? "Düşük Risk" : score >= 40 ? "Orta Risk" : "Yüksek Risk";
  return (
    <div className="rounded-md bg-aq-orbital/40 p-3">
      <div className="flex items-baseline justify-between mb-2">
        <span className="text-2xl font-bold tabular num">{score}</span>
        <Badge tone={tone}>{label}</Badge>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-aq-mist">
        <div
          className={cn(
            "h-full transition-all duration-700",
            score >= 75 ? "bg-aq-fusion" : score >= 40 ? "bg-aq-solar" : "bg-aq-fission",
          )}
          style={{ width: `${score}%` }}
        />
      </div>
      <p className="mt-2 text-[10px] text-aq-trace">Geçmiş ödeme davranışından hesaplandı</p>
    </div>
  );
}
