# Alpha Quantum – Ürün & Çözüm Paket Matrisi

**Sprint:** 2.3 – Task T-233-1
**Tarih:** 24 Mart 2026
**Owner:** Claude (23martclaude branch)

---

## 1. Paket Tanımları

Alpha Quantum üç ana ürün paketiyle sunulur. Her paket bağımsız devreye alınabilir; bağımlılık kuralları aşağıda tanımlanmıştır.

---

## 2. Paket A – ERP Çekirdeği

**Hedef Segment:** Operasyonel yönetim ihtiyacı olan şirketler
**Değer Önermesi:** Tek panelden çok şirket yönetimi, stok kontrolü, satın alma süreç otomasyonu

| Modül | Engine | Endpoint Grubu | Zorunlu Migrasyon |
|---|---|---|---|
| Çok Şirket Yönetimi | `company_engine` | `/api/v1/companies` | baseline |
| Stok / Envanter | `inventory_engine` | `/api/v1/inventory-engine/*` | baseline |
| Satınalma & Tedarik | `procurement_engine` | `/api/v1/procurement/*` | `004_procurement` |
| Tender Yönetimi | `tender_engine` | `/api/v1/tender/*` | baseline |
| Holding & İştirak | `holding_engine` | `/api/v1/holdings/*` | `008_holdings_onboarding` |

**Bağımlılıklar:**
- Auth + RBAC (baseline zorunlu)
- Migration `001` (permissions), `004` (procurement), `008` (holdings)

**Dışlanabilir Modüller (opsiyonel):** Tender, Holding

---

## 3. Paket B – Fintech & Analitik

**Hedef Segment:** Finansal yönetim, piyasa takibi ve risk analizi yapan kuruluşlar
**Değer Önermesi:** Ledger, cashflow, piyasa sinyalleri, backtest ve küresel makro entegrasyonu

| Modül | Engine | Endpoint Grubu | Zorunlu Migrasyon |
|---|---|---|---|
| Finance Ledger/Cashflow | `finance_engine` | `/api/v1/finance-engine/*` | `002_finance_ledger` |
| Piyasa Verisi & Sinyaller | `market_data_engine` | `/api/v1/market/*` | `003_market_data_cache` |
| Piyasa İstihbaratı | `market_intelligence_engine` | `/api/v1/market/intelligence` | `003_market_data_cache` |
| Backtest | `market_data_engine` | `/api/v1/market/backtest` | `003_market_data_cache` |
| Global Merkez Bankası / World Bank | `global_analysis_engine` | `/api/v1/global/*` | baseline |
| Kamu Kurumu Web İstihbaratı | `institution_web_engine` | `/api/v1/public-institutions/*` | baseline |

**Bağımlılıklar:**
- Auth + RBAC (baseline zorunlu)
- Migration `002`, `003`
- Paket A bağımlılığı: **YOK** (bağımsız devreye alınabilir)

**Dışlanabilir Modüller:** Backtest, Piyasa İstihbaratı, Kamu Kurumu

---

## 4. Paket C – Global Intel & Ekosistem Orkestrasyonu

**Hedef Segment:** Uluslararası büyüme hedefleyen holding / çok uluslu şirketler
**Değer Önermesi:** Fizibilite + uluslararası proje + satın alma tek akışta; global intel ile destekli

| Modül | Engine | Endpoint Grubu | Zorunlu Migrasyon |
|---|---|---|---|
| Fizibilite Analizi | `feasibility_engine` | `/api/v1/feasibility/*` | `005_feasibility_reports` |
| Uluslararası Operasyon | `international_operations_engine` | `/api/v1/international/*` | `006_international_projects` |
| Stratejik Ekosistem | `strategic_ecosystem_engine` | `/api/v1/ecosystem/*` | `005`, `006` |
| Entegrasyon Konektörü | `connector_engine` | `/api/v1/connectors/*` | `009`, `010`, `011` |

**Bağımlılıklar:**
- Auth + RBAC (baseline zorunlu)
- **Paket A gerekli** (Satınalma modülü ecosystem activate içinde çalışır)
- Migration `005`, `006`, `007` (user company scopes), `009`–`011` (connectors)

**Dışlanabilir Modüller:** Connector (bağımsız devre dışı bırakılabilir)

---

## 5. Paket Bağımlılık Özeti

```
Paket A (ERP Çekirdeği)
    └── Bağımsız devreye alınabilir

Paket B (Fintech & Analitik)
    └── Bağımsız devreye alınabilir

Paket C (Global Intel & Ekosistem)
    └── Paket A'ya bağımlı (Procurement zorunlu)
    └── Paket B opsiyonel (Global Intel entegrasyonu için önerilir)
```

---

## 6. Migrasyon Bağımlılık Sırası

| Sıra | Migrasyon | Paket |
|---|---|---|
| 001 | permissions_matrix | A, B, C (ortak baseline) |
| 002 | finance_ledger | B |
| 003 | market_data_cache | B |
| 004 | procurement | A |
| 005 | feasibility_reports | C |
| 006 | international_projects | C |
| 007 | user_company_scopes | C |
| 008 | holdings_onboarding | A |
| 009 | connectors_and_sync_queue | C |
| 010 | connector_sync_retry_dlq | C |
| 011 | connector_worker_leases | C |

---

## 7. Rollout Senaryoları

| Senaryo | Paket Seti | Notlar |
|---|---|---|
| Küçük İşletme ERP | A | Holding ve Tender opsiyonel |
| Finans Odaklı Kuruluş | A + B | Connector olmadan çalışır |
| Uluslararası Holding | A + B + C | Tam paket; tüm migration'lar gerekli |
| SaaS / White-label | A + B | C sonradan aktive edilebilir |

---

## 8. Referans

- Rollout checklist: `docs/PRODUCT_ROLLOUT_CHECKLIST.md`
- Sprint: `SPRINT_BACKLOG.md` → S-233, S-234
- Migration sırası: `migrations/` dizini
