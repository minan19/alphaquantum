"use client";

/**
 * BZ1: Onboarding Wizard — 5 adımlı self-service aktivasyon.
 *
 * Hedef: 10 dakikada yeni kullanıcının "ilk değer" anına ulaşması.
 *  - Tek route, çoklu adım state machine
 *  - Sol panel: progress steps + "ne kazanıyorum" mikrocopy
 *  - Sağ panel: aktif step formu
 *  - Submit tek-shot POST → backend OnboardingEngine.complete
 *
 * Adımlar:
 *  1. Hoşgeldin (motivation + 10dk taahhüt)
 *  2. Şirket bilgileri (name, sector, employee_count, initial_balance)
 *  3. Connector seçimi (Logo/Mikro/Paraşüt/skip)
 *  4. İlk fatura (customer + amount + dates) — demo aktivasyon
 *  5. Özet + Submit
 *
 * Backend canlıysa POST /api/v1/onboarding/complete.
 * Hata yönetimi: toast.error + step'i geri al.
 */
import { useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowLeft,
  ArrowRight,
  Building2,
  Check,
  Loader2,
  Plug,
  Receipt,
  Sparkles,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiRequest } from "@/lib/api";
import { cn } from "@/lib/cn";

interface CompanyForm {
  name: string;
  sector: string;
  employee_count: number;
  initial_balance: number;
}

interface ConnectorForm {
  connector_type: string;
}

interface InvoiceForm {
  customer_name: string;
  amount: number;
  currency: string;
  issue_date: string;
  due_date: string;
  description: string;
}

interface OnboardingState {
  step: number;
  company: CompanyForm;
  connector: ConnectorForm;
  invoice: InvoiceForm;
}

const TOTAL_STEPS = 5;

const SECTORS = [
  "Tekstil",
  "İnşaat",
  "Lojistik",
  "Gıda",
  "Bilişim",
  "Üretim",
  "Hizmet",
  "Ticaret",
  "Diğer",
];

const CONNECTORS = [
  { value: "skip", label: "Şimdilik atla", description: "Settings'ten sonra eklerim" },
  { value: "logo_tiger", label: "Logo Tiger", description: "Türkiye'nin en yaygın ERP'si" },
  { value: "parasut", label: "Paraşüt", description: "KOBİ muhasebe lider" },
  { value: "mikro", label: "Mikro", description: "Geleneksel ERP" },
  { value: "netsis", label: "Netsis", description: "Orta segment ERP" },
];

function todayISO(): string {
  const d = new Date();
  return d.toISOString().slice(0, 10);
}

function plusDaysISO(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

export function OnboardingWizard({ onComplete }: { onComplete?: () => void }) {
  const [state, setState] = useState<OnboardingState>(() => ({
    step: 1,
    company: { name: "", sector: "Tekstil", employee_count: 10, initial_balance: 0 },
    connector: { connector_type: "skip" },
    invoice: {
      customer_name: "",
      amount: 25000,
      currency: "TRY",
      issue_date: todayISO(),
      due_date: plusDaysISO(30),
      description: "",
    },
  }));
  const [submitting, setSubmitting] = useState(false);

  const progress = useMemo(
    () => Math.round(((state.step - 1) / (TOTAL_STEPS - 1)) * 100),
    [state.step],
  );

  const canGoNext = useMemo(() => {
    switch (state.step) {
      case 1:
        return true; // welcome
      case 2:
        return state.company.name.trim().length > 0;
      case 3:
        return state.connector.connector_type.length > 0;
      case 4:
        return state.invoice.customer_name.trim().length > 0 && state.invoice.amount > 0;
      case 5:
        return true;
      default:
        return false;
    }
  }, [state]);

  const next = () => setState((s) => ({ ...s, step: Math.min(s.step + 1, TOTAL_STEPS) }));
  const back = () => setState((s) => ({ ...s, step: Math.max(s.step - 1, 1) }));

  async function submit() {
    setSubmitting(true);
    try {
      await apiRequest("/api/v1/onboarding/complete", {
        method: "POST",
        body: {
          company: state.company,
          connector: state.connector,
          first_invoice: state.invoice,
        },
      });
      toast.success("Onboarding tamamlandı 🎉", {
        description: `${state.company.name} sisteme eklendi.`,
      });
      onComplete?.();
    } catch (err) {
      toast.error("Onboarding başarısız", {
        description: err instanceof Error ? err.message : "Bilinmeyen hata",
      });
      setSubmitting(false);
    }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-8 max-w-5xl mx-auto py-8 px-4">
      {/* Sol panel — steps progress */}
      <aside className="space-y-6">
        <div>
          <div className="flex items-center justify-between text-xs mb-2">
            <span className="text-aq-dust">İlerleme</span>
            <span className="font-mono text-aq-mint tabular-nums">%{progress}</span>
          </div>
          <div className="h-1 rounded-full bg-aq-mist/40 overflow-hidden">
            <motion.div
              className="h-full bg-gradient-to-r from-aq-mint to-aq-fusion"
              animate={{ width: `${progress}%` }}
              transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
            />
          </div>
        </div>

        <ol className="space-y-3" aria-label="Onboarding adımları">
          {[
            { num: 1, label: "Hoşgeldin", icon: Sparkles },
            { num: 2, label: "Şirket bilgileri", icon: Building2 },
            { num: 3, label: "Entegrasyon", icon: Plug },
            { num: 4, label: "İlk fatura", icon: Receipt },
            { num: 5, label: "Özet & başlat", icon: Check },
          ].map(({ num, label, icon: Icon }) => {
            const active = num === state.step;
            const done = num < state.step;
            return (
              <li
                key={num}
                className={cn(
                  "flex items-center gap-3 rounded-lg border px-3 py-2.5 transition-colors",
                  active
                    ? "border-aq-mint/50 bg-aq-mint/10"
                    : done
                    ? "border-aq-fusion/40 bg-aq-fusion/5"
                    : "border-aq-mist/30 bg-transparent",
                )}
              >
                <span
                  className={cn(
                    "grid h-8 w-8 place-items-center rounded-full text-xs font-bold",
                    active
                      ? "bg-aq-mint text-white"
                      : done
                      ? "bg-aq-fusion text-white"
                      : "bg-aq-mist/40 text-aq-dust",
                  )}
                >
                  {done ? <Check className="h-4 w-4" /> : <Icon className="h-4 w-4" />}
                </span>
                <span
                  className={cn(
                    "text-sm",
                    active ? "text-foreground font-medium" : "text-aq-dust",
                  )}
                >
                  {label}
                </span>
              </li>
            );
          })}
        </ol>

        <div className="rounded-lg border border-aq-mint/20 bg-aq-mint/5 p-3 text-xs text-aq-mint">
          ⏱ Yaklaşık <strong>10 dakika</strong> sürer. İstediğin yerden çıkıp tekrar
          devam edebilirsin.
        </div>
      </aside>

      {/* Sağ panel — aktif step formu */}
      <main>
        <AnimatePresence mode="wait">
          <motion.div
            key={state.step}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -16 }}
            transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
          >
            {state.step === 1 && <StepWelcome />}
            {state.step === 2 && (
              <StepCompany
                value={state.company}
                onChange={(c) => setState((s) => ({ ...s, company: c }))}
              />
            )}
            {state.step === 3 && (
              <StepConnector
                value={state.connector}
                onChange={(c) => setState((s) => ({ ...s, connector: c }))}
              />
            )}
            {state.step === 4 && (
              <StepInvoice
                value={state.invoice}
                onChange={(i) => setState((s) => ({ ...s, invoice: i }))}
              />
            )}
            {state.step === 5 && <StepSummary state={state} />}
          </motion.div>
        </AnimatePresence>

        {/* Footer navigation */}
        <div className="mt-8 flex items-center justify-between">
          <Button
            variant="ghost"
            onClick={back}
            disabled={state.step === 1 || submitting}
          >
            <ArrowLeft className="h-4 w-4 mr-1" /> Geri
          </Button>
          {state.step < TOTAL_STEPS ? (
            <Button onClick={next} disabled={!canGoNext}>
              İleri <ArrowRight className="h-4 w-4 ml-1" />
            </Button>
          ) : (
            <Button
              onClick={submit}
              disabled={submitting}
              className="bg-aq-mint hover:bg-aq-mint-2 text-white"
            >
              {submitting ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Aktifleştiriliyor…
                </>
              ) : (
                <>
                  Onboarding&apos;i tamamla{" "}
                  <Check className="h-4 w-4 ml-1" />
                </>
              )}
            </Button>
          )}
        </div>
      </main>
    </div>
  );
}

/* ── Steps ────────────────────────────────────────────────────────── */

function StepWelcome() {
  return (
    <div>
      <h2 className="text-2xl font-bold tracking-tight">
        Hoş geldin — birlikte 10 dakikada sisteme alalım
      </h2>
      <p className="mt-3 text-sm text-aq-dust max-w-xl">
        Bu sihirbaz şirketini Alpha Quantum&apos;a hazırlar. 4 küçük adım:
        şirket bilgisi, ERP/muhasebe sistemini tanı, ilk faturayı oluştur,
        çalıştır.
      </p>

      <ul className="mt-6 space-y-2 text-sm">
        {[
          "Şirket profili — sektör + büyüklük (1dk)",
          "ERP/muhasebe sistemi seçimi — opsiyonel (1dk)",
          "İlk faturayı oluştur — demo aktivasyon (3dk)",
          "Bildirim tercihleri ve devam et",
        ].map((line) => (
          <li key={line} className="flex items-center gap-2">
            <Check className="h-4 w-4 text-aq-mint shrink-0" />
            <span className="text-aq-dust">{line}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function StepCompany({
  value,
  onChange,
}: {
  value: CompanyForm;
  onChange: (v: CompanyForm) => void;
}) {
  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Şirket bilgileri</h2>
        <p className="mt-1 text-sm text-aq-dust">
          Sadece operasyonel ihtiyaçlar — KVKK kapsamında kişisel veri yok.
        </p>
      </div>

      <div>
        <label className="block text-xs uppercase tracking-wider text-aq-trace mb-1.5">
          Şirket adı
        </label>
        <Input
          value={value.name}
          onChange={(e) => onChange({ ...value, name: e.target.value })}
          placeholder="örn. Atlas Tekstil A.Ş."
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-xs uppercase tracking-wider text-aq-trace mb-1.5">
            Sektör
          </label>
          <select
            value={value.sector}
            onChange={(e) => onChange({ ...value, sector: e.target.value })}
            className="w-full rounded-md border border-aq-mist/40 bg-aq-orbital/40 px-3 py-2 text-sm"
          >
            {SECTORS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs uppercase tracking-wider text-aq-trace mb-1.5">
            Çalışan sayısı
          </label>
          <Input
            type="number"
            min={1}
            max={10000}
            value={value.employee_count}
            onChange={(e) =>
              onChange({ ...value, employee_count: Number(e.target.value) || 1 })
            }
          />
        </div>
      </div>

      <div>
        <label className="block text-xs uppercase tracking-wider text-aq-trace mb-1.5">
          Başlangıç bakiyesi (TRY)
        </label>
        <Input
          type="number"
          min={0}
          value={value.initial_balance}
          onChange={(e) =>
            onChange({ ...value, initial_balance: Number(e.target.value) || 0 })
          }
        />
        <p className="text-[10px] text-aq-trace mt-1">
          Bilmiyorsan 0 bırakabilirsin — sonra ledger&apos;dan hesaplanır.
        </p>
      </div>
    </div>
  );
}

function StepConnector({
  value,
  onChange,
}: {
  value: ConnectorForm;
  onChange: (v: ConnectorForm) => void;
}) {
  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Entegrasyon</h2>
        <p className="mt-1 text-sm text-aq-dust">
          Mevcut ERP/muhasebe sisteminden veri çekmek istersen seç. Atlamak
          serbest — sonra Ayarlar&apos;dan ekleyebilirsin.
        </p>
      </div>

      <div className="space-y-2">
        {CONNECTORS.map((opt) => {
          const active = value.connector_type === opt.value;
          return (
            <button
              key={opt.value}
              type="button"
              onClick={() => onChange({ connector_type: opt.value })}
              className={cn(
                "w-full text-left rounded-lg border p-3 transition-all",
                active
                  ? "border-aq-mint/50 bg-aq-mint/10"
                  : "border-aq-mist/30 hover:border-aq-mint/30 bg-transparent",
              )}
            >
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-medium text-sm">{opt.label}</div>
                  <div className="text-xs text-aq-dust mt-0.5">{opt.description}</div>
                </div>
                {active && (
                  <Check className="h-4 w-4 text-aq-mint" />
                )}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function StepInvoice({
  value,
  onChange,
}: {
  value: InvoiceForm;
  onChange: (v: InvoiceForm) => void;
}) {
  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">İlk fatura</h2>
        <p className="mt-1 text-sm text-aq-dust">
          Bir fatura örneği ekle — vade hatırlatma, risk skoru ve raporlar
          burada başlayacak.
        </p>
      </div>

      <div>
        <label className="block text-xs uppercase tracking-wider text-aq-trace mb-1.5">
          Müşteri adı
        </label>
        <Input
          value={value.customer_name}
          onChange={(e) => onChange({ ...value, customer_name: e.target.value })}
          placeholder="örn. Acme Konfeksiyon"
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-xs uppercase tracking-wider text-aq-trace mb-1.5">
            Tutar (TRY)
          </label>
          <Input
            type="number"
            min={1}
            value={value.amount}
            onChange={(e) => onChange({ ...value, amount: Number(e.target.value) || 0 })}
          />
        </div>
        <div>
          <label className="block text-xs uppercase tracking-wider text-aq-trace mb-1.5">
            Para birimi
          </label>
          <select
            value={value.currency}
            onChange={(e) => onChange({ ...value, currency: e.target.value })}
            className="w-full rounded-md border border-aq-mist/40 bg-aq-orbital/40 px-3 py-2 text-sm"
          >
            {["TRY", "USD", "EUR", "GBP"].map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-xs uppercase tracking-wider text-aq-trace mb-1.5">
            Düzenleme
          </label>
          <Input
            type="date"
            value={value.issue_date}
            onChange={(e) => onChange({ ...value, issue_date: e.target.value })}
          />
        </div>
        <div>
          <label className="block text-xs uppercase tracking-wider text-aq-trace mb-1.5">
            Vade
          </label>
          <Input
            type="date"
            value={value.due_date}
            onChange={(e) => onChange({ ...value, due_date: e.target.value })}
          />
        </div>
      </div>

      <div>
        <label className="block text-xs uppercase tracking-wider text-aq-trace mb-1.5">
          Açıklama (opsiyonel)
        </label>
        <Input
          value={value.description}
          onChange={(e) => onChange({ ...value, description: e.target.value })}
          placeholder="örn. Q2 sezon teslimatı"
        />
      </div>
    </div>
  );
}

function StepSummary({ state }: { state: OnboardingState }) {
  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Özet & başlat</h2>
        <p className="mt-1 text-sm text-aq-dust">
          Aşağıdaki bilgiler ile sistemini başlatıyoruz.
        </p>
      </div>

      <div className="rounded-lg border border-aq-mist/40 divide-y divide-aq-mist/30">
        <SummaryRow label="Şirket" value={state.company.name} />
        <SummaryRow label="Sektör" value={state.company.sector} />
        <SummaryRow
          label="Çalışan sayısı"
          value={state.company.employee_count.toString()}
        />
        <SummaryRow
          label="Başlangıç bakiyesi"
          value={`₺${state.company.initial_balance.toLocaleString("tr-TR")}`}
        />
        <SummaryRow label="Entegrasyon" value={state.connector.connector_type} />
        <SummaryRow
          label="İlk müşteri"
          value={state.invoice.customer_name || "—"}
        />
        <SummaryRow
          label="Fatura tutarı"
          value={`${state.invoice.currency} ${state.invoice.amount.toLocaleString("tr-TR")}`}
        />
        <SummaryRow
          label="Vade"
          value={state.invoice.due_date}
        />
      </div>

      <div className="rounded-lg border border-aq-mint/30 bg-aq-mint/5 p-3 text-xs text-aq-mint">
        ✨ Tamamlandığında dashboard&apos;a yönlendirileceksin. Vade uyarı motoru
        otomatik aktive olacak.
      </div>
    </div>
  );
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between px-4 py-2.5 text-sm">
      <span className="text-aq-dust">{label}</span>
      <span className="font-medium tabular-nums">{value}</span>
    </div>
  );
}
