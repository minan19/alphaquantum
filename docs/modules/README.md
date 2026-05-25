# Alpha Quantum — Modüller

Alpha Quantum, **iki ana modülden** oluşan multi-tenant yönetim platformudur.
Modüller aynı kod tabanında yaşar; lisans / feature flag ile bağımsız aktive
edilebilir.

## Modül 1: PatronOS — Çok Şirketli Yönetim

> "Bir kişinin birden fazla şirketi, şubesi, markası olabilir; hepsini tek
> platformdan yönetebilsin."

Hedef kitle: Holding sahipleri, çoklu işletme yöneten patronlar.

Kapsam:
- Şirket / holding / multi-tenant izolasyon
- CRM (müşteri, teklif)
- Tasks (görev takibi + atama)
- Inventory (envanter / stok)
- Procurement (tedarik)
- Feasibility (fizibilite)
- International Operations (uluslararası operasyon)
- Strategic Ecosystem
- Dashboard / Live Signals / Comparison
- User / Auth / RBAC

Bkz: [docs/modules/patronos/](./patronos/)

---

## Modül 2: FinOS — Finansal Operasyon

> "KOBİ'lerin dijital sinir sistemi: her tahsilatı zamanında al, nakit
> hareketini sezinle, finansal kararı veriyle ver."

Hedef kitle: KOBİ'ler, ihracatçılar, gecikmiş alacaklarla mücadele eden firmalar.

Kapsam:
- Finance ledger (gelir/gider defteri)
- Recurring & Budget
- Collections — faturalar, ödeme kaydı, tahsilat
- Receivables aging (30/60/90/90+ dilim)
- Cashflow projeksiyon (30/60/90 gün)
- Customer payment risk score (0-100)
- Notifications — vade uyarı motoru (T-3, T-1, T+1, T+7, T+14)
- Financial Instruments — senet / çek / bono
- Delivery Channels — e-posta / SMS / WhatsApp + KVKK consent
- FX / Multi-currency exposure
- Market Data (FX kurları)
- Reporting — PDF / Excel imzalı export

Bkz: [docs/modules/finos/](./finos/)

---

## Modül-arası ilişki

İki modül aynı çekirdek üzerinde çalışır:

- Aynı **multi-tenant izolasyon katmanı** (company_name + RBAC)
- Aynı **migration sistemi** (`migrations/`)
- Aynı **engine deseni** (`app/engines/*`)
- Aynı **API gateway** (`app/api.py`)
- Aynı **frontend skeleton** (`frontend/`)

Veri akışı örnekleri:

```
PatronOS  →  FinOS:
    CRM müşterisi  →  FinOS müşteri risk skoru hesaplanırken referans
    Holding şirketleri → FinOS company comparison'da listelenir

FinOS  →  PatronOS:
    FinOS notification (overdue fatura)  →  PatronOS dashboard sinyali
    FinOS receivables  →  PatronOS company karşılaştırma metriği
```

## Mevcut sprint geçmişi (modül etiketli)

PatronOS ailesi:
- S-211/212/213/214 — Governance, KPI, SLA
- S-221/222/223/224 — Backup, kapasite, API operations
- S-231/232/233/234 — UX, ürün paketleme
- S-311/312/313 — Dashboard signals, scheduled reports, comparison
- S-321/322 — CRM, Tasks (S-323 Collections aslında FinOS'a ait)
- S-361 — Docker / CI
- S-362 — Frontend skeleton

FinOS ailesi:
- S-323 — Collections (Faturalar, alacaklar)
- P1-1 — Recurring + Budget
- P1-2 — PDF/Excel reporting
- S-331 — Alacak yaşlandırma analizi
- S-332 — Nakit akışı projeksiyonu
- S-333 — Müşteri ödeme risk skoru
- S-334 — Vade uyarı / bildirim motoru
- S-335 — Dashboard'a finans sinyalleri (cross-cutting)
- S-341 — Çok para birimi FX nakit akışı
- S-342 — Senet / Çek / Bono takibi
- S-343 — Tahsilat kanalı + KVKK consent
- QW-2 — Tek fatura PDF export
