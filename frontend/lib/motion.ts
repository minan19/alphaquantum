/**
 * Shared Framer Motion presets for Alpha Quantum.
 *
 * Two ease curves are exposed:
 * - `easeQuantum` — physics-inspired bounce-free curve, used for general
 *   transitions (hovers, layout changes). Slightly snappier than enterprise.
 * - `easeEnterprise` — easeOutExpo (0.16, 1, 0.3, 1). Used for slow, premium
 *   entrance reveals (section reveal, hero cascade, modal). Reads as
 *   "thoughtful, grounded" — the enterprise tone our design doc calls for.
 *
 * Standard durations (in seconds, Framer Motion convention):
 * - micro:   0.15-0.2   (hover state change)
 * - element: 0.3-0.4    (card hover, button transition)
 * - section: 0.7        (reveal-on-scroll, ağırbaşlı premium)
 * - hero:    2.5 total  (cascade with staggered children)
 *
 * Stagger:
 * - tight:  0.05  (charts, icons)
 * - medium: 0.08  (stat cards)
 * - slow:   0.12  (sections, hero) — enterprise default
 */

export const easeQuantum = [0.32, 0.72, 0, 1] as const;
export const easeEnterprise = [0.16, 1, 0.3, 1] as const;

export const motionDuration = {
  micro: 0.15,
  element: 0.3,
  card: 0.4,
  section: 0.7,
  hero: 2.5,
} as const;

export const motionStagger = {
  tight: 0.05,
  medium: 0.08,
  slow: 0.12,
} as const;

/* ── Variant presets ──────────────────────────────────────────────────────── */

/** Section reveal: slow, ağırbaşlı, viewport %25'te tetiklenir. */
export const sectionReveal = {
  hidden: { opacity: 0, y: 24 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: motionDuration.section, ease: easeEnterprise },
  },
} as const;

/** Card reveal: lighter, faster — used for grids/lists. */
export const cardReveal = {
  hidden: { opacity: 0, y: 12 },
  visible: (i: number = 0) => ({
    opacity: 1,
    y: 0,
    transition: {
      duration: motionDuration.card,
      delay: i * motionStagger.medium,
      ease: easeEnterprise,
    },
  }),
} as const;

/** Container for staggered children entry. */
export const staggerContainer = {
  hidden: {},
  visible: {
    transition: { staggerChildren: motionStagger.slow },
  },
} as const;
