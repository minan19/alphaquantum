"use client";

import { useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Building2,
  Factory,
  type LucideIcon,
  Quote,
  ShoppingBag,
  Truck,
  Utensils,
  Wheat,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/cn";

type Sector = "all" | "tekstil" | "insaat" | "gida" | "lojistik" | "perakende" | "uretim";

interface CaseStudy {
  id: string;
  sector: Exclude<Sector, "all">;
  sectorLabel: string;
  sectorIcon: LucideIcon;
  company: string;
  quote: string;
  metric: string;
  metricLabel: string;
  module: "CorpOS" | "FinOS" | "CorpOS + FinOS";
  tone: "primary" | "plasma" | "solar";
}

const SECTOR_FILTERS: { id: Sector; label: string; icon?: LucideIcon }[] = [
  { id: "all",       label: "Tümü" },
  { id: "tekstil",   label: "Tekstil",   icon: ShoppingBag },
  { id: "insaat",    label: "İnşaat",    icon: Building2 },
  { id: "gida",      label: "Gıda",      icon: Utensils },
  { id: "lojistik",  label: "Lojistik",  icon: Truck },
  { id: "perakende", label: "Perakende", icon: Wheat },
  { id: "uretim",    label: "Üretim",    icon: Factory },
];

const CASE_STUDIES: CaseStudy[] = [
  {
    id: "alpha-tekstil",
    sector: "tekstil",
    sectorLabel: "Tekstil",
    sectorIcon: ShoppingBag,
    company: "Alpha Tekstil Grubu",
    quote: "3 fabrika, 18 müşteri kategorisi. Eskiden ay sonunda 4 gün rapor topluyorduk. Şimdi saatlik bakıyoruz.",
    metric: "%42",
    metricLabel: "alacak azalması",
    module: "CorpOS + FinOS",
    tone: "primary",
  },
  {
    id: "delta-lojistik",
    sector: "lojistik",
    sectorLabel: "Lojistik",
    sectorIcon: Truck,
    company: "Delta Lojistik A.Ş.",
    quote: "Aylık 1.200 fatura kesiyorduk; gecikme oranımız %18'di. Otomatik vade uyarısı %6'ya indirdi.",
    metric: "16 saat / ay",
    metricLabel: "iş gücü tasarrufu",
    module: "FinOS",
    tone: "plasma",
  },
  {
    id: "epsilon-gida",
    sector: "gida",
    sectorLabel: "Gıda Toptan",
    sectorIcon: Utensils,
    company: "Epsilon Gıda",
    quote: "Bayilerimize ödeme risk skoru veriyoruz. Yeni bayilik açmadan önce davranışsal veriyi görüyoruz.",
    metric: "0",
    metricLabel: "kötü alacak (6 ay)",
    module: "FinOS",
    tone: "primary",
  },
  {
    id: "beta-insaat",
    sector: "insaat",
    sectorLabel: "İnşaat",
    sectorIcon: Building2,
    company: "Beta İnşaat Holding",
    quote: "5 farklı proje şirketinin nakit akışını tek panelden takip ediyoruz. Konsolide rapor 1 tıkla geliyor.",
    metric: "3 gün → 10 dk",
    metricLabel: "rapor hazırlama",
    module: "CorpOS",
    tone: "solar",
  },
  {
    id: "gamma-perakende",
    sector: "perakende",
    sectorLabel: "Perakende",
    sectorIcon: Wheat,
    company: "Gamma Mağazacılık",
    quote: "USD bazlı tedarikçi ödemelerimizi FX exposure paneliyle takip ediyoruz; kur şokuna önceden hazırlanıyoruz.",
    metric: "%28",
    metricLabel: "FX risk azalması",
    module: "FinOS",
    tone: "plasma",
  },
  {
    id: "zeta-uretim",
    sector: "uretim",
    sectorLabel: "Makine Üretimi",
    sectorIcon: Factory,
    company: "Zeta Endüstri",
    quote: "Senet ve çek takibi karmaşıktı. Şimdi vade yaklaşan çekleri otomatik görüyoruz, karşılıksız riski kaybolduk.",
    metric: "0",
    metricLabel: "karşılıksız çek (4 ay)",
    module: "FinOS",
    tone: "solar",
  },
];

export function CaseStudiesGrid() {
  const [filter, setFilter] = useState<Sector>("all");

  const filtered = useMemo(
    () => (filter === "all" ? CASE_STUDIES : CASE_STUDIES.filter((c) => c.sector === filter)),
    [filter],
  );

  return (
    <section className="relative z-10 mx-auto max-w-7xl px-6 py-20">
      <div className="text-center mb-8">
        <Badge tone="primary" className="mb-3">Sektör Hikayeleri</Badge>
        <h2 className="text-3xl font-bold tracking-tight">
          Her sektörden gerçek sonuçlar
        </h2>
        <p className="mt-2 text-sm text-aq-dust">
          Filtrele · sektörünüze en yakın referansı görün
        </p>
      </div>

      {/* Filter chips */}
      <div className="flex flex-wrap items-center justify-center gap-2 mb-10">
        {SECTOR_FILTERS.map((s) => {
          const Icon = s.icon;
          const active = filter === s.id;
          return (
            <button
              key={s.id}
              onClick={() => setFilter(s.id)}
              className={cn(
                "inline-flex items-center gap-2 rounded-full px-4 py-1.5 text-xs font-medium",
                "border transition-all duration-300 ease-quantum",
                active
                  ? "border-aq-quantum/60 bg-aq-quantum/15 text-aq-quantum-2 shadow-quantum"
                  : "border-aq-mist/40 text-aq-dust hover:border-aq-mist/80 hover:text-foreground hover:bg-aq-mist/20",
              )}
            >
              {Icon && <Icon className="h-3.5 w-3.5" />}
              {s.label}
            </button>
          );
        })}
      </div>

      {/* Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
        <AnimatePresence mode="popLayout">
          {filtered.map((cs, i) => {
            const Icon = cs.sectorIcon;
            return (
              <motion.article
                key={cs.id}
                layout
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                transition={{
                  duration: 0.4,
                  delay: i * 0.05,
                  ease: [0.32, 0.72, 0, 1],
                }}
                className={cn(
                  "group relative overflow-hidden rounded-xl border bg-card/60 p-6",
                  "transition-all duration-300 ease-quantum backdrop-blur-sm",
                  cs.tone === "primary" && "border-aq-mist/40 hover:border-aq-quantum/50 hover:shadow-quantum",
                  cs.tone === "plasma" && "border-aq-mist/40 hover:border-aq-plasma/50 hover:shadow-[0_0_24px_-4px_rgba(6,182,212,0.4)]",
                  cs.tone === "solar" && "border-aq-mist/40 hover:border-aq-solar/50 hover:shadow-[0_0_24px_-4px_rgba(245,158,11,0.4)]",
                )}
              >
                {/* Tonal glow */}
                <div
                  aria-hidden
                  className={cn(
                    "absolute -right-12 -top-12 h-40 w-40 rounded-full blur-3xl opacity-30",
                    "transition-opacity duration-500 group-hover:opacity-60",
                    cs.tone === "primary" && "bg-aq-quantum",
                    cs.tone === "plasma" && "bg-aq-plasma",
                    cs.tone === "solar" && "bg-aq-solar",
                  )}
                />

                <div className="relative">
                  {/* Sector + module */}
                  <div className="flex items-center justify-between gap-2 mb-4">
                    <div className="flex items-center gap-2 text-xs">
                      <Icon className="h-3.5 w-3.5 text-aq-trace" />
                      <span className="text-aq-dust">{cs.sectorLabel}</span>
                    </div>
                    <span className="rounded bg-aq-mist/60 px-1.5 py-0.5 font-mono text-[9px] text-aq-dust">
                      {cs.module}
                    </span>
                  </div>

                  {/* Big metric */}
                  <div className="mb-4">
                    <div
                      className={cn(
                        "text-3xl font-bold tabular num bg-gradient-to-r bg-clip-text text-transparent",
                        cs.tone === "primary" && "from-aq-quantum-2 to-aq-plasma",
                        cs.tone === "plasma" && "from-aq-plasma to-aq-quantum-2",
                        cs.tone === "solar" && "from-aq-solar to-aq-quantum-2",
                      )}
                    >
                      {cs.metric}
                    </div>
                    <div className="text-xs text-aq-dust mt-0.5">
                      {cs.metricLabel}
                    </div>
                  </div>

                  {/* Quote */}
                  <Quote
                    className="h-5 w-5 text-aq-quantum/30 mb-2"
                    aria-hidden="true"
                  />
                  <blockquote className="text-sm text-aq-dust leading-relaxed mb-4">
                    &ldquo;{cs.quote}&rdquo;
                  </blockquote>

                  {/* Company */}
                  <div className="pt-4 border-t border-aq-mist/30">
                    <div className="text-xs font-semibold">{cs.company}</div>
                  </div>
                </div>
              </motion.article>
            );
          })}
        </AnimatePresence>
      </div>

      {filtered.length === 0 && (
        <div className="text-center text-sm text-aq-dust py-12">
          Bu sektör için henüz yayınlanmış vaka yok. Yakında!
        </div>
      )}
    </section>
  );
}
