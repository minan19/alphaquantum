# FINOS MASTER DOCUMENT

**Belge versiyonu:** 1.0
**Tarih:** 23 Mayıs 2026
**Proje sahibi:** Mustafa Inan
**Repo:** /Users/mustafainan/alpha-quantum
**Mevcut proje adı:** Alpha Quantum
**Hedef proje adı:** FinOS

Bu belge, projenin **anayasası**dır. Tüm geliştirme oturumlarında Claude Code dahil olmak üzere birincil referanstır. Bu belgeyle çelişen herhangi bir yönlendirme bu belgeye karşı sınanır. İki ana bölümden oluşur:

1. **Bölüm A — Stratejik Brief (Project Brief):** Ne yapıyoruz, neden, hangi sırayla
2. **Bölüm B — Geliştirme Anayasası (CLAUDE.md):** Nasıl yapıyoruz, hangi standartla

---

# BÖLÜM A — STRATEJIK BRIEF

## A.1 EXECUTIVE DECISION

Alpha Quantum projesini **FinOS** çatı markası altında **iki ürün hattına** evrimleştir. Sıfırdan yeni bir proje BAŞLAMA. Mevcut kod tabanı (22 engine, 211 test, 18 migration, 116 endpoint) korunacak ve genişletilecek.

### İki Ürün Hattı

**FinOS Holding** — Mevcut Alpha Quantum'un evrimi
- Hedef kitle: Çoklu şirket sahipleri, aile holdingleri (Türkiye'de yaklaşık 8.000 holding)
- Tüm modüller erişimde (holding, feasibility, international, procurement, finans, CRM, vb.)
- Fiyat: 9.999-29.999 TL/ay

**FinOS Nakit** — Alpha Quantum'un KOBİ versiyonu
- Hedef kitle: Tek şirket KOBİ'ler (Türkiye'de yaklaşık 3 milyon KOBİ)
- Aynı kod tabanı, feature flag ile sınırlandırılmış
- Erişilen modüller: auth, finance, crm, task, collections, invoices, reporting, dashboard, notification, audit
- Gizlenen modüller: holding, feasibility, international, tender, market_data, strategic_ecosystem
- Fiyat: 999-4.999 TL/ay + tahsil edilen geç ödemelerden %1-2 başarı bazlı opsiyonel komisyon

**Aynı kod tabanı, iki ürün, iki fiyatlandırma. Microservice DEĞİL — Modular Monolith.**

---

## A.2 12 AYLIK YOL HARİTASI

| Ay | Faz | Çıktı |
|----|-----|-------|
| 1 | Stabilizasyon | Docker, env hijyeni, branch stratejisi, API router refactor |
| 2-3 | PostgreSQL Geçişi | SQLite'tan PostgreSQL'e geçiş, SQLAlchemy 2.0, Alembic |
| 4 | OAuth2 + Auth Evolution | Client Credentials flow, IdP hazırlığı |
| 5-6 | FinOS Nakit MVP | Feature flag sistemi, KOBİ UI/UX, sadeleştirilmiş onboarding |
| 6 | Pilot Lansman | 10-20 KOBİ pilot müşteri |
| 7-9 | Frontend SPA | Next.js 15 + TypeScript modern arayüz |
| 9-12 | Eksik Modüller | Notification engine, gerçek connector adaptörleri (Paraşüt/Logo), KVKK uyum API'leri, WhatsApp AI bot |

---

## A.3 ÜRETİME ENGEL P0 SORUNLARI

Bu üç sorun çözülmeden müşteri kabul EDİLMEZ:

### P0.1 — Docker / Containerization (Hafta 1)
- Mevcut durum: uvicorn main:app --reload ile çalışıyor
- Hedef: Dockerfile + docker-compose.yml ile reproducible deployment
- Tahmini süre: 1 hafta

### P0.2 — PostgreSQL Geçişi (Hafta 2-8)
- Mevcut durum: SQLite (multi-tenant SaaS için yetersiz)
- Hedef: PostgreSQL 16 + SQLAlchemy 2.0 + Alembic
- Etkilenen: 15 repository dosyası refactor edilecek
- Tahmini süre: 3-5 sprint

### P0.3 — OAuth2 Client Credentials (Hafta 9-12)
- Mevcut durum: Sadece kullanıcı login JWT
- Hedef: Service-to-service token + iki ürün için ortak kimlik
- Tahmini süre: 2-3 sprint

---

## A.4 SONRAKİ AKSİYONLAR — İLK 4 HAFTA DETAY

### Hafta 1 — Temizlik
1. Bu FINOS_MASTER.md dosyasını proje köküne kaydet
2. .env.example güncelle (Bölüm B.6'daki şablon)
3. develop branch aç
4. Dockerfile yaz (Bölüm B'de tam şablon var)
5. docker-compose.yml yaz (Bölüm B'de tam şablon var)
6. Lokal Docker ile çalıştır, doğrula
7. pyproject.toml hazırla (ruff, mypy, pytest config)
8. pre-commit hook kur

### Hafta 2 — API Refactor
9. app/api.py (3.710 satır) → app/routers/ modüllerine böl
10. Tüm testler geçtiğini doğrula
11. PR aç, kendine review, merge

### Hafta 3-4 — PostgreSQL Hazırlığı
12. Lokal Docker'da PostgreSQL 16 container
13. SQLAlchemy 2.0 + Alembic + asyncpg ekle
14. app/database.py oluştur
15. Alembic init
16. İlk SQLAlchemy model (users tablosu)
17. SQLite'tan PostgreSQL'e data export scripti
18. İlk migration uygula
19. Tüm users ile ilgili kod PostgreSQL'e geçsin (auth flow dahil)

---

# BÖLÜM B — GELİŞTİRME ANAYASASI (CLAUDE.md)

## B.1 PROJE KİMLİĞİ

**Mevcut ad:** Alpha Quantum
**Hedef çatı marka:** FinOS
**İki ürün hattı:**
- **FinOS Holding:** Mevcut Alpha Quantum'un evrimi. Çoklu şirket / aile holdingi.
- **FinOS Nakit:** KOBİ versiyonu (tek şirket). Aynı kod tabanı, feature flag ile sınırlandırılmış.

**Tek cümle vizyon:** Türkiye KOBİ ve holdinglerinin finansal işletim sistemi.

**Hedef pazar:** 3 milyon Türk KOBİ + 8.000 aile holdingi + 100 bin ihracatçı.

---

## B.2 TEKNOLOJİ YIĞINI (KİLİTLİ)

Bu yığın dışına çıkma. Yeni kütüphane eklemek için ADR (Architecture Decision Record) yaz.

| Bileşen | Teknoloji | Versiyon | Karar Gerekçesi |
|---------|-----------|----------|-----------------|
| Backend framework | FastAPI | 0.135+ | Async, type-safe, OpenAPI native |
| Python | 3.11 | 3.11.x | Production-stable |
| ORM (yeni) | SQLAlchemy 2.0 | 2.0+ | Async, type hints, migration arkadaşı |
| Migration | Alembic | 1.13+ | SQLAlchemy resmi |
| Veritabanı (hedef) | PostgreSQL | 16 | Production-grade, JSONB |
| Cache / Queue | Redis | 7+ | Mevcut, korunacak |
| HTTP istemci | httpx | 0.28+ | Async-native |
| Doğrulama | Pydantic v2 | 2.12+ | Mevcut |
| JWT | python-jose | 3.3+ | OAuth2 hazır, battle-tested |
| Parola hash | passlib[bcrypt] | 1.7+ | Argon2 alternatif değerlendirme |
| Frontend (Ay 7+) | Next.js + TypeScript | 15 + 5 | SEO, performans, modern |
| UI library | Tailwind + shadcn/ui | son | Hızlı geliştirme |
| Container | Docker | son | Reproducible deployment |
| Orkestrasyon | docker-compose | son (dev), K8s (prod) | Aşamalı |
| CI/CD | GitHub Actions | mevcut | Mevcut workflow korunacak |
| Test | pytest + pytest-asyncio | son | unittest'ten geçiş |
| Linter | ruff | son | hızlı, modern |
| Formatter | ruff format | son | black yerine |
| Type check | mypy | strict | Yeni kod için zorunlu |
| Cloud (hedef) | AWS Frankfurt | eu-central-1 | KVKK uyumlu, Activate kredi |
| Monitoring | Sentry + OpenTelemetry | son | Hata + tracing |

YASAK: Bu yığın dışına çıkma. Yeni kütüphane eklemek için ADR gerekli.

---

## B.3 MİMARİ PRENSİPLER

### B.3.1 Katman Mimarisi (KORUNACAK)

Mevcut Alpha Quantum mimarisi tutarlı, bozma:

```
API (FastAPI Router)
  ↓
Engine (Business Logic)
  ↓
Repository (Data Access)
  ↓
Database (PostgreSQL)
```

**Kurallar:**
- Engine içinde SQL yazma — yalnızca Repository'de
- API içinde business logic yazma — yalnızca Engine'i çağır
- Repository'den Engine veya API'ye çıkış yapma (one-way)
- Cross-engine bağımlılık varsa, orchestrator engine kullan (strategic_ecosystem_engine pattern örneği gibi)

### B.3.2 Modüler Monolit (12 ay boyunca)

Microservice'e geçme. Ama her engine bağımsız çıkarılabilir olarak tasarla:
- Engine'in tek public API'si var
- Engine içi state, Repository üzerinden okunur
- Cross-engine çağrılar Engine arayüzü üzerinden, doğrudan Repository çağrısı yasak

### B.3.3 Multi-Tenancy

**Mevcut:** company_name TEXT discriminator. Korunacak ama güçlendirilecek.

**Yapılacak değişiklikler (P1):**
1. companies.id (UUID) primary key olarak eklenecek
2. Tüm tablolarda company_id UUID FOREIGN KEY eklenecek
3. company_name geriye dönük uyumluluk için kalacak ama yeni kod company_id kullanacak

**Tenant izolasyonu kuralı:** Repository'deki HER query, company_id filtresine sahip olmalı (admin endpoint'ler hariç). Bu kural ihlal edilirse veri sızıntısı olur.

### B.3.4 İki Ürün Hattı — Feature Flag

Yeni dosya app/feature_flags.py oluşturulacak. İçerik şablonu:

```python
from enum import Enum

class Product(Enum):
    FINOS_HOLDING = "holding"
    FINOS_NAKIT = "nakit"

PRODUCT_FEATURES = {
    Product.FINOS_HOLDING: {
        "modules": ["all"],
    },
    Product.FINOS_NAKIT: {
        "modules": [
            "auth", "finance", "crm", "task", "collections",
            "invoices", "reporting", "dashboard", "notification", "audit"
        ],
    }
}
```

Her API endpoint başında require_module(Product.X, "module_name") kontrolü yapılacak.

---

## B.4 KODLAMA STANDARTLARI

### B.4.1 Adlandırma

- Dosya: snake_case.py
- Sınıf: PascalCase
- Fonksiyon/değişken: snake_case
- Sabit: UPPER_SNAKE_CASE
- Veritabanı tablosu: snake_case, çoğul (users, companies)
- Veritabanı sütunu: snake_case, tekil
- API endpoint: kebab-case, çoğul (/api/v1/cash-flow-profiles)

### B.4.2 Tip Anotasyonu (ZORUNLU)

Yeni kodun %100'ü type hint'li olacak. mypy --strict geçecek.

YANLIŞ örnek:
```python
def calculate(data):
    return data["amount"] * 1.18
```

DOĞRU örnek:
```python
def calculate(data: InvoiceData) -> Decimal:
    return data.amount * Decimal("1.18")
```

### B.4.3 Docstring (Public API'ler için ZORUNLU)

Şablon:
```python
def create_invoice(
    company_id: UUID,
    customer_id: UUID,
    amount: Decimal,
) -> Invoice:
    """Yeni fatura oluştur.
    
    Args:
        company_id: Faturayı kesen şirket
        customer_id: Faturanın kesileceği müşteri
        amount: KDV dahil tutar
    
    Returns:
        Oluşturulan Invoice
    
    Raises:
        ValueError: Tutar negatifse
        CustomerNotFound: Müşteri yoksa
    """
```

### B.4.4 Hata Yönetimi

- Özel exception class hierarchy kullan: FinosError → BusinessError → CustomerNotFound
- try/except Exception: YASAK. Spesifik exception yakala.
- Hata log'ları structlog ile yapılandırılmış formatta
- Kullanıcıya dönen hata mesajı Türkçe ve eyleme yönelik

### B.4.5 Asla Yapma

- print() kullanma. logger kullan.
- Hardcoded secret. Tüm secret .env'den okunmalı.
- f-string SQL. Parametrik query veya ORM kullan.
- from x import * gibi star import.
- Function/class 50 satırdan büyük. Böl.
- Dosya 500 satırdan büyük. Böl. (Mevcut api.py 3.710 satır, refactor edilecek)
- Test yazmadan PR.

## B.5 KLASÖR YAPISI (HEDEF)

```
alpha-quantum/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI entry
│   ├── config.py                  # Pydantic Settings
│   ├── feature_flags.py           # Ürün ayrımı (YENİ)
│   ├── security.py                # Auth, JWT, OAuth2
│   ├── database.py                # SQLAlchemy engine, session (YENİ)
│   ├── routers/                   # API endpoints (api.py yerine, YENİ)
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── companies.py
│   │   ├── finance.py
│   │   ├── crm.py
│   │   ├── tasks.py
│   │   ├── collections.py
│   │   ├── invoices.py
│   │   ├── reporting.py
│   │   └── dashboard.py
│   ├── engines/                   # Business logic (mevcut, korunacak)
│   ├── repositories/              # Data access (mevcut, refactor edilecek)
│   ├── models/                    # SQLAlchemy models (YENİ)
│   ├── schemas/                   # Pydantic models (YENİ)
│   └── services/                  # Cross-cutting (notification, etc.) (YENİ)
├── alembic/                       # Migrations (YENİ)
│   └── versions/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── scripts/
├── docs/
│   └── adr/                       # Architecture Decision Records (YENİ)
├── docker/
│   ├── Dockerfile
│   ├── Dockerfile.prod
│   └── docker-compose.yml
├── .github/workflows/
├── pyproject.toml                 # Poetry / hatch (YENİ)
├── alembic.ini                    # (YENİ)
├── FINOS_MASTER.md                # Bu dosya
├── README.md
└── .env.example
```

---

## B.6 ÇEVRESEL DEĞİŞKENLER (.env.example şablonu)

```bash
# .env.example
APP_ENV=development                    # development | staging | production
APP_VERSION=2.0.0
LOG_LEVEL=INFO

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/finos
DATABASE_POOL_SIZE=20
DATABASE_POOL_TIMEOUT=30

# Redis
REDIS_URL=redis://localhost:6379/0

# Security
AQ_JWT_SECRET=
AQ_JWT_ALGORITHM=HS256
AQ_ACCESS_TOKEN_MINUTES=60
AQ_REFRESH_TOKEN_DAYS=30
AQ_PASSWORD_PEPPER=

# OAuth2
OAUTH2_ISSUER=https://api.finos.tr
OAUTH2_AUDIENCE=finos-api

# CORS
AQ_ALLOWED_ORIGINS=https://app.finos.tr,https://holding.finos.tr

# Feature Flags
FINOS_PRODUCT=holding              # holding | nakit | both

# Notification
EMAIL_PROVIDER=sendgrid            # sendgrid | ses | smtp
SENDGRID_API_KEY=
WHATSAPP_PROVIDER=twilio           # twilio | 360dialog
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_WHATSAPP_FROM=+14155238886

# Storage
S3_BUCKET=finos-uploads
AWS_REGION=eu-central-1            # Frankfurt — KVKK uyumlu

# Monitoring
SENTRY_DSN=
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318

# Demo
AQ_ENABLE_DEMO_USERS=false         # Production'da KESİNLİKLE false
```

---

## B.7 GÜVENLİK KURALLARI

### B.7.1 Asla Yapılmayacaklar

- Secret'ı kod tabanına commit etme
- .env dosyasını commit etme (.gitignore'da olduğundan emin ol)
- Production'da AQ_ENABLE_DEMO_USERS=true çalıştırma
- Customer veriye plain-text log atma (KDV no, IBAN, kart, telefon)
- SQL injection — her query parametrik veya ORM
- XSS — her user input Pydantic ile valide edilmiş

### B.7.2 Her Zaman Yapılacaklar

- Yeni endpoint = yeni permission tanımı + test
- Yeni tablo = company_id foreign key + index
- Repository query'sinde company_id filtresi (admin hariç)
- Password = bcrypt veya argon2 (passlib)
- HTTPS = production'da nginx/CloudFront katmanında zorunlu
- Audit log = login, logout, permission değişikliği, finansal işlem

### B.7.3 KVKK Uyum

Her kişisel veri içeren endpoint için:
- Veri minimizasyonu: Yalnızca gerekli alan
- Veri sahibi hakları: GET /me/data (export), DELETE /me/data (silme)
- Veri saklama: TTL ya da archive policy
- Veri işleme rıza kaydı: consent_records tablosu
- KVK ihlali tespit: security_incidents tablosu + alert

---

## B.8 VERİTABANI KURALLARI

### B.8.1 Migration

- Tüm şema değişikliği Alembic migration ile
- Migration ismi: <timestamp>_<verb>_<table>_<column>.py
- Production'da --sql ile preview yapmadan migration uygulama
- Migration'lar idempotent olmalı (downgrade çalışmalı)

### B.8.2 Şema İlkeleri

Her tablo:
- id UUID PRIMARY KEY DEFAULT gen_random_uuid() (CSPRNG)
- company_id UUID NOT NULL (multi-tenant) + FOREIGN KEY
- created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
- updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
- deleted_at TIMESTAMPTZ NULL (soft delete)
- INDEX (company_id, created_at)

### B.8.3 İsimlendirme

- Tablo: çoğul, snake_case (invoices, cash_flow_profiles)
- Sütun: tekil, snake_case (amount, due_date)
- Index: ix_<table>_<columns> (ix_invoices_company_due_date)
- FK: fk_<table>_<reftable> (fk_invoices_companies)

---

## B.9 API TASARIM KURALLARI

### B.9.1 URL Yapısı

```
/api/v1/<resource>                  # GET liste, POST oluştur
/api/v1/<resource>/{id}             # GET tek, PATCH güncelle, DELETE sil
/api/v1/<resource>/{id}/<action>    # POST eylem (örn. /invoices/{id}/send)
```

### B.9.2 Pagination

Cursor-based pagination (limit-only DEĞİL):
```
GET /api/v1/invoices?cursor=<base64>&limit=20
```

Response:
```json
{
  "data": [...],
  "next_cursor": "",
  "has_more": true
}
```

### B.9.3 Filtreleme

```
?company_id=<uuid>&status=overdue&due_date_after=2026-05-01
```

### B.9.4 Hata Formatı

```json
{
  "error": {
    "code": "INVOICE_NOT_FOUND",
    "message": "Belirtilen fatura bulunamadı",
    "details": {"invoice_id": "..."},
    "request_id": "req_..."
  }
}
```

### B.9.5 Versiyonlama

- Major değişiklik = yeni URL versiyonu (/api/v2/)
- Eski versiyon 6 ay desteklenir, sonra deprecated
- Deprecation header: Deprecation: true; Sunset: 2027-01-01

---

## B.10 TÜRKİYE'YE ÖZEL KURALLAR

### B.10.1 KDV / Vergi

- Tüm para alanları Decimal, kuruş hassasiyetinde
- KDV oranları config'de (yüzde 1, 8, 18, 20)
- E-fatura için GIB UUID formatı

### B.10.2 Tarih / Saat

- Veritabanında TIMESTAMPTZ (UTC)
- Display'de Europe/Istanbul
- Tatil takvimi: app/services/holidays_tr.py

### B.10.3 Telefon / Kimlik

- Telefon: +90 prefix zorunlu, E.164 format
- TC Kimlik: 11 hane validation algoritması
- Vergi No: 10 hane (kurumsal) veya 11 hane (TC Kimlik = şahıs şirketi)

### B.10.4 Para Birimi

- Birden fazla para birimi desteklenir (TRY, USD, EUR)
- Her tutar yanında currency alanı zorunlu
- TCMB kuru günlük çekilir, cache'lenir

### B.10.5 Banka / IBAN

- IBAN: TR prefix + 24 hane
- Validation: MOD 97 algoritması
- Asla plain text storage — minimum AES-256

## B.11 AI / ML PRENSİPLERİ

### B.11.1 Hangi modeli ne için

- **Risk skoru:** XGBoost (tabular data, açıklanabilir)
- **Türkçe NLP:** OpenAI GPT-4o-mini (cost-effective) veya kendi fine-tune
- **WhatsApp müzakere botu:** Anthropic Claude API (multi-turn iyi)
- **Tahmin (forecast):** Prophet veya Statsforecast (zaman serisi)

### B.11.2 Veri Kullanımı

- Müşteri verisi modelleri eğitmek için anonimleştirilmiş kullanılır
- Diferansiyel mahremiyet uygulanır
- AI çıktıları açıklanabilir olmalı (SHAP, LIME)
- Her AI önerisi yanında "Bu öneri %X olasılıkla, şu verilere dayanıyor" diye gerekçe

### B.11.3 LLM Maliyet

- Production'da her LLM çağrısı için cost tracking
- Cache: aynı prompt 24 saat içinde tekrar çağrılırsa cache'den
- Rate limit: kullanıcı başına saatlik tavan

---

## B.12 TEST STRATEJİSİ

### B.12.1 Test Türleri

- **Unit:** Tek fonksiyon, tek sınıf. Dependency mock
- **Integration:** Engine + Repository + DB. Test container'da PostgreSQL
- **E2E:** API endpoint → DB → response. Auth dahil

### B.12.2 Coverage Hedefi

- Yeni kod: %90+
- Genel: %75+
- Critical path (auth, payment, audit): %95+

### B.12.3 Yapı

```
tests/
├── unit/
│   ├── engines/
│   ├── repositories/
│   └── services/
├── integration/
│   ├── test_auth_flow.py
│   ├── test_invoice_lifecycle.py
│   └── ...
└── e2e/
    └── test_critical_paths.py
```

### B.12.4 Fixture Şablonu

```python
@pytest.fixture
async def test_company(db):
    return await create_test_company(db, name="Test A.Ş.")

@pytest.fixture
async def authenticated_client(test_user):
    token = create_access_token(test_user)
    return httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"})
```

### B.12.5 Mevcut Durum

- 211 test geçiyor (10 skip)
- pytest config eksik → pyproject.toml'a ekle
- Coverage tool eksik → pytest-cov ekle

---

## B.13 DEPLOYMENT SÜRECİ

### B.13.1 Branch Stratejisi

```
main                    # Production
├── staging             # Pre-production test
└── develop             # Active development
    ├── feat/oauth2-implementation
    ├── feat/postgresql-migration
    └── fix/audit-log-truncation
```

### B.13.2 PR Kuralları

- Her PR'da CI gate geçmeli (bandit, pip-audit, pytest, ruff)
- Tek geliştirici de olsan çıktıyı kendin oku
- Squash merge
- Commit mesajı: feat:, fix:, refactor:, docs:, test:, chore:

### B.13.3 Deployment Aşamaları

```
develop → CI testleri → staging → manuel test → main → production
```

### B.13.4 Rollback

- Her release Docker image tag'i ile
- Rollback = önceki tag deploy
- DB migration rollback: Alembic downgrade

---

## B.14 PERFORMANS HEDEFLERİ

### B.14.1 API Response Time (p95)

- Auth endpoint: < 200ms
- Read endpoint (list, get): < 300ms
- Write endpoint: < 500ms
- Report generation: < 5s (sync), async ise queue

### B.14.2 Database

- Connection pool: 20 connection
- Slow query log: > 1s
- Index hit ratio: > %99

### B.14.3 Frontend

- LCP: < 2.5s
- FID: < 100ms
- CLS: < 0.1

---

## B.15 KARAR KAYITLARI (ADR)

Önemli teknik karar her zaman ADR olarak docs/adr/ altına kaydedilir:

```markdown
# ADR-001: PostgreSQL'e Geçiş

**Tarih:** 2026-06-01
**Durum:** Kabul edildi
**Karar veren:** Mustafa Inan

## Bağlam
SQLite multi-tenant SaaS için yetersiz.

## Karar
PostgreSQL 16 + SQLAlchemy 2.0 + Alembic.

## Sonuçlar
- Yatay ölçekleme mümkün
- Tüm repository refactor gerekli
- 3-5 sprint maliyet
```

---

## B.16 CLAUDE İLE ÇALIŞIRKEN

### B.16.1 Her Oturumda

Claude Code'u açtığında ilk komut:
```
FINOS_MASTER.md ve ALPHA_QUANTUM_AUDIT.md dosyalarını oku ve bu belgelere göre çalış.
```

### B.16.2 Claude'a Yasak Davranışlar

Claude'a şunları söyle:
- Var olan kodu silmeden değiştir
- Refactor için ayrı PR
- Test yazmadan production kodu yazma
- Bağımlılık eklemek için onay iste
- Mimari değişiklik için ADR yaz

### B.16.3 Tipik İş Akışı

```
1. Görev tanımla (örnek: "Invoice repository'yi PostgreSQL'e taşı")
2. Claude planı çıkarsın
3. Sen planı onayla
4. Claude değişiklik yapsın
5. Sen test çalıştır
6. Geçerse commit, PR
```

---

## B.17 YAPILMASI YASAK ŞEYLER

- ❌ Microservice'e geçiş (12 ay içinde)
- ❌ MongoDB veya farklı DB ekleme
- ❌ Mobile native app (önce web)
- ❌ Sıfırdan yeni proje başlatma — Alpha Quantum'u evrimleştir
- ❌ Cryptocurrency / blockchain modülü
- ❌ Marketplace / e-ticaret pivot
- ❌ Foundation model eğitimi (API kullan)
- ❌ Custom UI framework (shadcn/ui yeterli)
- ❌ Tek dosyada 500 satırdan büyük dosya
- ❌ Test yazmadan production kodu
- ❌ Sözlü mutabakat — her şey yazılı (ADR, ticket)
- ❌ Yığın dışı kütüphane (ADR yazmadan)

---

# BÖLÜM C — HIZLI BAŞLATMA KOMUTLARI

## C.1 Dockerfile (docker/Dockerfile)

```dockerfile
FROM python:3.11-slim AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 appuser
COPY --from=builder /root/.local /home/appuser/.local
COPY --chown=appuser:appuser . .
USER appuser
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

## C.2 docker-compose.yml (docker/docker-compose.yml)

```yaml
version: '3.9'

services:
  postgres:
    image: postgres:16-alpine
    container_name: finos-postgres
    environment:
      POSTGRES_DB: finos
      POSTGRES_USER: finos
      POSTGRES_PASSWORD: dev_password_change_in_prod
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U finos"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: finos-redis
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  api:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    container_name: finos-api
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql+asyncpg://finos:dev_password_change_in_prod@postgres:5432/finos
      REDIS_URL: redis://redis:6379/0
      APP_ENV: development
      AQ_JWT_SECRET: dev_secret_change_in_prod_min_32_chars_long
      AQ_ENABLE_DEMO_USERS: "false"
    ports:
      - "8000:8000"
    volumes:
      - ../app:/app/app

volumes:
  postgres_data:
```

## C.3 pyproject.toml (proje köküne)

```toml
[project]
name = "finos-platform"
version = "2.0.0"
description = "FinOS — Türkiye KOBİ ve Holding Finansal İşletim Sistemi"
authors = [{name = "Mustafa Inan"}]
requires-python = ">=3.11"

[tool.ruff]
target-version = "py311"
line-length = 100
extend-exclude = ["alembic/versions"]

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "C4", "SIM", "RUF"]
ignore = ["E501"]

[tool.ruff.format]
quote-style = "double"

[tool.mypy]
python_version = "3.11"
strict = true
ignore_missing_imports = true
exclude = ["alembic/versions"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
asyncio_mode = "auto"
addopts = [
    "--strict-markers",
    "--cov=app",
    "--cov-report=term-missing",
    "--cov-report=html",
    "--cov-fail-under=75",
]

[tool.coverage.run]
source = ["app"]
omit = ["app/main.py", "alembic/*"]
```

---

# BÖLÜM D — 30 GÜNLÜK KONTROL LİSTESİ

## D.1 Altyapı (Hafta 1)

- [ ] FINOS_MASTER.md kaydedildi (bu dosya)
- [ ] Dockerfile yazıldı ve test edildi
- [ ] docker-compose.yml yazıldı ve up çalışıyor
- [ ] pyproject.toml hazırlandı
- [ ] ruff + mypy + pytest-cov kuruldu
- [ ] pre-commit hook kuruldu
- [ ] develop branch açıldı
- [ ] .env.example güncellendi
- [ ] .gitignore doğrulandı (.env, __pycache__, venv, *.db)

## D.2 Bedava Cloud Kredi Başvuruları

- [ ] AWS Activate başvurusu yapıldı ($100K kredi)
- [ ] Microsoft for Startups Founders Hub başvurusu yapıldı ($150K kredi)
- [ ] Google for Startups başvurusu yapıldı ($200K kredi)
- [ ] OpenAI Startup Fund başvurusu yapıldı
- [ ] Anthropic Claude API kredisi için başvuru yapıldı

## D.3 Resmi Statüler

- [ ] Teknopark araştırması yapıldı (ITÜ Arı, ODTÜ Teknokent vb.)
- [ ] Teknopark başvurusu yapıldı
- [ ] Şirket kuruluşu (henüz yoksa) — Ltd Şti tavsiye edilir
- [ ] TÜBİTAK BiGG başvuru hazırlığı başladı

## D.4 Kod Hijyeni

- [ ] Mevcut SQLite veritabanı yedeklendi
- [ ] Tüm .env dosyaları temizlendi
- [ ] Hardcoded secret taraması yapıldı (gitleaks, truffleHog)
- [ ] AQ_ENABLE_DEMO_USERS=false doğrulandı
- [ ] AQ_JWT_SECRET production için CSPRNG üretildi

## D.5 Geliştirme Disiplini

- [ ] Haftalık takvim oluşturuldu
- [ ] Notion/Linear/GitHub Projects sprint board kuruldu
- [ ] Her sprint = 1 hafta (kısa döngü)
- [ ] Daily standup (kendi kendine, 5 dakika, yazılı)

---

# BÖLÜM E — META

## E.1 Bu Belge Hakkında

Bu belge FinOS projesinin **anayasası**dır. Çelişen herhangi bir yönlendirme bu belgeye karşı sınanır. Bu belgenin her güncellemesi docs/adr/ altında ayrı bir ADR ile belgelenir. Bu belge yalnızca major karar değişikliğinde güncellenir; günlük detaylar ADR'lere gider.

## E.2 Versiyon Geçmişi

- v1.0 — 23 Mayıs 2026 — İlk versiyon, Alpha Quantum'dan FinOS'a evrim kararı

## E.3 İlgili Belgeler

- ALPHA_QUANTUM_AUDIT.md — Mevcut kod tabanının teknik denetim raporu
- README.md — Proje genel tanıtım
- docs/adr/ — Architecture Decision Records

---

**SON.**

Bu belgenin sonudur. Tüm kararlar yukarıda. Yola çıkıyoruz.

**Sahibi:** Mustafa Inan
**Durum:** Aktif
**Versiyon:** 1.0
**Son güncelleme:** 2026-05-23
