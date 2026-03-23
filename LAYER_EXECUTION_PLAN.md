# Alpha Quantum - 7 Katman Uygulama Planı (Phase/Owner/KPI/SLA)

Bu doküman, 7 katmanlı kurumsal mimariyi uygulama backlog'una çevirir.

## 1) Yürütme Matrisi

| Katman | Workstream | Öncelik | Faz | Owner | KPI | SLA/Hedef |
|---|---|---|---|---|---|---|
| Kullanıcı/İstemci | Dashboard bilgi mimarisi, rol bazlı ekran akışları, mobil-ready UI | P1 | Faz 1-2 | Mustafa Inan (Frontend Lead + Product Owner) | Aktif kullanıcı başına günlük görev tamamlama oranı | Kritik kullanıcı akışında p95 render `<2.5sn` |
| Platform/API | API versiyonlama standardı, endpoint sözleşmeleri, rate limit profilleri | P0 | Faz 1 | Mustafa Inan (Backend Lead) | Başarılı API çağrı oranı | `/api/v1/*` uptime `>=99.9%` |
| Backend/Veri | Engine ayrıştırma, DB migration disiplini, audit & data quality kontrolleri | P0 | Faz 1-2 | Mustafa Inan (Backend Lead + Data Engineer) | Veri tutarlılık ihlali sayısı | Kritik veri yazma işlemlerinde hata oranı `<0.1%` |
| Fiziksel/Donanım | Runtime standardı, backup politikası, kapasite ve log retention | P1 | Faz 2 | Mustafa Inan (DevOps Lead) | Kaynak kullanım stabilitesi (CPU/RAM) | Günlük backup başarı oranı `>=99.5%` |
| Ürün & Çözüm | ERP/Fintech/Operasyon paketlerinin hizmet kataloglaştırılması | P0 | Faz 2-3 | Mustafa Inan (Product Manager) | Paket bazlı adoption oranı | Yeni modül rollout süresi `<=2 sprint` |
| Dijital Platform | Canlı grafik, sinyal kartı, kurumsal rapor deneyimi, entegrasyon UX | P1 | Faz 3 | Mustafa Inan (Frontend Lead), UX Lead (Atanacak) | Dashboard etkileşim oranı | Kullanıcı rapor üretim akışı `<60sn` |
| Hizmet | DevSecOps gate, incident response, release governance, destek modeli | P0 | Faz 1-3 | Mustafa Inan (DevSecOps Lead + SRE Lead) | Güvenlik gate pass oranı | P1 olay ilk müdahale süresi `<15dk` |

## 2) Faz Bazlı Teslimatlar

### Faz 1 (Temel Kontrol ve Güvenlik)
- Platform/API:
  - Endpoint sözleşme standardı, auth ve permission kontrolleri sertleştirme
- Backend/Veri:
  - Migration + rollback disiplini, audit tamlığı, kritik path test kapsamı
- Hizmet:
  - CI security gate zorunluluğu (bandit + pip-audit + dynamic smoke)

### Faz 2 (Ölçekleme ve Operasyonel Dayanıklılık)
- Kullanıcı/İstemci:
  - Rol bazlı kullanıcı deneyimi, dashboard kullanılabilirlik iyileştirmeleri
- Fiziksel/Donanım:
  - Backup/restore prova, kapasite ve log stratejisi
- Ürün & Çözüm:
  - ERP-finance modül paketleri ve rollout playbook

### Faz 3 (Gelişmiş Dijital Deneyim ve Kurumsal Servisleşme)
- Dijital Platform:
  - Canlı veri, gelişmiş görselleştirme, yönetici rapor akışları
- Ürün & Çözüm:
  - Global ve kamu-kurum istihbarat paketlerinin iş karar akışına entegrasyonu
- Hizmet:
  - SLA raporlama, operasyonel olgunluk ve governance dashboard

## 3) RACI Özeti

| Alan | Responsible | Accountable | Consulted | Informed |
|---|---|---|---|---|
| API ve Auth güvenliği | Mustafa Inan (Backend Lead) | Mustafa Inan (CTO) | Mustafa Inan (DevSecOps Lead) | Product, QA |
| Veri/migration/audit | Mustafa Inan (Data Engineer) | Mustafa Inan (Backend Lead) | QA, DevSecOps | Product |
| Dashboard ve dijital deneyim | Mustafa Inan (Frontend Lead) | Mustafa Inan (Product Owner) | UX Lead (Atanacak), Backend | Tüm ekip |
| Altyapı ve operasyon | Mustafa Inan (DevOps Lead) | Mustafa Inan (CTO) | Security, Backend | Tüm ekip |
| Ürün paketleme ve rollout | Mustafa Inan (Product Manager) | Mustafa Inan (Product Owner) | Tech Leads | Tüm ekip |

## 3.1 Eskalasyon Basamakları (T-212-1)

1. Operasyonel blokaj veya güvenlik riski owner tarafından aynı gün içinde kayda alınır.
2. 4 saat içinde çözülemeyen P1 etkili işlerde CTO (Mustafa Inan) seviyesine eskalasyon yapılır.
3. 24 saatten uzun süren tüm blokajlar sprint hedefi revizyonu ile Product Owner kararına çıkarılır.
4. Release etkili konularda DevSecOps gate başarısızsa yayın otomatik durdurulur.

## 4) Ölçüm ve Yönetim Ritmi

- Haftalık:
  - Katman KPI trendleri, güvenlik gate sonuçları, açık risk listesi
- Sprint sonu:
  - Faz hedeflerine göre teslimat doğrulaması
- Aylık:
  - SLA uyum raporu, teknik borç ve kapasite gözden geçirme

## 5) Mevcut Durum Etiketi (21 Mart 2026)

- Platform/API: `İleri Seviye`
- Backend/Veri: `İleri Seviye`
- Hizmet: `Orta-İleri`
- Kullanıcı/İstemci: `Orta`
- Dijital Platform: `Orta`
- Ürün & Çözüm: `Orta`
- Fiziksel/Donanım: `Planlama Aşaması`

## 6) Öncelikli Sonraki Adımlar

1. KPI/SLA metriklerini tek dashboard üzerinden yayınlama
2. Faz 1 için zorunlu release checklist'ini CI ile bağlayıcı hale getirme
3. Open roller (UX Lead, QA Lead) için atama yapma

## 7) Owner Referansı

- Resmi owner kaydı: [TEAM_OWNERS.md](/Users/mustafainan/alpha-quantum/TEAM_OWNERS.md)
