"use client";

import { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  AlertTriangle,
  Bell,
  CheckCircle2,
  Clock,
  Info,
  Inbox,
  Sparkles,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";
import {
  ApiError,
  fetchCompanies,
  fetchNotifications,
  fetchNotificationSummary,
  markNotificationRead,
  type Notification,
  type NotificationSummary,
} from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/cn";

type Filter = "all" | "unread" | "info" | "warning" | "critical";

const SEVERITY_META: Record<
  Notification["severity"],
  { tone: "info" | "warn" | "critical"; icon: typeof Info; ring: string; label: string }
> = {
  info:     { tone: "info",     icon: Info,          ring: "ring-aq-plasma/40",  label: "Bilgi" },
  warning:  { tone: "warn",     icon: AlertTriangle, ring: "ring-aq-solar/40",   label: "Uyarı" },
  critical: { tone: "critical", icon: XCircle,       ring: "ring-aq-fission/40", label: "Kritik" },
};

function timeAgo(epoch: number): string {
  const ms = Date.now() - epoch * 1000;
  const sec = Math.floor(ms / 1000);
  if (sec < 60) return `${sec} sn önce`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min} dk önce`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr} saat önce`;
  const day = Math.floor(hr / 24);
  if (day < 30) return `${day} gün önce`;
  return new Date(epoch * 1000).toLocaleDateString("tr-TR");
}

export default function NotificationsPage() {
  const [company, setCompany] = useState<string | undefined>(undefined);
  const [items, setItems] = useState<Notification[]>([]);
  const [summary, setSummary] = useState<NotificationSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<Filter>("all");

  // Bootstrap company
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const companies = await fetchCompanies();
        if (!cancelled) setCompany(companies[0]?.name);
      } catch {
        /* silent */
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // Load notifications + summary
  useEffect(() => {
    if (!company) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const [list, sum] = await Promise.all([
          fetchNotifications({
            company,
            severity: filter === "info" || filter === "warning" || filter === "critical" ? filter : undefined,
            unread_only: filter === "unread" || undefined,
          }),
          fetchNotificationSummary(company),
        ]);
        if (!cancelled) {
          setItems(list.notifications);
          setSummary(sum);
        }
      } catch (err) {
        if (!cancelled) {
          toast.error(err instanceof ApiError ? `API hatası (${err.status})` : "Yüklenemedi");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [company, filter]);

  const grouped = useMemo(() => {
    // Group by day for timeline
    const map = new Map<string, Notification[]>();
    for (const n of items) {
      const day = new Date(n.created_at * 1000).toLocaleDateString("tr-TR", {
        weekday: "long", day: "numeric", month: "long",
      });
      const arr = map.get(day) ?? [];
      arr.push(n);
      map.set(day, arr);
    }
    return Array.from(map.entries());
  }, [items]);

  async function handleMarkRead(id: number) {
    try {
      await markNotificationRead(id);
      setItems((prev) => prev.map((n) => (n.id === id ? { ...n, is_read: true } : n)));
      if (summary) {
        setSummary({ ...summary, unread: Math.max(0, summary.unread - 1) });
      }
      toast.success("Okundu olarak işaretlendi");
    } catch {
      toast.error("İşlem başarısız");
    }
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Badge tone="primary" withDot>FinOS</Badge>
            <span className="text-xs text-aq-trace font-mono">Notifications · S-334</span>
          </div>
          <h1 className="text-3xl font-bold tracking-tight">Bildirimler</h1>
          <p className="mt-1 text-sm text-aq-dust">
            {summary
              ? <>Toplam {summary.total} · <span className="text-aq-quantum-2">{summary.unread} okunmamış</span></>
              : "Yükleniyor…"}
          </p>
        </div>
      </header>

      {/* Stats row */}
      {summary && (
        <section className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <SeverityChip label="Toplam"  value={summary.total}    icon={Bell}          tone="primary" onClick={() => setFilter("all")} active={filter === "all"} />
          <SeverityChip label="Bilgi"   value={summary.info}     icon={Info}          tone="info"    onClick={() => setFilter("info")} active={filter === "info"} />
          <SeverityChip label="Uyarı"   value={summary.warning}  icon={AlertTriangle} tone="warn"    onClick={() => setFilter("warning")} active={filter === "warning"} />
          <SeverityChip label="Kritik"  value={summary.critical} icon={XCircle}       tone="critical" onClick={() => setFilter("critical")} active={filter === "critical"} />
        </section>
      )}

      {/* Unread filter chip */}
      <div className="flex items-center gap-2">
        <button
          onClick={() => setFilter(filter === "unread" ? "all" : "unread")}
          className={cn(
            "rounded-md px-3 py-1.5 text-xs font-medium transition-all",
            filter === "unread"
              ? "bg-aq-quantum/20 text-aq-quantum-2 ring-1 ring-aq-quantum/40"
              : "text-aq-dust hover:text-foreground hover:bg-aq-mist/40",
          )}
        >
          {filter === "unread" ? "✓ Yalnız okunmamış" : "Yalnız okunmamış"}
        </button>
      </div>

      {/* Timeline */}
      <Card className="p-6">
        {loading && (
          <div className="space-y-3">
            {[0, 1, 2, 3].map((i) => <div key={i} className="h-16 rounded shimmer" />)}
          </div>
        )}

        {!loading && grouped.length === 0 && (
          <div className="py-12 text-center">
            <Inbox className="mx-auto h-10 w-10 text-aq-trace opacity-40" />
            <p className="mt-3 text-sm text-aq-dust">Bildirim yok.</p>
            <p className="text-xs text-aq-trace mt-1">
              Tüm vade pencereleri sakin · sistem normal
            </p>
          </div>
        )}

        {!loading && grouped.length > 0 && (
          <div className="space-y-8">
            {grouped.map(([day, dayItems], dayIdx) => (
              <div key={day} className="relative">
                {/* Day header */}
                <div className="flex items-center gap-3 mb-4">
                  <div className="text-[10px] uppercase tracking-wider font-mono text-aq-trace">
                    {day}
                  </div>
                  <div className="h-px flex-1 bg-aq-mist/40" />
                </div>

                {/* Items */}
                <ul className="space-y-3 relative">
                  {/* Vertical timeline rail */}
                  <div className="absolute left-[15px] top-2 bottom-2 w-px bg-gradient-to-b from-aq-quantum/40 via-aq-mist/40 to-transparent" />

                  <AnimatePresence>
                    {dayItems.map((n, idx) => {
                      const meta = SEVERITY_META[n.severity];
                      const Icon = meta.icon;
                      return (
                        <motion.li
                          key={n.id}
                          initial={{ opacity: 0, x: -8 }}
                          animate={{ opacity: 1, x: 0 }}
                          exit={{ opacity: 0, x: 8 }}
                          transition={{
                            duration: 0.4,
                            delay: 0.04 * (dayIdx + idx),
                            ease: [0.32, 0.72, 0, 1],
                          }}
                          className="relative pl-10"
                        >
                          {/* Timeline dot */}
                          <div
                            className={cn(
                              "absolute left-0 top-3 grid h-8 w-8 place-items-center rounded-full",
                              "bg-aq-cosmos ring-2",
                              meta.ring,
                              !n.is_read && "animate-pulse-ring",
                            )}
                          >
                            <Icon className={cn(
                              "h-3.5 w-3.5",
                              n.severity === "critical" && "text-aq-fission",
                              n.severity === "warning" && "text-aq-solar",
                              n.severity === "info" && "text-aq-plasma",
                            )} />
                          </div>

                          {/* Card */}
                          <div
                            className={cn(
                              "rounded-lg border p-4 transition-all ease-quantum",
                              "border-aq-mist/40 bg-aq-orbital/40",
                              "hover:border-aq-quantum/40 hover:bg-aq-quantum/5",
                              !n.is_read && "border-l-2 border-l-aq-quantum",
                            )}
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0 flex-1">
                                <div className="flex items-center gap-2">
                                  <h3 className={cn(
                                    "font-medium",
                                    !n.is_read && "text-foreground",
                                    n.is_read && "text-aq-dust",
                                  )}>
                                    {n.title}
                                  </h3>
                                  <Badge tone={meta.tone} className="px-1.5 py-0 text-[9px]">
                                    {n.window_key}
                                  </Badge>
                                  {!n.is_read && (
                                    <span className="h-1.5 w-1.5 rounded-full bg-aq-quantum animate-pulse shadow-[0_0_8px_currentColor] text-aq-quantum" />
                                  )}
                                </div>
                                {n.message && (
                                  <p className="mt-1 text-sm text-aq-dust line-clamp-2">
                                    {n.message}
                                  </p>
                                )}
                                <div className="mt-2 flex items-center gap-3 text-[10px] font-mono text-aq-trace">
                                  <Clock className="h-3 w-3" />
                                  {timeAgo(n.created_at)}
                                  <span>·</span>
                                  <span>{n.subject_type} #{n.subject_id}</span>
                                </div>
                              </div>
                              {!n.is_read && (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleMarkRead(n.id)}
                                  aria-label="Okundu işaretle"
                                >
                                  <CheckCircle2 className="h-3.5 w-3.5" />
                                </Button>
                              )}
                            </div>
                          </div>
                        </motion.li>
                      );
                    })}
                  </AnimatePresence>
                </ul>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Hint footer */}
      <div className="flex items-center gap-2 text-xs text-aq-trace font-mono">
        <Sparkles className="h-3 w-3 text-aq-quantum-2" />
        Vade Uyarı Motoru (S-334) · T-3/T-1 hatırlatma + T+1/T+7/T+14 gecikme alarmları
      </div>
    </div>
  );
}

function SeverityChip({
  label, value, icon: Icon, tone, onClick, active,
}: {
  label: string; value: number; icon: typeof Bell;
  tone: "primary" | "info" | "warn" | "critical";
  onClick?: () => void; active?: boolean;
}) {
  const toneClass = {
    primary:  "text-aq-quantum-2 ring-aq-quantum/30",
    info:     "text-aq-plasma ring-aq-plasma/30",
    warn:     "text-aq-solar ring-aq-solar/30",
    critical: "text-aq-fission ring-aq-fission/30",
  }[tone];
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex items-center gap-3 rounded-lg bg-aq-orbital/40 px-4 py-3 ring-1 text-left",
        "transition-all duration-200 ease-quantum",
        "hover:scale-[1.02]",
        toneClass,
        active && "scale-[1.02] shadow-quantum",
      )}
    >
      <Icon className="h-4 w-4" />
      <div>
        <div className="text-xl font-bold tabular num">{value}</div>
        <div className="text-[10px] uppercase tracking-wider text-aq-trace">{label}</div>
      </div>
    </button>
  );
}
