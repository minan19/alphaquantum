"use client";

import { motion } from "framer-motion";
import {
  AlertTriangle,
  Bell,
  Database,
  Download,
  FileSignature,
  Lock,
  Mail,
  MessageSquare,
  Phone,
  ShieldCheck,
  Smartphone,
  Trash2,
  User as UserIcon,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
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

function KVKKTab() {
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
            <Badge tone="success" withDot>Aktif</Badge>
          </div>
        </div>
      </Card>

      {/* Rights grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <RightCard
          icon={Database}
          title="Verilerimi indir"
          description="Hesabınıza ait tüm kişisel verilerin JSON dışa aktarımı"
          ctaLabel="Hazırla ve indir"
          tone="primary"
          onClick={() => toast.success("Veri export hazırlanıyor", { description: "E-postanıza gönderilecek." })}
        />
        <RightCard
          icon={FileSignature}
          title="İşleme faaliyetleri"
          description="Verilerinizin hangi amaçla işlendiğini görüntüleyin"
          ctaLabel="Listeyi gör"
          tone="info"
        />
        <RightCard
          icon={ShieldCheck}
          title="Onay geçmişi"
          description="KVKK onay versiyonu ve verme tarihi"
          ctaLabel="Geçmişi gör"
          tone="info"
        />
        <RightCard
          icon={Trash2}
          title="Hesabı sil"
          description="Silme talebi başlatın (yasal saklama süresi sonrası anonimleştirilir)"
          ctaLabel="Talep oluştur"
          tone="critical"
          onClick={() => toast.warning("Onay gerekli", {
            description: "Silme talebi açıldıktan sonra admin onayı bekler.",
          })}
        />
      </div>

      {/* Activity */}
      <Card>
        <CardHeader>
          <CardTitle>Son veri erişim hareketleri</CardTitle>
          <CardDescription>Audit log — KVKK madde 12 izlenebilirlik</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          <ActivityRow time="Bugün 14:22" event="Veri erişimi" detail="GET /me/data — başarılı" />
          <ActivityRow time="Bugün 11:08" event="Oturum başlatma" detail="IP 192.168.1.34" />
          <ActivityRow time="Dün 09:15" event="Onay güncellemesi" detail="KVKK v1 → v1" />
          <ActivityRow time="3 gün önce" event="Şifre değişikliği" detail="Kullanıcı tetikledi" />
        </CardContent>
      </Card>

      {/* Legal note */}
      <div className="flex items-start gap-3 rounded-lg border border-aq-mist/40 bg-aq-orbital/30 p-4">
        <AlertTriangle className="h-4 w-4 text-aq-solar shrink-0 mt-0.5" />
        <p className="text-xs text-aq-dust leading-relaxed">
          Verilerinizden bir kısmı yasal saklama yükümlülüğü (KVKK madde 7) gereği
          5 yıla kadar arşivde tutulabilir. Bu süre boyunca PII alanlar
          maskelenir ve aktif kullanım dışıdır.
        </p>
      </div>
    </motion.div>
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
  icon: Icon, title, description, ctaLabel, tone, onClick,
}: {
  icon: typeof Database;
  title: string;
  description: string;
  ctaLabel: string;
  tone: "primary" | "info" | "critical";
  onClick?: () => void;
}) {
  const toneClass = {
    primary:  "ring-aq-quantum/30 from-aq-quantum/10",
    info:     "ring-aq-plasma/30 from-aq-plasma/10",
    critical: "ring-aq-fission/30 from-aq-fission/10",
  }[tone];
  return (
    <Card
      onClick={onClick}
      className={cn(
        "group relative overflow-hidden p-5 cursor-pointer ring-1",
        toneClass,
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
        >
          {tone === "critical" && <Download className="h-3.5 w-3.5" />}
          {tone !== "critical" && <Download className="h-3.5 w-3.5" />}
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
