# ALPHA QUANTUM – Kapsamlı Teknik Denetim Raporu

**Tarih:** 23 Mayıs 2026  
**Denetçi:** Claude Sonnet 4.6 (kıdemli teknik denetçi + ürün stratejisti rolü)  
**Kapsam:** Tüm kaynak kodu, veri tabanı, dokümantasyon, test altyapısı, CI/CD  
**Dal:** `23martclaude`  
**Amaç:** Mevcut durum analizi + KOBİ Nakit Akışı İstihbarat Platformu ile entegrasyon hazırlığı

---

## 1. Yönetici Özeti

Alpha Quantum, tek bir holding sahibinin birden fazla şirketini merkezi bir platform üzerinden yönetmesine olanak tanıyan FastAPI tabanlı bir kurumsal yönetim sistemidir. Mart 2026'da başlayan aktif geliştirme, Mayıs 2026'ya kadar hızlanmış; test sayısı 29'dan 211'e çıkmış, 18 migration uygulanmış ve PatronOS (CRM/Tasks/Collections) modülleri tamamlanmıştır.

**Güçlü Taraflar:** Proje mimarisi —engine/repository/api katmanlaması— son derece tutarlı ve genişletilebilir. Güvenlik temeli sağlam: PBKDF2-SHA256 parola hash'leme (260.000 iterasyon), özel JWT uygulaması, RBAC + permission matrisi, company-scope izolasyonu, audit log, Redis tabanlı rate limiting ve kapsamlı CI güvenlik kapısı gerçek bir production baseline'ı temsil etmektedir.

**Kritik Zayıflıklar:** Veri tabanı olarak SQLite kullanılması, çok-kiracılı (multi-tenant) bir SaaS ürünü için en büyük üretim engelidir. Containerization (Docker/docker-compose) yoktur. Frontend tamamen sunucu taraflı HTML'dir — ayrı bir React/Vue SPA mevcut değildir. OAuth2/SSO akışı implemente edilmemiştir; bu durum iki ürün hattını (Alpha Quantum + Nakit Akışı Platformu) ortak kullanıcı sistemine bağlamayı zorlaştırmaktadır.

**Multi-tenancy modeli** beklenmedik biçimde `company_name TEXT` discriminator tabanlıdır. Her tablo bir `company_name` sütunu taşır, ancak `companies` tablosuna foreign key bağlantısı yoktur. Bu yaklaşım esnek fakat referential integrity açısından kırılgandır. Şirket ismi değiştiğinde tüm ilişkili verileri cascade güncelleyecek bir mekanizma bulunmamaktadır.

**Mevcut olgunluk seviyesi:** Modül bazında **Alpha/Beta** aralığında. Temel finans, procurement, feasibility, uluslararası operasyon modülleri Beta düzeyinde test edilmiştir. PatronOS (CRM/Tasks/Collections) Alpha düzeyindedir. Gerçek üretim ortamı için PostgreSQL geçişi, containerization ve OAuth2 implementasyonu zorunludur.

**Entegrasyon hazırlığı (KOBİ Nakit Akışı Platformu ile):** Mimari temiz ve genişlemeye açık. 7/10 zorluk skoru — büyük engel OAuth2/SSO eksikliği ve SQLite. Ortak bir kullanıcı servisi (Identity Provider) kurulduğu anda entegrasyon akışı mantıklı hale gelir.

---

## 2. Doküman Envanteri ve Bulgular

| Dosya | İçerik | Doğrulama Durumu |
|---|---|---|
| `README.md` | Endpoint listesi, env var katalogu, güvenlik gate komutları | **Güncel ve doğru.** Endpoint sayısı kodla eşleşiyor. |
| `MASTER_BLUEPRINT.md` | Proje vizyonu, 7-katman mimarisi, modül listesi | **Kısmen eski.** `notification_engine`, `task_engine` koda eklenmiş ama Blueprint çok yüzeysel kalıyor. |
| `ARCHITECTURE_LAYER_MODEL.md` | 7 katman tanımı | **Tutarlı.** Gerçek mimariyi iyi özetliyor. |
| `LAYER_EXECUTION_PLAN.md` | KPI/SLA/owner bazlı yürütme planı | Okundu, içerik dokümantasyon düzeyinde. |
| `TECHNICAL_AUDIT_2026-03-20.md` | Önceki denetim (Mart 2026) | **P0 borçlar kapatılmış** (company-scope, migration güvenliği, audit event). |
| `PENTEST_REPORT_2026-03-20.md` | Güvenlik testi sonuçları (Mart 2026) | AQ-SEC-001 kapatılmış, AQ-SEC-002/003 kontrollü açık. Bulgular mevcut kodla uyuşuyor. |
| `SPRINT_BACKLOG.md` | Sprint geçmişi (Faz 1 → PatronOS) | **En güncel kaynak.** Test sayısı ve sprint ilerlemesi doğrulandı. |
| `KPI_SLA_DICTIONARY.md` | KPI/SLA hedef seti | Tanımsal; gerçek ölçüm dashboardı yok. |
| `API_ERROR_BUDGET_POLICY.md` | Hata bütçesi politikası | Script mevcut (`scripts/api_error_budget_report.py`). |
| `BACKUP_RESTORE_RUNBOOK.md` | Backup/restore adımları | Script mevcut, otomasyonu yok. |
| `RELEASE_OPERATION_CHECKLIST.md` | Release gate | CI'a bağlı; manuel adımlar hâlâ checklist formatında. |
| `TEAM_OWNERS.md` | Owner atamaları | **Tüm roller Mustafa Inan'da.** Backup owner atanmamış. Tek-noktasal-arıza riski. |
| `GOVERNANCE_REVIEW_NOTE_2026-03-21.md` | Yönetim kararları | Okundu. |
| `CLAUDE_MANAGEMENT.md` | Claude yönetim notu | Okundu. |
| `docs/TECHNICAL_STATUS_AND_ROADMAP.md` | Mart 2026 itibarıyla teknik durum | Büyük ölçüde doğru, bazı P0 maddeler o tarihten itibaren kapatılmış. |

---

## 3. Teknoloji Yığını

| Bileşen | Teknoloji | Versiyon | Not |
|---|---|---|---|
| Web framework | FastAPI | 0.135.1 | Python `asynccontextmanager` lifespan kullanıyor |
| ASGI server | Uvicorn | 0.42.0 | Tek process, reload modu |
| Veri doğrulama | Pydantic | 2.12.5 | V2, `ConfigDict` ile |
| HTTP istemci | httpx | 0.28.1 | Dış API çağrıları için |
| Cache / Rate limit | Redis | 5.2.1 (client) | Opsiyonel, auth limiter backend |
| Excel export | openpyxl | 3.1.5 | Raporlama motoru |
| PDF export | ReportLab | 4.4.1 | Raporlama motoru |
| Veri tabanı | SQLite | — | WAL modu, FK aktif, 29 tablo |
| ORM / Query builder | **Yok** | — | Ham `sqlite3` + parametreli sorgular |
| Migration | Özel MigrationManager | — | `app/migration_manager.py`, 18 migration |
| JWT | **Özel implementasyon** | — | `app/security.py`, HMAC-SHA256 |
| Parola hash | PBKDF2-SHA256 | 260.000 iter | `app/security.py` |
| Static analiz | Bandit | 1.9.4 | CI'da aktif |
| Dependency audit | pip-audit | 2.10.0 | CI'da aktif |
| CI/CD | GitHub Actions | — | 3 workflow |
| Python versiyonu | 3.11 | — | CI'da `setup-python@v5` |
| Containerization | **Yok** | — | Docker/docker-compose dosyası yok |

---

## 4. Mimari Diyagram (ASCII)

```
┌──────────────────────────────────────────────────────────────────┐
│                  KULLANICI / İSTEMCİ KATMANI                     │
│   Web browser → /dashboard (server-side HTML)                     │
│   API clients → Bearer token ile /api/v1/*                        │
└──────────────────────────┬───────────────────────────────────────┘
                           │ HTTPS (zorunlu değil, config'e bağlı)
┌──────────────────────────▼───────────────────────────────────────┐
│                PLATFORM / API KATMANI (FastAPI)                   │
│  main.py → app/__init__.py → create_app()                         │
│  app/api.py (tek router, 116 endpoint)                            │
│  Middleware: CORS, request-logging, security headers              │
│  Auth: JWT Bearer → get_current_user() → require_permissions()    │
│  Rate limit: auth_limiter (memory | Redis)                        │
└────────┬──────────────────────────────────────────┬──────────────┘
         │                                          │
┌────────▼──────────────┐              ┌────────────▼───────────────┐
│   ENGINE KATMANI      │              │   AUTH / IDENTITY KATMANI  │
│  app/engines/         │              │  auth_service.py            │
│  ├─ company_engine    │              │  identity_repository.py     │
│  ├─ inventory_engine  │              │  security.py (JWT/hash)     │
│  ├─ finance_engine    │              │  auth_limiter.py            │
│  ├─ crm_engine        │              └────────────────────────────┘
│  ├─ task_engine       │
│  ├─ collections_engine│
│  ├─ procurement_engine│
│  ├─ feasibility_engine│
│  ├─ holding_engine    │
│  ├─ connector_engine  │
│  ├─ market_data_engine│
│  ├─ reporting_engine  │
│  ├─ schedule_engine   │
│  ├─ tender_engine     │
│  ├─ strategic_ecosystem_engine
│  └─ ... (22 engine)   │
└────────┬──────────────┘
         │
┌────────▼──────────────────────────────────────────────────────────┐
│              REPOSITORY / VERİ KATMANI                             │
│  app/*_repository.py (15 repository dosyası)                       │
│  SQLite (alpha_quantum.db) — WAL modu, FK aktif                    │
│  29 tablo, 28 index, 18 migration                                   │
│  Multi-tenancy: company_name TEXT discriminator (shared schema)     │
└───────────────────────────────────────────────────────────────────┘
         │                    │
┌────────▼─────────┐  ┌──────▼──────────────┐
│  Redis (opsiyonel)│  │  Dış API'ler        │
│  Auth rate limit  │  │  httpx (market data,│
│  Leader lock      │  │  macro data, web    │
└──────────────────┘  │  intelligence)      │
                       └─────────────────────┘
```

---

## 5. Modül Envanteri

| Modül | Dosya Yolu | Durum | Tamamlanma % | Not |
|---|---|---|---|---|
| Auth / Identity | `app/auth_service.py`, `app/security.py`, `app/identity_repository.py` | **Beta** | 90% | SSO/OAuth2 yok. Refresh token rotation var. |
| RBAC + Permission Matrix | `app/identity_repository.py`, `migrations/001` | **Beta** | 90% | 27 güvenlik testi geçmiş. |
| Company Scope İzolasyonu | `migrations/007`, `app/models.py` | **Beta** | 85% | company_name discriminator — FK yok. |
| Audit Log | `app/audit_repository.py`, `migrations/013` | **Beta** | 80% | HTTP tabanlı; iş olayı audit'i kısmi. |
| Şirket Yönetimi | `app/engines/company_engine.py`, `app/repository.py` | **Beta** | 75% | Temel CRUD. Gerçek şirket datasının kalıcılığı CSV'ye bağlı. |
| Envanter Yönetimi | `app/engines/inventory_engine.py` | **Alpha** | 60% | Temel stok; supplier/reorder yok. |
| Finans Defteri (Ledger) | `app/engines/finance_engine.py`, `app/finance_repository.py`, `migrations/002` | **Beta** | 80% | Ledger, cashflow, forecast, recurring, budget var. Senaryo forecast kısmi. |
| Holding Yönetimi | `app/engines/holding_engine.py`, `app/holding_repository.py`, `migrations/008` | **Beta** | 75% | Onboarding readiness scoring var. |
| Procurement | `app/engines/procurement_engine.py`, `migrations/004` | **Beta** | 80% | RFQ/quote/PO tam. Onay workflow yok (4-eyes). |
| Feasibility Engine | `app/engines/feasibility_engine.py`, `migrations/005, 012` | **Beta** | 80% | GO/NO-GO analizi, senaryo. |
| Uluslararası Operasyon | `app/engines/international_operations_engine.py`, `migrations/006` | **Beta** | 75% | Ülke profili, yol haritası. |
| Stratejik Ekosistem | `app/engines/strategic_ecosystem_engine.py` | **Beta** | 75% | Orchestration (feasibility+intl+procurement). |
| Pazar Verisi / Teknik Analiz | `app/engines/market_data_engine.py`, `migrations/003` | **Beta** | 75% | OHLCV cache, RSI, MACD, backtest. Gerçek veri feed'i offline modda. |
| Market Intelligence | `app/engines/market_intelligence_engine.py`, `exchange_source_catalog.py` | **Alpha** | 60% | Web scraping bazlı; lisanslı veri feed yok. |
| Global Analiz | `app/engines/global_analysis_engine.py` | **Alpha** | 60% | Merkez bankası, World Bank. FRED API offline modda çalışıyor. |
| Kurum Web İstihbaratı | `app/engines/institution_web_engine.py` | **Alpha** | 55% | URL tabanlı; SSRF guardrail var. |
| İhale (Tender) | `app/engines/tender_engine.py` | **Beta** | 75% | Dossier üretimi, checklist, uygunluk matrisi. |
| Connector / Entegrasyon | `app/engines/connector_engine.py`, `migrations/009-011` | **Alpha** | 60% | Queue/DLQ/leader-lock hazır. Gerçek adaptör yok (mock). |
| Raporlama (PDF/Excel) | `app/engines/reporting_engine.py`, `migrations/015` | **Alpha** | 65% | Export hazır. Scheduled report sistemi var. |
| Dashboard / Canlı Sinyaller | `app/engines/dashboard_engine.py`, `comparison_engine.py` | **Alpha** | 60% | Server-side HTML. SSE/WebSocket yok. |
| CRM (PatronOS S-321) | `app/engines/crm_engine.py`, `app/crm_repository.py`, `migrations/016` | **Alpha** | 65% | Müşteri + teklif yönetimi. Temel CRUD. |
| Görev Yönetimi (PatronOS S-322) | `app/engines/task_engine.py`, `app/task_repository.py`, `migrations/017` | **Alpha** | 60% | Task atama, durum takibi. |
| Tahsilat (PatronOS S-323) | `app/engines/collections_engine.py`, `app/invoice_repository.py`, `migrations/018` | **Alpha** | 65% | Fatura oluşturma, ödeme kayıt, gecikme tespiti. |
| Bildirim Motoru | **Yok** | **Planned** | 0% | Email/WhatsApp — Blueprint'te var, kodda yok. |

---

## 6. Veri Modeli ve Multi-Tenancy

### 6.1 Tablo Sayısı ve Yapısı

Aktif veritabanında **29 tablo**, **28 index** bulunmaktadır. `schema_migrations` tablosu 18 uygulanan migration'ı takip etmektedir.

Temel tablolar:
- **Identity:** `users`, `roles`, `permissions`, `role_permissions`, `refresh_tokens`, `revoked_access_tokens`
- **Scope:** `user_company_scopes`
- **Finans:** `finance_ledger_entries`, `finance_recurring_entries`, `finance_budgets`
- **Şirket/Holding:** `companies`, `inventory`, `holdings`, `holding_companies`
- **Procurement:** `procurement_requests`, `procurement_request_items`, `procurement_vendor_quotes`, `procurement_quote_items`, `procurement_purchase_orders`, `procurement_purchase_order_lines`
- **Feasibility/International:** `feasibility_reports`, `international_projects`
- **Connector:** `integration_connectors`, `integration_sync_jobs`, `integration_worker_leases`
- **Pazar:** `market_ohlcv_cache`
- **PatronOS:** `customers`, `proposals`, `tasks` (eksik — tablo henüz oluşturulmamış), `invoices`
- **Diğer:** `audit_logs`, `schema_migrations`

### 6.2 Multi-Tenancy Modeli: "Shared Schema + company_name Discriminator"

**Gerçek mimari:** Tüm iş verileri aynı SQLite dosyasındadır. Her tabloda `company_name TEXT NOT NULL` sütunu bulunur ve sorgu düzeyinde filtreleme ile tenant izolasyonu sağlanır.

```sql
-- Örnek: finance_ledger_entries
company_name TEXT NOT NULL  -- Tenant discriminator
```

**Avantajlar:**
- Yeni şirket ekleme anında gerçekleşir — şema değişikliği gerektirmez.
- Query pattern tutarlı ve anlaşılır.

**Kritik Zayıflıklar:**
1. `company_name` TEXT tipinde; `companies` tablosuna foreign key bağlantısı **yoktur**. Şirket ismi değiştiğinde orphan kayıtlar oluşur.
2. Schema-level tenant isolation yoktur — bir programcı hatası tüm şirketlerin verisini sızdırabilir.
3. SQLite'ın yük altında WAL kilitleme davranışı çok-kiracılı yoğun yazmalarda darboğaz yaratır.

### 6.3 Kullanıcı-Şirket-Rol İlişkisi

```
users (id, username, password_hash, role_id, is_active)
  └─► roles (id, name)
        └─► role_permissions (role_id, permission_id)
              └─► permissions (id, name)

user_company_scopes (user_id, company_scope)
  - company_scope = "*" → holding-wide (tüm şirketlere erişim)
  - company_scope = "ŞirketAdı" → o şirkete kısıtlı
```

`scope_mode` alanı (single/multi/holding) JWT payload'a işlenmez; her istekte DB sorgusuyla alınır. Bu yaklaşım güvenli ama yavaştır.

---

## 7. Kimlik ve Yetkilendirme

### 7.1 Parola Güvenliği
- **Algoritma:** PBKDF2-SHA256, **260.000 iterasyon** (`app/security.py:20-35`)
- **Salt:** `os.urandom(16)` — kriptografik olarak güvenli
- **Saklama formatı:** `pbkdf2_sha256$260000$<b64salt>$<b64digest>`
- **Değerlendirme:** Güçlü. OWASP önerisi (600.000 iterasyon) altında ama kabul edilebilir.

### 7.2 JWT Uygulaması
- **Özel implementasyon:** `app/security.py` (PyJWT kütüphanesi kullanılmıyor)
- **Algoritma:** HS256 (HMAC-SHA256), `hmac.compare_digest` ile timing-safe karşılaştırma
- **Payload:** `sub` (username), `uid` (user_id), `role`, `jti` (UUID), `iat`, `exp`
- **Access token:** 120 dakika (default), çevresel değişkenle ayarlanabilir
- **Refresh token:** Veritabanında SHA-256 hash olarak saklanır, rotasyon desteklenir
- **Revoke listesi:** `revoked_access_tokens` tablosu (`jti` ile)
- **Risk:** `AQ_JWT_SECRET` default değeri `"change-this-secret"` — development dışında runtime hata fırlatıyor (`validate_security_settings`)

### 7.3 RBAC + Permission Matrix
- 3 sistem rolü: `admin`, `manager`, `viewer`
- 20+ tanımlı permission (read_companies, write_finance, manage_holdings vb.)
- Permission kontrolü: `require_permissions()` decorator pattern — `app/security.py:183-196`
- Company scope enforcement: `_filter_companies_by_user_scope()` ile API katmanında

### 7.4 Eksikler
- **OAuth2/SSO yok** — Dış kimlik sağlayıcıyla entegrasyon mevcut değil
- **KVKK/GDPR uyumu:** Açık rıza, data subject rights, retention policy API'leri kodda bulunmuyor
- **Device/session metadata:** Token bazlı, cihaz bilgisi takip edilmiyor
- **MFA/2FA:** Implementasyon yok

---

## 8. API Yapısı

### 8.1 Genel Bilgiler
- **Framework:** FastAPI 0.135.1
- **Router:** Tek `APIRouter`, `app/api.py` içinde (3.710 satır)
- **Endpoint sayısı:** 116 route tanımı (`@router.get`, `@router.post`, `@router.patch`, `@router.delete`, `@router.put`)
- **Versiyonlama:** `/api/v1/*` prefix — legacy uçlar `/`, `/dashboard`, `/analyze_all`, `/auto_update` olarak ayrı tutuluyor
- **OpenAPI/Swagger:** FastAPI'nin otomatik üretimi aktif (başlık: "Alpha Quantum", version: app_version)

### 8.2 Pagination ve Filtreleme
- **Pagination tipi:** Limit tabanlı (`limit: int = Query(default=200, ge=1, le=1000)`)
- **Cursor/offset:** **Yok** — büyük veri kümeleri için ölçekleme riski
- **Filtreleme:** `status`, `company`, `overdue_only`, `active_only` gibi query param filtreleri tutarlı biçimde uygulanmış
- **Sıralama:** Backend bazında uygulanan fixed sort (DESC updated_at vb.), client kontrolü yok

### 8.3 Standartlar
- `X-Request-ID` header her yanıtta var
- Security header'lar middleware'de ekleniyor: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, `Cache-Control: no-store`
- Rate limiting: Auth endpoint'leri için 5 deneme/60 saniye (default)
- Hata yanıtları: FastAPI HTTPException formatı — tutarlı

### 8.4 Async/Sync Durum
- **Route handler'lar:** `def` (sync) — async değil
- **Lifespan:** `asynccontextmanager` ile async
- **Middleware:** `async def`
- **Tahmin:** Uzun süren hesaplama motorları (feasibility, market analysis vb.) thread-blocking yapabilir. Uvicorn threadpool'u bu riski kısmen azaltır.

---

## 9. Mevcut Entegrasyonlar

| Entegrasyon | Durum | Dosya |
|---|---|---|
| Redis (rate limit / leader lock) | Opsiyonel, aktif | `app/auth_limiter.py`, `app/connector_sync_worker.py` |
| httpx (dış API çağrıları) | Aktif | `app/macro_data_provider.py`, `app/market_data_provider.py` |
| FRED (World Bank, merkez bankaları) | Offline moda sahip | `app/macro_data_provider.py` |
| Piyasa verisi (OHLCV) | Offline moda sahip | `app/market_data_provider.py` |
| Web scraping (kurum siteleri) | SSRF guard var | `app/engines/institution_web_engine.py` |
| Connector çerçevesi (ERP/CRM/accounting) | **Şablon seviyesinde** | `app/connector_adapters.py` — gerçek adaptör yok |
| Email / WhatsApp bildirimi | **Yok** | — |
| Cloud storage | **Yok** | — |
| SSO / LDAP | **Yok** | — |

---

## 10. Güvenlik

### 10.1 Pentest Raporu Özeti (Mart 2026)
- **Kritik/Yüksek bulgu:** 0
- **Orta (kapatıldı):** AQ-SEC-001 — Finance ledger dinamik SQL riski → parametrik sorguya geçirildi
- **Düşük (açık):**
  - AQ-SEC-002: In-memory rate limiter çoklu instance'da yetersiz (Redis backend ile çözüm var)
  - AQ-SEC-003: Migration rollback operasyonu güçlü (backup checkpoint önerisi açık)
- **Dinamik test:** 27/27 geçti (JWT tamper, brute-force, RBAC bypass, SQLi, security headers, CORS)

### 10.2 Kendi Bulgularım

**Güçlü taraflar:**
- `validate_security_settings()` — production'da default JWT secret'ı engelliyor
- `hmac.compare_digest` kullanımı — timing attack koruması
- PBKDF2 260K iterasyon — yeterli
- `AQ_ALLOW_ALL_CORS=false` default — CORS güvenli
- SSRF guardrail institution web engine'de aktif
- Security headers middleware'de var

**Endişe noktaları:**
- **JWT özel implementasyonu risk taşır:** PyJWT gibi battle-tested kütüphane yerine custom kod. `app/security.py:199-201`'de `hmac.new` → `hmac.new()` değil, `hmac.HMAC()` demek istiyor; ama Python stdlib'de `hmac.new` mevcut, sorun yok — ancak standart dışı.
- **Hardcoded secret:** Kod tabanında `"change-this-secret"` string'i `app/config.py:67` ve `app/security.py:222` içinde referans olarak var (guard için), gerçek hardcoded secret değil.
- **KVKK uyum izleri:** Kodda açık rıza, veri silme hakkı, aktarım kaydı gibi KVKK gereksinimleri bulunmuyor.
- **HTTPS zorunluluğu:** Uygulama düzeyinde HTTPS redirect yok — altyapıya bırakılmış (uygun ama dokümante edilmeli).
- **Audit log kapsamı:** HTTP istek bazlı tüm kayıtlar var. Ancak iş seviyesi olaylar (müşteri silindi, fatura ödendi) hâlâ kısmi.

---

## 11. Kod Kalitesi

### 11.1 Mimari Tutarlılık
- Engine → Repository → SQLite yığını tüm modüllerde tutarlı biçimde uygulanmış.
- Dependency injection: FastAPI `Depends()` + `request.app.state.*` pattern — tutarlı.
- `app/__init__.py:create_app()` — tüm bağımlılıkların oluşturulduğu merkezi fabrika.

### 11.2 Teknik Borç Gözlemleri
- `app/api.py` 3.710 satır — tek dosyada tüm route'lar. Router'ları modüllere bölmek (`app/routers/crm.py` vb.) gerekiyor.
- `companies` tablosu `name TEXT UNIQUE` ile ayrı bir kimlik sütunu olmaksızın tasarlanmış; `company_name` discriminator referential integrity'siz kullanılıyor.
- Senkron route handler'lar uzun süren engine çağrılarında thread-blocking yapabilir.
- Test framework: `unittest.discover` kullanılıyor, `pytest` konfigürasyonu yok (`pytest.ini`, `pyproject.toml` eksik).
- Coverage tool (`coverage.py`) konfigürasyonu yok — gerçek coverage oranı bilinmiyor.

### 11.3 ORM Tercihi
- Tüm veri erişimi ham `sqlite3` + parametreli sorgular. Pydantic V2 model doğrulaması iyi entegre edilmiş.
- Avantaj: Düşük bağımlılık, tam kontrol.
- Dezavantaj: PostgreSQL geçişinde tüm query'ler elle gözden geçirilmeli.

---

## 12. Test Durumu

### 12.1 Genel Tablo

| Metrik | Değer |
|---|---|
| Test dosyası sayısı | 30 (`tests/` klasöründe) |
| Toplam test sayısı (11 Mayıs 2026) | 211 (201 pass, 10 skip) |
| Test framework | `unittest` (Python stdlib) |
| pytest konfigürasyonu | **Yok** |
| Coverage konfigürasyonu | **Yok** |
| Test tipi ayrımı | Unit + API (integration) — aynı dosyada iç içe |

### 12.2 Test Büyüme Geçmişi
- Mart 2026: 29 test
- Mart (pentest sonrası): 73 test
- Mart (technical audit): 74 test
- Nisan (P0/P1 borç): 155 test
- Mayıs 11 (PatronOS): 211 test

### 12.3 Test Derinliği
- Her engine dosyası için ayrı test dosyası mevcut.
- `test_api_auth.py`, `test_auth_limiter.py`, `test_auth_service.py` — auth katmanı kapsamlı.
- `test_crm_engine.py`, `test_collections_engine.py`, `test_task_engine.py` — PatronOS test edilmiş.
- E2E test: Redis e2e smoke (`scripts/staging_redis_e2e_smoke.py`) var, ancak tam e2e test suite yok.
- **Gerçek coverage oranı bilinmiyor** — coverage.py konfigürasyonu eksik.

---

## 13. DevOps ve Deployment

### 13.1 CI/CD
- **Platform:** GitHub Actions
- **Workflow'lar:**
  1. `.github/workflows/security-gate.yml` — PR ve main/master push'ta tetiklenir. 6 aşama: bandit, pip-audit, unittest, security smoke, Redis E2E, Redis chaos. Redis 7-alpine ve Toxiproxy servisleri sağlanıyor.
  2. `.github/workflows/staging-redis-e2e.yml` — Manuel tetikleyici, staging Redis URL ile.
  3. `.github/workflows/staging-redis-chaos.yml` — Manuel tetikleyici, Toxiproxy chaos testi.

### 13.2 Containerization
- **Dockerfile:** **Yok**
- **docker-compose.yml:** **Yok**
- Uygulama doğrudan `uvicorn main:app --reload` ile başlatılıyor.
- Production için container olmadan deployment zor ve tekrar üretilemez.

### 13.3 Deployment Stratejisi
- Tek bir Python prosesi, tek SQLite dosyası.
- Yatay ölçekleme **mümkün değil** (SQLite).
- Backup: `./scripts/backup_db.sh` — manuel bash scripti.
- Release gate: `./scripts/security_gate.sh` — 6 aşama güvenlik kontrolü.
- Monitoring: `/api/v1/health` endpoint, `scripts/api_error_budget_report.py`.
- Log: stdout (structlog benzeri format, `|` ayrılmış).

---

## 14. Olgunluk Seviyesi (Modül Bazında)

| Modül Grubu | Seviye | Açıklama |
|---|---|---|
| Auth / RBAC / Audit | **Beta** | Kapsamlı test, güvenlik gate geçili. Production için SSO eksik. |
| Finans Defteri + Cashflow | **Beta** | Ledger, forecast, recurring, budget. Senaryo forecast P1 borç. |
| Holding Yönetimi | **Beta** | Onboarding readiness scoring iyi. |
| Procurement / Tender | **Beta** | RFQ→PO tam. Onay workflow (4-eyes) eksik. |
| Feasibility / International | **Beta** | GO/NO-GO, senaryo, ülke profili. |
| Stratejik Ekosistem | **Beta** | Orchestration kaliteli. Gerçek production verisi test edilmedi. |
| CRM / Tasks / Collections | **Alpha** | Yeni (11 Mayıs). Temel CRUD çalışıyor. |
| Market Data / Technical Analysis | **Alpha/Beta** | OHLCV cache var, gerçek veri feed lisanssız. |
| Connector Framework | **Alpha** | Queue/DLQ/leader-lock var. Gerçek adaptör yok. |
| Raporlama (PDF/Excel) | **Alpha** | Scheduled report var. Gerçek template tasarımı eksik. |
| Dashboard (UI) | **Pre-Alpha** | Server-side HTML. React/Vue SPA yok. |
| Bildirim (Email/WhatsApp) | **Planned** | Blueprint'te var, kodda yok. |
| Global Intel / Web Intel | **Alpha** | Offline/mock mode. Gerçek lisanslı kaynak yok. |
| **Genel Platform** | **Alpha/Beta** | Production için SQLite→PostgreSQL, Docker, OAuth2 gerekiyor. |

---

## 15. ENTEGRASYON HAZIRLIĞI (KOBİ Nakit Akışı İstihbarat Platformu ile)

Bu bölüm raporun en kritik kısmıdır. Senaryo: Alpha Quantum (çok-şirketli holding yönetimi) ve KOBİ Nakit Akışı İstihbarat Platformu, tek bir holding markası altında ortak kullanıcı sistemi ve ortak veri katmanıyla çalışacak.

### 15a. Kullanıcı Modeli — SSO Uygulanabilirliği

**Mevcut durum:** Kullanıcılar `users` tablosunda saklanıyor. JWT kendi `app/security.py` uygulaması. OAuth2/OIDC yok.

**SSO uygulanabilirliği:** Teknik olarak mümkün, ancak **önemli değişiklik gerektirir:**

1. **Gerekli değişiklikler:**
   - `app/security.py`'deki özel JWT doğrulamasını OIDC/OAuth2 Bearer token doğrulamasıyla değiştirmek veya yan yana çalıştırmak.
   - External Identity Provider (Keycloak, Auth0, AWS Cognito) entegrasyonu.
   - `users` tablosunda `external_provider_id` alanı eklemek.
   - Company scope mapping'i IdP group/claim'lerine bağlamak.

2. **En kolay yol:** Auth0 veya Keycloak ile OIDC — FastAPI'de `python-jose` veya `authlib` kütüphanesi ile mevcut `get_current_user()` dependency'si değiştirilebilir. Bu değişiklik diğer kodu etkilemez çünkü dependency injection zaten temiz ayrılmış.

3. **Tahmini maliyet:** Orta — 2-3 sprint, core auth değişikliği + test yeniden yazımı.

**Sonuç:** SSO uygulanabilir. Mevcut auth katmanı modüler yapısı sayesinde cerrahi değişiklikle geçiş yapılabilir.

---

### 15b. Company/Şirket Modeli — Yeni Modül Eklemeye Açıklık

**Mevcut durum:** `company_name TEXT` discriminator pattern tüm tablolarda uygulanmış. Yeni modül eklemek için şablon nettir:

```sql
CREATE TABLE nakit_akis_profilleri (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name TEXT NOT NULL,  -- Mevcut discriminator ile uyumlu
    ...
);
```

**Değerlendirme:** Model açık. "Her şirket için ayrı tahsilat profili" veya "nakit akışı analiz profili" eklemek için yeni migration + engine + repository dosyaları yeterli — mevcut koda dokunmak gerekmez.

**Uyarı:** `company_name` foreign key olmadığı için Nakit Akışı platformunda yaratılan bir profil, Alpha Quantum'da var olmayan bir şirkete referans verebilir. Ortak kullanımda bu tutarsızlık yönetilmeli.

---

### 15c. Veritabanı — SQLite Üretim Yeterliliği ve PostgreSQL Geçiş Maliyeti

**SQLite üretim yeterliliği:**

| Kriter | SQLite | Değerlendirme |
|---|---|---|
| Tek kullanıcı / küçük veri | Yeterli | ✅ |
| Çoklu eşzamanlı yazma (WAL ile) | Sınırlı | ⚠️ WAL modu iyileştiriyor ama yeterli değil |
| Yatay ölçekleme | **Yok** | ❌ |
| Multi-tenant SaaS (çok kullanıcı) | **Uygun değil** | ❌ |
| Replikasyon / Failover | **Yok** | ❌ |
| JSON sütun (kaçınılmaz) | Destekleniyor | ✅ |

**Kesin sonuç:** SQLite, bir holding bireyinin kişisel kullanımı için çalışır. Birden fazla kullanıcının eşzamanlı yazdığı bir SaaS ürün için **yeterli değildir.**

**PostgreSQL geçiş maliyeti:**

Ham `sqlite3` kullanıldığı için PostgreSQL geçişi ORM kullanılmış olsaydaki kadar basit olmayacak:

1. Tüm `sqlite3.connect()` → `psycopg2`/`asyncpg` değiştirme (15 repository dosyası).
2. SQLite'a özgü syntax: `INTEGER PRIMARY KEY AUTOINCREMENT` → `SERIAL` veya `BIGSERIAL`.
3. `PRAGMA foreign_keys = ON`, `PRAGMA journal_mode = WAL` → PostgreSQL'de varsayılan.
4. `JSON_EXTRACT()` gibi SQLite fonksiyonları → PostgreSQL `->` / `->>`  operatörleri.
5. Migration sistemi tamamen PostgreSQL uyumlu yeniden yazılmalı (Alembic önerilir).

**Tahmini maliyet:** Yoğun — 3-5 sprint. Ancak ORM (SQLAlchemy 2.0) geçişiyle birlikte yapılırsa daha az teknik borç oluşur.

---

### 15d. API — 3. Parti Uygulama Kullanıma Uygunluk ve OAuth Flow

**Mevcut API durumu:**
- `/api/v1/*` versiyonlu, OpenAPI otomatik belgelenmiş.
- Bearer token auth aktif.
- Nakit Akışı Platformu bu API'yi çağırabilir — teknik olarak hazır.

**OAuth flow:** **Yok.** Nakit Akışı Platformu'nun Alpha Quantum API'sine erişmesi için service-to-service OAuth2 Client Credentials flow implementasyonu gerekiyor.

**Gerekli değişiklikler:**
1. OAuth2 Client Credentials endpoint (`/oauth/token`) eklemek.
2. `client_id` / `client_secret` yönetimi (yeni tablo).
3. Service account scope tanımları.

**Alternatif (kısa yol):** API Key mekanizması eklemek — daha basit ama OAuth2'den az güvenli.

**Tahmini maliyet:** Orta — 1-2 sprint.

---

### 15e. Mimari — Microservice mi, Modular Monolith mi?

**Mevcut durum:** Modular monolith. Tek FastAPI uygulaması, tüm engine'ler `app.state`'te yaşıyor.

**Öneri:** **Modular Monolith olarak kalın — en azından 12-18 ay.**

Gerekçeler:
- Takım küçük (tek geliştirici + Claude). Microservice operasyonel yükü (service discovery, inter-service auth, distributed tracing, deployment bağımlılıkları) prematüre.
- Engine katmanı zaten modüler — ileride ayrı servis olarak çıkarılabilir tasarımda.
- Paylaşılan SQLite, microservice'i teknik olarak daha zor yapıyor. PostgreSQL'e geçildikten sonra microservice değerlendirme yapılmalı.
- İki ürün hattı (Alpha Quantum + Nakit Akışı) ayrı deployable servis olabilir ama **ortak bir Identity + Company Service** ile ortak veri modeli üzerinde çalışmalı.

**Önerilen mimari (12-18 ay içinde):**
```
┌─────────────────────┐  ┌──────────────────────────┐
│  Alpha Quantum API  │  │  KOBİ Nakit Akışı API    │
│  (bu platform)      │  │  (yeni ürün)             │
└──────────┬──────────┘  └────────────┬─────────────┘
           │                          │
           └──────────┬───────────────┘
                      │
            ┌─────────▼──────────┐
            │  Identity Service  │
            │  (OAuth2/OIDC)     │
            │  Shared User DB    │
            └─────────┬──────────┘
                      │
            ┌─────────▼──────────┐
            │  PostgreSQL         │
            │  (Shared schema     │
            │   per tenant)       │
            └────────────────────┘
```

---

### 15f. Marka — UI/Branding Nötrlüğü

**Mevcut UI:** `/dashboard` endpoint'i server-side HTML döndürüyor (`app/api.py` içinde HTMLResponse). "Alpha Quantum" başlığı, renk şeması (Deep Blue/Cyan) hard-coded HTML string içinde.

**Değerlendirme:**
- Ayrı bir React/Vue frontend yok — API nötr, HTML katmanı Alpha Quantum'a özel.
- Ayrı bir "KOBİ Nakit Akışı" ürününün kendi frontend'i olması gerekecek.
- API katmanı tamamen nötr — herhangi bir frontend tarafından kullanılabilir.
- Tek yapılacak: Nakit Akışı Platformu kendi frontend'ini inşa edip Alpha Quantum API'sini bir backend olarak kullanabilir.

---

### 15g. Integration Zorluk Skoru

**Skor: 6/10 — Orta-Yüksek**

| Konu | Zorluk | Neden |
|---|---|---|
| OAuth2/SSO eklenmesi | Yüksek | Yeni tablo, yeni dependency, test yeniden yazımı |
| SQLite → PostgreSQL | Çok Yüksek | 15 repository, tüm query'ler, migration sistemi |
| Docker + containerization | Orta | Tek Dockerfile yeterli, ancak orchestration gerektiriyor |
| Company model uyumu | Düşük | company_name pattern tutarlı, yeni tablo eklemek kolay |
| API erişimi (service token) | Orta | Client credentials eklemek 1-2 sprint |
| Frontend entegrasyonu | Düşük | API nötr, her frontend kullanabilir |
| Shared user service | Yüksek | Identity service kurmak, mapping yönetmek |

**Sonuç:** Core mimari temiz ve genişlemeye açık. Asıl yatırım OAuth2+SSO ve PostgreSQL geçişinde. Bu iki blok çözülünce entegrasyon akışı makul sürede (2-3 ay) tamamlanabilir.

---

## 16. Eksikler ve Teknik Borç

### P0 (Üretim Engelleyici)
1. **SQLite → PostgreSQL geçişi** — Yatay ölçekleme ve eşzamanlı yazma için zorunlu.
2. **Docker / containerization** — Dockerfile ve docker-compose yok. Deployment tekrar üretilemez.
3. **OAuth2/SSO** — İki ürün hattı için zorunlu. Şu an yok.

### P1 (Kısa Vadeli)
4. **company_name FK bütünlüğü** — `company_name` discriminator `companies.name`'e foreign key ile bağlanmalı.
5. **API router modülarizasyonu** — `app/api.py` 3.710 satır tek dosya. `app/routers/` alt klasörlerine bölünmeli.
6. **pytest + coverage konfigürasyonu** — `pytest.ini`, `pyproject.toml`, `coverage.py` eksik.
7. **Async route handler'lar** — Uzun süren engine çağrıları için `async def` + `run_in_executor` veya background task.
8. **KVKK uyum API'leri** — Veri silme, aktarım kaydı, rıza yönetimi.
9. **Bildirim motoru** — Email/WhatsApp — Blueprint'te var, kodda yok.
10. **Connector gerçek adaptörler** — `connector_adapters.py` şablon seviyesinde. ERP/CRM/accounting gerçek connector yok.

### P2 (Orta Vadeli)
11. **Cursor-based pagination** — Büyük veri kümelerinde limit-only pagination yetersiz.
12. **Onay workflow** (4-eyes) — Procurement/tender/finance aksiyonları için.
13. **SLO dashboard** — p95 latency, queue lag, sync failure görünürlüğü.
14. **Backup otomasyonu** — Manuel bash scripti; cron + S3/GCS upload gerekiyor.
15. **Session metadata** — Cihaz/tarayıcı bilgisi, çok oturum yönetimi.

---

## 17. Risk Haritası

| Risk | Etki | Olasılık | Önem | Önlem |
|---|---|---|---|---|
| SQLite concurrency limiti | Çok Yüksek | Yüksek | 🔴 Kritik | PostgreSQL geçişi |
| Tek geliştirici bağımlılığı | Yüksek | Yüksek | 🔴 Kritik | Backup owner, dokümantasyon, onboarding |
| company_name FK eksikliği | Yüksek | Orta | 🟠 Yüksek | FK constraint + cascade rule |
| JWT özel implementasyonu | Yüksek | Düşük | 🟠 Yüksek | PyJWT veya python-jose geçişi |
| Bilinen zafiyet (pip-audit): 0 | Düşük | — | 🟢 İyi | Düzenli audit devam etmeli |
| Demo kullanıcılar production'da | Çok Yüksek | Orta | 🔴 Kritik | `AQ_ENABLE_DEMO_USERS=false` zorunlu |
| KVKK uyumsuzluğu | Çok Yüksek | Orta | 🟠 Yüksek | Uyum API'leri + hukuki danışmanlık |
| Container yokluğu | Yüksek | Yüksek | 🔴 Kritik | Dockerfile eklemek |
| Offline market veri feed | Orta | Yüksek | 🟡 Orta | Lisanslı feed veya gerçek kaynak |
| Tek noktasal arıza (SQLite) | Çok Yüksek | Orta | 🔴 Kritik | PostgreSQL + replikasyon |

---

## 18. Önerilen Sonraki Adımlar (Önceliklendirilmiş)

### Faz A — Üretim Altyapısı (0-3 ay)
1. **Dockerfile + docker-compose** yaz. Uvicorn production config ile.
2. **PostgreSQL geçişi** — SQLAlchemy 2.0 + Alembic ile. Tüm repository'leri birlikte taşı.
3. **OAuth2 Client Credentials** endpoint ekle — servisler arası token için.
4. **company_name → company_id FK** migrasyonu yaz.

### Faz B — Entegrasyon Hazırlığı (3-6 ay)
5. **OIDC/SSO entegrasyonu** — Keycloak veya Auth0 ile IdP kurulumu.
6. **Shared Identity Service** — Alpha Quantum ve Nakit Akışı Platformu aynı user store'u kullansın.
7. **API router modülarizasyonu** — `app/routers/crm.py`, `app/routers/finance.py` vb.
8. **pytest + coverage** konfigürasyonu — hedef: %80 coverage.

### Faz C — Ürün Olgunluk (6-12 ay)
9. **Bildirim motoru** — Email (SendGrid/SES) + WhatsApp (Twilio) provider abstraction.
10. **Async engine çağrıları** — Uzun süren hesaplama motorları background task'a taşı.
11. **Frontend SPA** — React/Next.js ile ayrı bir frontend oluştur. Mevcut `/dashboard` HTML kaldırılabilir.
12. **SLO dashboard** — Grafana veya benzeri ile p95 latency, error budget görünürlüğü.
13. **Connector gerçek adaptörler** — İlk hedef: Parasut, Logo, E-fatura entegrasyonu.
14. **KVKK uyum API'leri** — Veri silme, export, consent yönetimi.
15. **Backup otomasyonu** — S3/GCS'e günlük cron backup.

---

## 19. Açık Sorular (Proje Sahibine)

1. **Hangi şirketi kaç kullanıcı aynı anda kullanacak?** Bu sayı SQLite vs PostgreSQL kararını somutlaştırır.

2. **KOBİ Nakit Akışı Platformu ne zaman başlıyor?** Eğer 6 ay içindeyse OAuth2/SSO Faz A'ya alınmalı.

3. **Connector adaptörleri için hedef ERP/muhasebe sistemi ne?** (Parasut, Logo, SAP, e-fatura/e-arşiv?) Bu, Faz C'nin en kritik teknik kararı.

4. **Market verisi için gerçek veri feed sağlayıcısı planlandı mı?** (Bloomberg, Refinitiv, Borsa İstanbul API?) Şu an offline/mock modda.

5. **KVKK danışmanlığı alındı mı?** Platform kişisel veri işliyorsa (kullanıcılar, müşteriler, çalışanlar) KVKK uyum yükümlülükleri başlamış demektir.

6. **Frontend stratejisi nedir?** Mevcut server-side HTML dashboard'u geliştirmek mi, React SPA kurmak mı, yoksa hazır low-code dashboard (Retool, Metabase) kullanmak mı?

7. **Deployment hedefi nedir?** AWS / GCP / Azure? Yönetilen Kubernetes (EKS, GKE) mı, basit VM mi? Bu soruya göre PostgreSQL seçimi (RDS, CloudSQL) ve container stratejisi şekillenir.

8. **Çok kiracılı (gerçek SaaS) mi, tek kiracılı (tek holding için) mi?** Eğer ileride farklı holdinglere satış planlanıyorsa multi-tenant mimari köklü değişiklik gerektirir.

9. **Bildirim sistemi için GDPR/KVKK opt-in süreci kim yönetecek?** Email/WhatsApp için yasal altyapı hazır mı?

10. **Connector worker (background sync job) production'da aktif olacak mı?** `AQ_CONNECTOR_WORKER_ENABLED=false` şu an. Aktif edilirse SQLite lock problemi ortaya çıkabilir.

---

## 20. Ek: Önemli Dosya Yolları

| Bileşen | Dosya Yolu |
|---|---|
| Uygulama fabrikası | `app/__init__.py` |
| Tüm route'lar (116 endpoint) | `app/api.py` |
| Güvenlik (JWT, parola) | `app/security.py` |
| Auth servisi | `app/auth_service.py` |
| Konfigürasyon | `app/config.py` |
| Model tanımları (Pydantic) | `app/models.py` |
| Migration yöneticisi | `app/migration_manager.py` |
| Audit log repository | `app/audit_repository.py` |
| Auth rate limiter | `app/auth_limiter.py` |
| Engine katmanı | `app/engines/` (22 dosya) |
| Migration SQL dosyaları | `migrations/001-018.up.sql` |
| CI güvenlik gate | `.github/workflows/security-gate.yml` |
| Güvenlik smoke test | `scripts/security_smoke.py` |
| Bandit konfigürasyonu | `security/bandit.yaml` |
| SQLite veritabanı | `alpha_quantum.db` |
| Önceki teknik denetim | `TECHNICAL_AUDIT_2026-03-20.md` |
| Pentest raporu | `PENTEST_REPORT_2026-03-20.md` |
| Sprint geçmişi | `SPRINT_BACKLOG.md` |

---

*Bu rapor `alpha_quantum.db`, `app/` kaynak kodu, `migrations/`, `tests/`, `.github/workflows/`, tüm `.md` dokümantasyon dosyaları ve CI konfigürasyonu incelenerek üretilmiştir. Hiçbir kod değiştirilmemiştir.*
