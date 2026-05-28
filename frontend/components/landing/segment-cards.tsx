"use client";

import { motion } from "framer-motion";
import {
  ArrowRight,
  Briefcase,
  Building2,
  Crown,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/cn";

interface Segment {
  id: string;
  icon: LucideIcon;
  badge: string;
  title: string;
  subtitle: string;
  bullets: string[];
  href: string;
  tone: "primary" | "plasma" | "solar";
}

const SEGMENTS: Segment[] = [
  {
    id: "holding",
    icon: Crown,
    badge: "Holding Sahibi",
    title: "Birden fazla şirket. Tek panel.",
    subtitle: "3+ şirket yöneten patronlar",
    bullets: [
      "Konsolide P&L raporlama",
      "Inter-company transferler",
      "Holding seviyesi dashboard",
      "Çapraz şirket karşılaştırma",
    ],
    href: "/login?plan=enterprise",
    tone: "primary",
  },
  {
    id: "kobi",
    icon: Briefcase,
    badge: "KOBİ Patron",
    title: "Alacaklarınız zamanında. Otomatik.",
    subtitle: "100-2.500 fatura/ay arası KOBİ",
    bullets: [
      "Vade uyarı motoru (T-3..T+14)",
      "Müşteri risk skoru",
      "WhatsApp/SMS/E-posta dispatch",
      "KVKK uyumlu consent",
    ],
    href: "/login?plan=pro",
    tone: "plasma",
  },
  {
    id: "corporate",
    icon: Building2,
    badge: "Kurumsal CFO",
    title: "Karar veriyle. Hızlı.",
    subtitle: "Mali işler departmanı için",
    bullets: [
      "OAuth2 / SSO entegrasyonu",
      "4-eyes onay workflow",
      "Audit log + KVKK madde 12",
      "ISO 27001 uyumlu kurulum",
    ],
    href: "/login?plan=enterprise",
    tone: "solar",
  },
];

const TONE_STYLES = {
  primary: {
    iconBg: "from-aq-quantum/20 to-aq-quantum-2/20",
    iconRing: "ring-aq-quantum/30",
    iconColor: "text-aq-quantum-2",
    badgeTone: "bg-aq-quantum/15 text-aq-quantum-2 ring-aq-quantum/30",
    glow: "from-aq-quantum/10",
    hover: "hover:border-aq-quantum/50 hover:shadow-quantum",
  },
  plasma: {
    iconBg: "from-aq-plasma/20 to-aq-plasma/30",
    iconRing: "ring-aq-plasma/30",
    iconColor: "text-aq-plasma",
    badgeTone: "bg-aq-plasma/15 text-aq-plasma ring-aq-plasma/30",
    glow: "from-aq-plasma/10",
    hover: "hover:border-aq-plasma/50 hover:shadow-[0_0_24px_-4px_rgba(6,182,212,0.4)]",
  },
  solar: {
    iconBg: "from-aq-solar/20 to-aq-solar/30",
    iconRing: "ring-aq-solar/30",
    iconColor: "text-aq-solar",
    badgeTone: "bg-aq-solar/15 text-aq-solar ring-aq-solar/30",
    glow: "from-aq-solar/10",
    hover: "hover:border-aq-solar/50 hover:shadow-[0_0_24px_-4px_rgba(245,158,11,0.4)]",
  },
} as const;

export function SegmentCards() {
  return (
    <section className="relative z-10 mx-auto max-w-7xl px-6">
      <div className="text-center mb-10">
        <p className="text-[10px] font-mono uppercase tracking-[0.22em] text-aq-trace mb-3">
          Hangi seviyedesin?
        </p>
        <h2 className="text-2xl sm:text-3xl font-bold tracking-tight">
          İhtiyacına göre konfigüre edilmiş yol
        </h2>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {SEGMENTS.map((seg, i) => {
          const styles = TONE_STYLES[seg.tone];
          const Icon = seg.icon;
          return (
            <motion.div
              key={seg.id}
              initial={{ opacity: 0, y: 18 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.3 }}
              transition={{ duration: 0.55, delay: i * 0.08, ease: [0.32, 0.72, 0, 1] }}
            >
              <Link
                href={seg.href}
                className={cn(
                  "group relative block h-full rounded-xl border border-aq-mist/40 bg-card/60",
                  "p-6 transition-all duration-300 ease-quantum",
                  "backdrop-blur-sm",
                  styles.hover,
                )}
              >
                {/* Tonal glow */}
                <div
                  aria-hidden
                  className={cn(
                    "absolute -right-12 -top-12 h-40 w-40 rounded-full blur-3xl",
                    "bg-gradient-to-br opacity-40 transition-opacity duration-500",
                    "group-hover:opacity-70",
                    styles.glow,
                  )}
                />

                <div className="relative">
                  {/* Icon + Badge */}
                  <div className="flex items-start justify-between gap-3 mb-5">
                    <div
                      className={cn(
                        "grid h-12 w-12 place-items-center rounded-xl",
                        "bg-gradient-to-br ring-1",
                        styles.iconBg,
                        styles.iconRing,
                      )}
                    >
                      <Icon className={cn("h-6 w-6", styles.iconColor)} />
                    </div>
                    <span
                      className={cn(
                        "rounded-full px-2.5 py-0.5 text-[10px] font-medium ring-1",
                        styles.badgeTone,
                      )}
                    >
                      {seg.badge}
                    </span>
                  </div>

                  {/* Title + subtitle */}
                  <h3 className="text-lg font-bold tracking-tight leading-snug">
                    {seg.title}
                  </h3>
                  <p className="mt-1 text-xs text-aq-trace">{seg.subtitle}</p>

                  {/* Bullets */}
                  <ul className="mt-5 space-y-2">
                    {seg.bullets.map((b) => (
                      <li
                        key={b}
                        className="flex items-start gap-2 text-sm text-aq-dust"
                      >
                        <span
                          className={cn(
                            "mt-1 h-1 w-1 rounded-full shrink-0",
                            seg.tone === "primary" && "bg-aq-quantum-2",
                            seg.tone === "plasma" && "bg-aq-plasma",
                            seg.tone === "solar" && "bg-aq-solar",
                          )}
                          aria-hidden
                        />
                        <span>{b}</span>
                      </li>
                    ))}
                  </ul>

                  {/* CTA */}
                  <div className="mt-6 flex items-center gap-2 text-sm font-medium text-foreground">
                    <span>Bu yola bak</span>
                    <ArrowRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-1" />
                  </div>
                </div>
              </Link>
            </motion.div>
          );
        })}
      </div>
    </section>
  );
}
