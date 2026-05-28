"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { motion, AnimatePresence } from "framer-motion";
import {
  AlertTriangle,
  Bell,
  CheckCircle2,
  ChevronRight,
  Database,
  Download,
  FileSignature,
  Loader2,
  Lock,
  Mail,
  MessageSquare,
  Phone,
  ShieldCheck,
  Smartphone,
  Trash2,
  User as UserIcon,
  X,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import {
  ApiError,
  createDeletionRequest,
  fetchConsentStatus,
  fetchMyDataExport,
  fetchMyDeletionRequests,
  fetchProcessingActivities,
  recordConsent,
  type KVKKConsentStatus,
  type KVKKDeletionRequest,
  type KVKKProcessingActivity,
} from "@/lib/api";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/cn";

type Tab = "profile" | "security" | "kvkk" | "notifications";

const TABS: { id: Tab; label: string; icon: typeof UserIcon }[] = [
  { id: "profile",       label: "Profil",          icon: UserIcon },
  { id: "security",      label: "Güvenlik",        icon: Lock },
  { id: "kvkk",          label: "KVKK & Veriler",  icon: ShieldCheck },
  { id: "notifications", label: "Bildirim Tercihleri", icon: Bell },
];

const CURRENT_CONSENT_VERSION = "v1";

export default function SettingsPage() {
  const [tab, setTab] = useState<Tab>("kvkk");

  return (
    <div className="space-y-6 animate-fade-in">
      <header>
        <h1 className="text-3xl font-bold tracking-tight">Ayarlar</h1>
        <p className="mt-1 text-sm text-aq-dust">Hesap, güvenlik ve KVKK haklarınız</p>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-[220px_1fr] gap-6">
        {/* Sidebar tabs */}
        <aside className="space-y-1">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={cn(
                "group w-full flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-all",
                tab === t.id
                  ? "bg-aq-quantum/15 text-foreground ring-1 ring-aq-quantum/30"
                  : "text-aq-dust hover:text-foreground hover:bg-aq-mist/40",
              )}
            >
              <t.icon className={cn(
                "h-4 w-4 shrink-0",
                tab === t.id && "text-aq-quantum-2",
              )} />
              <span className="flex-1 text-left">{t.label}</span>
            </button>
          ))}
        </aside>

        {/* Content */}
        <section>
          {tab === "profile" && <ProfileTab />}
          {tab === "security" && <SecurityTab />}
          {tab === "kvkk" && <KVKKTab />}
          {tab === "notifications" && <NotificationsTab />}
        </section>
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────────── */

function ProfileTab() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="space-y-6"
    >
      <Card>
        <CardHeader>
          <CardTitle>Profil bilgileri</CardTitle>
          <CardDescription>Kişisel bilgilerinizi yönetin</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Row icon={UserIcon} label="Ad Soyad" value="Yönetici" />
          <Row icon={Mail} label="E-posta" value="—" />
          <Row icon={Phone} label="Telefon" value="—" />
        </CardContent>
      </Card>
    </motion.div>
  );
}

function SecurityTab() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="space-y-6"
    >
      <Card>
        <CardHeader>
          <CardTitle>Şifre & oturum</CardTitle>
          <CardDescription>Hesabınızı koruyun</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Button variant="secondary" className="w-full justify-start">
            <Lock className="h-4 w-4" /> Şifreyi değiştir
          </Button>
          <Button variant="secondary" className="w-full justify-start">
            <Smartphone className="h-4 w-4" /> İki faktörlü doğrulama (yakında)
          </Button>
        </CardContent>
      </Card>
    </motion.div>
  );
}

function NotificationsTab() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="space-y-6"
    >
      <Card>
        <CardHeader>
          <CardTitle>Bildirim kanalları</CardTitle>
          <CardDescription>Hangi kanaldan haberdar olmak istersiniz?</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <ToggleRow icon={Mail}            label="E-posta"  defaultOn={true} />
          <ToggleRow icon={Smartphone}      label="SMS"      defaultOn={false} />
          <ToggleRow icon={MessageSquare}   label="WhatsApp" defaultOn={false} />
        </CardContent>
      </Card>
    </motion.div>
  );
}

/* ── KVKK live tab ────────────────────────────────────────────────────── */

function KVKKTab() {
  const [consent, setConsent] = useState<KVKKConsentStatus | null>(null);
  const [consentLoading, setConsentLoading] = useState(true);
  const [consentSaving, setConsentSaving] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [deletionRequests, setDeletionRequests] = useState<KVKKDeletionRequest[]>([]);
  const [activities, setActivities] = useState<KVKKProcessingActivity[] | null>(null);
  const [activitiesOpen, setActivitiesOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  const loadAll = useCallback(async () => {
    setConsentLoading(true);
    try {
      const [c, d] = await Promise.all([
        fetchConsentStatus(),
        fetchMyDeletionRequests(),
      ]);
      setConsent(c);
      setDeletionRequests(d.requests);
    } catch (err) {
      const detail =
        err instanceof ApiError ? `HTTP ${err.status}` : "Bilinmeyen hata";
      toast.error("KVKK verileri yüklenemedi", { description: detail });
    } finally {
      setConsentLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const handleGiveConsent = async () => {
    setConsentSaving(true);
    try {
      const status = await recordConsent(CURRENT_CONSENT_VERSION);
      setConsent(status);
      toast.success("KVKK onayı kaydedildi", {
        description: `Versiyon ${status.consent_version}`,
      });
    } catch (err) {
      const detail =
        err instanceof ApiError ? `HTTP ${err.status}` : "Bilinmeyen hata";
      toast.error("Onay kaydedilemedi", { description: detail });
    } finally {
      setConsentSaving(false);
    }
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      const data = await fetchMyDataExport();
      // download as JSON file
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `kvkk-data-${data.username}-${data.exported_at}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast.success("Veri export indirildi", {
        description: `İmza: ${data.export_signature.slice(0, 32)}…`,
      });
      // refresh consent status so last_data_export_at reflects
      loadAll();
    } catch (err) {
      const detail =
        err instanceof ApiError ? `HTTP ${err.status}` : "Bilinmeyen hata";
      toast.error("Export başarısız", { description: detail });
    } finally {
      setExporting(false);
    }
  };

  const handleViewActivities = async () => {
    if (!activities) {
      try {
        const r = await fetchProcessingActivities();
        setActivities(r.activities);
      } catch (err) {
        const detail =
          err instanceof ApiError ? `HTTP ${err.status}` : "Bilinmeyen hata";
        toast.error("Aydınlatma metni yüklenemedi", { description: detail });
        return;
      }
    }
    setActivitiesOpen(true);
  };

  const consentGiven = (consent?.consent_at ?? 0) > 0;
  const pendingDeletion = deletionRequests.find((r) => r.status === "pending");

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="space-y-6"
    >
      {/* Hero */}
      <Card variant="gradient" className="p-[1px]">
        <div className="rounded-lg bg-card p-6">
          <div className="flex items-start gap-4">
            <div className="grid h-10 w-10 place-items-center rounded-md bg-gradient-to-br from-aq-quantum/20 to-aq-plasma/20 ring-1 ring-aq-quantum/30">
              <ShieldCheck className="h-5 w-5 text-aq-quantum-2" />
            </div>
            <div className="flex-1">
              <h2 className="text-lg font-semibold">KVKK Veri Hakları Merkezi</h2>
              <p className="mt-1 text-sm text-aq-dust">
                Kişisel Verilerin Korunması Kanunu madde 11 kapsamında haklarınızı bu sayfadan kullanabilirsiniz.
              </p>
            </div>
            {consentLoading ? (
              <Badge tone="neutral">Yükleniyor…</Badge>
            ) : consentGiven ? (
              <Badge tone="success" withDot>Onay verildi</Badge>
            ) : (
              <Badge tone="warn" withDot>Onay yok</Badge>
            )}
          </div>

          {/* Consent action band */}
          {!consentLoading && !consentGiven && (
            <div className="mt-4 flex items-center justify-between gap-4 rounded-md border border-aq-solar/30 bg-aq-solar/5 p-3">
              <p className="text-sm">
                <span className="font-medium">Açık rıza gerekli:</span>{" "}
                <span className="text-aq-dust">
                  Veri hakları araçlarını kullanmak için KVKK aydınlatma metnini onaylayın.
                </span>
              </p>
              <Button
                size="sm"
                onClick={handleGiveConsent}
                disabled={consentSaving}
              >
                {consentSaving ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <CheckCircle2 className="h-3.5 w-3.5" />
                )}
                Onayla (v{CURRENT_CONSENT_VERSION})
              </Button>
            </div>
          )}
        </div>
      </Card>

      {/* Rights grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <RightCard
          icon={Database}
          title="Verilerimi indir"
          description="HMAC-SHA256 imzalı JSON dışa aktarım (madde 11/b)"
          ctaLabel={exporting ? "Hazırlanıyor…" : "Hazırla ve indir"}
          tone="primary"
          loading={exporting}
          disabled={!consentGiven || exporting}
          onClick={handleExport}
        />
        <RightCard
          icon={FileSignature}
          title="İşleme faaliyetleri"
          description="Hangi veriler hangi amaçla işlenir (madde 13)"
          ctaLabel="Listeyi gör"
          tone="info"
          onClick={handleViewActivities}
        />
        <RightCard
          icon={ShieldCheck}
          title="Onay geçmişi"
          description={
            consent && consentGiven
              ? `Versiyon ${consent.consent_version} — ${epochToHuman(consent.consent_at)}`
              : "Henüz onay verilmedi"
          }
          ctaLabel={consentGiven ? "Onayı yenile" : "Onay ver"}
          tone="info"
          disabled={consentSaving}
          onClick={handleGiveConsent}
        />
        <RightCard
          icon={Trash2}
          title="Hesabı sil"
          description={
            pendingDeletion
              ? `Talep #${pendingDeletion.id} işlemde (admin onayı bekleniyor)`
              : "Silme talebi başlat (yasal saklama süresi sonrası anonimleştirilir)"
          }
          ctaLabel={pendingDeletion ? "Talep oluşturuldu" : "Talep oluştur"}
          tone="critical"
          disabled={!!pendingDeletion || !consentGiven}
          onClick={() => setDeleteOpen(true)}
        />
      </div>

      {/* Deletion request history */}
      <Card>
        <CardHeader>
          <CardTitle>Silme talebi geçmişi</CardTitle>
          <CardDescription>KVKK madde 11/e — geçmiş talepleriniz ve durumları</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {consentLoading ? (
            <div className="text-sm text-aq-dust">Yükleniyor…</div>
          ) : deletionRequests.length === 0 ? (
            <div className="rounded-md border border-dashed border-aq-mist/40 bg-aq-orbital/20 p-4 text-center text-sm text-aq-dust">
              Henüz silme talebi yok.
            </div>
          ) : (
            deletionRequests.map((r) => (
              <DeletionRow key={r.id} request={r} />
            ))
          )}
        </CardContent>
      </Card>

      {/* Activity overview */}
      <Card>
        <CardHeader>
          <CardTitle>Son veri erişim hareketleri</CardTitle>
          <CardDescription>KVKK madde 12 — izlenebilirlik</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {consent ? (
            <>
              <ActivityRow
                time={epochToHuman(consent.last_data_access_at ?? 0)}
                event="Son veri erişimi"
                detail={consent.last_data_access_at ? "GET /me/data" : "—"}
              />
              <ActivityRow
                time={epochToHuman(consent.last_data_export_at ?? 0)}
                event="Son veri export"
                detail={consent.last_data_export_at ? "HMAC imzalı JSON" : "Henüz yok"}
              />
              <ActivityRow
                time={epochToHuman(consent.consent_at)}
                event="KVKK onayı"
                detail={
                  consent.consent_at
                    ? `Versiyon ${consent.consent_version}`
                    : "Verilmedi"
                }
              />
            </>
          ) : (
            <div className="text-sm text-aq-dust">Yükleniyor…</div>
          )}
        </CardContent>
      </Card>

      {/* Legal note */}
      <div className="flex items-start gap-3 rounded-lg border border-aq-mist/40 bg-aq-orbital/30 p-4">
        <AlertTriangle className="h-4 w-4 text-aq-solar shrink-0 mt-0.5" />
        <p className="text-xs text-aq-dust leading-relaxed">
          Verilerinizden bir kısmı yasal saklama yükümlülüğü (KVKK madde 7 / VUK madde 253)
          gereği 5–10 yıla kadar arşivde tutulabilir. Bu süre boyunca PII alanlar
          maskelenir ve aktif kullanım dışıdır.
        </p>
      </div>

      {/* Modals */}
      <DeletionRequestModal
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        onSubmitted={(req) => {
          setDeletionRequests((prev) => [req, ...prev]);
          setDeleteOpen(false);
        }}
      />
      <ActivitiesDrawer
        open={activitiesOpen}
        onOpenChange={setActivitiesOpen}
        activities={activities ?? []}
      />
    </motion.div>
  );
}

/* ─── KVKK sub-components ────────────────────────────────────────────────── */

function DeletionRow({ request }: { request: KVKKDeletionRequest }) {
  const toneByStatus: Record<KVKKDeletionRequest["status"], "warn" | "critical" | "success" | "neutral"> = {
    pending:   "warn",
    approved:  "success",
    rejected:  "critical",
    completed: "neutral",
  };
  return (
    <div className="flex items-start justify-between gap-3 rounded-md border border-aq-mist/30 bg-aq-orbital/30 px-3 py-2.5 text-sm">
      <div className="space-y-0.5">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs text-aq-trace">#{request.id}</span>
          <Badge tone={toneByStatus[request.status]} withDot>
            {request.status}
          </Badge>
        </div>
        <div className="text-xs text-aq-dust line-clamp-1">
          {request.reason || "(sebep belirtilmedi)"}
        </div>
        {request.decision_note && (
          <div className="text-[11px] text-aq-trace italic">
            Karar notu: {request.decision_note}
          </div>
        )}
      </div>
      <div className="text-right shrink-0">
        <div className="text-[10px] uppercase tracking-wider text-aq-trace">
          {epochToHuman(request.requested_at)}
        </div>
        {request.anonymized_fields.length > 0 && (
          <div className="mt-1 text-[10px] text-aq-quantum-2">
            {request.anonymized_fields.length} alan anonimleştirildi
          </div>
        )}
      </div>
    </div>
  );
}

function DeletionRequestModal({
  open,
  onOpenChange,
  onSubmitted,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmitted: (req: KVKKDeletionRequest) => void;
}) {
  const [reason, setReason] = useState("");
  const [confirmText, setConfirmText] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const canSubmit = confirmText.trim().toUpperCase() === "SİL" && !submitting;

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    try {
      const req = await createDeletionRequest(reason.trim());
      toast.success("Silme talebi oluşturuldu", {
        description: `Talep #${req.id} — admin onayı bekleniyor`,
      });
      setReason("");
      setConfirmText("");
      onSubmitted(req);
    } catch (err) {
      const detail =
        err instanceof ApiError ? `HTTP ${err.status}` : "Bilinmeyen hata";
      toast.error("Talep oluşturulamadı", { description: detail });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-aq-void/70 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
        <Dialog.Content
          className={cn(
            "fixed left-1/2 top-1/2 z-50 w-[95vw] max-w-md -translate-x-1/2 -translate-y-1/2",
            "rounded-lg border border-aq-fission/30 bg-card p-6 shadow-elevation-3",
            "data-[state=open]:animate-in data-[state=closed]:animate-out",
            "data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
            "data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95",
          )}
        >
          <div className="flex items-start gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-md bg-aq-fission/15 ring-1 ring-aq-fission/30">
              <Trash2 className="h-5 w-5 text-aq-fission" />
            </div>
            <div className="flex-1">
              <Dialog.Title className="text-lg font-semibold">
                Hesabı silme talebi
              </Dialog.Title>
              <Dialog.Description className="mt-1 text-sm text-aq-dust">
                Bu işlem admin onayından sonra hesabınızı anonimleştirir. Yasal
                saklama yükümlülüğü gereği kayıt tamamen silinmez, PII alanları
                maskelenir.
              </Dialog.Description>
            </div>
            <Dialog.Close className="rounded-md p-1 text-aq-dust hover:text-foreground hover:bg-aq-mist/30">
              <X className="h-4 w-4" />
            </Dialog.Close>
          </div>

          <div className="mt-5 space-y-4">
            <label className="block">
              <span className="text-xs uppercase tracking-wider text-aq-trace">
                Talep sebebi (opsiyonel)
              </span>
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                rows={3}
                maxLength={500}
                placeholder="Örn: Hesabımı artık kullanmıyorum"
                className={cn(
                  "mt-1 w-full rounded-md border border-aq-mist/40 bg-aq-orbital/40",
                  "px-3 py-2 text-sm placeholder:text-aq-trace",
                  "focus:outline-none focus:ring-2 focus:ring-aq-quantum/40 focus:border-aq-quantum/40",
                )}
              />
              <div className="mt-1 text-right text-[10px] text-aq-trace">
                {reason.length}/500
              </div>
            </label>

            <label className="block">
              <span className="text-xs uppercase tracking-wider text-aq-trace">
                Onaylamak için &quot;SİL&quot; yazın
              </span>
              <input
                type="text"
                value={confirmText}
                onChange={(e) => setConfirmText(e.target.value)}
                placeholder="SİL"
                className={cn(
                  "mt-1 w-full rounded-md border border-aq-fission/30 bg-aq-fission/5",
                  "px-3 py-2 text-sm font-mono",
                  "focus:outline-none focus:ring-2 focus:ring-aq-fission/40",
                )}
              />
            </label>
          </div>

          <div className="mt-6 flex justify-end gap-2">
            <Dialog.Close asChild>
              <Button variant="ghost">Vazgeç</Button>
            </Dialog.Close>
            <Button
              variant="destructive"
              onClick={handleSubmit}
              disabled={!canSubmit}
            >
              {submitting ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Trash2 className="h-3.5 w-3.5" />
              )}
              Silme talebini gönder
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function ActivitiesDrawer({
  open,
  onOpenChange,
  activities,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  activities: KVKKProcessingActivity[];
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-aq-void/70 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
        <Dialog.Content
          className={cn(
            "fixed left-1/2 top-1/2 z-50 w-[95vw] max-w-2xl max-h-[85vh] -translate-x-1/2 -translate-y-1/2",
            "overflow-y-auto rounded-lg border border-aq-quantum/30 bg-card p-6 shadow-elevation-3",
          )}
        >
          <div className="flex items-start gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-md bg-aq-quantum/15 ring-1 ring-aq-quantum/30">
              <FileSignature className="h-5 w-5 text-aq-quantum-2" />
            </div>
            <div className="flex-1">
              <Dialog.Title className="text-lg font-semibold">
                Veri İşleme Faaliyetleri
              </Dialog.Title>
              <Dialog.Description className="mt-1 text-sm text-aq-dust">
                KVKK madde 13 — aydınlatma yükümlülüğü kapsamında verilerinizin
                hangi amaçla ve yasal gerekçeyle işlendiğinin dökümü.
              </Dialog.Description>
            </div>
            <Dialog.Close className="rounded-md p-1 text-aq-dust hover:text-foreground hover:bg-aq-mist/30">
              <X className="h-4 w-4" />
            </Dialog.Close>
          </div>

          <div className="mt-5 space-y-3">
            <AnimatePresence>
              {activities.map((a, idx) => (
                <motion.div
                  key={a.activity}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.25, delay: idx * 0.04 }}
                  className="rounded-md border border-aq-mist/30 bg-aq-orbital/30 p-4"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1">
                      <h3 className="font-semibold">{a.activity}</h3>
                      <p className="mt-0.5 text-xs text-aq-dust">{a.purpose}</p>
                    </div>
                    {a.third_party_sharing && (
                      <Badge tone="warn">3. taraf paylaşımı</Badge>
                    )}
                  </div>
                  <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
                    <div>
                      <span className="uppercase tracking-wider text-aq-trace text-[10px]">
                        Yasal gerekçe
                      </span>
                      <div className="text-aq-dust">{a.legal_basis}</div>
                    </div>
                    <div>
                      <span className="uppercase tracking-wider text-aq-trace text-[10px]">
                        Saklama süresi
                      </span>
                      <div className="text-aq-dust">{a.retention_period}</div>
                    </div>
                    <div className="sm:col-span-2">
                      <span className="uppercase tracking-wider text-aq-trace text-[10px]">
                        Veri kategorileri
                      </span>
                      <div className="mt-1 flex flex-wrap gap-1.5">
                        {a.data_categories.map((c) => (
                          <span
                            key={c}
                            className="rounded-full bg-aq-quantum/10 px-2 py-0.5 text-[10px] text-aq-quantum-2"
                          >
                            {c}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>

          <div className="mt-5 flex justify-end">
            <Dialog.Close asChild>
              <Button variant="secondary">Kapat</Button>
            </Dialog.Close>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

/* ─────────────────────────────────────────────────────────────────────── */

function Row({
  icon: Icon, label, value,
}: { icon: typeof UserIcon; label: string; value: string }) {
  return (
    <div className="flex items-center gap-3 rounded-md bg-aq-orbital/40 px-3 py-2.5">
      <Icon className="h-4 w-4 text-aq-dust" />
      <div className="flex-1">
        <div className="text-[10px] uppercase tracking-wider text-aq-trace">{label}</div>
        <div className="text-sm">{value}</div>
      </div>
    </div>
  );
}

function ToggleRow({
  icon: Icon, label, defaultOn,
}: { icon: typeof Mail; label: string; defaultOn: boolean }) {
  const [on, setOn] = useState(defaultOn);
  return (
    <div className="flex items-center justify-between rounded-md bg-aq-orbital/40 px-3 py-2.5">
      <div className="flex items-center gap-3">
        <Icon className="h-4 w-4 text-aq-dust" />
        <span className="text-sm">{label}</span>
      </div>
      <button
        role="switch"
        aria-checked={on}
        onClick={() => setOn(!on)}
        className={cn(
          "relative h-5 w-9 rounded-full transition-colors ease-quantum",
          on ? "bg-aq-quantum" : "bg-aq-mist",
        )}
      >
        <motion.span
          layout
          className={cn(
            "absolute top-0.5 left-0.5 h-4 w-4 rounded-full bg-white shadow",
            on && "translate-x-4",
          )}
          transition={{ duration: 0.25, ease: [0.32, 0.72, 0, 1] }}
        />
      </button>
    </div>
  );
}

function RightCard({
  icon: Icon, title, description, ctaLabel, tone, onClick, disabled, loading,
}: {
  icon: typeof Database;
  title: string;
  description: string;
  ctaLabel: string;
  tone: "primary" | "info" | "critical";
  onClick?: () => void;
  disabled?: boolean;
  loading?: boolean;
}) {
  const toneClass = {
    primary:  "ring-aq-quantum/30 from-aq-quantum/10",
    info:     "ring-aq-plasma/30 from-aq-plasma/10",
    critical: "ring-aq-fission/30 from-aq-fission/10",
  }[tone];
  return (
    <Card
      className={cn(
        "group relative overflow-hidden p-5 ring-1 transition-opacity",
        toneClass,
        disabled && "opacity-60 pointer-events-none",
      )}
    >
      <div className={cn(
        "absolute -right-10 -top-10 h-32 w-32 rounded-full blur-3xl bg-gradient-to-br opacity-50",
        toneClass,
      )} />
      <div className="relative space-y-3">
        <div className={cn(
          "grid h-10 w-10 place-items-center rounded-md bg-aq-orbital/60",
          tone === "primary" && "text-aq-quantum-2",
          tone === "info" && "text-aq-plasma",
          tone === "critical" && "text-aq-fission",
        )}>
          <Icon className="h-5 w-5" />
        </div>
        <div>
          <h3 className="font-semibold">{title}</h3>
          <p className="mt-1 text-sm text-aq-dust">{description}</p>
        </div>
        <Button
          variant={tone === "critical" ? "destructive" : "secondary"}
          size="sm"
          className="w-full"
          onClick={onClick}
          disabled={disabled}
        >
          {loading ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : tone === "info" ? (
            <ChevronRight className="h-3.5 w-3.5" />
          ) : (
            <Download className="h-3.5 w-3.5" />
          )}
          {ctaLabel}
        </Button>
      </div>
    </Card>
  );
}

function ActivityRow({
  time, event, detail,
}: { time: string; event: string; detail: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 rounded-md bg-aq-orbital/30 px-3 py-2 text-sm">
      <div className="flex items-center gap-3">
        <span className="h-1.5 w-1.5 rounded-full bg-aq-quantum-2" />
        <span className="font-medium">{event}</span>
        <span className="text-aq-dust text-xs">— {detail}</span>
      </div>
      <span className="font-mono text-[10px] text-aq-trace shrink-0">{time}</span>
    </div>
  );
}

/* ─── helpers ──────────────────────────────────────────────────────────── */

function epochToHuman(epoch: number): string {
  if (!epoch || epoch <= 0) return "—";
  const d = new Date(epoch * 1000);
  return d.toLocaleString("tr-TR", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}
