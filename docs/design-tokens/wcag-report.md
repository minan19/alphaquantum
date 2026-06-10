# Alpha Quantum — Design Token WCAG Raporu
### Faz 0 · Otomatik üretildi (10 Haziran 2026)

> Bu rapor `docs/design-tokens/system.mjs` tarafından mekanik olarak
> üretilmiştir. Manuel değiştirme YASAK. Yeniden üretim: `node docs/design-tokens/system.mjs`.

## Özet: ✅ TÜM KAPILAR GEÇTİ

**Kapı sonucu:** 7/7 pass

## 6 Pazarlıksız Kapı

| # | Kapı | Hedef | Ölçülen | Sonuç |
|---|------|-------|---------|-------|
| 1 | FinOS CTA × white text ≥ 4.5:1 | 4.5 | 4.59 | ✅ |
| 2 | FinOS link-back × bg-primary(dark) ≥ 4.5:1 | 4.5 | 7.44 | ✅ |
| 2 | CorpOS link-back × bg-primary(dark) ≥ 4.5:1 | 4.5 | 7.44 | ✅ |
| 3 | Negatif renk (status-error) tanımlı + okunabilir | 3 | 4.83 | ✅ |
| 4 | FinOS (teal) ≠ CorpOS accent (slate, teal değil) | CorpOS accent hue ∉ [170, 210] | Δh = 63.3°, CorpOS hue = 257.3° | ✅ |
| 5 | Ortak semantik katman (success/warning/error/info) çekirdekte | 4/4 status token core scope'unda | success=true warning=true error=true info=true | ✅ |
| 6 | focus-ring tanımlı + bg-primary üzerinde görünür ≥ 3:1 | 3 | 5.97 | ✅ |

### Detaylar

- **Kapı 1 — FinOS CTA × white text ≥ 4.5:1**
  - cta=#CD4A00 text=#FFFFFF → 4.59:1
  - ✅ PASS
- **Kapı 2 — FinOS link-back × bg-primary(dark) ≥ 4.5:1**
  - link_back=#94A3B8 bg=#0C1015 → 7.44:1
  - ✅ PASS
- **Kapı 2 — CorpOS link-back × bg-primary(dark) ≥ 4.5:1**
  - link_back=#94A3B8 bg=#0C1015 → 7.44:1
  - ✅ PASS
- **Kapı 3 — Negatif renk (status-error) tanımlı + okunabilir**
  - status_error=#DE4F46 bg=#0C1015 → 4.83:1
  - ✅ PASS
- **Kapı 4 — FinOS (teal) ≠ CorpOS accent (slate, teal değil)**
  - finos.brand hue=194.0, corpos.accent hue=257.3
  - ✅ PASS
- **Kapı 5 — Ortak semantik katman (success/warning/error/info) çekirdekte**
  - Modüller status token'larını ezemez (governance).
  - ✅ PASS
- **Kapı 6 — focus-ring tanımlı + bg-primary üzerinde görünür ≥ 3:1**
  - focus_ring=#0094F6 bg=#0C1015 → 5.97:1
  - ✅ PASS

## CORE palet

### Dark teması
| Token | Hex |
|---|---|
| `bg_primary` | `#0C1015` |
| `bg_secondary` | `#13161C` |
| `bg_tertiary` | `#191D23` |
| `surface_01` | `#20242A` |
| `surface_02` | `#282C31` |
| `surface_03` | `#2F3339` |
| `border` | `#1F242D` |
| `text_primary` | `#E2E4E8` |
| `text_secondary` | `#A5A8AD` |
| `text_muted` | `#777B82` |
| `text_inverse` | `#0C1224` |
| `status_success` | `#62BB78` |
| `status_success_surface` | `#1E2A20` |
| `status_warning` | `#ECAA0B` |
| `status_warning_surface` | `#3D3424` |
| `status_error` | `#DE4F46` |
| `status_error_surface` | `#1D0C0A` |
| `status_info` | `#4CABFD` |
| `status_info_surface` | `#1C2833` |
| `focus_ring` | `#0094F6` |

### Metin kontrastları (bg_primary'ye karşı)

| Çift | Kontrast | Derece |
|---|---|---|
| text_primary × bg_primary | 14.99:1 | AAA |
| text_secondary × bg_primary | 8.00:1 | AAA |
| text_muted × bg_primary | 4.49:1 | AA-Lg |

## AQ kimlik tokenları

| Token | Değer |
|---|---|
| `scope` | `aq` |
| `brand` | `#0C2D6B` |
| `brand_hover` | `#000342` |
| `cta` | `#2563EB` |
| `cta_hover` | `#0033BA` |
| `cta_text` | `#FFFFFF` |
| `on_brand` | `#E8EFF9` |
| `accent` | `#2563EB` |

### Kritik kontrastlar

| Çift | Kontrast | Derece |
|---|---|---|
| aq.cta × aq.cta_text | 5.17:1 | AA |
| aq.brand × core.bg_primary | 1.46:1 | FAIL |

## FINOS kimlik tokenları

| Token | Değer |
|---|---|
| `scope` | `finos` |
| `brand` | `#0EA5A4` |
| `brand_hover` | `#007A7A` |
| `cta` | `#CD4A00` |
| `cta_hover` | `#922A00` |
| `cta_text` | `#FFFFFF` |
| `accent` | `#4CABFD` |
| `link_back` | `#94A3B8` |

### Kritik kontrastlar

| Çift | Kontrast | Derece |
|---|---|---|
| finos.cta × finos.cta_text | 4.59:1 | AA |
| finos.link_back × core.bg_primary | 7.44:1 | AAA |
| finos.brand × core.bg_primary | 6.30:1 | AA |

## CORPOS kimlik tokenları

| Token | Değer |
|---|---|
| `scope` | `corpos` |
| `brand` | `#F4C542` |
| `brand_hover` | `#D3A505` |
| `cta` | `#F4C542` |
| `cta_hover` | `#D3A505` |
| `cta_text` | `#0C1224` |
| `cta_text_weight` | `500` |
| `accent` | `#475569` |
| `accent_light` | `#94A3B8` |
| `link_back` | `#94A3B8` |

### Kritik kontrastlar

| Çift | Kontrast | Derece |
|---|---|---|
| corpos.cta × corpos.cta_text | 11.45:1 | AAA |
| corpos.link_back × core.bg_primary | 7.44:1 | AAA |
| corpos.brand × core.bg_primary | 11.73:1 | AAA |

## Modül ayırt edilebilirlik (renk körlüğü dayanıklılığı)

Kapı #4'ün ötesi: FinOS ve CorpOS kimlik token'larının hue uzayında
yeterli uzaklıkta olması — protan/deutan körlüğüne karşı dayanıklılık.

