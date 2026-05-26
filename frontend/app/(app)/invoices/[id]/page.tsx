"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  ArrowLeft,
  Calendar,
  CheckCircle2,
  ChevronRight,
  Clock,
  Download,
  FileText,
  Hash,
  Receipt,
  Send,
  User as UserIcon,
  XCircle,
} from "lucide-react";
import {
  apiRequest,
  ApiError,
  getApiBaseUrl,
  getToken,
  type Customer,
  type Invoice,
} from "@/lib/api";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { cn } from "@/lib/cn";

function fmt(n: number, ccy = "TRY") {
  return new Intl.NumberFormat("tr-TR", {
    style: "currency", currency: ccy, minimumFractionDigits: 2,
  }).format(n);
}

const STATUS_META: Record<
  string,
  { tone: "success"|"warn"|"critical"|"primary"|"neutral"; label: string; icon: typeof Receipt }
> = {
  paid:      { tone: "success",  label: "Ödendi",   icon: CheckCircle2 },
  partial:   { tone: "warn",     label: "Kısmi",    icon: Clock },
  overdue:   { tone: "critical", label: "Gecikmiş", icon: AlertTriangle },
  pending:   { tone: "primary",  label: "Bekliyor", icon: Clock },
  cancelled: { tone: "neutral",  label: "İptal",    icon: XCircle },
};

export default function InvoiceDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = Number(params.id);

  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!Number.isFinite(id)) return;
    let cancelled = false;
    (async () => {
      try {
        const inv = await apiRequest<Invoice>(`/api/v1/collections/invoices/${id}`);
        if (cancelled) return;
        setInvoice(inv);
        if (inv.customer_id) {
          try {
            const c = await apiRequest<Customer>(`/api/v1/crm/customers/${inv.customer_id}`);
            if (!cancelled) setCustomer(c);
          } catch { /* ignore */ }
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
  }, [id]);

  async function downloadPdf() {
    if (!invoice) return;
    try {
      const token = getToken();
      const resp = await fetch(
        `${getApiBaseUrl()}/api/v1/collections/invoices/${invoice.id}/pdf`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `invoice_${invoice.invoice_number || invoice.id}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("PDF indirildi");
    } catch (err) {
      toast.error("PDF indirilemedi", {
        description: err instanceof Error ? err.message : undefined,
      });
    }
  }

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

  if (!invoice) {
    return (
      <div className="py-20 text-center">
        <XCircle className="mx-auto h-10 w-10 text-aq-trace opacity-40" />
        <p className="mt-3 text-sm text-aq-dust">Fatura bulunamadı.</p>
        <Button variant="secondary" className="mt-4" onClick={() => router.push("/invoices")}>
          <ArrowLeft className="h-4 w-4" /> Listeye dön
        </Button>
      </div>
    );
  }

  const outstanding = invoice.amount - invoice.paid_amount;
  const progress = invoice.amount > 0 ? (invoice.paid_amount / invoice.amount) * 100 : 0;
  const meta = STATUS_META[invoice.status] ?? STATUS_META.pending;
  const StatusIcon = meta.icon;

  // Timeline events
  type TLEvent = { date: string; label: string; icon: typeof Receipt; tone: string };
  const timeline: TLEvent[] = [
    { date: invoice.issue_date, label: "Fatura düzenlendi",   icon: FileText,      tone: "text-aq-plasma" },
    { date: invoice.due_date,    label: "Vade tarihi",          icon: Calendar,      tone: "text-aq-solar" },
  ];
  if (invoice.paid_amount > 0) {
    timeline.push({
      date: new Date().toISOString().slice(0, 10),
      label: `Ödeme alındı: ${fmt(invoice.paid_amount, invoice.currency)}`,
      icon: CheckCircle2,
      tone: "text-aq-fusion",
    });
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 text-sm text-aq-dust">
        <Link href="/invoices" className="hover:text-foreground transition-colors">Faturalar</Link>
        <ChevronRight className="h-3 w-3 text-aq-trace" />
        <span className="text-foreground font-mono">
          {invoice.invoice_number || `#${invoice.id}`}
        </span>
      </nav>

      {/* Hero card */}
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.32, 0.72, 0, 1] }}
      >
        <Card variant="gradient" className="p-[1px]">
          <div className="relative overflow-hidden rounded-lg bg-card p-6">
            <div className={cn(
              "absolute -right-16 -top-16 h-48 w-48 rounded-full blur-3xl opacity-40",
              meta.tone === "success" && "bg-aq-fusion",
              meta.tone === "critical" && "bg-aq-fission",
              meta.tone === "warn" && "bg-aq-solar",
              (meta.tone === "primary" || meta.tone === "neutral") && "bg-aq-quantum",
            )} />
            <div className="relative flex flex-wrap items-start justify-between gap-4">
              <div className="flex items-center gap-4">
                <div className={cn(
                  "grid h-16 w-16 place-items-center rounded-xl text-white shadow-quantum",
                  meta.tone === "success" && "bg-gradient-to-br from-aq-fusion to-aq-fusion/70",
                  meta.tone === "critical" && "bg-gradient-to-br from-aq-fission to-aq-fission/70",
                  meta.tone === "warn" && "bg-gradient-to-br from-aq-solar to-aq-solar/70",
                  (meta.tone === "primary" || meta.tone === "neutral") && "bg-gradient-to-br from-aq-quantum to-aq-plasma",
                )}>
                  <StatusIcon className="h-7 w-7" />
                </div>
                <div>
                  <div className="flex items-center gap-2 text-xs text-aq-trace font-mono">
                    <Hash className="h-3 w-3" />
                    {invoice.invoice_number || `INV-${invoice.id}`}
                  </div>
                  <h1 className="text-2xl font-bold tracking-tight mt-0.5">{invoice.title}</h1>
                  <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-aq-dust">
                    <Badge tone={meta.tone} withDot>{meta.label}</Badge>
                    {customer && (
                      <>
                        <span className="text-aq-trace">·</span>
                        <Link
                          href={`/customers/${customer.id}`}
                          className="flex items-center gap-1.5 hover:text-foreground transition-colors"
                        >
                          <UserIcon className="h-3.5 w-3.5" />
                          {customer.full_name}
                        </Link>
                      </>
                    )}
                  </div>
                </div>
              </div>
              <div className="flex gap-2">
                <Button variant="secondary" size="sm" onClick={downloadPdf}>
                  <Download className="h-3.5 w-3.5" /> PDF indir
                </Button>
                {invoice.status !== "paid" && invoice.status !== "cancelled" && (
                  <Button size="sm">
                    <Send className="h-3.5 w-3.5" /> Ödeme kaydet
                  </Button>
                )}
              </div>
            </div>
          </div>
        </Card>
      </motion.div>

      {/* Amount summary */}
      <section className="grid grid-cols-1 lg:grid-cols-[2fr_1fr] gap-4">
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
        >
          <Card className="p-6">
            <CardHeader className="p-0 pb-4">
              <CardTitle>Tutar Özeti</CardTitle>
              <CardDescription>{invoice.currency} cinsinden</CardDescription>
            </CardHeader>
            <CardContent className="p-0 space-y-4">
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <div className="text-[10px] uppercase tracking-wider text-aq-trace">Toplam</div>
                  <div className="text-2xl font-bold tabular num">
                    {fmt(invoice.amount, invoice.currency)}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] uppercase tracking-wider text-aq-trace">Ödenen</div>
                  <div className="text-2xl font-bold tabular num text-aq-fusion">
                    {fmt(invoice.paid_amount, invoice.currency)}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] uppercase tracking-wider text-aq-trace">Açık Bakiye</div>
                  <div className={cn(
                    "text-2xl font-bold tabular num",
                    outstanding > 0 ? "text-aq-fission" : "text-aq-trace",
                  )}>
                    {fmt(outstanding, invoice.currency)}
                  </div>
                </div>
              </div>

              <div>
                <div className="flex items-baseline justify-between mb-1.5 text-xs">
                  <span className="text-aq-dust">Ödeme ilerlemesi</span>
                  <span className="font-mono tabular num">{progress.toFixed(0)}%</span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-aq-mist">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${progress}%` }}
                    transition={{ duration: 0.8, ease: [0.32, 0.72, 0, 1] }}
                    className="h-full bg-gradient-to-r from-aq-quantum via-aq-quantum-2 to-aq-plasma"
                  />
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.15 }}
        >
          <Card className="h-full p-6">
            <CardHeader className="p-0 pb-4">
              <CardTitle className="flex items-center gap-2">
                <FileText className="h-4 w-4 text-aq-quantum-2" />
                Detaylar
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0 space-y-2.5">
              <DetailRow label="Düzenlenme" value={invoice.issue_date} />
              <DetailRow label="Vade Tarihi" value={invoice.due_date} />
              <DetailRow label="Para Birimi" value={invoice.currency} />
              <DetailRow label="Şirket" value={invoice.company} />
              {customer && <DetailRow label="Müşteri" value={customer.full_name} />}
            </CardContent>
          </Card>
        </motion.div>
      </section>

      {/* Timeline */}
      <motion.section
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.2 }}
      >
        <Card className="p-6">
          <CardHeader className="p-0 pb-4">
            <CardTitle>Zaman Çizgisi</CardTitle>
            <CardDescription>Fatura ile ilgili olaylar</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            <ul className="relative space-y-4">
              <div className="absolute left-[15px] top-2 bottom-2 w-px bg-gradient-to-b from-aq-quantum/40 to-transparent" />
              {timeline.map((t, i) => {
                const Icon = t.icon;
                return (
                  <li key={i} className="relative pl-10">
                    <div className={cn(
                      "absolute left-0 top-0 grid h-8 w-8 place-items-center rounded-full bg-aq-cosmos ring-2",
                      t.tone.includes("fusion") && "ring-aq-fusion/40",
                      t.tone.includes("solar") && "ring-aq-solar/40",
                      t.tone.includes("plasma") && "ring-aq-plasma/40",
                    )}>
                      <Icon className={cn("h-3.5 w-3.5", t.tone)} />
                    </div>
                    <div className="rounded-lg border border-aq-mist/40 bg-aq-orbital/40 p-3">
                      <div className="text-sm font-medium">{t.label}</div>
                      <div className="text-xs text-aq-trace font-mono mt-0.5">{t.date}</div>
                    </div>
                  </li>
                );
              })}
            </ul>
          </CardContent>
        </Card>
      </motion.section>

      {/* Description */}
      {invoice.title && (
        <Card className="p-6">
          <CardHeader className="p-0 pb-3">
            <CardTitle className="text-base">Açıklama</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <p className="text-sm text-aq-dust leading-relaxed">{invoice.title}</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-aq-trace text-xs uppercase tracking-wider">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}
