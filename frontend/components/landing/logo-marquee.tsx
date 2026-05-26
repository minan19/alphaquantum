"use client";

import { cn } from "@/lib/cn";

/**
 * Customer / partner logo marquee — infinite horizontal scroll.
 * Pure CSS animation (no JS), respects prefers-reduced-motion.
 *
 * Pass an array of company display names; this renders them as stylized
 * pill tags. Replace with real <Image> components once real logo SVGs exist.
 */
export function LogoMarquee({
  logos,
  label = "Türkiye'nin lider holdinglerinin tercihi",
}: {
  logos: string[];
  label?: string;
}) {
  // Duplicate the array so the marquee loops seamlessly
  const doubled = [...logos, ...logos];

  return (
    <section
      aria-label="Müşteri logoları"
      className="relative overflow-hidden border-y border-aq-mist/30 bg-aq-cosmos/30 py-10"
    >
      <p className="mb-6 text-center text-[10px] font-mono uppercase tracking-[0.22em] text-aq-trace">
        {label}
      </p>

      <div className="relative">
        {/* Fade-out gradients on edges */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-y-0 left-0 z-10 w-24 bg-gradient-to-r from-aq-void to-transparent"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute inset-y-0 right-0 z-10 w-24 bg-gradient-to-l from-aq-void to-transparent"
        />

        <div
          className={cn(
            "flex w-max items-center gap-12",
            "animate-[marquee_40s_linear_infinite]",
            "motion-reduce:animate-none",
          )}
        >
          {doubled.map((name, i) => (
            <div
              key={`${name}-${i}`}
              className={cn(
                "flex items-center gap-2.5 rounded-lg border border-aq-mist/40 bg-card/50 px-5 py-2.5",
                "text-sm font-medium tracking-tight text-aq-dust hover:text-foreground",
                "transition-colors duration-300",
              )}
            >
              {/* Stylized logo placeholder (initials in monogram) */}
              <span
                className="grid h-6 w-6 place-items-center rounded bg-gradient-to-br from-aq-quantum/40 to-aq-plasma/40 text-[10px] font-bold text-white"
                aria-hidden
              >
                {name
                  .split(" ")
                  .map((s) => s[0])
                  .slice(0, 2)
                  .join("")
                  .toUpperCase()}
              </span>
              <span>{name}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
