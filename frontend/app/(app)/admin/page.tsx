"use client";

/**
 * SEC1: Admin Panel — Audit Log Review + KVKK.
 *
 * 3 sekme:
 *   1. Özet — son 24 saat: total events, error rate, by_method, by_user
 *   2. Audit Search — filtreli arama (user, method, path, status, time)
 *   3. KVKK — silme talepleri + ihlal raporları
 */
import { useCallback, useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  Clock,
  Filter,
  Loader2,
  RefreshCw,
  Search,
  Shield,
  ShieldAlert,
  User,
} from "lucide-react";
import {
  fetchAuditSummary,
  listKvkkDeletionRequests,
  listKvkkIncidents,
  searchAuditLogs,
  type AuditLogEntry,
  type AuditSearchFilters,
  type AuditSummary,
  type KvkkDeletionRequest,
  type KvkkIncident,
} from "@/lib/admin-api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/cn";


type Tab = "summary" | "search" | "kvkk";


export default function AdminPage() {
  const [tab, setTab] = useState<Tab>("summary");

  return (
    <div className="space-y-6 animate-fade-in">
      <motion.header
        initial={{ opacity: 0, y: -6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <Badge tone="critical" withDot>Admin Paneli</Badge>
        <h1 className="text-2xl font-bold mt-2">
          Güvenlik &{" "}
          <span className="bg-gradient-to-r from-aq-quantum-2 to-aq-plasma bg-clip-text text-transparent">
            Uyumluluk
          </span>
        </h1>
        <p className="text-sm text-aq-dust mt-1">
          Audit log incelemesi, KVKK silme talepleri ve güvenlik ihlali
          raporları. Sadece admin kullanıcılar erişebilir.
        </p>
      </motion.header>

      {/* Tabs */}
      <div className="flex flex-wrap gap-2">
        <TabPill active={tab === "summary"} onClick={() => setTab("summary")} icon={Activity} label="Özet" />
        <TabPill active={tab === "search"} onClick={() => setTab("search")} icon={Search} label="Audit Arama" />
        <TabPill active={tab === "kvkk"} onClick={() => setTab("kvkk")} icon={Shield} label="KVKK" />
      </div>

      {tab === "summary" && <SummaryView />}
      {tab === "search" && <SearchView />}
      {tab === "kvkk" && <KvkkView />}
    </div>
  );
}


function TabPill({
  active,
  onClick,
  icon: Icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: typeof Activity;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "px-3 py-1.5 rounded-full text-xs transition-colors inline-flex items-center gap-1.5",
        active
          ? "bg-aq-quantum/20 text-aq-quantum-2 border border-aq-quantum/30"
          : "bg-aq-orbital/40 text-aq-dust border border-aq-mist/30 hover:border-aq-mist/60",
      )}
    >
      <Icon className="h-3 w-3" />
      {label}
    </button>
  );
}


// ── Summary ────────────────────────────────────────────────────────────


function SummaryView() {
  const [summary, setSummary] = useState<AuditSummary | null>(null);
  const [window, setWindow] = useState(24);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setSummary(await fetchAuditSummary(window));
    } catch {
      setSummary(null);
    } finally {
      setLoading(false);
    }
  }, [window]);

  useEffect(() => { void load(); }, [load]);

  return (
    <Card variant="glass" className="p-6">
      <CardHeader className="p-0 pb-3 flex-row items-center justify-between">
        <div>
          <CardTitle>Son {window} saat</CardTitle>
          <CardDescription>
            Toplam istek, hata oranı, en aktif kullanıcı ve yavaş rotalar.
          </CardDescription>
        </div>
        <div className="flex items-center gap-2">
          {[1, 24, 168].map((h) => (
            <button
              key={h}
              type="button"
              onClick={() => setWindow(h)}
              className={cn(
                "px-2 py-1 text-[10px] uppercase font-mono rounded transition-colors",
                window === h
                  ? "bg-aq-quantum/20 text-aq-quantum-2 border border-aq-quantum/30"
                  : "text-aq-dust hover:text-foreground",
              )}
            >
              {h === 1 ? "1s" : h === 24 ? "24s" : "1h"}
            </button>
          ))}
          <Button variant="ghost" size="sm" onClick={() => void load()} disabled={loading}>
            {loading ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <RefreshCw className="h-3.5 w-3.5" />
            )}
          </Button>
        </div>
      </CardHeader>

      <CardContent className="p-0 space-y-4">
        {loading && !summary && (
          <div className="flex items-center justify-center py-8 text-aq-dust">
            <Loader2 className="h-4 w-4 animate-spin mr-2" />
            Yükleniyor…
          </div>
        )}

        {summary && (
          <>
            {/* KPI strip */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <KpiCard label="Toplam istek" value={summary.total_events} tone="primary" />
              <KpiCard label="Hata" value={summary.error_count} tone={summary.error_count > 0 ? "critical" : "neutral"} />
              <KpiCard
                label="Hata oranı"
                value={`%${summary.error_rate_pct.toFixed(1)}`}
                tone={summary.error_rate_pct > 5 ? "critical" : summary.error_rate_pct > 1 ? "warn" : "success"}
              />
              <KpiCard
                label="Aktif kullanıcı"
                value={summary.events_by_user.length}
                tone="primary"
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <SubCard title="Method dağılımı" icon={Activity}>
                {summary.events_by_method.map((m) => (
                  <BarRow key={m.method} label={m.method} value={m.count} max={summary.total_events} />
                ))}
              </SubCard>
              <SubCard title="En aktif kullanıcılar" icon={User}>
                {summary.events_by_user.slice(0, 5).map((u) => (
                  <BarRow key={u.username} label={u.username} value={u.count} max={summary.total_events} />
                ))}
                {summary.events_by_user.length === 0 && (
                  <p className="text-xs text-aq-dust">Aktivite yok.</p>
                )}
              </SubCard>
            </div>

            <SubCard title="Yavaş endpoint'ler" icon={Clock}>
              {summary.slow_routes.length === 0 ? (
                <p className="text-xs text-aq-dust">≥3 istek alan yavaş endpoint yok.</p>
              ) : (
                <div className="space-y-1.5">
                  {summary.slow_routes.map((r) => (
                    <div key={r.path} className="flex items-center gap-2 text-xs">
                      <code className="bg-aq-orbital/60 px-1.5 py-0.5 rounded text-aq-quantum-2 truncate flex-1">
                        {r.path}
                      </code>
                      <span className="font-mono text-aq-dust">
                        ø {r.avg_duration_ms.toFixed(0)}ms · {r.request_count}×
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </SubCard>
          </>
        )}
      </CardContent>
    </Card>
  );
}


// ── Audit Search ───────────────────────────────────────────────────────


function SearchView() {
  const [filters, setFilters] = useState<AuditSearchFilters>({
    fromHoursAgo: 24,
    limit: 100,
  });
  const [rows, setRows] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(false);

  async function handleSearch() {
    setLoading(true);
    try {
      setRows(await searchAuditLogs(filters));
    } catch {
      setRows([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void handleSearch(); /* eslint-disable-next-line */ }, []);

  return (
    <Card variant="glass" className="p-6">
      <CardHeader className="p-0 pb-3">
        <CardTitle className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-aq-quantum-2" />
          Filtreli Audit Arama
        </CardTitle>
        <CardDescription>
          Kullanıcı, method, path, status ve zaman penceresine göre filtrele.
        </CardDescription>
      </CardHeader>

      <CardContent className="p-0 space-y-3">
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-2">
          <InputField label="Kullanıcı" value={filters.username ?? ""} onChange={(v) => setFilters({ ...filters, username: v || undefined })} placeholder="alice" />
          <SelectField
            label="Method"
            value={filters.method ?? ""}
            onChange={(v) => setFilters({ ...filters, method: v || undefined })}
            options={["", "GET", "POST", "PUT", "PATCH", "DELETE", "EVENT"]}
          />
          <InputField label="Path içerir" value={filters.pathContains ?? ""} onChange={(v) => setFilters({ ...filters, pathContains: v || undefined })} placeholder="/customers" />
          <SelectField
            label="Zaman aralığı"
            value={String(filters.fromHoursAgo ?? "")}
            onChange={(v) => setFilters({ ...filters, fromHoursAgo: v ? Number(v) : undefined })}
            options={[
              { value: "", label: "Hepsi" },
              { value: "1", label: "Son 1 saat" },
              { value: "24", label: "Son 24 saat" },
              { value: "168", label: "Son 1 hafta" },
              { value: "720", label: "Son 1 ay" },
            ]}
          />
          <NumberField
            label="Min status"
            value={filters.statusCodeMin}
            onChange={(v) => setFilters({ ...filters, statusCodeMin: v })}
            placeholder="400"
          />
          <NumberField
            label="Max status"
            value={filters.statusCodeMax}
            onChange={(v) => setFilters({ ...filters, statusCodeMax: v })}
            placeholder="599"
          />
        </div>
        <div className="flex justify-end">
          <Button onClick={handleSearch} disabled={loading} size="sm">
            {loading ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" />
            ) : (
              <Search className="h-3.5 w-3.5 mr-1" />
            )}
            Ara
          </Button>
        </div>

        <div className="border-t border-aq-mist/30 pt-3">
          {rows.length === 0 && !loading && (
            <p className="text-xs text-aq-dust text-center py-6">
              Eşleşen kayıt yok.
            </p>
          )}
          <div className="space-y-1.5 max-h-[480px] overflow-y-auto">
            {rows.map((row) => (
              <AuditRow key={row.id} row={row} />
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}


function AuditRow({ row }: { row: AuditLogEntry }) {
  const isError = row.status_code >= 400;
  return (
    <div className={cn(
      "rounded-md border bg-aq-orbital/40 p-2.5 text-xs",
      isError ? "border-aq-fission/40" : "border-aq-mist/30",
    )}>
      <div className="flex items-center gap-2 flex-wrap">
        <Badge tone={isError ? "critical" : row.status_code >= 300 ? "warn" : "success"}>
          {row.status_code}
        </Badge>
        <span className="font-mono text-aq-quantum-2 text-[10px]">{row.method}</span>
        <code className="bg-aq-orbital/60 px-1.5 py-0.5 rounded text-aq-dust truncate flex-1">
          {row.path}
        </code>
        <span className="text-[10px] text-aq-trace shrink-0">
          {row.duration_ms.toFixed(0)}ms
        </span>
      </div>
      <div className="flex items-center gap-2 mt-1 text-[10px] text-aq-trace">
        <span>{row.username || "—"}</span>
        <span>·</span>
        <span>{row.ip_address || "?"}</span>
        <span className="ml-auto">
          {new Date(row.created_at * 1000).toLocaleString("tr-TR")}
        </span>
      </div>
    </div>
  );
}


// ── KVKK ───────────────────────────────────────────────────────────────


function KvkkView() {
  const [deletions, setDeletions] = useState<KvkkDeletionRequest[]>([]);
  const [incidents, setIncidents] = useState<KvkkIncident[]>([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const [d, i] = await Promise.all([
        listKvkkDeletionRequests().catch(() => []),
        listKvkkIncidents().catch(() => []),
      ]);
      setDeletions(d);
      setIncidents(i);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  return (
    <div className="space-y-4">
      <Card variant="glass" className="p-6">
        <CardHeader className="p-0 pb-3 flex-row items-start justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Shield className="h-4 w-4 text-aq-quantum-2" />
              Silme Talepleri
            </CardTitle>
            <CardDescription>
              KVKK Madde 7 — kullanıcının silme talebi (right to erasure).
            </CardDescription>
          </div>
          <Button variant="ghost" size="sm" onClick={() => void load()} disabled={loading}>
            {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
          </Button>
        </CardHeader>
        <CardContent className="p-0">
          {deletions.length === 0 && !loading && (
            <p className="text-xs text-aq-dust text-center py-4">Bekleyen silme talebi yok.</p>
          )}
          <div className="space-y-2">
            {deletions.map((d) => (
              <div key={d.id} className="rounded-md border border-aq-mist/40 bg-aq-orbital/40 p-3 text-xs">
                <div className="flex items-center gap-2 flex-wrap">
                  <Badge tone={d.status === "pending" ? "warn" : d.status === "approved" ? "success" : "neutral"}>
                    {d.status}
                  </Badge>
                  <span className="font-medium">{d.user_id}</span>
                  <span className="ml-auto text-[10px] text-aq-trace">
                    {new Date(d.created_at * 1000).toLocaleDateString("tr-TR")}
                  </span>
                </div>
                {d.reason && <p className="mt-1.5 text-aq-dust">{d.reason}</p>}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card variant="glass" className="p-6">
        <CardHeader className="p-0 pb-3">
          <CardTitle className="flex items-center gap-2">
            <ShieldAlert className="h-4 w-4 text-aq-fission" />
            Güvenlik İhlali Raporları
          </CardTitle>
          <CardDescription>
            KVKK Madde 12 — veri güvenliği ihlali bildirimi (72 saat).
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {incidents.length === 0 && !loading && (
            <p className="text-xs text-aq-dust text-center py-4">Aktif ihlal yok.</p>
          )}
          <div className="space-y-2">
            {incidents.map((i) => (
              <div key={i.id} className="rounded-md border border-aq-fission/40 bg-aq-fission/5 p-3 text-xs">
                <div className="flex items-center gap-2 flex-wrap">
                  <Badge tone={i.severity === "critical" ? "critical" : "warn"}>
                    {i.severity}
                  </Badge>
                  <span className="font-medium">{i.incident_type}</span>
                  <span className="text-[10px] text-aq-trace">
                    {i.affected_record_count} kayıt
                  </span>
                  <span className="ml-auto text-[10px] text-aq-trace">
                    {new Date(i.reported_at * 1000).toLocaleString("tr-TR")}
                  </span>
                </div>
                <p className="mt-1.5 text-aq-dust">{i.description}</p>
                {i.notification_required === 1 && (
                  <div className="mt-2 inline-flex items-center gap-1.5 text-[11px] text-aq-fission">
                    <AlertTriangle className="h-3 w-3" />
                    KVKK Kuruluna bildirim zorunlu (72 saat içinde)
                  </div>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}


// ── Small helpers ──────────────────────────────────────────────────────


function KpiCard({
  label,
  value,
  tone,
}: {
  label: string;
  value: string | number;
  tone: "primary" | "warn" | "critical" | "success" | "neutral";
}) {
  return (
    <div className="rounded-lg border border-aq-mist/40 bg-aq-orbital/40 p-3">
      <div className={cn(
        "text-2xl font-bold num",
        tone === "primary" && "text-aq-quantum-2",
        tone === "warn" && "text-aq-solar",
        tone === "critical" && "text-aq-fission",
        tone === "success" && "text-aq-mint",
        tone === "neutral" && "text-foreground",
      )}>
        {value}
      </div>
      <div className="text-[10px] uppercase tracking-wider text-aq-trace mt-1">
        {label}
      </div>
    </div>
  );
}


function SubCard({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon: typeof Activity;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-aq-mist/40 bg-aq-cosmos/40 p-3">
      <div className="flex items-center gap-1.5 mb-2 text-[10px] uppercase tracking-wider text-aq-trace">
        <Icon className="h-3 w-3" />
        {title}
      </div>
      {children}
    </div>
  );
}


function BarRow({
  label,
  value,
  max,
}: {
  label: string;
  value: number;
  max: number;
}) {
  const pct = max > 0 ? (value / max) * 100 : 0;
  return (
    <div className="text-xs">
      <div className="flex items-center justify-between mb-0.5">
        <span className="text-aq-dust">{label}</span>
        <span className="font-mono text-aq-trace">{value}</span>
      </div>
      <div className="h-1 rounded-full bg-aq-mist/20">
        <div
          className="h-full rounded-full bg-aq-quantum/60"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}


function InputField({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <div>
      <label className="text-[10px] uppercase tracking-wider text-aq-trace block mb-1">
        {label}
      </label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded-md border border-aq-mist/40 bg-aq-orbital/60 px-2 py-1.5 text-xs text-foreground focus:outline-none focus:border-aq-quantum/40"
      />
    </div>
  );
}


function NumberField({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: number | undefined;
  onChange: (v: number | undefined) => void;
  placeholder?: string;
}) {
  return (
    <div>
      <label className="text-[10px] uppercase tracking-wider text-aq-trace block mb-1">
        {label}
      </label>
      <input
        type="number"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value ? Number(e.target.value) : undefined)}
        placeholder={placeholder}
        className="w-full rounded-md border border-aq-mist/40 bg-aq-orbital/60 px-2 py-1.5 text-xs text-foreground focus:outline-none focus:border-aq-quantum/40"
      />
    </div>
  );
}


function SelectField({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: Array<string | { value: string; label: string }>;
}) {
  return (
    <div>
      <label className="text-[10px] uppercase tracking-wider text-aq-trace block mb-1">
        {label}
      </label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-md border border-aq-mist/40 bg-aq-orbital/60 px-2 py-1.5 text-xs text-foreground focus:outline-none focus:border-aq-quantum/40"
      >
        {options.map((opt, i) => {
          const v = typeof opt === "string" ? opt : opt.value;
          const l = typeof opt === "string" ? opt || "(hepsi)" : opt.label;
          return (
            <option key={i} value={v}>{l}</option>
          );
        })}
      </select>
    </div>
  );
}
