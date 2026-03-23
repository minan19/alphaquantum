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

| Story ID | Epic | Story | Owner | Kabul Kriteri |
|---|---|---|---|---|
| S-231 | E-205 | Rol bazlı dashboard akışları netleşir | Frontend + UX | Admin/Manager/Viewer için akışlar ayrı |
| S-232 | E-205 | Kritik kartlar için kullanılabilirlik revizyonu yapılır | Frontend | Kritik eylemler 3 tık altında tamamlanır |
| S-233 | E-206 | ERP/Fintech/Global Intel ürün paketi tanımı çıkarılır | Product | Paket kapsam ve bağımlılıklar net |
| S-234 | E-206 | Paket bazlı rollout checklist hazırlanır | Product + Backend | Her paket için rollout/rollback adımı var |

| Task ID | Story | Task | Tahmin |
|---|---|---|---|
| T-231-1 | S-231 | Rol bazlı menü görünürlük kurallarını dokümante et | 0.5g |
| T-231-2 | S-231 | Dashboard senaryo akış diyagramı ekle | 1g |
| T-232-1 | S-232 | Kritik aksiyon kartlarını öncelik sırasına göre düzenle | 1g |
| T-233-1 | S-233 | Ürün paket matrisi (modül, değer, bağımlılık) yaz | 1g |
| T-234-1 | S-234 | Rollout/rollback checklist şablonu oluştur | 0.5g |

## Faz 3 Hazırlık Backlog'u (Ön Kuyruk)

| Story ID | Epic | Story | Öncelik | Not |
|---|---|---|---|---|
| S-311 | E-301 | Canlı grafik + sinyal + profesyonel rapor akışını tek ekranda birleştir | P1 | Faz 3 başlangıç işi |
| S-312 | E-301 | Yönetici rapor zamanlama ve otomatik dağıtım | P1 | Hizmet katmanı ile entegre |
| S-313 | E-301 | Çoklu kurum ve ülke bazlı karşılaştırma paneli | P1 | Ürün&Çözüm + Dijital Platform ortak |

## Definition of Done

1. Story kabul kriteri dokümante edilmiş ve karşılanmış olacak.
2. Güvenlik gate (`bandit`, `pip-audit`, `unittest`, `security_smoke`) yeşil olacak.
3. İlgili doküman linkleri README/Blueprint içinde güncel olacak.
4. Audit edilebilir değişiklik notu ve owner bilgisi yazılmış olacak.

## 21 Mart 2026 İlerleme Notu

- Sprint 2.1 çekirdek işleri tamamlandı (`5/5 task done`).
- Sprint 2.2 çekirdek işleri tamamlandı (`5/5 task done`).
- Sonraki yürütme odağı: Sprint 2.3 (ürün paketleme + UX iyileştirme).
