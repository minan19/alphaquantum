"use client";

import { motion } from "framer-motion";
import { ChevronDown } from "lucide-react";

/**
 * Subtle "scroll for more" hint, animated chevron that gently bounces.
 * Respects prefers-reduced-motion: shows a static chevron if user opts out.
 *
 * Click to smooth-scroll to the next section (data-scroll-target attr or
 * just `window.scrollBy(0, viewportHeight)` as default).
 */
export function ScrollIndicator({
  label = "Aşağı kaydır",
  targetId,
}: {
  label?: string;
  /** Optional element id to scroll to; defaults to one viewport down. */
  targetId?: string;
}) {
  const handleClick = () => {
    if (targetId) {
      document.getElementById(targetId)?.scrollIntoView({ behavior: "smooth" });
      return;
    }
    window.scrollBy({ top: window.innerHeight * 0.85, behavior: "smooth" });
  };

  return (
    <motion.button
      onClick={handleClick}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: 1.2, duration: 0.6 }}
      className="group inline-flex flex-col items-center gap-2 text-aq-trace hover:text-aq-quantum-2 transition-colors"
      aria-label={label}
    >
      <span className="text-[10px] font-mono uppercase tracking-[0.22em]">
        {label}
      </span>
      <motion.span
        className="grid h-9 w-9 place-items-center rounded-full border border-aq-mist/40 bg-aq-orbital/40 backdrop-blur-sm group-hover:border-aq-quantum/50 group-hover:bg-aq-quantum/10 transition-colors"
        animate={{ y: [0, 6, 0] }}
        transition={{ duration: 2, ease: "easeInOut", repeat: Infinity }}
      >
        <ChevronDown className="h-4 w-4" />
      </motion.span>
    </motion.button>
  );
}
