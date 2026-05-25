# Alpha Quantum — Roadmap

**Son güncelleme:** 26 Mayıs 2026
**Canonical öncelik kaynağı.** Diğer dokümanlardaki sıralamalar bu dosyaya
referans verir.

Yapı:
```
ALPHA QUANTUM (ana çatı / platform / repo / şirket markası)
   ├── CorpOS  →  Multi-company / Holding yönetimi
   └── FinOS   →  KOBİ nakit akışı / finansal operasyon
```

Marka emojileri:
- 🤖  Kod ajanı (Claude) yapacak
- 👤  Mustafa (Product Owner + CTO) yapacak
- 🤝  Birlikte

---

## 🔥 ŞİMDİ (24 saat içinde)

| ID  | Kim | İş | Durum |
|-----|-----|----|----|
| 0.1 | 🤖 | mypy CI relax (pre-existing type debt kabul) | ✅ done |
| 0.2 | 🤖 | PatronOS → CorpOS rename tamamla | ✅ done |
| 0.3 | 🤖 | PR #1 CI yeşil bekle + merge | 🟡 in progress |
| 0.4 | 🤖 | `develop` + ölü branch'leri sil | ⏳ pending |
| 0.5 | 🤖 | Tag'leri push'la | ⏳ pending |

## 🟥 P0 — Üretime Engel (1-3 hafta)

| ID  | Kim | İş | Süre |
|-----|-----|----|------|
| A1  | 🤖 | Migration uyumsuzluğu fix (DB'de 14 → 21) | 30 dk |
| A5  | 🤖 | `api.py` modülerizasyonu (4165 satır → `app/routers/`) | 2-3 gün |
| A4  | 🤖 | KVKK uyum API'leri (data export/delete/consent) | 2-3 gün |
| F1  | 🤖 | Type debt cleanup (mypy strict hazırlık) | 2-3 gün |
| -   | 👤 | Şirket kuruluşu (Ltd. Şti.) | 2-4 hafta |
| -   | 👤 | Domain alımı + TÜRKPATENT marka kontrolü | 1-2 gün |
| -   | 🤝 | Production deployment kararı + setup (cloud) | 1-2 hafta |
| -   | 👤 | HTTPS / SSL kurulumu | 1 gün |
| D3  | 🤖 | Backup otomasyon scripti (cron + S3) | 1 gün |
| -   | 🤝 | Backup restore prova | 1 gün |

## 🟧 P1 — Üretim sonrası ilk hafta (3-6 hafta)

| ID  | Kim | İş | Süre |
|-----|-----|----|------|
| B1  | 🤖 | Async route handlers | 3-4 gün |
| B2  | 🤖 | Background task / queue (Celery / Arq) | 2-3 gün |
| B7  | 🤖 | shadcn/ui kurulumu + tasarım sistemi | 2-3 gün |
| B8  | 🤖 | Frontend modül sayfaları (~12 modül backend bağla) | 4-6 hafta |
| A3  | 🤖 | OAuth2 / SSO (CorpOS + FinOS ortak login) | 3-5 gün |
| B3  | 🤖 | Cursor-based pagination | 1-2 gün |
| B4  | 🤖 | Rate limiting tüm endpoint'lere yay | 1-2 gün |
| -   | 👤 | Müşteri görüşmesi planı (5-10 KOBİ patronu) | 2-3 hafta |
| -   | 👤 | Pricing modeli kararı (Starter/Pro/Enterprise) | 1 hafta |
| -   | 👤 | Hukuki sözleşmeler (KVKK aydınlatma, gizlilik) | 2-3 hafta |

## 🟨 P2 — Ürün Olgunluğu (Ay 2-3)

### CorpOS özel
| ID  | Kim | İş | Süre |
|-----|-----|----|------|
| E3  | 🤖 | Holding-level dashboard | 3-4 gün |
| E1  | 🤖 | Konsolide finansal raporlama | 4-5 gün |
| E4  | 🤖 | ComparisonEngine geliştir (%60→%100) | 2-3 gün |
| E6  | 🤖 | Holding onboarding wizard (Excel import) | 4-5 gün |
| E2  | 🤖 | Inter-company transactions + cari hesap | 5-7 gün |
| E5  | 🤖 | Çapraz şirket bütçe / forecast | 4-5 gün |
| E7  | 🤖 | Karmaşık yetki matrisi (per-company role) | 3-4 gün |

### FinOS özel
| ID  | Kim | İş | Süre |
|-----|-----|----|------|
| C4  | 🤖 | Nakit akışı stres testi | 2-3 gün |
| C2  | 🤖 | Tahsilat psikolojisi motoru | 4-5 gün |
| C3  | 🤖 | AI tahsilat koçu (LLM) | 3-4 gün |
| C7  | 🤖 | Müşteri iflas erken uyarı (KAP scraper) | 3-4 gün |
| C6  | 🤖 | WhatsApp müzakere botu | 5-7 gün |
| C5  | 🤖 | Sektör benchmark karşılaştırma | 3-4 gün |

### Cross-cutting
| ID  | Kim | İş | Süre |
|-----|-----|----|------|
| C1  | 🤖 | 4-eyes onay workflow | 3-4 gün |
| B5  | 🤖 | MFA / 2FA (TOTP) | 3-4 gün |
| B6  | 🤖 | Session / device metadata | 2 gün |
| C9  | 🤖 | i18n (TR/EN) | 2 gün |

## 🟩 P3 — Altyapı & Kalite (Ay 3-6)

| ID  | Kim | İş | Süre |
|-----|-----|----|------|
| D1  | 🤖 | Sentry + OpenTelemetry | 2-3 gün |
| D4  | 🤖 | Test coverage (pytest-cov + threshold) | 1 gün |
| D5  | 🤖 | E2E test suite (Playwright) | 1 hafta |
| D6  | 🤖 | Performance test (Locust) | 2-3 gün |
| D2  | 🤖 | Error budget dashboard | 2 gün |
| D7  | 🤖 | Mutation testing (mutmut) | 2 gün |
| D8  | 🤖 | Yaptırım listesi taraması (OFAC/BM/EU) | 2-3 gün |
| F2  | 🤖 | `ruff check --fix` modernizasyonu (B, UP, I) | 1 gün |
| A6  | 🤖 | company_name → company_id FK refactor | 4-5 gün |
| A2  | 🤖 | PostgreSQL geçişi | 5-7 gün |

## 🟦 P4 — Marka, Ürün, Satış (paralel, Mustafa liderliğinde)

| ID  | Kim | İş | Süre |
|-----|-----|----|------|
| -   | 👤 | Logo + kurumsal kimlik | 2-4 hafta |
| -   | 🤝 | Landing page (alphaquantum.com.tr) | 2-3 hafta |
| -   | 🤝 | Pricing + iyzico/Stripe entegrasyonu | 2-3 hafta |
| -   | 👤 | Müşteri destek (Intercom/Crisp) | 1 hafta |
| -   | 👤 | Bilgi tabanı / dokümantasyon | 4-8 hafta |
| -   | 👤 | AWS Activate / Microsoft / Google Cloud kredi | 1-2 hafta |
| -   | 👤 | TÜBİTAK BiGG (250K TL hibe) | 2-3 ay |
| -   | 👤 | KOSGEB başvurusu (1.5M TL'ye kadar) | 1-2 ay |
| -   | 👤 | Teknopark başvurusu | 1-2 ay |
| -   | 🤝 | Onboarding süreci (UX brief + akış kodu) | 2-3 hafta |
| -   | 👤 | Vergi danışmanı / mali müşavir | 1 hafta |
| -   | 👤 | Siber sigorta + mesleki sorumluluk | 2-3 gün |
| -   | 🤖 | Mobil app skeleton (React Native) | 3-6 ay |

## ⚫ P5 — Uzun Vade (Yıl 1-2)

| ID  | Kim | İş | Süre |
|-----|-----|----|------|
| -   | 👤 | ISO 27001 sertifikası | 6-12 ay |
| -   | 👤 | SOC 2 Type II | 12-18 ay |
| -   | 👤 | BDDK uyum / sandbox | 3-6 ay + onay |
| -   | 👤 | MASAK uyum | 2-3 ay |
| C8  | 🤝 | Faktoring marketplace | 1-2 hafta kod + sözleşmeler |
| -   | 🤝 | Türk bankaları açık bankacılık | 4-8 hafta her banka |
| -   | 🤝 | GİB / KEP / UYAP entegrasyonlar | 1-2 hafta her biri |
| -   | 👤 | Yatırımcı pitch deck + metrikler | 2-4 hafta |

---

## Notlar

- **Adam-hafta tahmini:** ~6 ay tek geliştirici tempoyla. Paralel iş işleri Mustafa
  zamanı yer.
- **Üretime çıkmak için minimum:** Şimdi (0.x) + P0 (10 madde) + P1'in yarısı +
  P4 acilleri ≈ 22-25 madde, ~3 ay.
- **Geri dönüş garantisi:** Her sprint öncesi `backup/<tag-name>` etiketi
  push'lanır. Geri dönüş tek komut: `git reset --hard backup/<tag-name>`.

## Geçmiş

| Tarih | Yapılan |
|---|---|
| 25 Mayıs 2026 | KOBİ Cash Flow sprint günü — 10 sprint (S-331/332/333/334/341/342/343/335 + QW-1/2), 211→367 test, 18→21 migration |
| 26 Mayıs 2026 | Marka kararı (Alpha Quantum + CorpOS + FinOS), branch konsolidasyon (PR #1), ROADMAP.md yazıldı |
