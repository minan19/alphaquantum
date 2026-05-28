"use client";

import { useCallback, useRef } from "react";

/**
 * Cursor-following spotlight hook (Linear/Vercel pattern).
 *
 * Returns a ref + onMouseMove handler that writes mouse pixel coordinates
 * into `--mx` / `--my` CSS variables on the element. Pair with the
 * `.spotlight-card` utility class (defined in `globals.css`) which uses
 * these variables to render a subtle radial-gradient highlight.
 *
 * Usage:
 *   const { ref, onMouseMove } = useSpotlight<HTMLDivElement>();
 *   return <div ref={ref} onMouseMove={onMouseMove} className="spotlight-card">…</div>;
 *
 * Performance: writes inline CSS variables (no React state). Browser composites
 * the gradient cheaply. Honors prefers-reduced-motion implicitly (CSS gradient
 * is static; only `--mx/--my` change, which the user can disable via media query
 * if they wish).
 */
export function useSpotlight<T extends HTMLElement>() {
  const ref = useRef<T | null>(null);

  const onMouseMove = useCallback((event: React.MouseEvent<T>) => {
    const node = ref.current;
    if (!node) return;
    const rect = node.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    node.style.setProperty("--mx", `${x}px`);
    node.style.setProperty("--my", `${y}px`);
  }, []);

  return { ref, onMouseMove };
}
