# Alpha Quantum — Design Token Foundation
### Faz 0 · Kilitli temel · OKLCH/WCAG · Çok-marka (çatı + FinOS + CorpOS)

> Bu doküman master prompt'taki **Faz 0 matrisinin birebir transkriptidir**.
> Yeniden türetilmedi; kilit kaynak burasıdır. Sonraki tüm fazlar bu çapalardan üretilir.

---

## 1. Scope modeli

Alpha Quantum'un üç kimliği vardır: **çatı (AlphaQ)**, **FinOS**, **CorpOS**. Her birinin
kendi accent'i; ama nötrler ve durum renkleri **ortaktır**. Bu yüzden sisteme bir **scope**
boyutu eklenir:

```
Scope = 'core' | 'aq' | 'finos' | 'corpos'
```

- `core` — ortak (bg/surface/border, text, 4 durum, focus-ring)
- `aq`, `finos`, `corpos` — yalnızca kimlik token'larını ezer

### Governance kuralı (sistemin belkemiği)

**core** sahibi: tüm bg/surface/border, tüm text, 4 durum (success/warning/error/info),
focus-ring. **Modüller bu token'ları EZEMEZ.**

**Modül** yalnız ezebileceği token'lar:
- `brand`, `brand-hover`
- `cta`, `cta-hover`, `cta-text`
- `on-brand`
- `accent`
- `link-back`

Panelde core satırları modül scope'unda **read-only**.

---

## 2. CORE — ortak çapalar (tüm modüllerde aynı)

### Nötr eksen
- **Hue:** `258°`
- **Chroma:** `0.012` (soğuk lacivert-gri "renkli gri")

### bg-primary

| Tema  | L    | h   | C     |
|-------|------|-----|-------|
| dark  | 0.17 | 258 | 0.012 |
| light | 0.99 | 258 | 0.006 |

### Elevation
Her katman **+0.03 ΔL**:
`bg-primary → bg-secondary → bg-tertiary → surface-01 → surface-02 → surface-03`

### Metin (kontrast-hedefli; L'ler ikili aramayla çözülür)

| Token           | Hedef Kontrast | Notlar                  |
|-----------------|----------------|-------------------------|
| text-primary    | ~15:1          | bg-primary'ye karşı     |
| text-secondary  | ~8:1           | bg-primary'ye karşı     |
| text-muted      | ~4.5:1         | bg-primary'ye karşı     |

Hue: `258`, chroma çok düşük (≤ 0.01).

### Durum renkleri (hue-sabitli, ortak)

| Token           | Hue | L    | C    | Notlar                       |
|-----------------|-----|------|------|------------------------------|
| status-success  | 150 | 0.72 | 0.13 | data-positive ile aynı       |
| status-warning  |  80 | 0.78 | 0.16 |                              |
| status-error    |  27 | 0.62 | 0.18 | data-negative ile aynı       |
| status-info     | 248 | 0.72 | 0.15 |                              |

Her biri için ayrıca `-surface` (düşük-L/C zemin tonu) üretilir.

### focus-ring
- **Hue:** info hue'su (`248`)
- **L:** accent'e yakın görünür ton (`0.65`)
- **C:** `0.18`

---

## 3. ÇATI (AlphaQ) — yalnız kimlik token'larını ezer

| Token        | L     | C     | h     | Hex       | Not                           |
|--------------|-------|-------|-------|-----------|-------------------------------|
| brand        | 0.316 | 0.115 | 261.5 | `#0C2D6B` | Safir                         |
| cta          | 0.546 | 0.215 | 263.0 | `#2563EB` | Azure — ÇATIYA KİLİTLİ        |
| cta-hover    |       |       |       |           | L−0.14                        |
| cta-text     |       |       |       | white     |                               |
| on-brand     | 0.95  | 0.012 | 258   | `#E8EFF9` | Yüzey rengi; üstüne text-inverse |

> "ÇATIYA KİLİTLİ" = hiçbir modül bu hue'da CTA kullanmaz.

---

## 4. FinOS — yalnız kimlik token'larını ezer

| Token        | L     | C     | h    | Hex       | Not                                |
|--------------|-------|-------|------|-----------|------------------------------------|
| brand        | 0.654 | 0.110 | 194  | `#0EA5A4` | Turkuaz                            |
| brand-hover  |       |       |      |           | L−0.14                             |
| cta          | 0.580 |       | 47.6 | `#CD4A00` | **Kapı #1** — koyulaştırılmış turuncu |
| cta-text     |       |       |      | white     | (≥ 4.5:1 doğrulanmış)              |
| accent       |       |       |      |           | core info veya turkuazın açık tonu |
| link-back    |       |       |      | `#94A3B8` | **Kapı #2** — silver, çatıya dönüş |

### Pozitif/negatif KPI
- Büyüme/pozitif = core `status-success`
- Düşüş/negatif = core `status-error` (kapı #3)

> CTA yalnız **tek aksiyon** içindir; warning'le karışmasın diye warning core'da kalır.

---

## 5. CorpOS — yalnız kimlik token'larını ezer

| Token        | L     | C     | h   | Hex       | Not                            |
|--------------|-------|-------|-----|-----------|--------------------------------|
| brand        | 0.843 | 0.151 | 88  | `#F4C542` | Altın                          |
| brand-hover  |       |       |     |           | L−0.10 (altın açık → daha az)  |
| cta          | 0.843 | 0.151 | 88  | `#F4C542` | Altın dolgu                    |
| cta-text     |       |       |     | dark      | text-inverse, font-weight 500  |
| accent       | 0.446 |       | 257 | `#475569` | Slate — **TEAL DEĞİL** (kapı #4) |
| accent-light | 0.711 |       | 257 | `#94A3B8` |                                |
| link-back    |       |       |     | `#94A3B8` | Kapı #2 — silver               |

### Not
CorpOS koyu zemin = core nötr dark bg'den gelir. Kendi özel zeminini TANIMLAMAZ
→ "iki neredeyse-aynı koyu zemin" sorunu böyle çözülür.

---

## 6. PAZARLIKSIZ KAPILAR (6 adet)

WCAG raporu bu kapıların tümünü **mekanik olarak geçmek zorundadır**:

| # | Kapı | Doğrulama |
|---|------|-----------|
| 1 | FinOS birincil CTA beyaz metinle ≥ **4.5:1** | `#CD4A00` ≈ 4.59:1. Eski `#F97316` (2.80) YASAK. |
| 2 | Çatıya geri-dönüş linki koyu zeminde ≥ **4.5:1** | silver `#94A3B8` ≈ 6.9–7.3:1. Eski navy@%31 (≈1.08) YASAK. |
| 3 | Negatif/kayıp rengi tanımlı | core `status-error` mevcut + KPI senaryosunda doğru renkte |
| 4 | FinOS ve CorpOS aynı teal'e demir atmaz | CorpOS accent = slate `#475569`, teal değil |
| 5 | Ortak semantik katman markadan bağımsız | success/warning/error/info çekirdekte tek tanım |
| 6 | focus-ring tanımlı | her interaktif öğede görünür, info hue ile renklendirilmiş |

---

## 7. Cascade & specificity (Faz 2'de uygulanır, burada referans)

```
:root{...}                                              spec (0,1,0)  ← core fallback
html[data-module='finos']{...}                          spec (0,1,1)  ← modül kimliği
html[data-theme='light']{...}                           spec (0,1,1)  ← tema
html[data-module='finos'][data-theme='light']{...}      spec (0,2,1)  ← modül+tema (kazanır)
```

**Kritik:** Modül seçicisini MUTLAKA `html[data-module=...]` yaz (0,1,1). `[data-module]`
tek başına `:root` ile aynı specificity'de (0,1,0) olur, kaynak sırasına kalır → kırılgan.

---

## 8. Sonraki fazlar

Bu doküman Faz 0'ın "kilit" çıktısıdır. Faz 1+ üretilen tüm token sözlükleri buradaki
çapaları **birebir** takip eder. Eğer ileride bir token değiştirilirse, foundation.md
ilk önce buraya not düşülür (versiyon + tarih + neden).

| Faz | Kapsam | Branch |
|-----|--------|--------|
| 0   | Foundation (bu) | `design-tokens/faz-0-foundation` |
| 1   | Token mimarisi + scope boyutu | `design-tokens/faz-1-token-architecture` |
| 2   | SSR enjeksiyon + cascade | `design-tokens/faz-2-ssr-cascade` |
| 3   | OKLCH + WCAG motoru (uygulama) | `design-tokens/faz-3-engine` |
| 4   | Panel çekirdeği + scope switcher | `design-tokens/faz-4-panel` |
| 5   | Panel özellikleri (import/export/preview) | `design-tokens/faz-5-panel-features` |
| 6   | Tipografi + dış font | `design-tokens/faz-6-typography` |
| 7   | Light/Dark × modül matrisi | `design-tokens/faz-7-light-dark` |
| 8   | Doğrulama & kabul | `design-tokens/faz-8-acceptance` |

---

## 9. Versiyon

- **v1.0.0** — 10 Haziran 2026 — ilk transkript (master prompt'tan birebir).
