"use client";

import { useEffect, useRef, useState } from "react";
import { motion, useInView } from "framer-motion";
import { cn } from "@/lib/cn";

interface AnimatedCounterProps {
  /** Final value the counter rolls up to. */
  to: number;
  /** Animation duration in ms (default 1600). */
  duration?: number;
  /** Format the displayed number (e.g. Intl.NumberFormat). */
  format?: (n: number) => string;
  /** Suffix appended (e.g. "+", "₺", "%"). */
  suffix?: string;
  /** Prefix appended (e.g. "₺"). */
  prefix?: string;
  /** Tailwind classes for the number element. */
  className?: string;
}

/**
 * AnimatedCounter — rolls the displayed number from 0 to `to` once the
 * element scrolls into view. Uses IntersectionObserver via Framer Motion's
 * `useInView`. Respects `prefers-reduced-motion`: if reduced, jumps to final.
 */
export function AnimatedCounter({
  to,
  duration = 1600,
  format,
  suffix = "",
  prefix = "",
  className,
}: AnimatedCounterProps) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.4 });
  const [value, setValue] = useState(0);

  useEffect(() => {
    if (!inView) return;

    const prefersReduced =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    if (prefersReduced) {
      setValue(to);
      return;
    }

    const start = performance.now();
    let frame = 0;
    const step = (now: number) => {
      const t = Math.min((now - start) / duration, 1);
      // ease-out cubic
      const eased = 1 - Math.pow(1 - t, 3);
      setValue(Math.round(to * eased));
      if (t < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [inView, to, duration]);

  const display = format ? format(value) : value.toLocaleString("tr-TR");

  return (
    <motion.span
      ref={ref}
      className={cn("tabular num", className)}
      initial={{ opacity: 0 }}
      animate={inView ? { opacity: 1 } : { opacity: 0 }}
      transition={{ duration: 0.4 }}
    >
      {prefix}
      {display}
      {suffix}
    </motion.span>
  );
}
