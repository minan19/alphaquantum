/**
 * Design Token Programı — Faz 6 · SSR FontLoader.
 *
 * Çalışma zamanı font yüklemesi — ÇERÇEVE FONTUNUN ÜSTÜNE binmez, ON YANINA
 * eklenir. Token zinciri:
 *   --font-display: var(--font-inter), 'Inter', system-ui, ...   ← globals.css base
 *   html[data-module='X'] { --font-display: 'X-Default', <yukarıdaki zincir>; } ← burada eklenir
 *
 * Default font yüklenmezse zincir KIRILMADAN frame Inter'a → system-ui'a düşer.
 *
 * Çıktı (3 blok):
 *   1) Google fontlar için <link rel="stylesheet" href="https://fonts.googleapis.com/...">
 *   2) Upload fontlar için <style>@font-face{ src: url(/api/fonts/<id>) format(...) }</style>
 *   3) Her scope için is_default'lu font'u --font-display zincirine prepend eden override CSS
 */
import { cssFormatHint, getFonts, type CustomFont } from "@/lib/fonts";

function escapeFamily(family: string): string {
  // CSS'de family adı tek tırnak içinde — içeriği için backslash escape.
  // Family adı ASCII + üretici-kontrollü; yine de defansif kaçış.
  return family.replace(/\\/g, "\\\\").replace(/'/g, "\\'");
}

function googleLinks(fonts: CustomFont[]): React.ReactElement[] {
  return fonts
    .filter((f) => f.source === "google" && f.css_url)
    .map((f) => (
      <link
        key={`g-${f.id}`}
        rel="stylesheet"
        href={f.css_url as string}
        // Faz 6 §6: display=swap CSS URL inşasında zaten var; rel attr olarak da işaretle.
        data-aq-font-source="google"
        data-aq-font-scope={f.scope}
      />
    ));
}

function uploadFaceFaces(fonts: CustomFont[]): string {
  const lines: string[] = [];
  for (const f of fonts) {
    if (f.source !== "upload") continue;
    const fmtHint = cssFormatHint(f.format);
    const formatPart = fmtHint ? ` format('${fmtHint}')` : "";
    const w = f.weight ? `font-weight: ${f.weight};` : "";
    const s = f.style ? `font-style: ${f.style};` : "";
    lines.push(
      `@font-face {` +
        `font-family: '${escapeFamily(f.family)}';` +
        `src: url('/api/fonts/${f.id}')${formatPart};` +
        `font-display: swap;${w}${s}` +
      `}`,
    );
  }
  return lines.join("");
}

/**
 * Default font'u scope-aware --font-display zincirine prepend et.
 * core'da is_default ise :root, modülde ise html[data-module='X'].
 *
 * KRİTİK: ham aile adıyla EZME değil, ZİNCİRİN BAŞINA EKLEME. Yüklenmezse
 * tarayıcı sıradaki var(--font-inter)'a → system-ui'a düşer.
 */
function defaultOverrides(fonts: CustomFont[]): string {
  // Base fallback zinciri — globals.css ile aynı sıra.
  const baseChain = "var(--font-inter), 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif";
  const segments: string[] = [];
  for (const f of fonts) {
    if (!f.is_default) continue;
    const fam = `'${escapeFamily(f.family)}'`;
    if (f.scope === "core") {
      segments.push(`:root { --font-display: ${fam}, ${baseChain}; }`);
    } else {
      segments.push(`html[data-module='${f.scope}'] { --font-display: ${fam}, ${baseChain}; }`);
    }
  }
  return segments.join("\n");
}

/**
 * SSR FontLoader — async server component.
 * Listenin başarısız çekilmesi sessiz drop; çerçeve fontu kalır (regresyon-güvenli).
 */
export async function FontLoader() {
  const { fonts } = await getFonts();
  const faceFaces = uploadFaceFaces(fonts);
  const overrides = defaultOverrides(fonts);
  return (
    <>
      {googleLinks(fonts)}
      {(faceFaces || overrides) && (
        <style
          // Token cascade'i için critical-path CSS; head'e inline iniyor.
          dangerouslySetInnerHTML={{ __html: faceFaces + overrides }}
          data-aq-faz="6"
        />
      )}
    </>
  );
}
