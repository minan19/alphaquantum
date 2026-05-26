import type { Config } from "tailwindcss";

/** rgb(var(--token) / <alpha-value>) helper */
const c = (token: string) => `rgb(var(--${token}) / <alpha-value>)`;

export default {
  darkMode: ["class"],
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: { "2xl": "1400px" },
    },
    extend: {
      colors: {
        // Semantic (shadcn-compatible)
        background:  c("background"),
        foreground:  c("foreground"),
        card:        { DEFAULT: c("card"), foreground: c("card-foreground") },
        popover:     { DEFAULT: c("popover"), foreground: c("popover-foreground") },
        primary:     { DEFAULT: c("primary"), foreground: c("primary-foreground") },
        secondary:   { DEFAULT: c("secondary"), foreground: c("secondary-foreground") },
        muted:       { DEFAULT: c("muted"), foreground: c("muted-foreground") },
        accent:      { DEFAULT: c("accent"), foreground: c("accent-foreground") },
        destructive: { DEFAULT: c("destructive"), foreground: c("destructive-foreground") },
        border:      c("border"),
        input:       c("input"),
        ring:        c("ring"),

        // Brand palette (Alpha Quantum signature)
        aq: {
          void:      c("aq-void"),
          cosmos:    c("aq-cosmos"),
          orbital:   c("aq-orbital"),
          mist:      c("aq-mist"),
          quantum:   c("aq-quantum"),
          "quantum-2": c("aq-quantum-2"),
          plasma:    c("aq-plasma"),
          solar:     c("aq-solar"),
          fission:   c("aq-fission"),
          fusion:    c("aq-fusion"),
          neutron:   c("aq-neutron"),
          dust:      c("aq-dust"),
          trace:     c("aq-trace"),
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      fontFamily: {
        display: ["var(--font-display)"],
        mono:    ["var(--font-mono)"],
      },
      backgroundImage: {
        "quantum-gradient":
          "linear-gradient(135deg, rgb(var(--aq-quantum)), rgb(var(--aq-plasma)))",
        "cosmos-gradient":
          "radial-gradient(ellipse at top, rgb(var(--aq-cosmos)), rgb(var(--aq-void)))",
        "aurora":
          "conic-gradient(from 180deg at 50% 50%, rgb(var(--aq-quantum)), rgb(var(--aq-plasma)), rgb(var(--aq-quantum-2)), rgb(var(--aq-quantum)))",
      },
      animation: {
        "fade-in":     "fadeIn 400ms cubic-bezier(0.32, 0.72, 0, 1) both",
        "slide-up":    "slideUp 500ms cubic-bezier(0.32, 0.72, 0, 1) both",
        "scale-in":    "scaleIn 350ms cubic-bezier(0.32, 0.72, 0, 1) both",
        "pulse-ring":  "pulse-ring 1.6s ease-out infinite",
        "shimmer":     "shimmer 2s linear infinite",
        "float":       "float 20s ease-in-out infinite",
        "spin-slow":   "spin 12s linear infinite",
      },
      keyframes: {
        fadeIn:   { from: { opacity: "0" }, to: { opacity: "1" } },
        slideUp:  {
          from: { opacity: "0", transform: "translateY(8px)" },
          to:   { opacity: "1", transform: "translateY(0)" },
        },
        scaleIn:  {
          from: { opacity: "0", transform: "scale(0.96)" },
          to:   { opacity: "1", transform: "scale(1)" },
        },
      },
      boxShadow: {
        "quantum":     "0 0 0 1px rgba(91,71,251,0.18), 0 8px 32px -8px rgba(91,71,251,0.40)",
        "quantum-lg":  "0 0 0 1px rgba(91,71,251,0.25), 0 24px 60px -20px rgba(91,71,251,0.55)",
        "glass":       "0 1px 0 rgba(255,255,255,0.04) inset, 0 0 0 1px rgba(255,255,255,0.02), 0 20px 60px -20px rgba(0,0,0,0.6)",
        "elevation-1": "0 1px 2px rgba(0,0,0,0.3)",
        "elevation-2": "0 4px 12px rgba(0,0,0,0.35)",
        "elevation-3": "0 10px 30px -10px rgba(0,0,0,0.5)",
      },
    },
  },
  plugins: [],
} satisfies Config;
