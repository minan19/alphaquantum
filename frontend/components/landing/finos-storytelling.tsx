"use client";

/**
 * F3: "KOBİ patronu bir sabahı" — FinOS Storytelling
 *
 * B1'in (Holding patronu bir günü) FinOS karşılığı. Mint accent + KOBİ
 * patron Ahmet bey'in günü (07:30-16:30). Tek tekstil firması işleten
 * patron için S-331/S-332/S-333/S-334 özelliklerini canlı gösterir.
 *
 * Tasarım doc K4.2: "FinOS karşılığı: KOBİ patronu bir sabahı — daha
 * hızlı, daha enerjik geçişler (mint renk). Telefon mockup (CorpOS
 * laptop, FinOS telefon)."
 *
 * Stack: Framer Motion useScroll + useTransform + mountall mockup
 * (B1-FIX-v2'deki race condition fix'i ile aynı strateji).
 */

import { useEffect, useRef, useState } from "react";
import {
  motion,
  useScroll,
  useTransform,
} from "framer-motion";
import {
  AlertTriangle,
  CalendarClock,
  Coffee,
  MessageCircle,
  TrendingUp,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/cn";
import { easeEnterprise } from "@/lib/motion";

interface FinosScene {
  time: string;
  icon: LucideIcon;
  title: string;
  body: string;
  metric: string;
  mockup: FinosMockupVariant;
}

type FinosMockupVariant =
  | "morning-cash"
  | "risk-score"
  | "aging-analysis"
  | "cashflow-projection"
  | "whatsapp-collection";

const SCENES: FinosScene[] = [
  {
    time: "07:30",
    icon: Coffee,
    title: "Sabah ofise gelmeden — Cep telefonundan bakiye",
    body: "Banka bakiyesi 285.000₺. Gece otomatik tahsilat 14.500₺ geldi. Bu hafta 4 vade hatırlatması atılmış, 2 müşteri ödeme yapmış.",
    metric: "₺285.000 bakiye · 4 hatırlatma · 2 tahsilat",
    mockup: "morning-cash",
  },
  {
    time: "09:15",
    icon: AlertTriangle,
    title: "Yeni müşteri — Risk skoru kararı",
    body: "X Tekstil siparişi geldi: ₺75.000, 60 gün vade. Risk skoru 73/100 (orta-iyi). AI önerisi: Avans ile satışı kabul et, ek teminat iste.",
    metric: "73/100 risk · AI önerili karar",
    mockup: "risk-score",
  },
  {
    time: "11:00",
    icon: CalendarClock,
    title: "Alacak yaşlandırma — Hangileri kritik",
    body: "5 fatura 30+ gün geçmiş. Toplam ₺142.000. 2 müşteri 60+ gün — hukuki süreç eşiğinde. Aging analizi tek bakışta öncelikleri gösterir.",
    metric: "5 overdue · 2 hukuki risk",
    mockup: "aging-analysis",
  },
  {
    time: "14:00",
    icon: TrendingUp,
    title: "30 günlük nakit projeksiyon",
    body: "Önümüzdeki 30 günde ₺180.000 giriş, ₺120.000 çıkış bekleniyor. Net pozitif ₺60.000. Maliyet ek finansman gereksiz — büyüme planı için elverişli pencere.",
    metric: "₺60K net 30 gün · büyüme açık",
    mockup: "cashflow-projection",
  },
  {
    time: "16:30",
    icon: MessageCircle,
    title: "WhatsApp tahsilat — Otomatik gönderim",
    body: "12 müşteriye otomatik vade hatırlatma WhatsApp ile gönderildi. 6 müşteri okudu, 3'ü ödeme sözü verdi. Hatırlatma için iş gücü harcanmıyor.",
    metric: "12 hatırlatma · 3 ödeme sözü",
    mockup: "whatsapp-collection",
  },
];

export function FinosStorytelling() {
  const containerRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start start", "end end"],
  });

  // Sahne index — clock kararsız float'a karşı sağlam guard
  const sceneIndex = useTransform(scrollYProgress, (v) => {
    const idx = Math.floor(v * SCENES.length);
    return Math.min(Math.max(idx, 0), SCENES.length - 1);
  });

  // KOBİ patron 07:30 → 16:30 (9 saat)
  const clockLabel = useTransform(scrollYProgress, (v) => {
    const totalMin = 7 * 60 + 30 + v * 9 * 60;
    const h = Math.floor(totalMin / 60);
    const m = Math.floor(totalMin % 60);
    return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
  });

  return (
    <section
      ref={containerRef}
      aria-label="KOBİ patronu bir sabahı"
      className="relative bg-aq-void"
      style={{ height: `${SCENES.length * 100}vh` }}
    >
      <div className="sticky top-0 grid h-screen grid-cols-1 lg:grid-cols-[0.95fr_1.05fr] overflow-hidden">
        {/* Left: scenes (text-first, FinOS enerjik akış) */}
        <div className="relative flex flex-col justify-center px-6 lg:px-16 py-10 overflow-y-auto bg-gradient-to-br from-aq-cosmos to-aq-void">
          <FinosClockIndicator clockLabel={clockLabel} />

          <header className="mb-10 mt-6">
            <div className="inline-flex items-center gap-2 rounded-full border border-aq-mint/30 bg-aq-mint/10 px-3 py-1 text-[10px] font-mono uppercase tracking-[0.18em] text-aq-mint mb-3">
              <span className="h-1.5 w-1.5 rounded-full bg-aq-mint animate-pulse" />
              FinOS · KOBİ senaryosu
            </div>
            <h2 className="text-3xl lg:text-4xl font-bold tracking-tight">
              KOBİ patronu{" "}
              <span className="bg-gradient-to-r from-aq-mint to-aq-fusion bg-clip-text text-transparent">
                bir sabahı
              </span>
            </h2>
            <p className="mt-3 text-sm lg:text-base text-aq-dust max-w-xl">
              5 sahne — 07:30&apos;dan 16:30&apos;a. Tek tekstil firması işleten
              Ahmet bey&apos;in FinOS ile günü.
            </p>
            <div className="mt-4 inline-flex items-center gap-2 rounded-md border border-aq-fusion/25 bg-aq-fusion/5 px-2.5 py-1 text-[10px] font-mono text-aq-fusion/90">
              <span className="grid h-1.5 w-1.5 place-items-center rounded-full bg-aq-fusion animate-pulse" />
              S-331 + S-332 + S-333 + S-334 gerçek backend
            </div>
          </header>

          <div className="space-y-10">
            {SCENES.map((scene, idx) => (
              <FinosSceneBlock
                key={idx}
                scene={scene}
                index={idx}
                sceneIndex={sceneIndex}
              />
            ))}
          </div>
        </div>

        {/* Right: phone mockup (FinOS = telefon, doc K4.2) */}
        <div className="relative hidden lg:flex flex-col items-center justify-center p-12">
          <div className="relative w-full max-w-sm">
            <FinosMockupCrossfade sceneIndex={sceneIndex} />
            <FinosSceneCounter sceneIndex={sceneIndex} />
          </div>
        </div>
      </div>
    </section>
  );
}

/* ── Components ───────────────────────────────────────────────────────── */

function FinosClockIndicator({
  clockLabel,
}: {
  clockLabel: ReturnType<typeof useTransform<number, string>>;
}) {
  return (
    <div className="inline-flex items-center gap-3 rounded-full border border-aq-mint/30 bg-aq-orbital/60 backdrop-blur-sm px-4 py-2 w-fit">
      <span className="grid h-7 w-7 place-items-center rounded-full bg-aq-mint/15 ring-1 ring-aq-mint/30">
        <svg
          className="h-3.5 w-3.5 text-aq-mint"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        >
          <circle cx="12" cy="12" r="10" />
          <polyline points="12 6 12 12 16 14" />
        </svg>
      </span>
      <div>
        <div className="text-[9px] uppercase tracking-wider text-aq-trace">
          Bir sabahı
        </div>
        <motion.div className="font-mono font-bold tracking-tight tabular-nums">
          {clockLabel}
        </motion.div>
      </div>
    </div>
  );
}

function FinosSceneBlock({
  scene,
  index,
  sceneIndex,
}: {
  scene: FinosScene;
  index: number;
  sceneIndex: ReturnType<typeof useTransform<number, number>>;
}) {
  const active = useReactiveActiveIdx(sceneIndex) === index;
  const Icon = scene.icon;
  return (
    <motion.article
      animate={{
        opacity: active ? 1 : 0.35,
        scale: active ? 1 : 0.97,
      }}
      transition={{ duration: 0.4, ease: easeEnterprise }}
      className={cn(
        "rounded-2xl border p-5 transition-colors",
        active
          ? "border-aq-mint/40 bg-aq-mint/5"
          : "border-aq-mist/30 bg-transparent",
      )}
    >
      <div className="flex items-center gap-3 mb-2">
        <span
          className={cn(
            "inline-flex h-9 w-9 items-center justify-center rounded-lg ring-1",
            active
              ? "bg-aq-mint/15 ring-aq-mint/40 text-aq-mint"
              : "bg-aq-mist/20 ring-aq-mist/40 text-aq-dust",
          )}
        >
          <Icon className="h-4 w-4" />
        </span>
        <span className="font-mono text-xs text-aq-trace">{scene.time}</span>
      </div>
      <h3 className="text-base font-semibold mt-1">{scene.title}</h3>
      <p className="text-sm text-aq-dust mt-2 leading-relaxed">{scene.body}</p>
      <div
        className={cn(
          "mt-3 inline-flex items-center gap-2 rounded-full px-2.5 py-1 text-[10px] font-mono",
          active
            ? "bg-aq-mint/15 text-aq-mint"
            : "bg-aq-mist/20 text-aq-trace",
        )}
      >
        <span className="h-1 w-1 rounded-full bg-current" />
        {scene.metric}
      </div>
    </motion.article>
  );
}

function FinosMockupCrossfade({
  sceneIndex,
}: {
  sceneIndex: ReturnType<typeof useTransform<number, number>>;
}) {
  // B1-FIX-v2 mountall pattern — race condition'a karşı
  const currentScene = useReactiveActiveIdx(sceneIndex);

  return (
    <div className="relative h-[520px]">
      {SCENES.map((scene, idx) => {
        const isActive = idx === currentScene;
        return (
          <motion.div
            key={scene.mockup}
            initial={false}
            animate={{
              opacity: isActive ? 1 : 0,
              scale: isActive ? 1 : 0.97,
              y: isActive ? 0 : 8,
            }}
            transition={{ duration: 0.45, ease: easeEnterprise }}
            className="absolute inset-0"
            style={{ pointerEvents: isActive ? "auto" : "none" }}
            aria-hidden={!isActive}
          >
            <FinosPhoneMockup variant={scene.mockup} />
          </motion.div>
        );
      })}
    </div>
  );
}

function FinosSceneCounter({
  sceneIndex,
}: {
  sceneIndex: ReturnType<typeof useTransform<number, number>>;
}) {
  const current = useReactiveActiveIdx(sceneIndex);
  return (
    <div className="absolute bottom-6 left-1/2 -translate-x-1/2 flex items-center gap-1.5">
      {SCENES.map((_, idx) => (
        <span
          key={idx}
          className={cn(
            "h-1 rounded-full transition-all duration-300",
            idx === current
              ? "w-6 bg-aq-mint"
              : idx < current
              ? "w-1.5 bg-aq-mint/40"
              : "w-1.5 bg-aq-mist/40",
          )}
        />
      ))}
    </div>
  );
}

function useReactiveActiveIdx(
  motionValue: ReturnType<typeof useTransform<number, number>>,
): number {
  // B1-FIX-v2: Math.floor + clamp + functional guard
  const [val, setVal] = useState(() => {
    const v = motionValue.get();
    return Math.min(Math.max(Math.floor(v), 0), SCENES.length - 1);
  });
  useEffect(() => {
    const unsub = motionValue.on("change", (v) => {
      const rounded = Math.min(
        Math.max(Math.floor(v), 0),
        SCENES.length - 1,
      );
      setVal((prev) => (prev !== rounded ? rounded : prev));
    });
    return () => unsub();
  }, [motionValue]);
  return val;
}

/* ── Phone Mockups (FinOS = telefon, K4.2) ─────────────────────────── */

function PhoneFrame({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative mx-auto w-[280px] h-[520px] rounded-[2.75rem] border-[12px] border-aq-orbital bg-aq-cosmos overflow-hidden shadow-[0_30px_60px_-15px_rgba(16,185,129,0.35)]">
      {/* Notch */}
      <div className="absolute top-1.5 left-1/2 -translate-x-1/2 h-4 w-20 rounded-b-xl bg-aq-orbital z-10" />
      <div className="relative h-full pt-8 px-3 pb-4 text-foreground">
        {children}
      </div>
    </div>
  );
}

function FinosPhoneMockup({ variant }: { variant: FinosMockupVariant }) {
  return <PhoneFrame>{renderMockupContent(variant)}</PhoneFrame>;
}

function renderMockupContent(variant: FinosMockupVariant) {
  switch (variant) {
    case "morning-cash":
      return <MockupMorningCash />;
    case "risk-score":
      return <MockupRiskScore />;
    case "aging-analysis":
      return <MockupAgingAnalysis />;
    case "cashflow-projection":
      return <MockupCashflowProjection />;
    case "whatsapp-collection":
      return <MockupWhatsAppCollection />;
  }
}

function MockupMorningCash() {
  return (
    <div className="h-full flex flex-col">
      <div className="text-[10px] text-aq-trace font-mono">app.finos / morning</div>
      <div className="mt-1 text-sm font-semibold">Günaydın Ahmet bey</div>
      <div className="mt-4 rounded-xl bg-aq-mint/10 border border-aq-mint/30 p-3">
        <div className="text-[10px] uppercase text-aq-mint">Banka Bakiyesi</div>
        <div className="text-2xl font-bold tabular-nums mt-1">285.000 ₺</div>
        <div className="text-[10px] text-aq-fusion mt-1">+ ₺14.500 gece tahsilatı</div>
      </div>
      <div className="mt-3 space-y-2">
        <div className="flex justify-between text-xs">
          <span className="text-aq-dust">Bu hafta hatırlatma</span>
          <span className="font-mono tabular-nums">4</span>
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-aq-dust">Tahsilat (gece)</span>
          <span className="font-mono text-aq-fusion tabular-nums">2 · ₺14.5K</span>
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-aq-dust">Vade bugün</span>
          <span className="font-mono text-aq-solar tabular-nums">₺36.200</span>
        </div>
      </div>
      <div className="mt-auto rounded-lg border border-aq-mint/30 bg-aq-mint/5 p-2 text-[10px] text-aq-mint">
        💡 Vade hatırlatmaları 09:00&apos;da otomatik gönderilecek
      </div>
    </div>
  );
}

function MockupRiskScore() {
  return (
    <div className="h-full flex flex-col">
      <div className="text-[10px] text-aq-trace font-mono">app.finos / risk-score</div>
      <div className="mt-1 text-sm font-semibold">X Tekstil A.Ş.</div>
      <div className="mt-1 text-[10px] text-aq-dust">Yeni müşteri · ₺75.000 sipariş</div>

      <div className="mt-4 rounded-xl bg-aq-mint/10 border border-aq-mint/30 p-3 text-center">
        <div className="text-[10px] uppercase text-aq-mint">Risk Skoru</div>
        <div className="text-4xl font-bold tabular-nums mt-1">73<span className="text-base text-aq-dust">/100</span></div>
        <div className="text-[10px] text-aq-solar mt-1">Orta-iyi · şartlı kabul</div>
      </div>

      <div className="mt-3 space-y-1.5">
        <div className="flex justify-between text-xs">
          <span className="text-aq-dust">Ödeme geçmişi</span>
          <span className="font-mono text-aq-fusion">+82</span>
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-aq-dust">Sektör risk</span>
          <span className="font-mono text-aq-solar">+58</span>
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-aq-dust">Borç oranı</span>
          <span className="font-mono text-aq-dust">+71</span>
        </div>
      </div>

      <div className="mt-auto rounded-lg border border-aq-mint/30 bg-aq-mint/5 p-2 text-[10px] text-aq-mint">
        💡 AI önerisi: %30 avans + ek teminat ile kabul
      </div>
    </div>
  );
}

function MockupAgingAnalysis() {
  const buckets = [
    { label: "0-30 gün", amount: 95_000, color: "bg-aq-fusion" },
    { label: "30-60 gün", amount: 87_000, color: "bg-aq-solar" },
    { label: "60-90 gün", amount: 42_000, color: "bg-aq-fission" },
    { label: "90+ gün", amount: 13_000, color: "bg-aq-fission/60" },
  ];
  const max = Math.max(...buckets.map((b) => b.amount));
  return (
    <div className="h-full flex flex-col">
      <div className="text-[10px] text-aq-trace font-mono">app.finos / aging</div>
      <div className="mt-1 text-sm font-semibold">Alacak Yaşlandırma</div>
      <div className="mt-1 text-[10px] text-aq-dust">Toplam açık ₺237.000</div>

      <div className="mt-4 space-y-2.5">
        {buckets.map((b) => (
          <div key={b.label}>
            <div className="flex justify-between text-[10px] mb-1">
              <span className="text-aq-dust">{b.label}</span>
              <span className="font-mono tabular-nums">
                ₺{(b.amount / 1000).toFixed(0)}K
              </span>
            </div>
            <div className="h-2 rounded-full bg-aq-mist/30 overflow-hidden">
              <div
                className={cn("h-full rounded-full", b.color)}
                style={{ width: `${(b.amount / max) * 100}%` }}
              />
            </div>
          </div>
        ))}
      </div>

      <div className="mt-4 rounded-lg border border-aq-fission/30 bg-aq-fission/5 p-2 text-[10px] text-aq-fission">
        ⚠ 2 müşteri 60+ gün — hukuki süreç uyarısı
      </div>

      <div className="mt-auto rounded-lg border border-aq-mint/30 bg-aq-mint/5 p-2 text-[10px] text-aq-mint">
        💡 İlk önceliği yüksek tutarlı 60+ kalemlere ver
      </div>
    </div>
  );
}

function MockupCashflowProjection() {
  // 7 günlük net pozisyon trendi (simulated)
  const days = [12, 18, 8, 22, 28, 16, 24];
  const maxV = Math.max(...days);
  return (
    <div className="h-full flex flex-col">
      <div className="text-[10px] text-aq-trace font-mono">app.finos / forecast</div>
      <div className="mt-1 text-sm font-semibold">30 Gün Projeksiyon</div>

      <div className="mt-4 grid grid-cols-2 gap-2">
        <div className="rounded-lg bg-aq-fusion/10 border border-aq-fusion/30 p-2">
          <div className="text-[9px] uppercase text-aq-fusion">Beklenen Giriş</div>
          <div className="text-lg font-bold tabular-nums">₺180K</div>
        </div>
        <div className="rounded-lg bg-aq-fission/10 border border-aq-fission/30 p-2">
          <div className="text-[9px] uppercase text-aq-fission">Beklenen Çıkış</div>
          <div className="text-lg font-bold tabular-nums">₺120K</div>
        </div>
      </div>

      <div className="mt-3 rounded-xl bg-aq-mint/10 border border-aq-mint/30 p-3">
        <div className="text-[10px] uppercase text-aq-mint">Net Pozisyon (30g)</div>
        <div className="text-2xl font-bold tabular-nums">+₺60.000</div>
      </div>

      <div className="mt-3">
        <div className="text-[9px] uppercase text-aq-trace mb-2">Haftalık trend</div>
        <div className="flex items-end gap-1 h-16">
          {days.map((v, i) => (
            <div
              key={i}
              className="flex-1 rounded-t bg-gradient-to-t from-aq-mint to-aq-fusion"
              style={{ height: `${(v / maxV) * 100}%` }}
            />
          ))}
        </div>
      </div>

      <div className="mt-auto rounded-lg border border-aq-mint/30 bg-aq-mint/5 p-2 text-[10px] text-aq-mint">
        💡 Büyüme planı için elverişli pencere
      </div>
    </div>
  );
}

function MockupWhatsAppCollection() {
  const items = [
    { name: "Y Konfeksiyon", status: "Okundu", color: "text-aq-fusion", icon: "✓✓" },
    { name: "Z Boyacılık", status: "Ödeme sözü", color: "text-aq-fusion", icon: "✓✓" },
    { name: "M Tekstil", status: "Okundu", color: "text-aq-fusion", icon: "✓✓" },
    { name: "K Ticaret", status: "Yanıt yok", color: "text-aq-dust", icon: "✓" },
    { name: "L Mağaza", status: "Ödeme sözü", color: "text-aq-fusion", icon: "✓✓" },
  ];
  return (
    <div className="h-full flex flex-col">
      <div className="text-[10px] text-aq-trace font-mono">app.finos / whatsapp</div>
      <div className="mt-1 text-sm font-semibold">Otomatik Tahsilat</div>
      <div className="mt-1 text-[10px] text-aq-dust">16:30 · 12 gönderim tamamlandı</div>

      <div className="mt-3 grid grid-cols-3 gap-1.5">
        <div className="rounded-lg bg-aq-fusion/10 border border-aq-fusion/30 p-1.5 text-center">
          <div className="text-base font-bold tabular-nums">12</div>
          <div className="text-[8px] text-aq-fusion">Gönderim</div>
        </div>
        <div className="rounded-lg bg-aq-mint/10 border border-aq-mint/30 p-1.5 text-center">
          <div className="text-base font-bold tabular-nums">6</div>
          <div className="text-[8px] text-aq-mint">Okudu</div>
        </div>
        <div className="rounded-lg bg-aq-fusion/10 border border-aq-fusion/30 p-1.5 text-center">
          <div className="text-base font-bold tabular-nums">3</div>
          <div className="text-[8px] text-aq-fusion">Söz</div>
        </div>
      </div>

      <div className="mt-3 space-y-1.5">
        {items.map((it) => (
          <div
            key={it.name}
            className="flex items-center justify-between rounded-md bg-aq-orbital/40 px-2 py-1.5 text-[10px]"
          >
            <span className="text-aq-dust">{it.name}</span>
            <span className={cn("font-mono", it.color)}>
              {it.icon} {it.status}
            </span>
          </div>
        ))}
      </div>

      <div className="mt-auto rounded-lg border border-aq-mint/30 bg-aq-mint/5 p-2 text-[10px] text-aq-mint">
        💡 İş gücü harcamadan ₺50K+ tahsilat sözü alındı
      </div>
    </div>
  );
}
