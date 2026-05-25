# Alpha Quantum – Kritik Aksiyon Kartları Öncelik Sıralaması

**Sprint:** 2.3 – Task T-232-1
**Tarih:** 24 Mart 2026
**Owner:** Claude (23martclaude branch)

---

## 1. Öncelik Tanımı

Kritik aksiyon kartları, kullanıcının iş değeri üretmesi için en sık ihtiyaç duyduğu ve en fazla etkiye sahip olan işlemlerdir. Sıralama kriteri: **kullanım sıklığı × iş etkisi × risk düzeyi**.

---

## 2. Admin Kritik Aksiyon Sıralaması

| Sıra | Aksiyon | Bölüm | Endpoint | Risk |
|---|---|---|---|---|
| 1 | Sistem sağlık kontrolü | Health | `GET /api/v1/health` | Düşük |
| 2 | Audit log görüntüle | Güvenlik | `GET /api/v1/audit-logs` | Düşük |
| 3 | Migration uygula | Sistem | `POST /api/v1/admin/migrations/apply` | Yüksek |
| 4 | Kullanıcı oluştur / devre dışı bırak | Kullanıcı Yönetimi | `POST/PATCH /api/v1/users` | Orta |
| 5 | Rol izni güncelle | Rol Yönetimi | `PUT /api/v1/roles/{id}/permissions` | Yüksek |
| 6 | Ecosystem portföy aktivasyon | Ekosistem | `POST /api/v1/ecosystem/activate/portfolio` | Yüksek |
| 7 | Holding onboard | Holding | `POST /api/v1/holdings/{id}/onboard` | Orta |

---

## 3. Manager Kritik Aksiyon Sıralaması

| Sıra | Aksiyon | Bölüm | Endpoint | Risk |
|---|---|---|---|---|
| 1 | Procurement talebi aç | Satınalma | `POST /api/v1/procurement/requests` | Düşük |
| 2 | Vendor teklif değerlendirme | Satınalma | `GET /api/v1/procurement/requests/{id}/evaluation` | Düşük |
| 3 | Purchase order oluştur | Satınalma | `POST /api/v1/procurement/requests/{id}/purchase-orders/auto` | Orta |
| 4 | Fizibilite raporu oluştur | Fizibilite | `POST /api/v1/feasibility/report` | Düşük |
| 5 | Uluslararası proje başlat | Uluslararası | `POST /api/v1/international/projects` | Düşük |
| 6 | Ecosystem tek şirket aktivasyon | Ekosistem | `POST /api/v1/ecosystem/activate/portfolio` | Orta |
| 7 | Finance ledger girişi | Finans | `POST /api/v1/finance-engine/ledger` | Düşük |
| 8 | Tender dossier oluştur | Tender | `POST /api/v1/tender/generate` | Düşük |
| 9 | Market yenile | Piyasa | `POST /api/v1/market/refresh` | Düşük |

---

## 4. Viewer Kritik Aksiyon Sıralaması

| Sıra | Aksiyon | Bölüm | Endpoint |
|---|---|---|---|
| 1 | Şirket listesi ve KPI özeti | Dashboard | `GET /api/v1/summary` |
| 2 | AI insights görüntüle | Dashboard | `GET /api/v1/insights` |
| 3 | Finance cashflow görüntüle | Finans | `GET /api/v1/finance-engine/cashflow` |
| 4 | Procurement talep listesi | Satınalma | `GET /api/v1/procurement/requests` |
| 5 | Fizibilite rapor listesi | Fizibilite | `GET /api/v1/feasibility/reports` |
| 6 | Piyasa analizi görüntüle | Piyasa | `GET /api/v1/market/analysis` |
| 7 | Global rapor görüntüle | Global | `GET /api/v1/global/report` |

---

## 5. Kart Tasarım Kuralları (UI Uygulama Rehberi)

### 5.1 Yüksek Riskli Aksiyonlar
- Kırmızı çerçeve (`--critical` rengi)
- "Onaylıyor musunuz?" modal zorunlu
- Audit log girişi otomatik oluşturulur
- Örnekler: Migration apply, rol izni güncelleme, holding onboard

### 5.2 Orta Riskli Aksiyonlar
- Turuncu/sarı accent
- Tek tık onay toast ("Gönderiliyor…" spinner)
- Örnekler: Purchase order, ecosystem activate, kullanıcı devre dışı bırak

### 5.3 Düşük Riskli Aksiyonlar
- Standart `--accent` (cyan) rengi
- Doğrudan POST, sonuç kartı göster
- Örnekler: Fizibilite raporu, ledger girişi, market yenile

---

## 6. 3 Tık Uyumluluk Kontrolü

| Aksiyon | Mevcut Tık Sayısı | Hedef | Aksiyon |
|---|---|---|---|
| Procurement talebi aç | 2 | ≤3 | ✅ Uyumlu |
| Fizibilite raporu oluştur | 2 | ≤3 | ✅ Uyumlu |
| Ecosystem activate (multi-company) | 3 | ≤3 | ✅ Uyumlu |
| Migration apply | 3 (+ onay modal) | ≤3 | ✅ Kabul edilebilir (yüksek risk) |
| Rol izni güncelleme | 4 | ≤3 | ⚠️ İyileştirilmeli (S-232 kapsamı) |
| Connector sync job oluştur | 4 | ≤3 | ⚠️ İyileştirilmeli |

### Gerekli İyileştirmeler (S-232)
1. **Rol izni güncelleme:** Rol listesi → izin grid → inline kaydet (3 tık'a indir)
2. **Connector sync:** Connector kartından tek tıkla "Sync Başlat" butonu ekle

---

## 7. Referans

- Dashboard görünürlük matrisi: `docs/ROLE_BASED_DASHBOARD_RULES.md`
- Akış diyagramı: `docs/DASHBOARD_FLOW_DIAGRAM.md`
- Sprint: `SPRINT_BACKLOG.md` → S-232
