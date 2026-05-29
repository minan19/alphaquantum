"use client";

/**
 * F2: Sub-brand product cards — CorpOS + FinOS Hero ikilisi.
 *
 * Tasarım doc'tan: "tasarım katmanı 2.2 — İki Ürün Kartı (Hero'nun Kalbi)".
 * Glassmorphism + sub-brand renk accent + premium hover.
 *
 * Kartlar landing'in ana CTA noktası. Ziyaretçi buradan ürün sayfasına
 * gidecek (gelecek: /corpos, /finos slug'ları). Şu an # placeholder.
 *
 * Davranış:
 *  - Default: glassmorphism kart, muted aksent
 *  - Hover: 8px yukarı translateY, accent glow shadow, ikon doldur
 *  - prefers-reduced-motion: animasyon kapalı, opacity-only feedback
 *
 * a11y:
 *  - Semantic <article> + <h3> başlıklar
 *  - Focus-visible ring (Tab navigation)
 *  - aria-label CTA için açıklayıcı
 */

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight, Building2, TrendingUp } from "lucide-react";
import { cn } from "@/lib/cn";

interface ProductCardProps {
  variant: "corpos" | "finos";
  href: string;
}

function ProductCard({ variant, href }: ProductCardProps) {
  const isCorpos = variant === "corpos";

  const config = {
    label: isCorpos ? "HOLDİNG İÇİN" : "KOBİ İÇİN",
    name: isCorpos ? "CorpOS" : "FinOS",
    tagline: isCorpos
      ? "Çoklu şirket, tek pano"
      : "Nakit akışı, kontrol altında",
    description: isCorpos
      ? "Konsolide P&L · Intercompany transfer (4-eyes) · Karma sektör desteği"
      : "Vade hatırlatma · Risk skoru · Cash flow projeksiyonu",
    icon: isCorpos ? Building2 : TrendingUp,
    accentClass: isCorpos
      ? "text-aq-burgundy"
      : "text-aq-mint",
    badgeClass: isCorpos
      ? "border-aq-burgundy/30 bg-aq-burgundy/10 text-aq-burgundy"
      : "border-aq-mint/30 bg-aq-mint/10 text-aq-mint",
    glowClass: isCorpos
      ? "group-hover:shadow-corpos"
      : "group-hover:shadow-finos",
    iconBoxClass: isCorpos
      ? "bg-aq-burgundy/15 ring-aq-burgundy/30 group-hover:bg-aq-burgundy/25"
      : "bg-aq-mint/15 ring-aq-mint/30 group-hover:bg-aq-mint/25",
  } as const;

  const Icon = config.icon;

  return (
    <Link
      href={href}
      aria-label={`${config.name} ürün sayfasını keşfet`}
      className="group block focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-aq-quantum focus-visible:ring-offset-2 focus-visible:ring-offset-aq-void rounded-2xl"
    >
      <motion.article
        whileHover={{ y: -8 }}
        transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
        className={cn(
          "relative overflow-hidden rounded-2xl p-7",
          "bg-aq-orbital/60 backdrop-blur-xl",
          "border border-aq-mist/40",
          "transition-shadow duration-500",
          config.glowClass,
        )}
      >
        {/* Üst etiket */}
        <div
          className={cn(
            "inline-flex items-center rounded-full border px-2.5 py-0.5 text-[10px] font-mono uppercase tracking-[0.18em]",
            config.badgeClass,
          )}
        >
          {config.label}
        </div>

        {/* İkon kutusu */}
        <div
          className={cn(
            "mt-5 grid h-12 w-12 place-items-center rounded-xl ring-1 transition-all duration-400",
            config.iconBoxClass,
          )}
        >
          <Icon className={cn("h-6 w-6", config.accentClass)} />
        </div>

        {/* İsim */}
        <h3 className="mt-5 text-2xl font-bold tracking-tight text-foreground">
          {config.name}
        </h3>

        {/* Tagline */}
        <p className="mt-1 text-sm font-medium text-aq-dust">
          {config.tagline}
        </p>

        {/* Description */}
        <p className="mt-4 text-xs leading-relaxed text-aq-trace">
          {config.description}
        </p>

        {/* CTA */}
        <div className="mt-6 flex items-center justify-between">
          <span className={cn(
            "text-xs font-medium tracking-wide",
            config.accentClass,
          )}>
            Keşfet
          </span>
          <ArrowRight
            className={cn(
              "h-4 w-4 transition-transform duration-400 group-hover:translate-x-1",
              config.accentClass,
            )}
          />
        </div>
      </motion.article>
    </Link>
  );
}

/**
 * Hero altında iki ürün kartı (CorpOS + FinOS).
 * Mobil: dikey stack. Desktop: yan yana (md+).
 */
export function ProductCards() {
  return (
    <div
      className="mx-auto mt-10 grid max-w-3xl grid-cols-1 gap-4 md:grid-cols-2"
      aria-label="Alpha Quantum ürün modülleri"
    >
      <ProductCard variant="corpos" href="#corpos" />
      <ProductCard variant="finos" href="#finos" />
    </div>
  );
}
