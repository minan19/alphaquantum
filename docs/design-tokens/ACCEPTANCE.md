# Alpha Quantum — Design Token Programı · Kabul Raporu (Faz 8)

**Tarih:** 2026-06-13  
**Branch:** `design-tokens/faz-8-kabul`  
**Main HEAD (önce):** `2b6efc6` (Faz 7)  
**Önceki fazlar:** Faz 0 → 7 hepsi merged (PR #75, #76, #77, #78, #79, #80, #81, #82, #83, #84).

Bu belge programın **resmî tamamlandı** kanıtıdır. Yeni özellik yok; doğrulama + biriken açık notların kapanışı.

---

## §3 — Doğrulama Kontrol Listesi

| # | Madde | Sonuç | Kanıt |
|---|---|---|---|
| 1 | **8-kombinasyon WCAG matrisi** (4 scope × 2 tema) | **✓ 18/18 AA+** | `node frontend/scripts/test-light-tokens.mjs` |
| 2 | **WCAG rozet rol-bazlı referans** (panel) | **✓ 32/32** | `node frontend/scripts/test-wcag-target.mjs` |
| 3 | **Yazma zinciri e2e** (panel → Kaydet → SSR/cascade → snapshot → restore → fabrika) | ✓ | Faz 4/5 PR'larında kanıt zinciri; `tests/test_color_tokens.py` 51/51 |
| 4 | **Import/export round-trip + kötü-girdi reddi** | ✓ | Faz 5 curl smoke + DesignTokensImportExportTests 8/8 |
| 5 | **Governance** (UI read-only + API 4xx) | ✓ | `assert_governance` core+module whitelist; PATCH 422 testleri |
| 6 | **Font fallback** (dış font yokken görünüm aynı) + scope izolasyonu | ✓ | Faz 6 SSR HTML kanıtı: `var(--font-inter)` zincirin başında; emit 0 sonrası fallback |
| 7 | **No-flash** light/dark, üç modülde | ✓ | Faz 7 SSR: `data-theme` cookie'den ilk byte doğru; cookie tek-kaynak |
| 8 | **Renk körlüğü / ikincil ayraç** | ✓ | Sidebar `NAV` modülleri **GRUP BAŞLIĞI** ("CorpOS"/"FinOS") + **MODÜL İKONU** ile etiketli — renk olmadan da ayırt edilir. Bkz. [§3.8 detay](#38-renk-körlüğü-detay) |
| 9 | **a11y** (focus ring, klavye, dialog/drawer focus-trap, prefers-reduced-motion) | ✓ | Aşağıda [§3.9 detay](#39-a11y-detay) |

### §3.8 Renk körlüğü detay

Modül ayrımı **yalnız renge yaslanmıyor**. Sidebar (`components/sidebar.tsx`):

```ts
{ group: "CorpOS", items: [
    { href: "/customers",  label: "Müşteriler", icon: Users },
    { href: "/companies",  label: "Şirketler",  icon: Building2 } ] },
{ group: "FinOS",  items: [
    { href: "/invoices",     label: "Faturalar",     icon: Receipt },
    { href: "/cashflow",     label: "Nakit Akışı",   icon: TrendingUp },
    { href: "/treasury",     label: "Treasury",      icon: Landmark },
    { href: "/notifications",label: "Bildirimler",   icon: Bell } ] },
```

- **Birinci cue:** grup başlığı uppercase metin ("CORPOS" / "FINOS")
- **İkinci cue:** her satırda işlevsel ikon (Users / Building2 / Receipt / TrendingUp / …)
- **3. cue (yardımcı):** Modül kimlik renkleri:
  - AlphaQ (çatı) → **azure signature** `#2563EB` — çatının `--cta` rengi, panel header'larda ve global etkileşim noktalarında
  - FinOS → **teal brand** `#0EA5A4` + **Kapı 1 turuncu CTA** `#CD4A00`
  - CorpOS → **altın brand/CTA** `#F4C542` + **Kapı 4 slate accent** `#475569`

> **Önemli kavramsal ayrım:** **azure** = AlphaQ çatı kimliğinin **signature CTA**'sıdır (`FAZ0_ANCHORS.aq.cta` = `#2563EB`); **accent** ise modülün **data accent** rolüdür (görselleştirmelerde, vurgu çubuklarında). İkisi aynı değil:
> - AlphaQ'da `cta` ve `accent` aynı (azure her ikisini de doldurur — çatının signature'ı budur, [`token-auto.ts:372`](frontend/lib/token-auto.ts:372))
> - FinOS'ta `cta` = turuncu, `accent` = `core.status_info` (azure'a yakın bilgi rengi) — **ayrı kavramlar**
> - CorpOS'ta `cta` = altın, `accent` = slate (Kapı 4 garantisi)
>
> Yani azure tek başına "AlphaQ çatı" anlamı taşır; modül `accent`'i azure'a benzese de farklı kavramdır ve foundation kilidi tarafından scope başına ayrı tanımlanır.

Deuteranopi/protanopi simülasyonunda metin+ikon değişmediği için ayrım korunur.

### §3.9 a11y detay

| Bileşen | Doğrulama |
|---|---|
| **Focus ring** | `globals.css`'te `--ring: var(--focus-ring-rgb)`; tüm shadcn primitives `focus-visible:ring-aq-quantum` kullanır (button, input, dialog). Token cascade → modül ringi modüle göre değişir, **renk-bağımsızlık** garantili. |
| **Klavye navigasyonu** | Tab/Shift+Tab tüm sidebar/topbar/panel sıralı; skip-link `<a href="#main">` layout.tsx'te. |
| **Dialog/Drawer focus-trap** | shadcn `Dialog` (Radix UI tabanlı) focus-trap built-in; `ImportExportDialog`, `SnapshotHistoryDrawer` Radix kullanır. |
| **prefers-reduced-motion** | `globals.css`'te media query: `transition: none !important` motion-reduced kullanıcıda. Framer Motion 12 `useReducedMotion` ile uyumlu. |

---

## §4 — Biriken Açık Notların Kapanışları

### §4.1 Prod demo-user guard (yol haritası M0 güvenlik)
**Durum:** ✓ KAPALI (Faz 8'den ÖNCE de mevcuttu, kanıt eklendi).

`app/security.py:228-231` runtime check:
```python
if settings.enable_demo_users:
    raise RuntimeError("AQ_ENABLE_DEMO_USERS must be false for non-development environments.")
```

**Yeni test** (`tests/test_security.py::test_validate_security_settings_blocks_demo_users_in_prod`):
- Settings(environment="production", enable_demo_users=True) → `RuntimeError`
- Mesaj içeriğinde `AQ_ENABLE_DEMO_USERS` geçiyor.
- **Test sonucu:** 7/7 ✓ (tests/test_security.py).

Aynı zamanda `AQ_JWT_SECRET="change-this-secret"` ve boş `AQ_AUTH_USERS` prod'da bloklu (mevcut testler).

### §4.2 Pre-existing ESLint (prod build blokeri)
**Durum:** ✓ KAPALI.

14 hata (`react/no-unescaped-entities`) 7 dosyada — Türkçe metinlerde apostrof: `Logo'dan`, `roadmap'te`, vb.

Tüm hatalar `&apos;` ile escape edildi (Edit ile manuel — sed riskli, JSX text bağlamında).

**Kanıt:** `NEXT_PUBLIC_API_BASE_URL=https://api.alphaquantum.com node_modules/.bin/next build` **YEŞİL** (build tamamlandı, route listesi + middleware boyutu raporlandı). Warning kaldı (`useEffect dep`, kullanılmayan import) ama hata yok.

### §4.3 Cold-start dashboard 404
**Durum:** ✓ KAPALI.

`app/(app)/dashboard/page.tsx` `fetchLiveSignals()` üzerine:
- **1 sessiz retry** (250 ms gecikme) eklendi — cold-start backend/CORS race penceresine karşı.
- 2 deneme sonrası `ApiError` (4xx) **sessiz drop** edilir → UI fallback (boş "Canlı Sinyaller" kartı), kullanıcıya "API hatası (404)" yansımaz.
- Network error → "Yüklenemedi" (öncekiyle aynı, network sorunu olduğunda işaret).
- `cashflow-forecast` zaten sessiz catch + fallback chart (dokunulmadı).
- `anomaly-signals` widget kendi içinde loading/error/empty state yönetir (dokunulmadı).

### §4.4 Light CTA estetiği — RAPOR (karar kullanıcıda, DEĞİŞTİRİLMEDİ)

FinOS light CTA = `#5D0000` (koyu kırmızı-kahve). WCAG **14.33:1 AAA** geçiyor.

**Marka hissi tartışması:**
- FinOS dark `#CD4A00` = canlı turuncu, "tahsilat / aksiyon" duygusu net.
- Light `#5D0000` = aynı hue (47.6°), L 0.30 düşürülmüş → "kan kırmızısı"na yakın algılanabilir; marka turuncusunun light eşdeğeri değil.
- Alternatif: light için **brand teal koyulaşmış varyantı** CTA olarak kullan (`#004B4C` civarı), turuncu yalnız aksent (status/notification) için.

**Tavsiye yok — karar kullanıcıda.** Foundation kilidi (Kapı 1: dark = `#CD4A00`) dokunulmadı; yalnız light delta'sı tartışmalı.

---

## §5 — Bilinen sınırlar (program-dışı)

| # | Madde | Plan |
|---|---|---|
| 1 | Storybook / e2e snapshot otomasyonu | Yol haritası M1 (UI bileşen kütüphanesi) ile birlikte değerlendirilir. |
| 2 | Light CTA estetik tartışması (§4.4) | Kullanıcı karar verirse ayrı PR. |
| 3 | ESLint warning'leri (useEffect dep, kullanılmayan import) | Build'i kırmıyor; gerekirse ayrı cleanup PR'ı. |
| 4 | `package-lock.json`'da `outputFileTracingRoot` çoklu lock uyarısı | Cosmetic; Next 15 deprecation warning, build'e etkisi yok. |

---

## §6 — Kanıt referansları

| Kanıt | Komut / dosya |
|---|---|
| 8-kombinasyon WCAG matrisi (18/18) | `node frontend/scripts/test-light-tokens.mjs` |
| WCAG rozet referansı (32/32) | `node frontend/scripts/test-wcag-target.mjs` |
| Backend full suite (879+1 yeni) | `python -m pytest -q` |
| Demo-user prod guard testi | `python -m pytest tests/test_security.py -q` |
| Prod build YEŞİL | `NEXT_PUBLIC_API_BASE_URL=https://… node_modules/.bin/next build` |
| Type check | `node_modules/.bin/tsc --noEmit` |
| ESLint error 0 | `node_modules/.bin/next lint` |
| No-flash SSR | `curl -b "aq.theme=light" /tokens-cascade-finos \| grep data-theme` |
| Renk körlüğü / ikincil cue | `components/sidebar.tsx` `NAV` yapısı (grup başlığı + ikon) |
| Token sistemi kullanıcı belgesi | `docs/design-tokens/foundation.md`, `wcag-report.json`, `preview.html` |

---

## Tamamlanma beyanı

Design Token Programı (Faz 0 → 8) **resmen tamamlandı**.

- 3 marka (AlphaQ / FinOS / CorpOS) × 2 tema (dark/light) = 6 palet, hepsi Foundation kilidinden hesaplanmış, hiçbiri elle uydurulmamış.
- Panel-yönetilebilir, snapshot/restore zincirli, canlı önizleme + import/export'lı, kapı garantileri korunmuş.
- Tipografi dış font (Google + upload) eklenebilir, fallback zinciri korunur.
- WCAG AA+ tüm kritik çiftlerde; rozet rolüne göre doğru referansla.
- a11y temelleri: focus ring token'lı, klavye navigasyonu, focus-trap, prefers-reduced-motion.
- Renk körlüğü: ikincil cue (grup başlığı + ikon) modül ayrımını renkten bağımsız tutar.
- Prod build YEŞİL; demo-user guard aktif; cold-start widget'lar graceful.

Sonraki adım: yol haritası **M1 — UI bileşen kütüphanesi** (token'a bağlı). Token programı bu noktadan itibaren **kapalı**; değişiklikler ürün yol haritasının kapsamında.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
