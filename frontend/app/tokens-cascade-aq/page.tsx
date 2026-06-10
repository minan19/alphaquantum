/**
 * Design Token Programı — Faz 2 cascade visual proof (AlphaQ kimliği).
 *
 * Bu sayfa pathname `/tokens-cascade-aq` ile çakışan `detectModuleFromPathname`
 * tarafından `data-module='aq'` olarak işaretlenir. CSS variable cascade'i
 * `html[data-module='aq']` bloğundan değerleri alır.
 *
 * Probe component her 3 demo route'da aynı; yalnız `<html data-module>` değişir.
 */
import { CascadeProbe } from "@/components/dev/cascade-probe";

export const metadata = { title: "Token cascade proof — AlphaQ" };

export default function Page() {
  return <CascadeProbe expectedModule="aq" />;
}
