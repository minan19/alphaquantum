/**
 * Design Token Programı — Faz 2 · SSR Token Injector (server component).
 *
 * Görev:
 *   1. Backend `/api/v1/design-tokens`'ten tüm 4 scope'u çek (server-side, cache'li).
 *   2. Her scope için ayrı `<style>` bloğu enjekte et:
 *      - core   → `:root { ... }`                                 spec (0,1,0)
 *      - aq     → `html[data-module='aq']    { ... }`              spec (0,1,1)
 *      - finos  → `html[data-module='finos'] { ... }`              spec (0,1,1)
 *      - corpos → `html[data-module='corpos']{ ... }`              spec (0,1,1)
 *
 *   3. Tema ekseni iskelesi (Faz 7'de doldurulacak, ŞİMDİ DEĞERLER YOK):
 *      - `html[data-theme='light']                       { ... }`  spec (0,1,1)
 *      - `html[data-module='X'][data-theme='light']      { ... }`  spec (0,2,1) — kazanır
 *
 * KRİTİK specificity kuralı:
 *   `:root` → (0,1,0) ile çıplak `[data-module]` → (0,1,0) **aynı**.
 *   Bu yüzden modül seçicisini MUTLAKA `html[data-module='X']` yazıyoruz:
 *   `html` element selector = (0,0,1), `[data-module]` attribute = (0,1,0)
 *   → toplam (0,1,1). `:root` (0,1,0)'i özgüllükle yener; kaynak sırasına KALMAZ.
 *
 * KAYNAK SIRASI:
 *   Bu component root layout'ta `<body>` içine yerleştirilir → globals.css'in
 *   `<link>` etiketinden SONRA gelir → kaynak sırası garantili. Specificity ile
 *   modül zaten kazanır; sıra ek güvence.
 *
 * FALLBACK ZİNCİRİ (FOUC YOK):
 *   `getTokens()` backend ulaşılamazsa `lib/tokens-defaults.json` (Faz 0 kilidi)
 *   kullanır. Değerler her halde DOĞRU — backend kapalı olsa bile render bozulmaz.
 *
 * NO-FLASH:
 *   Bu server component, `<style>` etiketlerini SSR HTML'inde render eder. JS
 *   hidratasyonu beklenmez; ilk boyamada token'lar zaten yerinde.
 */
import {
  getTokens,
  keyToCssVar,
  type Token,
  VALID_SCOPES,
} from "@/lib/tokens";
import { lightCoreTokens, lightModuleTokens, type LightTokenMap } from "@/lib/light-tokens";

/**
 * Hex `#RRGGBB` → `"R G B"` (Tailwind alpha-pattern formatı).
 * Faz 3.5: alias köprüsü için her renk token'ın yanına `-rgb` varyantı türetiriz.
 * Hex DEĞİLSE boş döner — caller skip eder (örn. `cta_text_weight: 500`).
 */
function hexToRgbTriple(value: string): string {
  const m = value.match(/^#([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})$/);
  if (!m) return "";
  return `${parseInt(m[1], 16)} ${parseInt(m[2], 16)} ${parseInt(m[3], 16)}`;
}

/**
 * Bir token listesini "var: value;" deklarasyon bloğuna çevirir (deterministic sıra).
 *
 * Faz 3.5: Her renk token için iki satır basılır:
 *   --bg-primary:     #0C1015;
 *   --bg-primary-rgb: 12 16 21;
 *
 * `-rgb` varyantı yalnız hex değerlerden TÜRETİLİR (elle ikinci liste yok → drift yok).
 * Non-color değerler (örn. `cta_text_weight: 500`, font-family) sadece tek satır.
 */
function tokensToDeclarations(tokens: readonly Token[]): string {
  return tokens
    .slice()
    .sort((a, b) =>
      a.order !== b.order ? a.order - b.order : a.key.localeCompare(b.key),
    )
    .flatMap((t) => {
      const cssVar = keyToCssVar(t.key);
      const lines = [`  --${cssVar}: ${t.value};`];
      const rgb = hexToRgbTriple(String(t.value));
      if (rgb) {
        lines.push(`  --${cssVar}-rgb: ${rgb};`);
      }
      return lines;
    })
    .join("\n");
}

/** Bir selector + token listesinden komple `<style>` içeriğini üretir. */
function buildStyleBlock(selector: string, tokens: readonly Token[]): string {
  if (tokens.length === 0) return "";
  return `${selector} {\n${tokensToDeclarations(tokens)}\n}`;
}

/**
 * Faz 7 — light token map'inden CSS bloğu üretir.
 *
 * Şema dark blokları ile birebir aynı: her renk token için iki satır
 * (`--key:` ve `--key-rgb:`); non-color (cta_text_weight) tek satır.
 * Sıralama deterministik (key alfabetik).
 */
function lightTokensMapToCssBlock(selector: string, map: LightTokenMap): string {
  const keys = Object.keys(map).sort();
  if (keys.length === 0) return "";
  const lines: string[] = [];
  for (const key of keys) {
    const cssVar = keyToCssVar(key);
    const value = map[key];
    if (typeof value === "string") {
      lines.push(`  --${cssVar}: ${value};`);
      const rgb = hexToRgbTriple(value);
      if (rgb) lines.push(`  --${cssVar}-rgb: ${rgb};`);
    } else if (typeof value === "number") {
      lines.push(`  --${cssVar}: ${value};`);
    }
  }
  return `${selector} {\n${lines.join("\n")}\n}`;
}

/**
 * Faz 3.5 — Alias köprüsü.
 *
 * Mevcut shadcn semantic değişkenlerini Faz 1 token sözlüğüne bağlar. Eski isimler
 * KORUNUR (Tailwind utility'leri ve bileşenler etkilenmez); yalnız tanımları yeni
 * token'lardan beslenir. Tailwind `rgb(var(--token) / <alpha-value>)` pattern'i
 * için `-rgb` varyantları kullanılır.
 *
 * Cascade: alias `:root`'ta tanımlı ama `var(--cta-rgb)` USE-time'da çözülür →
 * modül scope'undaki `--cta-rgb` cascade otomatik devreye girer (FinOS'ta turuncu,
 * CorpOS'ta altın, AlphaQ'da azure).
 *
 * **Kapı 1 garanti çifti:**
 *   --primary           → --cta-rgb         (modül kimliği)
 *   --primary-foreground → --cta-text-rgb   (modül kimliğine uygun metin rengi)
 *   CorpOS altın CTA'sında metin OTOMATIK koyu (#0C1224 RGB) olur — beyaz kalmaz.
 */
const ALIAS_BRIDGE_CSS = `:root {
  /* Faz 3.5 alias köprüsü — shadcn semantic → Faz 1 token sözlüğü */
  --background:              var(--bg-primary-rgb);
  --foreground:              var(--text-primary-rgb);
  --card:                    var(--surface-01-rgb);
  --card-foreground:         var(--text-primary-rgb);
  --popover:                 var(--surface-02-rgb);
  --popover-foreground:      var(--text-primary-rgb);
  /* Q6 — Primary CTA çifti: dolgu + metin BİRLİKTE bağlanır (Kapı 1 garantisi) */
  --primary:                 var(--cta-rgb);
  --primary-foreground:      var(--cta-text-rgb);
  --secondary:               var(--surface-01-rgb);
  --secondary-foreground:    var(--text-primary-rgb);
  --muted:                   var(--bg-tertiary-rgb);
  --muted-foreground:        var(--text-muted-rgb);
  --accent:                  var(--accent-rgb);
  --accent-foreground:       var(--text-primary-rgb);
  --destructive:             var(--status-error-rgb);
  --destructive-foreground:  255 255 255;
  --border:                  var(--border-rgb);
  --input:                   var(--border-rgb);
  --ring:                    var(--focus-ring-rgb);
}`;

export async function ThemeTokens() {
  // Tüm 4 scope'u paralel çek — `unstable_cache(tags:['design-tokens'])` ile sarılı.
  // Backend kapalıysa: lib/tokens-defaults.json fallback otomatik devreye girer.
  const [coreTokens, aqTokens, finosTokens, corposTokens] = await Promise.all(
    VALID_SCOPES.map((s) => getTokens(s)),
  );

  // Source-of-truth doğrulaması (build-time invariant zaten lib/tokens.ts'te assertAllGovernance):
  // Burada ek runtime check yok — fast-path.

  // Style blokları string olarak hazırla.
  const coreCss = buildStyleBlock(":root", coreTokens);
  const aqCss = buildStyleBlock("html[data-module='aq']", aqTokens);
  const finosCss = buildStyleBlock("html[data-module='finos']", finosTokens);
  const corposCss = buildStyleBlock("html[data-module='corpos']", corposTokens);

  // Faz 7 — LIGHT değerler. Faz 3 motorundan hesaplanır (foundation kilidi).
  //
  // KRİTİK cascade kuralı (specificity tablosu):
  //   :root                                              (0,1,0) core dark
  //   html[data-module='X']                              (0,1,1) modül dark
  //   html[data-theme='light']                           (0,1,1) core light
  //   html[data-module='X'][data-theme='light']          (0,2,1) modül light ← KAZANIR
  //
  // (0,1,1) iki blok arasında çakışma var: aynı özgüllükte modül-dark ile
  // core-light. Modüldeyken core-light'a düşmemek için core-light bloğu
  // modül-dark'tan SONRA basılır (kaynak sırası). Asıl güvence (0,2,1) modül-
  // light birleşik seçici — her çakışan token modül-light bloğunda explicit.

  const coreLightCss = lightTokensMapToCssBlock(
    "html[data-theme='light']",
    lightCoreTokens(),
  );
  const moduleLightCss: Record<string, string> = {};
  for (const mod of ["aq", "finos", "corpos"] as const) {
    moduleLightCss[mod] = lightTokensMapToCssBlock(
      `html[data-module='${mod}'][data-theme='light']`,
      lightModuleTokens(mod),
    );
  }

  return (
    <>
      {/*
        Her blok ayrı <style id> ile basılır → DevTools/specificity testinde
        bireysel olarak disable edilebilir (kanıt #2 specificity ispatı için).
        dangerouslySetInnerHTML: React'in inner CSS'i escape ETMEMESİ için zorunlu.
      */}
      <style
        id="aq-tokens-core"
        dangerouslySetInnerHTML={{ __html: coreCss }}
      />
      <style
        id="aq-tokens-aq"
        dangerouslySetInnerHTML={{ __html: aqCss }}
      />
      <style
        id="aq-tokens-finos"
        dangerouslySetInnerHTML={{ __html: finosCss }}
      />
      <style
        id="aq-tokens-corpos"
        dangerouslySetInnerHTML={{ __html: corposCss }}
      />
      {/*
        Faz 7 — Light blokları. Sıra KRİTİK:
        Modül-dark blokları yukarıda basıldı. Core-light burada gelir ki
        modüldeyken light'a geçince modül-dark'ı (aynı özgüllük) kaynak
        sırasıyla yenebilsin. Sonra modül-light blokları (0,2,1) gelir,
        bunlar her şeyi kazanır.
      */}
      <style
        id="aq-tokens-core-light"
        dangerouslySetInnerHTML={{ __html: coreLightCss }}
      />
      <style
        id="aq-tokens-aq-light"
        dangerouslySetInnerHTML={{ __html: moduleLightCss.aq }}
      />
      <style
        id="aq-tokens-finos-light"
        dangerouslySetInnerHTML={{ __html: moduleLightCss.finos }}
      />
      <style
        id="aq-tokens-corpos-light"
        dangerouslySetInnerHTML={{ __html: moduleLightCss.corpos }}
      />
      {/*
        Faz 3.5 — Alias köprüsü. EN SON basılır → eski shadcn semantic değişkenleri
        yeni token'lardan beslenir. var() çözümlemesi USE-time olduğu için modül
        cascade'i otomatik devreye girer (data-module'a göre --cta-rgb değişir).
      */}
      <style
        id="aq-tokens-alias-bridge"
        dangerouslySetInnerHTML={{ __html: ALIAS_BRIDGE_CSS }}
      />
    </>
  );
}
