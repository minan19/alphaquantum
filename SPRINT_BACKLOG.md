# Alpha Quantum - Sprint Backlog (Epic > Story > Task)

Tarih: 21 Mart 2026  
Durum: Faz 2 başlatıldı, Faz 1 çıktıları korunuyor.

## Aşama Özeti

- Faz 1: Tamamlandı (güvenlik, auth, RBAC, migration, audit, test/security gate)
- Faz 2: Aktif (ölçekleme, operasyonel dayanıklılık, katman yönetimi)
- Faz 3: Planlandı (gelişmiş dijital platform + servisleşme)

## Epic Listesi

| Epic ID | Epic Adı | Katman | Öncelik | Hedef Faz |
|---|---|---|---|---|
| E-201 | Katman Owner ve Governance Modeli | Hizmet | P0 | Faz 2 |
| E-202 | KPI/SLA Ölçümleme ve Raporlama | Hizmet + Dijital Platform | P0 | Faz 2 |
| E-203 | Altyapı Dayanıklılık (Backup/Restore/Kapasite) | Fiziksel/Donanım | P1 | Faz 2 |
| E-204 | Platform/API Operasyonel Sertleştirme | Platform/API | P1 | Faz 2 |
| E-205 | Kullanıcı/İstemci Deneyimi İyileştirme | Kullanıcı/İstemci | P1 | Faz 2 |
| E-206 | Ürün & Çözüm Paketleme Standardı | Ürün & Çözüm | P1 | Faz 2-3 |
| E-301 | Gelişmiş Dijital Raporlama ve Canlı Görselleştirme | Dijital Platform | P1 | Faz 3 |

## Sprint Planı

### Sprint 2.1 (2 hafta) - Governance + Ölçüm Temeli

| Story ID | Epic | Story | Owner | Kabul Kriteri | Durum (21 Mart 2026) |
|---|---|---|---|---|---|
| S-211 | E-201 | Katman owner atama matrisi yayınlanır | Mustafa Inan (Product Owner + CTO) | 7 katmanın her biri için owner/backup owner tanımlı | Done |
| S-212 | E-201 | RACI ve karar/eskalasyon akışı netleşir | Mustafa Inan (Product Owner) | Onaylı RACI dokümanı repo içinde | Done |
| S-213 | E-202 | KPI sözlüğü çıkarılır | Mustafa Inan (Product + Data Engineer) | En az 1 KPI/katman, ölçüm tanımıyla yazılı | Done |
| S-214 | E-202 | SLA hedef seti tanımlanır | Mustafa Inan (SRE + DevOps Lead) | P1/P2 olay SLA hedefleri onaylı | Done |

| Task ID | Story | Task | Tahmin | Durum (21 Mart 2026) |
|---|---|---|---|---|
| T-211-1 | S-211 | `LAYER_EXECUTION_PLAN.md` owner alanlarını isim bazlı güncelle | 0.5g | Done |
| T-211-2 | S-211 | Owner atama review toplantı notunu ekle | 0.5g | Done |
| T-212-1 | S-212 | RACI dokümanına eskalasyon basamaklarını ekle | 0.5g | Done |
| T-213-1 | S-213 | KPI ölçüm formül ve veri kaynağı alanlarını yaz | 1g | Done |
| T-214-1 | S-214 | SLA hedef tablosu ve olay sınıfı matrisini ekle | 1g | Done |

### Sprint 2.2 (2 hafta) - Altyapı Dayanıklılık + API Operasyon

| Story ID | Epic | Story | Owner | Kabul Kriteri | Durum (21 Mart 2026) |
|---|---|---|---|---|---|
| S-221 | E-203 | Backup/restore runbook hazırlanır | Mustafa Inan (DevOps Lead) | Runbook + test senaryosu repo'da | Done |
| S-222 | E-203 | Kapasite ve log retention politikası tanımlanır | Mustafa Inan (DevOps Lead) | CPU/RAM/Disk alarm eşikleri yazılı | Done |
| S-223 | E-204 | API operasyon checklist'i release gate'e bağlanır | Mustafa Inan (Backend + DevSecOps) | Release öncesi checklist zorunlu hale gelir | Done |
| S-224 | E-204 | Endpoint bazlı hata bütçesi takibi başlar | Mustafa Inan (Backend Lead) | `/api/v1/*` hata oran raporu üretilir | Done |

| Task ID | Story | Task | Tahmin | Durum (21 Mart 2026) |
|---|---|---|---|---|
| T-221-1 | S-221 | Backup komut seti ve doğrulama adımı dokümante et | 1g | Done |
| T-221-2 | S-221 | Restore dry-run sonucu raporla | 1g | Done |
| T-222-1 | S-222 | Log saklama süresi ve rota politikasını yaz | 0.5g | Done |
| T-223-1 | S-223 | Release checklist markdown + CI referansı ekle | 1g | Done |
| T-224-1 | S-224 | API hata bütçesi ölçüm formatını ekle | 0.5g | Done |

### Sprint 2.3 (2 hafta) - Ürün Paketleme + UX İyileştirme

| Story ID | Epic | Story | Owner | Kabul Kriteri | Durum (24 Mart 2026) |
|---|---|---|---|---|---|
| S-231 | E-205 | Rol bazlı dashboard akışları netleşir | Claude (23martclaude) | Admin/Manager/Viewer için akışlar ayrı | Done |
| S-232 | E-205 | Kritik kartlar için kullanılabilirlik revizyonu yapılır | Claude (23martclaude) | Kritik eylemler 3 tık altında tamamlanır | Done |
| S-233 | E-206 | ERP/Fintech/Global Intel ürün paketi tanımı çıkarılır | Claude (23martclaude) | Paket kapsam ve bağımlılıklar net | Done |
| S-234 | E-206 | Paket bazlı rollout checklist hazırlanır | Claude (23martclaude) | Her paket için rollout/rollback adımı var | Done |

| Task ID | Story | Task | Tahmin | Durum (24 Mart 2026) |
|---|---|---|---|---|
| T-231-1 | S-231 | Rol bazlı menü görünürlük kurallarını dokümante et | 0.5g | Done |
| T-231-2 | S-231 | Dashboard senaryo akış diyagramı ekle | 1g | Done |
| T-232-1 | S-232 | Kritik aksiyon kartlarını öncelik sırasına göre düzenle | 1g | Done |
| T-233-1 | S-233 | Ürün paket matrisi (modül, değer, bağımlılık) yaz | 1g | Done |
| T-234-1 | S-234 | Rollout/rollback checklist şablonu oluştur | 0.5g | Done |

## Faz 3 Hazırlık Backlog'u (Ön Kuyruk)

| Story ID | Epic | Story | Öncelik | Not |
|---|---|---|---|---|
| S-311 | E-301 | Canlı grafik + sinyal + profesyonel rapor akışını tek ekranda birleştir | P1 | **Done** — Claude (23martclaude) |
| S-312 | E-301 | Yönetici rapor zamanlama ve otomatik dağıtım | P1 | **Done** — Claude (23martclaude) |
| S-313 | E-301 | Çoklu kurum ve ülke bazlı karşılaştırma paneli | P1 | **Done** — Claude (23martclaude) |
| S-321 | CorpOS | CRM — Müşteri ve Teklif yönetimi | P1 | **Done** — Claude (23martclaude) |
| S-322 | CorpOS | Tasks — Görev atama ve takip | P1 | **Done** — Claude (23martclaude) |
| S-323 | FinOS | Collections — Fatura ve alacak takibi | P1 | **Done** — Claude (23martclaude) |
| S-331 | KOBİ Cash Flow | Alacak yaşlandırma analizi (30/60/90/90+ buckets) | P1 | **Done** — Claude (23martclaude) |
| S-332 | KOBİ Cash Flow | Nakit akışı projeksiyonu (30/60/90 gün ileriye) | P1 | **Done** — Claude (23martclaude) |
| S-333 | KOBİ Cash Flow | Müşteri ödeme risk skoru (0-100) | P1 | **Done** — Claude (23martclaude) |
| S-334 | KOBİ Cash Flow | Vade uyarı / bildirim motoru (T-3..T+14 pencereleri) | P1 | **Done** — Claude (23martclaude) |
| S-335 | Dashboard | Görev + bildirim sinyallerini dashboard'a ekle | P2 | **Done** — Claude (23martclaude) |
| S-341 | KOBİ Cash Flow | Çok para birimi FX nakit akışı (TRY normalleştirme) | P2 | **Done** — Claude (23martclaude) |
| S-342 | KOBİ Cash Flow | Senet / Çek / Bono takibi + status FSM | P2 | **Done** — Claude (23martclaude) |
| S-343 | KOBİ Cash Flow | Tahsilat kanalı: provider abstraction + KVKK consent | P2 | **Done** — Claude (23martclaude) |
| QW-1 | Hardening | Hardcoded test password → env var | P3 | **Done** — Claude (23martclaude) |
| QW-2 | Reporting | Tek fatura için imzalı PDF export | P2 | **Done** — Claude (23martclaude) |

## Definition of Done

1. Story kabul kriteri dokümante edilmiş ve karşılanmış olacak.
2. Güvenlik gate (`bandit`, `pip-audit`, `unittest`, `security_smoke`) yeşil olacak.
3. İlgili doküman linkleri README/Blueprint içinde güncel olacak.
4. Audit edilebilir değişiklik notu ve owner bilgisi yazılmış olacak.

## 21 Mart 2026 İlerleme Notu

- Sprint 2.1 çekirdek işleri tamamlandı (`5/5 task done`).
- Sprint 2.2 çekirdek işleri tamamlandı (`5/5 task done`).
- Sonraki yürütme odağı: Sprint 2.3 (ürün paketleme + UX iyileştirme).

## 24 Mart 2026 İlerleme Notu

- Sprint 2.3 tüm task'ları tamamlandı (`5/5 task done`).
- Yönetim Claude'a devredildi; çalışma branch'i: `23martclaude`.
- Üretilen çıktılar:
  - [docs/ROLE_BASED_DASHBOARD_RULES.md](/Users/mustafainan/alpha-quantum/docs/ROLE_BASED_DASHBOARD_RULES.md)
  - [docs/DASHBOARD_FLOW_DIAGRAM.md](/Users/mustafainan/alpha-quantum/docs/DASHBOARD_FLOW_DIAGRAM.md)
  - [docs/CRITICAL_ACTION_CARDS.md](/Users/mustafainan/alpha-quantum/docs/CRITICAL_ACTION_CARDS.md)
  - [docs/PRODUCT_PACKAGE_MATRIX.md](/Users/mustafainan/alpha-quantum/docs/PRODUCT_PACKAGE_MATRIX.md)
  - [docs/PRODUCT_ROLLOUT_CHECKLIST.md](/Users/mustafainan/alpha-quantum/docs/PRODUCT_ROLLOUT_CHECKLIST.md)
- Sonraki odak: Faz 3 hazırlık backlog'u (S-311, S-312, S-313) + P0 teknik borç.

## 4 Mayıs 2026 İlerleme Notu

- Tüm P0 ve P1 teknik borç tamamlandı (P0-1, P0-2, P0-3, P1-1, P1-2).
- Faz 3 hazırlık backlog'u tamamlandı: S-311, S-312, S-313 Done.
- Çalışma branch'i: `23martclaude`. Test sayısı: 98 → 155.
- Yeni endpoint'ler:
  - GET /api/v1/dashboard/live-signals (S-311)
  - POST/GET /api/v1/reports/schedule (S-312)
  - POST /api/v1/reports/schedule/{id}/trigger (S-312)
  - DELETE /api/v1/reports/schedule/{id} (S-312)
  - GET /api/v1/analytics/company-comparison (S-313)

## 11 Mayıs 2026 İlerleme Notu

- CorpOS / FinOS modül entegrasyonu başlatıldı: S-321, S-322 (CorpOS), S-323 (FinOS) Done.
- Çalışma branch'i: `23martclaude`. Test sayısı: 155 → 211 (201 pass, 10 skip).
- 3 yeni migration (016, 017, 018), 6 yeni kaynak dosyası, 55 yeni test.
- Yeni endpoint'ler:
  - POST/GET /api/v1/crm/customers, GET/PATCH /api/v1/crm/customers/{id} (S-321)
  - POST/GET /api/v1/crm/proposals, GET /api/v1/crm/proposals/summary, PATCH /api/v1/crm/proposals/{id} (S-321)
  - POST/GET /api/v1/tasks, GET /api/v1/tasks/summary, PATCH /api/v1/tasks/{id} (S-322)
  - POST/GET /api/v1/collections/invoices, GET /api/v1/collections/invoices/{id} (S-323)
  - POST /api/v1/collections/invoices/{id}/payment, GET /api/v1/collections/summary (S-323)

## 25 Mayıs 2026 İlerleme Notu — KOBİ Nakit Akışı sprint'i

Kaynak: `KOBİ Nakit Akışı İstihbarat Platformu` proje tanım raporundaki MVP
özelliklerinin platforma uyarlanması. Bir günde 10 sprint tamamlandı.

**Tamamlananlar (commit sırasıyla):**

| Sprint | Commit | Test | Açıklama |
|---|---|---|---|
| Pre-push gate fix | `de88b6b` | — | `.gitignore` cert/key + write_finance permission |
| S-331 + S-332 | `9bec137` | +25 | Alacak yaşlandırma + 30/60/90 gün nakit projeksiyonu |
| S-333 | `a5a8c4d` | +19 | Müşteri ödeme risk skoru (0-100) |
| S-334 | `d206680` | +25 | Vade uyarı motoru (T-3, T-1, T+1, T+7, T+14) |
| S-341 | `d18d848` | +26 | FX nakit akışı (12 para birimi + env override) |
| S-342 | `7bb3f70` | +30 | Senet / Çek / Bono takibi + status FSM |
| S-343 | `e0f3692` | +24 | Tahsilat kanalı + provider abstraction + KVKK consent |
| S-335 + QW-1/2 | `dc14c81` | +17 | Dashboard sinyalleri + env password + Invoice PDF |

**Cumulative metrikler:**
- Test: 211 → 367 (+156, 10 skip platform bağımlılığı nedeniyle)
- Migration: 18 → 21 (notifications, financial_instruments, delivery_log+consent)
- Engine: 24 → 27 (NotificationEngine, FinancialInstrumentEngine, DeliveryEngine)
- Endpoint sayısı: ~116 → ~132
- Ruff: 0 hata · Mypy: 0 hata

**Önemli mimari kararlar:**
- KVKK consent flag'leri tüm kanallarda zorunlu — production'da AQ_NOTIFICATION_CHANNELS env değişkeniyle açılır, default sadece `console`
- SendGrid provider varsayılan olarak sandbox modunda — kazara gerçek e-posta atma riski yok
- CurrencyConverter deterministic + env override edilebilir — testler offline çalışır, prod'da live rate kolay enjekte edilebilir
- Notification idempotency UNIQUE constraint ile DB seviyesinde garantili — scheduled scan'ler güvenle çalışır
- DashboardEngine artık operasyonel sinyaller içeriyor (overdue tasks, critical notifications) — tek dashboard'da iş + finance görüntüsü

**Sıradaki odak:** Platform/DevOps katmanı (S-361 Docker pipeline, S-362 Frontend, S-363 Multi-tenant onboarding) ve P3 dış entegrasyonlar (GİB, KEP, UYAP).
