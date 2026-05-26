"use client";

import { motion } from "framer-motion";
import { ArrowDownRight, ArrowUpRight, type LucideIcon } from "lucide-react";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/cn";

type Tone = "neutral" | "ok" | "warn" | "alert" | "primary";

const TONE_STYLES: Record<Tone, { ring: string; glow: string; icon: string }> = {
  neutral: { ring: "ring-aq-mist/40", glow: "from-aq-mist/10 to-transparent", icon: "text-aq-dust" },
  primary: { ring: "ring-aq-quantum/40", glow: "from-aq-quantum/15 to-transparent", icon: "text-aq-quantum-2" },
  ok:      { ring: "ring-aq-fusion/40", glow: "from-aq-fusion/15 to-transparent", icon: "text-aq-fusion" },
  warn:    { ring: "ring-aq-solar/40", glow: "from-aq-solar/15 to-transparent", icon: "text-aq-solar" },
  alert:   { ring: "ring-aq-fission/40", glow: "from-aq-fission/15 to-transparent", icon: "text-aq-fission" },
};

interface StatCardProps {
  label: string;
  value: string | number;
  unit?: string;
  delta?: number;        // % change vs last period
  tone?: Tone;
  icon?: LucideIcon;
  hint?: string;
  index?: number;        // for staggered entry
}

export function StatCard({
  label,
  value,
  unit,
  delta,
  tone = "neutral",
  icon: Icon,
  hint,
  index = 0,
}: StatCardProps) {
  const styles = TONE_STYLES[tone];
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.05 * index, ease: [0.32, 0.72, 0, 1] }}
    >
      <Card
        variant="default"
        className={cn(
          "relative overflow-hidden p-5 ring-1",
          styles.ring,
        )}
      >
        {/* Tonal glow */}
        <div className={cn("absolute -right-8 -top-8 h-32 w-32 rounded-full blur-3xl bg-gradient-to-br opacity-60", styles.glow)} />

        <div className="relative flex items-start justify-between gap-3">
          <div className="space-y-1">
            <p className="text-xs font-medium uppercase tracking-wider text-aq-dust">{label}</p>
            <div className="flex items-baseline gap-1.5">
              <span className="text-3xl font-bold tabular num tracking-tight">
                {value}
              </span>
              {unit && (
                <span className="text-sm font-medium text-aq-dust">{unit}</span>
              )}
            </div>
            {hint && <p className="text-xs text-aq-trace">{hint}</p>}
          </div>
          {Icon && (
            <div className={cn("rounded-md bg-aq-orbital/60 p-2", styles.icon)}>
              <Icon className="h-5 w-5" />
            </div>
          )}
        </div>

        {delta !== undefined && (
          <div className="mt-4 flex items-center gap-1.5 text-xs">
            {delta >= 0 ? (
              <ArrowUpRight className="h-3.5 w-3.5 text-aq-fusion" />
            ) : (
              <ArrowDownRight className="h-3.5 w-3.5 text-aq-fission" />
            )}
            <span className={cn("font-mono tabular num", delta >= 0 ? "text-aq-fusion" : "text-aq-fission")}>
              {delta >= 0 ? "+" : ""}{delta.toFixed(1)}%
            </span>
            <span className="text-aq-trace">geçen aya göre</span>
          </div>
        )}
      </Card>
    </motion.div>
  );
}
