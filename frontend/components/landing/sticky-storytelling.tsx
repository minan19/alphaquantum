"use client";

/**
 * B1: "Holding patronu bir günü" — Sticky Storytelling Landing Pattern
 *
 * Tasarım doc'un EN ETKİLİ landing pattern'i. 5 sahne (08:00-17:00),
 * sticky sol dashboard mockup, scroll-driven sahne geçişleri.
 *
 * Yapı:
 * - Container: ~5x viewport yüksekliği (her sahne için 1 ekran)
 * - Sol: position:sticky dashboard mockup, sahneye göre crossfade
 * - Sağ: scroll boyunca sahne metinleri, aktif olan vurgulu
 * - Sol üstte saat göstergesi 08:00 → 17:00 ilerler
 *
 * Stack: Framer Motion useScroll + useTransform + AnimatePresence (mode="wait")
 * Easing: ease-enterprise (yavaş, premium) — doc'un enterprise tonu için.
 */

import { useRef } from "react";
import {
  AnimatePresence,
  motion,
  useScroll,
  useTransform,
} from "framer-motion";
import {
  Coffee,
  FileText,
  LineChart,
  Repeat,
  Users,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/cn";
import { easeEnterprise } from "@/lib/motion";

interface Scene {
  time: string;
  icon: LucideIcon;
  title: string;
  body: string;
  metric: string;
  mockup: MockupVariant;
  accent: "quantum" | "plasma" | "solar" | "fission" | "fusion";
}

type MockupVariant =
  | "morning-balance"
  | "consolidated-pl"
  | "feasibility-scorecard"
  | "cross-company-transfer"
  | "exec-summary";

const SCENES: Scene[] = [
  {
    time: "08:00",
    icon: Coffee,
    title: "Sabah kahvesi — Gece kapanış pozisyonu",
    body: "Üç şirketin toplam bakiyesi, gece otomatik tahsilat raporları, dövizdeki en son değişim — tek bakışta. Sabah ofise gelmeden önce holdingin nabzı kontrol edilir.",
    metric: "₺847.230 konsolide bakiye · %12.4 büyüme",
    mockup: "morning-balance",
    accent: "quantum",
  },
  {
    time: "10:30",
    icon: LineChart,
    title: "Yönetim toplantısı — Konsolide P&L",
    body: "CFO ile haftalık brifing. Gelir/gider trendleri, alacak yaşlandırma, FX exposure. Excel hazırlığı yok — anlık panel yansıtılır. Toplantı 30 dk yerine 12 dk.",
    metric: "30 → 12 dakikalık toplantı süresi",
    mockup: "consolidated-pl",
    accent: "plasma",
  },
  {
    time: "13:00",
    icon: FileText,
    title: "Yatırım kararı — Feasibility scorecard",
    body: "Yeni proje teklifi geldi: AI destekli fizibilite analizi 6 saniyede çalışır. Pazar payı, geri ödeme süresi, risk skoru — onay/red kararı veriye dayanır.",
    metric: "6 sn fizibilite analizi · NPV/IRR hesaplı",
    mockup: "feasibility-scorecard",
    accent: "solar",
  },
  {
    time: "15:00",
    icon: Repeat,
    title: "Şirketler arası transfer — Cross-company",
    body: "Lojistik şirketten gıda şirketine kaynak aktarımı. Mahsup, döviz dönüşümü, audit kaydı — tek tuş. Tek-double approval (4 göz) güvenlik katmanı otomatik tetiklenir.",
    metric: "4-eyes onay · audit log otomatik",
    mockup: "cross-company-transfer",
    accent: "fission",
  },
  {
    time: "17:00",
    icon: Users,
    title: "Günlük rapor — Exec summary",
    body: "Gün sonu bir tıkla PDF üretilir: HMAC-imzalı, KVKK uyumlu, e-posta ile yönetim kuruluna iletilir. Yarın sabahki kahveye kadar her şey hazır.",
    metric: "İmzalı PDF · KVKK uyumlu otomasyon",
    mockup: "exec-summary",
    accent: "fusion",
  },
];

const ACCENT_CLASSES: Record<
  Scene["accent"],
  { ring: string; glow: string; text: string; bar: string }
> = {
  quantum: {
    ring: "ring-aq-quantum/40",
    glow: "from-aq-quantum/20",
    text: "text-aq-quantum-2",
    bar: "bg-aq-quantum",
  },
  plasma: {
    ring: "ring-aq-plasma/40",
    glow: "from-aq-plasma/20",
    text: "text-aq-plasma",
    bar: "bg-aq-plasma",
  },
  solar: {
    ring: "ring-aq-solar/40",
    glow: "from-aq-solar/20",
    text: "text-aq-solar",
    bar: "bg-aq-solar",
  },
  fission: {
    ring: "ring-aq-fission/40",
    glow: "from-aq-fission/20",
    text: "text-aq-fission",
    bar: "bg-aq-fission",
  },
  fusion: {
    ring: "ring-aq-fusion/40",
    glow: "from-aq-fusion/20",
    text: "text-aq-fusion",
    bar: "bg-aq-fusion",
  },
};

export function StickyStorytelling() {
  const containerRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start start", "end end"],
  });

  // Active scene index based on scroll progress (0..4)
  // Each scene gets 1/N of the scroll range
  const sceneIndex = useTransform(scrollYProgress, (v) => {
    const idx = Math.floor(v * SCENES.length);
    return Math.min(idx, SCENES.length - 1);
  });

  // Clock progress: 08:00 (8h) → 17:00 (17h) over the scroll
  const clockProgress = useTransform(scrollYProgress, [0, 1], [0, 1]);
  const clockLabel = useTransform(clockProgress, (v) => {
    // Map 0..1 → 8:00..17:00
    const totalMinutes = 8 * 60 + v * 9 * 60;
    const h = Math.floor(totalMinutes / 60);
    const m = Math.floor(totalMinutes % 60);
    return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
  });

  return (
    <section
      ref={containerRef}
      aria-label="Holding patronu bir günü"
      className="relative bg-aq-void"
      // Container takes 5x viewport — each scene gets ~1 screen scroll
      style={{ height: `${SCENES.length * 100}vh` }}
    >
      {/* Sticky wrapper: stays in view while scenes scroll */}
      <div className="sticky top-0 grid h-screen grid-cols-1 lg:grid-cols-[1.05fr_0.95fr] overflow-hidden">
        {/* ─── LEFT: Sticky dashboard mockup ──────────────────────────── */}
        <div className="relative hidden lg:flex flex-col bg-gradient-to-br from-aq-cosmos to-aq-void p-12">
          {/* Animated clock indicator */}
          <ClockIndicator clockLabel={clockLabel} />

          {/* Mockup crossfade area */}
          <div className="relative flex-1 mt-8">
            <SceneMockupCrossfade sceneIndex={sceneIndex} />
          </div>

          {/* Sahne sayacı */}
          <SceneCounter sceneIndex={sceneIndex} />
        </div>

        {/* ─── RIGHT: Scenes (the scroll-active text) ─────────────────── */}
        <div className="relative flex flex-col justify-center px-6 lg:px-16 py-10 overflow-y-auto">
          {/* Mobile clock (lg ekranda gizli) */}
          <div className="lg:hidden mb-6">
            <ClockIndicator clockLabel={clockLabel} compact />
          </div>

          <header className="mb-10">
            <div className="inline-flex items-center gap-2 rounded-full border border-aq-quantum/30 bg-aq-quantum/10 px-3 py-1 text-[10px] font-mono uppercase tracking-[0.18em] text-aq-quantum-2 mb-3">
              <span className="h-1.5 w-1.5 rounded-full bg-aq-quantum-2 animate-pulse" />
              Bir gün senaryosu
            </div>
            <h2 className="text-3xl lg:text-4xl font-bold tracking-tight">
              Holding patronu{" "}
              <span className="bg-gradient-to-r from-aq-quantum to-aq-plasma bg-clip-text text-transparent">
                bir günü
              </span>
            </h2>
            <p className="mt-3 text-sm lg:text-base text-aq-dust max-w-xl">
              5 sahne — sabah 08:00&apos;den akşam 17:00&apos;ye. Alpha Quantum
              ile yönetilen üç şirketli bir holding patronu için.
            </p>
          </header>

          <div className="space-y-12">
            {SCENES.map((scene, idx) => (
              <SceneBlock
                key={idx}
                scene={scene}
                index={idx}
                sceneIndex={sceneIndex}
              />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

/* ──────────────────────────────────────────────────────────────────────── */

function ClockIndicator({
  clockLabel,
  compact = false,
}: {
  clockLabel: ReturnType<typeof useTransform<number, string>>;
  compact?: boolean;
}) {
  return (
    <div
      className={cn(
        "inline-flex items-center gap-3 rounded-full border border-aq-mist/30",
        "bg-aq-orbital/60 backdrop-blur-sm px-4 py-2 w-fit",
        compact && "text-sm",
      )}
    >
      <span className="grid h-7 w-7 place-items-center rounded-full bg-aq-quantum/15 ring-1 ring-aq-quantum/30">
        <svg
          className="h-3.5 w-3.5 text-aq-quantum-2"
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
          Bir günü
        </div>
        <motion.div className="font-mono font-bold tracking-tight tabular-nums">
          {clockLabel}
        </motion.div>
      </div>
    </div>
  );
}

function SceneCounter({
  sceneIndex,
}: {
  sceneIndex: ReturnType<typeof useTransform<number, number>>;
}) {
  return (
    <div className="mt-8 flex items-center gap-3">
      <span className="text-[10px] uppercase tracking-wider text-aq-trace">
        Sahne
      </span>
      <div className="flex gap-1.5 flex-1">
        {SCENES.map((_, i) => (
          <SceneCounterDot key={i} index={i} sceneIndex={sceneIndex} />
        ))}
      </div>
      <span className="text-[10px] uppercase tracking-wider text-aq-trace tabular-nums">
        <motion.span>{useTransform(sceneIndex, (v) => v + 1)}</motion.span>
        {" / "}
        {SCENES.length}
      </span>
    </div>
  );
}

function SceneCounterDot({
  index,
  sceneIndex,
}: {
  index: number;
  sceneIndex: ReturnType<typeof useTransform<number, number>>;
}) {
  const active = useTransform(sceneIndex, (v) => v === index);
  const opacity = useTransform(active, (v) => (v ? 1 : 0.3));
  const width = useTransform(active, (v) => (v ? "1.5rem" : "0.5rem"));

  return (
    <motion.span
      style={{ opacity, width }}
      className="h-1 rounded-full bg-aq-quantum-2 transition-all"
    />
  );
}

/* ─── Sahne metni (sağ taraf) ─────────────────────────────────────────── */

function SceneBlock({
  scene,
  index,
  sceneIndex,
}: {
  scene: Scene;
  index: number;
  sceneIndex: ReturnType<typeof useTransform<number, number>>;
}) {
  const Icon = scene.icon;
  const opacity = useTransform(sceneIndex, (v) => {
    const dist = Math.abs(v - index);
    if (dist === 0) return 1;
    if (dist === 1) return 0.35;
    return 0.15;
  });
  const scale = useTransform(sceneIndex, (v) => (v === index ? 1 : 0.97));

  const accent = ACCENT_CLASSES[scene.accent];

  return (
    <motion.article
      style={{ opacity, scale }}
      transition={{ duration: 0.6, ease: easeEnterprise }}
      className={cn(
        "rounded-xl border p-6",
        "border-aq-mist/40 bg-aq-orbital/30",
      )}
    >
      <div className="flex items-start gap-4">
        <div
          className={cn(
            "grid h-10 w-10 shrink-0 place-items-center rounded-md ring-1",
            accent.ring,
            "bg-gradient-to-br to-transparent",
            accent.glow,
          )}
        >
          <Icon className={cn("h-5 w-5", accent.text)} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-1">
            <span
              className={cn(
                "font-mono text-xs font-bold tracking-tight tabular-nums",
                accent.text,
              )}
            >
              {scene.time}
            </span>
            <span className={cn("h-px flex-1", accent.bar, "opacity-30")} />
          </div>
          <h3 className="text-lg font-semibold leading-tight">{scene.title}</h3>
          <p className="mt-2 text-sm text-aq-dust leading-relaxed">
            {scene.body}
          </p>
          <div
            className={cn(
              "mt-3 inline-flex items-center gap-2 rounded-full px-3 py-1",
              "bg-aq-orbital/60 ring-1 ring-aq-mist/30 text-xs",
            )}
          >
            <span
              className={cn("h-1.5 w-1.5 rounded-full", accent.bar)}
              aria-hidden
            />
            <span className="text-aq-dust">{scene.metric}</span>
          </div>
        </div>
      </div>
    </motion.article>
  );
}

/* ─── Mockup crossfade (sol taraf) ────────────────────────────────────── */

function SceneMockupCrossfade({
  sceneIndex,
}: {
  sceneIndex: ReturnType<typeof useTransform<number, number>>;
}) {
  // Read current value into state via motion's onChange — but for simplicity
  // use motion.div with key-based AnimatePresence
  const currentScene = useReactiveSceneIndex(sceneIndex);
  const scene = SCENES[currentScene];

  return (
    <div className="relative h-full">
      <AnimatePresence mode="wait">
        <motion.div
          key={scene.mockup}
          initial={{ opacity: 0, scale: 0.96, y: 12 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.98, y: -12 }}
          transition={{ duration: 0.6, ease: easeEnterprise }}
          className="absolute inset-0"
        >
          <DashboardMockup variant={scene.mockup} accent={scene.accent} />
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

import { useEffect, useState } from "react";

function useReactiveSceneIndex(
  motionValue: ReturnType<typeof useTransform<number, number>>,
): number {
  const [val, setVal] = useState(motionValue.get());
  useEffect(() => {
    const unsub = motionValue.on("change", (v) => setVal(v));
    return () => unsub();
  }, [motionValue]);
  return val;
}

/* ─── Dashboard mockups (5 sahne için ayrı görseller) ────────────────── */

function DashboardMockup({
  variant,
  accent,
}: {
  variant: MockupVariant;
  accent: Scene["accent"];
}) {
  const accentClass = ACCENT_CLASSES[accent];

  return (
    <div
      className={cn(
        "h-full w-full rounded-xl border bg-card/90 backdrop-blur-md",
        "border-aq-mist/40 shadow-elevation-3 overflow-hidden",
        "flex flex-col",
      )}
    >
      {/* Mock browser chrome */}
      <div className="flex items-center gap-2 border-b border-aq-mist/30 bg-aq-cosmos/60 px-4 py-2">
        <span className="h-2.5 w-2.5 rounded-full bg-aq-fission/60" />
        <span className="h-2.5 w-2.5 rounded-full bg-aq-solar/60" />
        <span className="h-2.5 w-2.5 rounded-full bg-aq-fusion/60" />
        <div className="ml-3 flex-1 truncate rounded bg-aq-orbital/60 px-3 py-0.5 text-[10px] font-mono text-aq-trace">
          app.alpha-quantum.com / dashboard
        </div>
      </div>

      {/* Per-variant mockup */}
      <div className="flex-1 p-6 overflow-hidden">
        {variant === "morning-balance" && <MockupMorningBalance accent={accent} />}
        {variant === "consolidated-pl" && <MockupConsolidatedPL accent={accent} />}
        {variant === "feasibility-scorecard" && (
          <MockupFeasibility accent={accent} />
        )}
        {variant === "cross-company-transfer" && (
          <MockupCrossCompany accent={accent} />
        )}
        {variant === "exec-summary" && <MockupExecSummary accent={accent} />}
      </div>

      {/* Subtle accent ring */}
      <div
        className={cn(
          "h-1 w-full ring-1",
          accentClass.bar,
          accentClass.ring,
          "opacity-60",
        )}
      />
    </div>
  );
}

/* ─── Mockup variant components ──────────────────────────────────────── */

function MockupMorningBalance({ accent }: { accent: Scene["accent"] }) {
  const a = ACCENT_CLASSES[accent];
  return (
    <div className="h-full flex flex-col gap-3">
      <div className="text-xs text-aq-dust">Konsolide Bakiye — Üç Şirket</div>
      <div className="flex items-baseline gap-2">
        <span className={cn("text-4xl font-bold num", a.text)}>847.230</span>
        <span className="text-sm text-aq-dust">₺</span>
        <span className={cn("ml-auto text-xs font-mono", a.text)}>↑ +12.4%</span>
      </div>

      <div className="grid grid-cols-3 gap-2 mt-2">
        {["Inşaat", "Tekstil", "Lojistik"].map((co, i) => (
          <div
            key={co}
            className="rounded-md border border-aq-mist/30 bg-aq-orbital/40 p-2"
          >
            <div className="text-[10px] uppercase tracking-wider text-aq-trace">
              {co}
            </div>
            <div className="text-sm font-bold num mt-0.5">
              {[412, 285, 150][i]}K
            </div>
          </div>
        ))}
      </div>

      <div className="mt-3 flex-1 rounded-md border border-aq-mist/30 bg-aq-orbital/30 p-3">
        <div className="text-[10px] uppercase tracking-wider text-aq-trace mb-2">
          Gece otomatik tahsilat
        </div>
        <div className="space-y-1.5">
          {[
            { ch: "WhatsApp", c: 14, st: "OK" },
            { ch: "SMS", c: 8, st: "OK" },
            { ch: "E-posta", c: 22, st: "OK" },
          ].map((r) => (
            <div
              key={r.ch}
              className="flex items-center justify-between text-xs"
            >
              <span className="text-aq-dust">{r.ch}</span>
              <span className="font-mono num">{r.c} gönderim</span>
              <span className={cn("font-mono text-[10px]", a.text)}>{r.st}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function MockupConsolidatedPL({ accent }: { accent: Scene["accent"] }) {
  const a = ACCENT_CLASSES[accent];
  return (
    <div className="h-full flex flex-col gap-3">
      <div className="text-xs text-aq-dust">Konsolide P&amp;L — Bu Çeyrek</div>
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-md border border-aq-mist/30 bg-aq-orbital/40 p-3">
          <div className="text-[10px] uppercase tracking-wider text-aq-trace">
            Toplam Gelir
          </div>
          <div className="text-2xl font-bold num text-aq-fusion mt-1">
            2.8M ₺
          </div>
        </div>
        <div className="rounded-md border border-aq-mist/30 bg-aq-orbital/40 p-3">
          <div className="text-[10px] uppercase tracking-wider text-aq-trace">
            Net Kar
          </div>
          <div className={cn("text-2xl font-bold num mt-1", a.text)}>
            +485K ₺
          </div>
        </div>
      </div>

      {/* Mini line chart placeholder (SVG) */}
      <div className="flex-1 rounded-md border border-aq-mist/30 bg-aq-orbital/30 p-3">
        <div className="text-[10px] uppercase tracking-wider text-aq-trace mb-2">
          12 Haftalık Trend
        </div>
        <svg viewBox="0 0 200 60" className="w-full h-16">
          <polyline
            points="0,45 18,40 36,42 54,30 72,32 90,25 108,28 126,18 144,22 162,12 180,15 200,8"
            fill="none"
            stroke="rgb(124, 96, 255)"
            strokeWidth="1.5"
            strokeLinejoin="round"
          />
          <polyline
            points="0,52 18,48 36,46 54,42 72,40 90,38 108,40 126,36 144,38 162,32 180,30 200,28"
            fill="none"
            stroke="rgb(6, 182, 212)"
            strokeWidth="1.2"
            strokeDasharray="3 3"
            opacity="0.6"
          />
        </svg>
        <div className="mt-2 flex gap-3 text-[10px]">
          <span className="text-aq-quantum-2">— Gelir</span>
          <span className="text-aq-plasma">— Gider (tahmin)</span>
        </div>
      </div>
    </div>
  );
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars
function MockupFeasibility({ accent }: { accent: Scene["accent"] }) {
  return (
    <div className="h-full flex flex-col gap-3">
      <div className="text-xs text-aq-dust">Fizibilite Skor Kartı</div>
      <div className="rounded-md border border-aq-mist/30 bg-aq-orbital/40 p-3">
        <div className="text-sm font-semibold">Yeni AR-GE projesi #142</div>
        <div className="text-[10px] text-aq-trace mt-0.5">
          Tekstil sektörü · NPV/IRR analizi
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2">
        {[
          { l: "NPV", v: "+1.2M ₺", ok: true },
          { l: "IRR", v: "%18.4", ok: true },
          { l: "Geri ödeme", v: "2.3 yıl", ok: true },
          { l: "Risk skoru", v: "67/100", ok: false },
        ].map((r) => (
          <div
            key={r.l}
            className="rounded-md border border-aq-mist/30 bg-aq-orbital/30 p-2.5"
          >
            <div className="text-[10px] uppercase tracking-wider text-aq-trace">
              {r.l}
            </div>
            <div className="flex items-center gap-1.5 mt-1">
              <span className="text-sm font-bold num">{r.v}</span>
              <span
                className={cn(
                  "h-1.5 w-1.5 rounded-full",
                  r.ok ? "bg-aq-fusion" : "bg-aq-solar",
                )}
              />
            </div>
          </div>
        ))}
      </div>

      <div
        className={cn(
          "mt-auto rounded-md border p-3",
          "border-aq-mist/30 bg-aq-orbital/30",
        )}
      >
        <div className="text-[10px] uppercase tracking-wider text-aq-trace mb-1">
          AI Öneri
        </div>
        <div className="text-xs text-aq-dust">
          Onayla — risk azaltma için sigorta opsiyonu önerilir.
        </div>
        <div className="mt-2 flex gap-2">
          <span
            className={cn(
              "px-2 py-0.5 rounded text-[10px] font-semibold",
              "bg-aq-fusion/20 text-aq-fusion",
            )}
          >
            ✓ Onayla
          </span>
          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-aq-mist/30 text-aq-dust">
            Geri çevir
          </span>
        </div>
      </div>
    </div>
  );
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars
function MockupCrossCompany({ accent }: { accent: Scene["accent"] }) {
  return (
    <div className="h-full flex flex-col gap-3">
      <div className="text-xs text-aq-dust">Şirketler Arası Transfer</div>

      {/* Flow visualization */}
      <div className="rounded-md border border-aq-mist/30 bg-aq-orbital/30 p-4">
        <div className="flex items-center justify-between gap-2">
          <div className="text-center">
            <div className="text-[10px] uppercase tracking-wider text-aq-trace">
              Kaynak
            </div>
            <div className="font-bold text-sm mt-1">Lojistik</div>
            <div className="text-[10px] text-aq-dust">Bakiye: 285K</div>
          </div>
          <div className="flex-1 px-3">
            <div className="h-px bg-gradient-to-r from-aq-mist to-aq-fission" />
            <div className="text-center text-xs font-mono text-aq-fission mt-1">
              ₺ 75.000
            </div>
          </div>
          <div className="text-center">
            <div className="text-[10px] uppercase tracking-wider text-aq-trace">
              Hedef
            </div>
            <div className="font-bold text-sm mt-1">Gıda</div>
            <div className="text-[10px] text-aq-dust">Bakiye: 150K</div>
          </div>
        </div>
      </div>

      {/* 4-eyes approval */}
      <div className="rounded-md border border-aq-fission/30 bg-aq-fission/5 p-3">
        <div className="flex items-center gap-2 text-xs font-semibold text-aq-fission">
          <span className="h-1.5 w-1.5 rounded-full bg-aq-fission animate-pulse" />
          4-eyes onay sistemi tetiklendi
        </div>
        <div className="mt-2 space-y-1">
          {[
            { who: "Talep eden", v: "✓ Patron M.K." },
            { who: "1. onay", v: "✓ CFO A.Y." },
            { who: "2. onay", v: "⧖ Beklemede — Mali Müşavir" },
          ].map((r) => (
            <div
              key={r.who}
              className="flex justify-between text-[11px] text-aq-dust"
            >
              <span>{r.who}</span>
              <span className="font-mono">{r.v}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-auto rounded-md border border-aq-mist/30 bg-aq-orbital/30 p-3">
        <div className="text-[10px] uppercase tracking-wider text-aq-trace mb-1">
          Audit log
        </div>
        <div className="text-[11px] text-aq-dust font-mono">
          tx_2026-05-28_15:08:23 · holding.transfer · HMAC-imzalı
        </div>
      </div>
    </div>
  );
}

function MockupExecSummary({ accent }: { accent: Scene["accent"] }) {
  const a = ACCENT_CLASSES[accent];
  return (
    <div className="h-full flex flex-col gap-3">
      <div className="flex items-baseline justify-between">
        <div className="text-xs text-aq-dust">Günlük Yönetici Raporu</div>
        <div className="text-[10px] font-mono text-aq-trace">
          28 Mayıs 2026
        </div>
      </div>

      <div className="rounded-md border border-aq-mist/30 bg-aq-orbital/40 p-4">
        <div className="grid grid-cols-3 gap-3 text-center">
          {[
            { l: "Gün sonu nakit", v: "847K", c: a.text },
            { l: "Tahsil edilen", v: "44K", c: "text-aq-fusion" },
            { l: "Yeni alacak", v: "18K", c: "text-aq-solar" },
          ].map((r) => (
            <div key={r.l}>
              <div className="text-[10px] uppercase tracking-wider text-aq-trace">
                {r.l}
              </div>
              <div className={cn("text-lg font-bold num mt-0.5", r.c)}>
                {r.v}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-md border border-aq-mist/30 bg-aq-orbital/30 p-3 space-y-2">
        <div className="text-[10px] uppercase tracking-wider text-aq-trace">
          Önemli olaylar
        </div>
        {[
          "10:30 — Konsolide P&L brifing (12 dk)",
          "13:00 — AR-GE #142 fizibilite onayı",
          "15:00 — Şirketler arası transfer 75K ₺",
          "17:00 — Otomatik rapor hazırlandı",
        ].map((evt) => (
          <div key={evt} className="text-[11px] text-aq-dust flex gap-2">
            <span className="text-aq-trace">●</span>
            <span>{evt}</span>
          </div>
        ))}
      </div>

      <div className="mt-auto rounded-md border border-aq-quantum/30 bg-aq-quantum/5 p-3">
        <div className="flex items-center gap-2">
          <span className="h-1.5 w-1.5 rounded-full bg-aq-quantum-2" />
          <span className="text-xs font-semibold">
            PDF gönderildi — Yönetim Kurulu
          </span>
        </div>
        <div className="mt-1 text-[10px] text-aq-trace font-mono">
          HMAC-SHA256 imzalı · KVKK madde 11 uyumlu
        </div>
      </div>
    </div>
  );
}
