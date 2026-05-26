"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, X } from "lucide-react";

/**
 * Floating sticky CTA bar that appears after the user scrolls past the
 * hero section. Provides a persistent path to /login or demo request,
 * without competing with the main hero CTAs on first view.
 *
 * Auto-hides if user dismisses (session-only — re-appears on next visit).
 */
export function StickyDemoCTA({
  href = "/login",
  label = "Hemen başla",
  /** Show after this scroll Y. */
  showAfter = 600,
}: {
  href?: string;
  label?: string;
  showAfter?: number;
}) {
  const [visible, setVisible] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (dismissed) return;
    const onScroll = () => setVisible(window.scrollY > showAfter);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [dismissed, showAfter]);

  const show = visible && !dismissed;

  return (
    <AnimatePresence>
      {show && (
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 30 }}
          transition={{ duration: 0.35, ease: [0.32, 0.72, 0, 1] }}
          className="fixed bottom-6 right-6 z-50 flex items-center gap-1"
        >
          {/* Dismiss */}
          <button
            onClick={() => setDismissed(true)}
            aria-label="Kapat"
            className="grid h-9 w-9 place-items-center rounded-full bg-aq-orbital/80 backdrop-blur-md border border-aq-mist/60 text-aq-dust hover:text-foreground hover:border-aq-mist transition-all"
          >
            <X className="h-4 w-4" />
          </button>

          {/* Main CTA */}
          <Link
            href={href}
            className="group flex items-center gap-2 rounded-full bg-gradient-to-br from-aq-quantum to-aq-quantum-2 px-5 py-3 text-sm font-semibold text-white shadow-quantum-lg transition-all hover:shadow-quantum-lg hover:scale-105"
          >
            <span className="relative">
              {/* Pulse ring */}
              <span className="absolute inset-0 -m-1 rounded-full bg-aq-quantum animate-pulse-ring" />
              <span className="relative inline-block h-2 w-2 rounded-full bg-white" />
            </span>
            {label}
            <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
          </Link>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
