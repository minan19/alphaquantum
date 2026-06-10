/**
 * Design Token Programı — Faz 2 cascade visual proof (CorpOS kimliği).
 * Pathname `/tokens-cascade-corpos` → `data-module='corpos'` → `--cta`=#F4C542 (altın).
 */
import { CascadeProbe } from "@/components/dev/cascade-probe";

export const metadata = { title: "Token cascade proof — CorpOS" };

export default function Page() {
  return <CascadeProbe expectedModule="corpos" />;
}
