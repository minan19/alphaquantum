"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  Building2,
  Calendar,
  CheckCircle2,
  ChevronRight,
  Clock,
  Download,
  Mail,
  MessageSquare,
  Phone,
  Receipt,
  ShieldCheck,
  Sparkles,
  Tag,
  XCircle,
} from "lucide-react";
import {
  apiRequest,
  ApiError,
  fetchCustomerRiskScore,
  type Customer,
  type CustomerRiskScore,
  type Invoice,
} from "@/lib/api";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/cn";

function fmt(n: number, ccy = "TRY") {
  return new Intl.NumberFormat("tr-TR", {
    style: "currency", currency: ccy, minimumFractionDigits: 0,
  }).format(n);
}

const RISK_TONE: Record<CustomerRiskScore["risk_level"], "success"|"warn"|"critical"|"neutral"> = {
  LOW:        "success",
  MEDIUM:     "warn",
  HIGH:       "critical",
  NO_HISTORY: "neutral",
};

const RISK_LABEL: Record<CustomerRiskScore["risk_level"], string> = {
  LOW:        "Düşük Risk",
  MEDIUM:     "Orta Risk",
  HIGH:       "Yüksek Risk",
  NO_HISTORY: "Geçmiş Yok",
};

export default function CustomerDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = Number(params.id);

  const [customer, setCustomer] = useState<Customer | null>(null);
  const [risk, setRisk] = useState<CustomerRiskScore | null>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!Number.isFinite(id)) return;
    let cancelled = false;
    (async () => {
      try {
        const [c, r, inv] = await Promise.all([
          apiRequest<Customer>(`/api/v1/crm/customers/${id}`).catch(() => null),
          fetchCustomerRiskScore(id).catch(() => null),
          apiRequest<{ total: number; invoices: Invoice[] }>(
            "/api/v1/collections/invoices",
            { params: { customer_id: id } },
          ).catch(() => ({ total: 0, invoices: [] })),
        ]);
        if (!cancelled) {
          setCustomer(c);
          setRisk(r);
          setInvoices(inv.invoices);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? `API hatası (${err.status})` : "Yüklenemedi");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [id]);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 shimmer rounded" />
        <div className="h-32 shimmer rounded-lg" />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {[0,1,2].map(i => <div key={i} className="h-48 shimmer rounded-lg" />)}
        </div>
      </div>
    );
  }

  if (!customer) {
    return (
      <div className="py-20 text-center">
        <XCircle className="mx-auto h-10 w-10 text-aq-trace opacity-40" />
        <p className="mt-3 text-sm text-aq-dust">Müşteri bulunamadı.</p>
        <Button variant="secondary" className="mt-4" onClick={() => router.push("/customers")}>
          <ArrowLeft className="h-4 w-4" /> Listeye dön
        </Button>
      </div>
    );
  }

  const outstanding = invoices
    .filter(i => !["paid","cancelled"].includes(i.status))
    .reduce((s, i) => s + (i.amount - i.paid_amount), 0);
  const overdueCount = invoices.filter(i => i.status === "overdue").length;
  const paidCount = invoices.filter(i => i.status === "paid").length;

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 text-sm text-aq-dust">
        <Link href="/customers" className="hover:text-foreground transition-colors">
          Müşteriler
        </Link>
        <ChevronRight className="h-3 w-3 text-aq-trace" />
        <span className="text-foreground">{customer.full_name}</span>
      </nav>

      {/* Hero card */}
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.32, 0.72, 0, 1] }}
      >
        <Card variant="gradient" className="p-[1px]">
          <div className="relative overflow-hidden rounded-lg bg-card p-6">
            <div className="absolute -right-16 -top-16 h-48 w-48 rounded-full bg-aq-quantum/15 blur-3xl" />
            <div className="relative flex flex-wrap items-start justify-between gap-4">
              <div className="flex items-center gap-4">
                <div className="grid h-16 w-16 place-items-center rounded-xl bg-gradient-to-br from-aq-quantum to-aq-plasma text-white text-xl font-semibold shadow-quantum">
                  {customer.full_name.split(" ").map(s => s[0]).slice(0, 2).join("")}
                </div>
                <div>
                  <h1 className="text-2xl font-bold tracking-tight">{customer.full_name}</h1>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-aq-dust">
                    <Tag className="h-3.5 w-3.5" />
                    <span>{customer.sector}</span>
                    <span className="text-aq-trace">·</span>
                    <span className="font-mono text-xs">ID #{customer.id}</span>
                    <span className="text-aq-trace">·</span>
                    <Building2 className="h-3.5 w-3.5" />
                    <span>{customer.company}</span>
                    {customer.is_active && <Badge tone="success" withDot>Aktif</Badge>}
                  </div>
                </div>
              </div>
              <div className="flex gap-2">
                <Button variant="secondary" size="sm">
                  <Download className="h-3.5 w-3.5" /> Veri export
                </Button>
                <Button size="sm">Düzenle</Button>
              </div>
            </div>
          </div>
        </Card>
      </motion.div>

      {/* Key metrics */}
      <section className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Metric label="Açık Bakiye"   value={fmt(outstanding)}        tone="warn"    icon={Receipt} />
        <Metric label="Geciken"       value={`${overdueCount} fatura`} tone="critical" icon={Clock} />
        <Metric label="Ödenen"        value={`${paidCount} fatura`}    tone="success" icon={CheckCircle2} />
        <Metric label="Toplam Fatura" value={String(invoices.length)}  tone="primary" icon={Receipt} />
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Risk score */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="lg:col-span-1"
        >
          <Card className="h-full p-6">
            <CardHeader className="p-0 pb-4">
              <CardTitle className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-aq-quantum-2" />
                Ödeme Risk Skoru
              </CardTitle>
              <CardDescription>S-333 · Davranışsal analiz</CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              {risk && risk.risk_level !== "NO_HISTORY" ? (
                <>
                  <div className="flex items-end justify-between mb-3">
                    <div>
                      <div className="text-4xl font-bold num">{risk.score.toFixed(0)}</div>
                      <div className="text-[10px] uppercase tracking-wider text-aq-trace mt-0.5">
                        / 100
                      </div>
                    </div>
                    <Badge tone={RISK_TONE[risk.risk_level]} withDot>
                      {RISK_LABEL[risk.risk_level]}
                    </Badge>
                  </div>
                  <div className="h-2 w-full overflow-hidden rounded-full bg-aq-mist mb-4">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${risk.score}%` }}
                      transition={{ duration: 0.8, ease: [0.32, 0.72, 0, 1] }}
                      className={cn(
                        "h-full",
                        risk.score >= 75 && "bg-gradient-to-r from-aq-fusion to-aq-fusion/60",
                        risk.score >= 40 && risk.score < 75 && "bg-gradient-to-r from-aq-solar to-aq-solar/60",
                        risk.score < 40 && "bg-gradient-to-r from-aq-fission to-aq-fission/60",
                      )}
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <Stat small label="Zamanında" value={risk.on_time_count} />
                    <Stat small label="Gecikmiş" value={risk.late_paid_count} />
                    <Stat small label="Avg gecikme" value={`${risk.avg_late_days.toFixed(0)}g`} />
                    <Stat small label="Güven" value={risk.confidence} />
                  </div>
                  <div className="mt-4 pt-4 border-t border-aq-mist/40 space-y-1.5">
                    {risk.factors.map((f, i) => (
                      <div key={i} className="text-xs text-aq-dust flex items-start gap-2">
                        <span className="text-aq-quantum-2 mt-1">·</span>
                        <span>{f}</span>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <div className="py-8 text-center text-sm text-aq-dust">
                  <Sparkles className="mx-auto h-6 w-6 mb-2 text-aq-trace opacity-40" />
                  Geçmiş veri yok — fatura kayıtlandıkça skor oluşur
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>

        {/* Contact + Consent */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.15 }}
          className="lg:col-span-2"
        >
          <Card className="h-full p-6">
            <CardHeader className="p-0 pb-4">
              <CardTitle>İletişim & İzinler</CardTitle>
              <CardDescription>KVKK uyumlu kanal yönetimi (S-343)</CardDescription>
            </CardHeader>
            <CardContent className="p-0 grid grid-cols-1 sm:grid-cols-3 gap-3">
              <ConsentChannel
                icon={Mail}
                channel="E-posta"
                target={customer.email || "—"}
                granted={customer.email_consent ?? false}
              />
              <ConsentChannel
                icon={Phone}
                channel="SMS"
                target={customer.phone || "—"}
                granted={customer.sms_consent ?? false}
              />
              <ConsentChannel
                icon={MessageSquare}
                channel="WhatsApp"
                target={customer.phone || "—"}
                granted={customer.whatsapp_consent ?? false}
              />
            </CardContent>
          </Card>
        </motion.div>
      </div>

      {/* Invoices timeline */}
      <motion.section
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.2 }}
      >
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Receipt className="h-4 w-4 text-aq-quantum-2" />
              Faturalar
            </CardTitle>
            <CardDescription>{invoices.length} kayıt · son tarih sırasına göre</CardDescription>
          </CardHeader>
          <CardContent className="px-0 pb-0">
            {invoices.length === 0 ? (
              <div className="px-6 pb-6 py-8 text-center text-sm text-aq-dust">
                Bu müşteriye ait fatura yok.
              </div>
            ) : (
              <ul className="divide-y divide-aq-mist/30">
                {invoices.map((inv, idx) => {
                  const outstanding = inv.amount - inv.paid_amount;
                  return (
                    <motion.li
                      key={inv.id}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ duration: 0.3, delay: 0.03 * idx }}
                      className="px-6 py-3 flex items-center gap-4 hover:bg-aq-quantum/5 transition-colors cursor-pointer"
                    >
                      <Receipt className="h-4 w-4 text-aq-dust" />
                      <div className="flex-1 min-w-0">
                        <div className="font-mono text-sm">{inv.invoice_number || `#${inv.id}`}</div>
                        <div className="text-xs text-aq-dust truncate">{inv.title}</div>
                      </div>
                      <div className="hidden sm:flex items-center gap-1.5 text-xs text-aq-dust">
                        <Calendar className="h-3 w-3" /> {inv.due_date}
                      </div>
                      <div className="text-right tabular num">
                        <div className="text-sm">{fmt(inv.amount, inv.currency)}</div>
                        {outstanding > 0 && (
                          <div className="text-xs text-aq-fission">
                            Açık: {fmt(outstanding, inv.currency)}
                          </div>
                        )}
                      </div>
                      <Badge
                        tone={
                          inv.status === "paid" ? "success" :
                          inv.status === "overdue" ? "critical" :
                          inv.status === "partial" ? "warn" : "primary"
                        }
                        withDot
                      >
                        {inv.status}
                      </Badge>
                    </motion.li>
                  );
                })}
              </ul>
            )}
          </CardContent>
        </Card>
      </motion.section>

      {error && (
        <Card className="border-aq-fission/40 bg-aq-fission/5 p-4 text-sm text-aq-fission">
          {error}
        </Card>
      )}
    </div>
  );
}

function Metric({
  label, value, tone, icon: Icon,
}: {
  label: string; value: string;
  tone: "primary" | "success" | "warn" | "critical";
  icon: typeof Receipt;
}) {
  const toneClass = {
    primary:  "ring-aq-quantum/30 text-aq-quantum-2",
    success:  "ring-aq-fusion/30 text-aq-fusion",
    warn:     "ring-aq-solar/30 text-aq-solar",
    critical: "ring-aq-fission/30 text-aq-fission",
  }[tone];
  return (
    <div className={cn("flex items-center gap-3 rounded-lg bg-aq-orbital/40 px-4 py-3 ring-1", toneClass)}>
      <Icon className="h-4 w-4" />
      <div>
        <div className="text-lg font-bold tabular num">{value}</div>
        <div className="text-[10px] uppercase tracking-wider text-aq-trace">{label}</div>
      </div>
    </div>
  );
}

function Stat({ label, value, small }: { label: string; value: string | number; small?: boolean }) {
  return (
    <div className="rounded-md bg-aq-orbital/40 px-3 py-2">
      <div className={cn("font-bold tabular num", small ? "text-sm" : "text-xl")}>{value}</div>
      <div className="text-[10px] uppercase tracking-wider text-aq-trace mt-0.5">{label}</div>
    </div>
  );
}

function ConsentChannel({
  icon: Icon, channel, target, granted,
}: {
  icon: typeof Mail; channel: string; target: string; granted: boolean;
}) {
  return (
    <div className={cn(
      "rounded-lg p-4 border transition-colors",
      granted ? "border-aq-fusion/30 bg-aq-fusion/5" : "border-aq-mist/40 bg-aq-orbital/40",
    )}>
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-2">
          <Icon className={cn(
            "h-4 w-4",
            granted ? "text-aq-fusion" : "text-aq-trace",
          )} />
          <span className="text-sm font-medium">{channel}</span>
        </div>
        {granted ? (
          <CheckCircle2 className="h-4 w-4 text-aq-fusion" />
        ) : (
          <XCircle className="h-4 w-4 text-aq-trace" />
        )}
      </div>
      <div className="text-xs text-aq-dust truncate">{target}</div>
      <div className="mt-3 flex items-center gap-1.5">
        <ShieldCheck className="h-3 w-3 text-aq-trace" />
        <span className="text-[10px] uppercase tracking-wider text-aq-trace">
          KVKK: {granted ? "İzin verildi" : "Yok"}
        </span>
      </div>
    </div>
  );
}
