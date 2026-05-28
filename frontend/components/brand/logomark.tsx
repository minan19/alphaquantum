"use client";

import { useId } from "react";
import { cn } from "@/lib/cn";

/**
 * Alpha Quantum logomark.
 *
 * The mark is a stylized "AQ" — an alpha glyph nested inside a quantum
 * orbital. The orbital is drawn with three rings at different phase angles
 * to suggest probability density. Rendered as inline SVG so we can color it
 * via CSS variables (gradients, hover states, dark/light themes).
 *
 * NOTE: React's useId() is used for the gradient ID. Earlier we used
 * Math.random() which caused SSR/CSR hydration mismatches (each render
 * generated a different ID). useId() is stable across server + client and
 * unique per instance — exactly what SVG defs need.
 */
export function Logomark({
  className,
  size = 32,
  animated = false,
}: {
  className?: string;
  size?: number;
  animated?: boolean;
}) {
  const rawId = useId();
  // useId() returns ":r1:" style values — SVG attribute names can't contain
  // colons in some renderers, so strip them.
  const id = `aq-gradient-${rawId.replace(/:/g, "")}`;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={cn(className, animated && "[&_g.orbits]:animate-spin-slow")}
      aria-hidden="true"
    >
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="48" y2="48" gradientUnits="userSpaceOnUse">
          <stop offset="0%"  stopColor="rgb(91 71 251)" />
          <stop offset="60%" stopColor="rgb(124 96 255)" />
          <stop offset="100%" stopColor="rgb(6 182 212)" />
        </linearGradient>
        <radialGradient id={`${id}-glow`} cx="50%" cy="50%" r="50%">
          <stop offset="0%"  stopColor="rgb(91 71 251)" stopOpacity="0.45" />
          <stop offset="100%" stopColor="rgb(91 71 251)" stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* Outer glow */}
      <circle cx="24" cy="24" r="22" fill={`url(#${id}-glow)`} />

      {/* Three orbitals at 0, 60, 120 degrees */}
      <g
        className="orbits"
        style={{ transformOrigin: "24px 24px" }}
        stroke={`url(#${id})`}
        strokeWidth="1.5"
        fill="none"
        opacity="0.65"
      >
        <ellipse cx="24" cy="24" rx="18" ry="7" />
        <ellipse cx="24" cy="24" rx="18" ry="7" transform="rotate(60 24 24)" />
        <ellipse cx="24" cy="24" rx="18" ry="7" transform="rotate(120 24 24)" />
      </g>

      {/* Alpha glyph (stylized A) — inset triangle */}
      <path
        d="M24 13 L33 33 H29.5 L27.5 28 H20.5 L18.5 33 H15 L24 13 Z M22 24 H26 L24 19 Z"
        fill={`url(#${id})`}
        stroke="rgba(255,255,255,0.15)"
        strokeWidth="0.5"
      />

      {/* Central nucleus */}
      <circle cx="24" cy="24" r="2" fill="rgb(255 255 255)" opacity="0.92" />
      <circle cx="24" cy="24" r="3.5" fill="none" stroke="rgb(255 255 255)" strokeWidth="0.5" opacity="0.4" />
    </svg>
  );
}

export function Wordmark({
  className,
  showModule = false,
}: {
  className?: string;
  showModule?: "corpos" | "finos" | false;
}) {
  return (
    <div className={cn("flex items-baseline gap-1.5", className)}>
      <span className="font-display text-lg font-bold tracking-tight text-foreground">
        Alpha<span className="text-aq-quantum-2">Quantum</span>
      </span>
      {showModule === "corpos" && (
        <span className="text-[10px] uppercase tracking-[0.18em] text-aq-plasma">
          · CorpOS
        </span>
      )}
      {showModule === "finos" && (
        <span className="text-[10px] uppercase tracking-[0.18em] text-aq-solar">
          · FinOS
        </span>
      )}
    </div>
  );
}
