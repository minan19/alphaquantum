# Alpha Quantum – Dashboard Senaryo Akış Diyagramı

**Sprint:** 2.3 – Task T-231-2
**Tarih:** 24 Mart 2026
**Owner:** Claude (23martclaude branch)

---

## 1. Giriş ve Token Akışı

```
Kullanıcı → /dashboard
        │
        ▼
  localStorage.aq_token var mı?
        │
   Evet │                   Hayır │
        ▼                         ▼
  GET /api/v1/auth/me       → Login modal göster
  (token doğrula)           → POST /api/v1/auth/login
        │                         │
   401  │ 200                      │ token alınır
        │  │                       │
  Login │  ▼                       └──────────────┐
  yönl. │  UserProfile (role, permissions,        │
        │  company_scopes)                        │
        │          │                              │
        └──────────┴──────────────────────────────┘
                   ▼
           Role-aware dashboard render
```

---

## 2. Admin Senaryosu

```
Admin giriş yapar
    │
    ▼
Tüm bölümler görünür:
  [KPI Özet] [Şirket Kartları] [AI Insights]
  [Market Sinyali] [Finance] [Procurement]
  [Fizibilite] [Uluslararası] [Holding]
  [Connector] [Kullanıcı Yönetimi] [Rol Yönetimi]
  [Audit Log] [Migration Yönetimi]
    │
    ├─→ Simulate butonu: Görünür → POST /api/v1/simulate
    ├─→ Finance yazma: Aktif → POST /api/v1/finance-engine/ledger
    ├─→ Tender oluştur: Aktif → POST /api/v1/tender/generate
    ├─→ Procurement PO: Aktif → POST /api/v1/procurement/requests/{id}/purchase-orders/auto
    ├─→ Ecosystem Activate: Aktif → POST /api/v1/ecosystem/activate/portfolio
    └─→ Kullanıcı ekle/sil: Aktif → POST/DELETE /api/v1/users
```

---

## 3. Manager Senaryosu

```
Manager giriş yapar (company_scopes: ["ABC Holding", "Delta Lojistik"])
    │
    ▼
Görünür bölümler (scope filtreli):
  [KPI Özet*] [Şirket Kartları*] [AI Insights]
  [Market Sinyali] [Finance*] [Procurement*]
  [Fizibilite*] [Uluslararası*] [Holding*]
  [Connector*]
  (* = yalnızca izinli şirketlerin verisi)

  GİZLİ bölümler:
  [Kullanıcı Yönetimi] [Rol Yönetimi]
  [Audit Log] [Migration Yönetimi]
    │
    ├─→ Simulate butonu: Görünür
    ├─→ Finance yazma: Aktif (scope içi şirket için)
    ├─→ Procurement PO: Aktif (scope içi)
    ├─→ Ecosystem Activate: Aktif (scope içi)
    └─→ Kullanıcı yönetimi: GİZLİ (403 olur)

Scope dışı şirket verisi istendiğinde:
    → API 403 döner → "Bu şirkete erişim yetkiniz yok" uyarısı
```

---

## 4. Viewer Senaryosu

```
Viewer giriş yapar
    │
    ▼
Görünür bölümler (sadece okuma):
  [KPI Özet] [Şirket Kartları] [AI Insights]
  [Market Sinyali] [Finance (read-only)]
  [Procurement (liste)] [Fizibilite (liste)]
  [Uluslararası (liste)] [Holding (liste)]
  [Connector (liste)]

  GİZLİ bölümler (tüm yazma aksiyonları):
  [Simulate] [Finance Yazma] [Market Refresh]
  [Tender Oluştur] [Procurement PO/Yeni Talep]
  [Fizibilite Rapor Oluştur] [Uluslararası Proje Oluştur]
  [Holding Onboard] [Connector Yönetimi]
  [Kullanıcı/Rol/Audit/Migration]
    │
    └─→ Yazma buton tıklamasında (varsa): 403 + "Salt okunur erişim"
```

---

## 5. Kritik Aksiyon Akışı (3 Tık Kuralı)

Tüm kritik eylemler en fazla **3 tıkta** tamamlanabilir:

```
[1. Tık] Dashboard bölümüne git (sol menü veya kart)
[2. Tık] Aksiyon butonuna tıkla ("Yeni Talep", "Rapor Oluştur" vb.)
[3. Tık] Formu doldurup "Gönder" → API çağrısı → Sonuç kartı
```

Akış örnekleri:

| Eylem | Tık 1 | Tık 2 | Tık 3 |
|---|---|---|---|
| Procurement talebi aç | Procurement bölümü | "Yeni Talep" butonu | Formu doldur + Gönder |
| Fizibilite raporu oluştur | Fizibilite bölümü | "Rapor Oluştur" butonu | Formu doldur + Gönder |
| Market yenile | Market bölümü | "Yenile" butonu | _(otomatik tamamlanır)_ |
| Ecosystem aktivasyon | Ecosystem bölümü | "Aktive Et" butonu | Parametreleri gir + Gönder |

---

## 6. Hata / Blokaj Akışları

```
API 401 → Token süresi doldu → Otomatik /api/v1/auth/refresh dene
       → Başarısız → Login sayfasına yönlendir

API 403 → İzin yok → Toast uyarı: "Bu işlem için yetkiniz yok"
        → Scope dışı → Toast uyarı: "Bu şirkete erişim yetkiniz yok"

API 422 → Form doğrulama hatası → İlgili alanın altında hata mesajı

API 5xx → Sunucu hatası → "Sistem şu anda yanıt vermiyor, lütfen tekrar deneyin"
         → GET /api/v1/health kontrolü → Servis durumu göster
```

---

## 7. Referans

- Görünürlük kuralları: `docs/ROLE_BASED_DASHBOARD_RULES.md`
- Sprint hedefi: `SPRINT_BACKLOG.md` → S-231, S-232
