import type { Config } from "tailwindcss";

export default {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Alpha Quantum corporate palette (inspired by FINOS_MASTER navy)
        brand: {
          50: "#EBF3FB",
          100: "#D6E5F3",
          500: "#1F4E79",
          600: "#1A4267",
          700: "#143452",
        },
        signal: {
          ok: "#1A7A4A",
          warn: "#E67E22",
          alert: "#C0392B",
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
