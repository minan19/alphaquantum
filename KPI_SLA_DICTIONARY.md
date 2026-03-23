# Alpha Quantum - KPI / SLA Sözlüğü

Tarih: 21 Mart 2026  
Kaynak Story/Task: `S-213`, `T-213-1`, `S-214`, `T-214-1`

## 1) KPI Sözlüğü (Katman Bazlı)

| Katman | KPI Adı | Formül | Veri Kaynağı | Ölçüm Frekansı | Hedef |
|---|---|---|---|---|---|
| Kullanıcı/İstemci | Günlük Görev Tamamlama Oranı | `(Tamamlanan görev / Başlatılan görev) * 100` | Dashboard event log | Günlük | `>=75%` |
| Platform/API | API Başarı Oranı | `(2xx + 3xx çağrı / toplam çağrı) * 100` | API access log + audit log | Saatlik | `>=99.0%` |
| Backend/Veri | Veri Tutarlılık Hata Oranı | `(Tutarsız kayıt / toplam kayıt işlemi) * 100` | DB validation + audit log | Günlük | `<=0.1%` |
| Fiziksel/Donanım | Backup Başarı Oranı | `(Başarılı backup / planlanan backup) * 100` | Backup job log | Günlük | `>=99.5%` |
| Ürün & Çözüm | Paket Adoption Oranı | `(Aktif paket kullanan müşteri / toplam müşteri) * 100` | Ürün kullanım raporu | Haftalık | `>=60%` |
| Dijital Platform | Rapor Üretim Tamamlanma Süresi | `Rapor bitiş zamanı - rapor başlangıç zamanı` | Dashboard job log | Günlük | `p95 <= 60sn` |
| Hizmet | Güvenlik Gate Geçiş Oranı | `(Başarılı pipeline / toplam pipeline) * 100` | CI/CD log | Her release | `>=98%` |

## 2) SLA Olay Sınıfı Matrisi

| Olay Sınıfı | Tanım | İlk Yanıt (Ack) | Geçici Çözüm (Mitigation) | Kalıcı Çözüm (Resolution) | Eskalasyon |
|---|---|---|---|---|---|
| P1 - Kritik | Servis kesintisi, auth/güvenlik ihlali, veri kaybı riski | `<=15dk` | `<=1s` | `<=24s` | CTO + DevSecOps anlık |
| P2 - Yüksek | Kritik fonksiyonlarda ciddi bozulma | `<=30dk` | `<=4s` | `<=48s` | Backend Lead + DevOps |
| P3 - Orta | Kısıtlı etki, alternatif akış mümkün | `<=4s` | `<=1g` | `<=5g` | Ürün + ilgili teknik owner |
| P4 - Düşük | Kozmetik/iyileştirme talepleri | `<=1g` | `<=3g` | Sprint planına alınır | Product backlog |

## 3) Ölçüm Notları

1. Tüm KPI ölçümleri UTC zaman damgası ile kayıt altına alınır.
2. SLA ihlalleri audit log ve incident kaydı ile eşleştirilir.
3. Release öncesi son 7 gün KPI trendi incelenmeden production onayı verilmez.
