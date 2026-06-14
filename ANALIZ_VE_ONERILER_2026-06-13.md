# Alpha Quantum — Analiz ve Öneriler

**Tarih:** 13 Haziran 2026
**Kapsam:** Genel proje + Backend/özellikler + Frontend/UI tasarımı
**Yöntem:** Kod tabanı, doküman ve yapısal inceleme (statik)

---

## 1. Özet

Alpha Quantum, FastAPI tabanlı, katmanlı (engine → repository → router) bir kurumsal yönetim platformu. Olgun bir backend (≈41.000 satır Python, ~45 engine, ~37 router, 35 migration, 68 test dosyası) ile modern bir Next.js 15 / React 19 frontend ve dikkat çekici şekilde sofistike bir tasarım-token sistemi (OKLCH + WCAG motoru, marka/tema cascade) içeriyor.

**En kritik tek bulgu:** Backend ile frontend arasında büyük bir **yüzey alanı uçurumu** var. Backend ~35 iş modülü sunarken, frontend yalnızca ~13 sayfa ile bunların belki üçte birini kullanıcıya açıyor. Projenin değeri arka tarafta birikmiş ama kullanıcının dokunabildiği yüzeye yansımıyor. Ürünün önündeki en büyük kaldıraç burada.

**İkinci kritik bulgu:** SQLite üzerinde çok-kiracılı (multi-tenant) SaaS. `company_name TEXT` discriminator'a dayalı izolasyon, foreign key olmadan — referential integrity açısından kırılgan ve gerçek production ölçeği için engel.

Genel olgunluk: backend **Beta**, frontend **Alpha/Beta**, tasarım sistemi **Beta+** (en güçlü taraf).

---

## 2. Güçlü Taraflar (korunması gerekenler)

- **Mimari tutarlılık.** engine/repository/router ayrımı net ve genişletilebilir. Yeni modül eklemek ucuz.
- **Güvenlik temeli.** PBKDF2-SHA256 (260k iter), özel JWT, RBAC + permission matrisi, audit log, rate limiting, SSRF guardrail. Gerçek bir production baseline.
- **Router modülerizasyonu yapılmış.** Eski 4000+ satırlık `api.py` artık `app/routers/*` altında ~37 dosyaya bölünmüş (ROADMAP A5 kapanmış görünüyor).
- **Tasarım sistemi.** Token mimarisi + OKLCH/WCAG kontrast motoru + modül×tema cascade + canlı önizleme paneli — bu seviyede bir sistem çoğu KOBİ SaaS'ından ileride.
- **Test kültürü.** 68 test dosyası, CI'da Bandit + pip-audit + mypy strict.

---

## 3. Backend / Özellik Önerileri

### P0 — Production'a engel

1. **PostgreSQL'e geçiş.** SQLite multi-tenant SaaS için en büyük engel; eşzamanlı yazma, connection pooling ve gerçek izolasyon yok. ORM olmadığı için (ham `sqlite3`) geçiş elle SQL uyumu gerektirecek — erken yapmak ucuz, geç yapmak pahalı.
2. **Multi-tenancy modelini sağlamlaştır.** `company_name TEXT` yerine `company_id` FK'ya geçiş + cascade. Şirket adı değişince veri kopması riski şu an gerçek. Orta vadede Row-Level Security (Postgres RLS) düşünülmeli.
3. **OAuth2 / SSO.** CorpOS + FinOS ortak login için şart; ROADMAP'te A3 olarak duruyor. Ortak bir Identity Provider olmadan iki ürün hattı birleşmiyor.
4. **Async route handler'lar + job kuyruğu.** OCR, rapor üretimi, connector sync, web scraping gibi işler senkron request içinde çalışıyorsa p95 latency'yi bozar. Arq/Celery ile background queue (ROADMAP B1/B2).

### P1 — Olgunluk

5. **Onay (approval) workflow'ları.** Procurement'ta 4-eyes onayı, intercompany transfer onayı yok. Kurumsal alıcı bunu ilk sorar.
6. **Gerçek connector adaptörleri.** Connector engine'de queue/DLQ/leader-lock hazır ama adaptörler mock. En az 1-2 gerçek entegrasyon (örn. bir banka API'si veya halihazırdaki Netsis ERP) "demo" algısını kırar.
7. **Bildirim teslim katmanı.** Notification engine eklenmiş; e-posta/WhatsApp gibi gerçek bir teslim kanalına bağlanması (provider + retry + template) lazım.
8. **Veri feed'leri.** Market/global intelligence offline/mock modda. Lisanslı ya da resmi bir kaynak bağlanmadan bu modüller satış argümanı olamaz; "beta" etiketi şeffaf tutulmalı.
9. **API tutarlılığı.** Cursor-based pagination ve rate limiting'i tüm endpoint'lere yaymak (ROADMAP B3/B4). Şu an kısmi.

### P2 — Teknik borç

10. **Tip borcu.** mypy strict açık ama `assignment/attr-defined/misc` hâlâ bastırılmış; kademeli temizlik.
11. **Gözlemlenebilirlik.** `observability.py` var; KPI/SLA sözlüğü tanımlı ama gerçek metrik dashboard'u yok. Prometheus/OpenTelemetry + tek bir "sistem sağlığı" sayfası.

---

## 4. Frontend / Özellik Önerileri

**Ana mesele kapsama açığı.** Backend'de karşılığı olup frontend'de **sayfası olmayan** başlıca modüller:

- Procurement (RFQ/teklif/PO)
- Feasibility (fizibilite / GO-NO-GO)
- Tender / İhale dossier
- Finance ledger + bütçe + recurring
- Holdings konsolidasyon + grup FX
- Intercompany transferler
- Scenario planning (what-if)
- Vendor risk skorlama
- AI Finance Copilot (NL → SQL)
- KVKK self-servis (export/delete/consent)
- Reports (PDF/Excel) merkezi ekranı
- Community, Financial instruments, Schedule, e-Fatura, Anomalies (widget var, sayfa yok)

**Öneri sırası:**

1. **Modül sayfası fabrikası kur.** 12+ sayfayı tek tek elde yazmak yerine; ortak liste/detay/filtre/form deseni + tablo + pagination + boş durum bileşenlerinden oluşan tekrarlanabilir bir "module page" şablonu çıkar. ROADMAP B8'in (4-6 hafta) süresini ciddi kısaltır.
2. **AI Copilot'u öne çıkar.** NL→SQL copilot zaten backend'de var; bunu global bir komut paleti / "sor" arayüzüne bağlamak ürünün en güçlü demo anı olur.
3. **Rol bazlı navigasyon.** 35 modül tek sidebar'a sığmaz; CorpOS (holding/CFO) ve FinOS (KOBİ nakit akışı) personalarına göre menü gruplama ve gizleme.
4. **Gerçek zamanlı dashboard.** `realtime` router'ı var; SSE/WebSocket ile canlı sinyal akışı dashboard'da değerlendirilebilir (şu an polling).

---

## 5. Tasarım / UI Önerileri

Tasarım **temeli güçlü** (token sistemi, animasyon vokabüleri, gölge skalası). Eksikler uygulama ve kapsama tarafında:

1. **Bileşen kütüphanesi ince.** `components/ui` altında yalnızca 9 primitive var (badge, button, card, dialog, input, skeleton, table, tabs, tooltip). 35 modüllük bir ERP için eksikler: **select, combobox, checkbox/radio, form (validation), date-picker, pagination, drawer/sheet, popover, toast (sonner var ama standardize edilmemiş), data-table (sıralama/filtre/sütun seçimi)**. Bunlar olmadan her yeni sayfa sıfırdan UI icat eder → tutarsızlık.
2. **Veri-yoğun ERP yüzeyleri için data-table.** Finans/procurement/CRM tabloları sıralama, sütun gizleme, sayfalama, satır seçimi ve dışa aktarma istiyor. Tek bir güçlü tablo bileşeni tüm modüllere yayılmalı.
3. **Açık tema (light) cilası.** Token'larda light tema opt-in tanımlı; gerçekte tüm sayfalarda test edilip kontrast/durum renkleri doğrulanmalı (özellikle grafikler ve badge'ler).
4. **Erişilebilirlik (a11y).** WCAG kontrast motoru token üretiminde var — bunu çalışma zamanına taşı: focus ring tutarlılığı, klavye navigasyonu, `aria-*`, dialog focus-trap, prefers-reduced-motion (framer-motion için).
5. **Mobil / responsive.** ERP genelde masaüstü ama en azından dashboard ve onay akışları tablet/mobil için test edilmeli; container 1400px sabit.
6. **Grafik tutarlılığı.** Recharts kullanımı sayfaya göre değişmesin; token renklerine bağlı tek bir "chart theme" yardımcısı (tooltip, grid, eksen stilleri) çıkar.
7. **Boş/yükleniyor/hata durumları.** `empty-state.tsx` ve `skeleton` var; her yeni modül sayfasının bu üç durumu standart şekilde göstermesini zorunlu kıl (deneyim tutarlılığı).
8. **Marka sub-brand'lerini görünür kıl.** CorpOS (bordo), FinOS (mint), çatı (gold) token'ları tanımlı; navigasyon ve üst bar bağlama göre marka rengini yansıtırsa ürün hattı ayrımı netleşir.

---

## 6. Doküman / Süreç Önerileri

- **Audit güncel değil.** `ALPHA_QUANTUM_AUDIT.md` (23 Mayıs) "18 migration / api.py tek router / notification engine yok" diyor; bugün 35 migration, router'lar bölünmüş ve notification engine mevcut. Audit'i yenile ya da "snapshot tarihi" etiketiyle dondur.
- **Tek-nokta-arıza riski.** `TEAM_OWNERS.md`'de tüm roller tek kişide; en azından backup owner ve restore prova takvimi.
- **Backup otomasyonu.** Runbook var, script var, cron/S3 otomasyonu (ROADMAP D3) hâlâ açık — production öncesi kapatılmalı.

---

## 7. Önerilen İlk 5 Hamle (en yüksek kaldıraç)

1. **PostgreSQL + `company_id` FK geçişi** — production'ın önündeki tek en büyük engel.
2. **`ui` bileşen kütüphanesini tamamla (select/form/data-table/pagination)** — sonraki tüm frontend işini hızlandırır.
3. **Tekrarlanabilir "modül sayfası" şablonu + ilk 4 yüksek değerli modül** (Procurement, Finance ledger, Feasibility, AI Copilot).
4. **OAuth2/SSO** — CorpOS+FinOS birleşmesinin ön koşulu.
5. **Async + job kuyruğu** — OCR/rapor/connector işlerini request'ten çıkar.

---

*Not: Bu rapor statik inceleme ve mevcut dokümanlara dayanır; çalışan uygulamada ekran ekran UX denetimi (light tema, a11y, mobil) ayrı bir tasarım turu gerektirir.*
