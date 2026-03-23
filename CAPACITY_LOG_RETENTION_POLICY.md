# Alpha Quantum - Capacity & Log Retention Policy

Tarih: 21 Mart 2026  
Kapsam: Sprint 2.2 (`S-222`, `T-222-1`)

## 1) Kapasite Eşik Politikası

| Kaynak | Uyarı Eşiği | Kritik Eşik | Aksiyon |
|---|---|---|---|
| CPU (ortalama, 5dk) | `>=70%` | `>=85%` | Otomatik alarm + kapasite analizi |
| RAM (kullanım) | `>=75%` | `>=90%` | Memory profiling + yük dengeleme |
| Disk (kullanım) | `>=70%` | `>=85%` | Log temizleme + kapasite genişletme |
| DB dosya büyümesi (haftalık) | `>=15%` artış | `>=25%` artış | Veri arşivleme planı devreye alınır |
| API p95 latency | `>=500ms` | `>=900ms` | Uygulama/DB performans incelemesi |

## 2) Log Retention Politikası

| Log Türü | Saklama Süresi | Arşiv | Erişim Seviyesi |
|---|---|---|---|
| Uygulama logları | 30 gün | 90 güne kadar sıkıştırılmış arşiv | DevOps + Backend |
| Audit logları | 180 gün | 365 güne kadar arşiv | Security + Audit + Admin |
| CI/CD logları | 90 gün | 180 güne kadar arşiv | DevSecOps + Backend |
| Incident logları | 365 gün | Uzun dönem arşiv | CTO + Security |

## 3) İzleme Frekansı

1. Günlük: CPU/RAM/Disk özet kontrolü
2. Haftalık: Kapasite trend raporu + log büyüme analizi
3. Aylık: Eşik güncelleme ve maliyet-optimizasyon gözden geçirmesi

## 4) İhlal Yönetimi

1. Kritik eşik aşımı -> anlık alarm + owner bilgilendirmesi
2. 2 saat içinde normalleşmeyen durum -> CTO eskalasyonu
3. Arka arkaya 3 gün uyarı eşiği aşımı -> kapasite artırımı planı zorunlu
