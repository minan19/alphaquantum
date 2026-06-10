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

/** Bir token listesini "var: value;" deklarasyon bloğuna çevirir (deterministic sıra). */
function tokensToDeclarations(tokens: readonly Token[]): string {
  return tokens
    .slice()
    .sort((a, b) =>
      a.order !== b.order ? a.order - b.order : a.key.localeCompare(b.key),
    )
    .map((t) => `  --${keyToCssVar(t.key)}: ${t.value};`)
    .join("\n");
}

/** Bir selector + token listesinden komple `<style>` içeriğini üretir. */
function buildStyleBlock(selector: string, tokens: readonly Token[]): string {
  if (tokens.length === 0) return "";
  return `${selector} {\n${tokensToDeclarations(tokens)}\n}`;
}

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

  // Faz 7 iskelesi — light değerler bu fazda DOLDURULMAZ, yalnız sıralama+seçici belgelenir.
  const themeScaffold = [
    "/* Theme axis scaffold — Faz 7'de light değerlerle doldurulacak */",
    "/* Cascade önceliği:",
    " *   html[data-theme='light']                          (0,1,1)",
    " *   html[data-module='finos'][data-theme='light']     (0,2,1) <- modül+tema kazanır",
    " */",
    "/* html[data-theme='light'] { ... } */",
    "/* html[data-module='aq'][data-theme='light']     { ... } */",
    "/* html[data-module='finos'][data-theme='light']  { ... } */",
    "/* html[data-module='corpos'][data-theme='light'] { ... } */",
  ].join("\n");

  return (
    <>
      {/*
        Her blok ayrı <style id> ile basılır → DevTools/specificity testinde
        bireysel olarak disable edilebilir (kanıt #2 specificity ispatı için).
        dangerouslySetInnerHTML: React'in inner CSS'i escape ETMEMESİ için zorunlu.
      */}
      <style
        id="aq-tokens-core"
        // eslint-disable-next-line react/no-danger
        dangerouslySetInnerHTML={{ __html: coreCss }}
      />
      <style
        id="aq-tokens-aq"
        // eslint-disable-next-line react/no-danger
        dangerouslySetInnerHTML={{ __html: aqCss }}
      />
      <style
        id="aq-tokens-finos"
        // eslint-disable-next-line react/no-danger
        dangerouslySetInnerHTML={{ __html: finosCss }}
      />
      <style
        id="aq-tokens-corpos"
        // eslint-disable-next-line react/no-danger
        dangerouslySetInnerHTML={{ __html: corposCss }}
      />
      <style
        id="aq-tokens-theme-scaffold"
        // eslint-disable-next-line react/no-danger
        dangerouslySetInnerHTML={{ __html: themeScaffold }}
      />
    </>
  );
}
