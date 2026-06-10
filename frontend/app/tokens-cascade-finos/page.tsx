/**
 * Design Token Programı — Faz 2 cascade visual proof (FinOS kimliği).
 * Pathname `/tokens-cascade-finos` → `data-module='finos'` → `--cta`=#CD4A00.
 */
import { CascadeProbe } from "@/components/dev/cascade-probe";

export const metadata = { title: "Token cascade proof — FinOS" };

export default function Page() {
  return <CascadeProbe expectedModule="finos" />;
}
