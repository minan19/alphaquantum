# A4: KVKK Uyum API Tasarımı

**Sprint:** A4 — KVKK Uyum (data export + deletion + consent lifecycle)
**Hedef:** KVKK (Kişisel Verilerin Korunması Kanunu) madde 11 ve madde 13
gereği veri sahibi haklarını teknik olarak sağlayan API'ler.
**Yasal risk:** Bu olmadan KVK Kurumu cezası 50.000 - 1.000.000 TL aralığında.

## Madde 11 — Veri Sahibinin Hakları

| Hak | API yöntemi | Endpoint | İzin |
|---|---|---|---|
| (a) İşleniyor mu öğrenme | GET | `/api/v1/me/data-processing` | Authenticated |
| (b) İşleniyor ise bilgi talep | GET | `/api/v1/me/data-processing` | Authenticated |
| (c) Amacın bilinmesi | GET | `/api/v1/me/data-processing-activities` | Authenticated (static) |
| (ç) Aktarıldığı üçüncü kişiler | GET | `/api/v1/me/data-sharing` | Authenticated |
| (d) Eksik / yanlış işlenmişse düzeltme | PATCH | `/api/v1/me/profile` | Authenticated |
| (e) Silme / yok etme | DELETE | `/api/v1/me/data` | Authenticated |
| (f) Düzeltme/silme bildirimi 3. kişilere | (otomatik) | (audit log) | — |
| (g) Otomatik karar itiraz | POST | `/api/v1/me/automated-decisions/objection` | Authenticated |
| (ğ) Zararın giderilmesi | POST | `/api/v1/me/data-breach-claim` | Authenticated |

## Migration 022 — Yeni Tablolar

```sql
-- account_deletion_requests: silme talepleri kuyruğu
CREATE TABLE account_deletion_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    requested_at INTEGER NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','approved','rejected','completed')),
    decision_at INTEGER,
    decision_by INTEGER REFERENCES users(id),
    decision_note TEXT NOT NULL DEFAULT ''
);

-- security_incidents: KVKK ihlal raporları
CREATE TABLE security_incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_type TEXT NOT NULL,  -- 'unauthorized_access' | 'data_loss' | ...
    severity TEXT NOT NULL,        -- 'low' | 'medium' | 'high' | 'critical'
    affected_user_id INTEGER REFERENCES users(id),
    affected_record_count INTEGER NOT NULL DEFAULT 0,
    description TEXT NOT NULL,
    reported_by INTEGER REFERENCES users(id),
    reported_at INTEGER NOT NULL,
    kvkk_notification_required INTEGER NOT NULL DEFAULT 0,
    kvkk_notification_sent_at INTEGER,
    resolution_status TEXT NOT NULL DEFAULT 'open',
    resolved_at INTEGER
);

-- users tablosuna consent + son erişim
ALTER TABLE users ADD COLUMN kvkk_consent_at INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN kvkk_consent_version TEXT NOT NULL DEFAULT 'v1';
ALTER TABLE users ADD COLUMN last_data_export_at INTEGER;
ALTER TABLE users ADD COLUMN last_data_access_at INTEGER;
```

## API Endpoints (8 yeni)

### Veri Erişim
- `GET /api/v1/me/data` — kullanıcının kendi datasının JSON export'u
- `GET /api/v1/me/data-processing` — aktif data işleme özet
- `GET /api/v1/me/data-processing-activities` — KVKK aydınlatma metni (statik)
- `GET /api/v1/me/data-sharing` — 3. taraflara aktarım durumu

### Veri Yönetimi
- `PATCH /api/v1/me/profile` — kişisel bilgi düzeltme (kendi)
- `DELETE /api/v1/me/data` — silme talebi başlat (status=pending)
- `POST /api/v1/me/consent` — KVKK onay güncelle (versiyon ile)
- `POST /api/v1/me/data-breach-claim` — KVKK ihlali şikayet kaydı

### Admin (KVKK sorumlu kişi için)
- `GET /api/v1/admin/deletion-requests` — bekleyen silme talepleri
- `POST /api/v1/admin/deletion-requests/{id}/decide` — onayla/reddet
- `GET /api/v1/admin/security-incidents` — KVKK ihlal raporları
- `POST /api/v1/admin/security-incidents` — yeni ihlal kaydı

## Implementation Plan

1. ✅ Tasarım dokümanı (bu dosya)
2. ⏳ migration 022_kvkk_compliance.up.sql + .down.sql
3. ⏳ app/kvkk_repository.py (KVKKRepository)
4. ⏳ app/engines/kvkk_engine.py (KVKKEngine — data export, deletion request, consent)
5. ⏳ app/models.py içine KVKK Pydantic modelleri
6. ⏳ API endpoints (8 + 4 admin = 12 endpoint)
7. ⏳ Tests — kullanıcı data export, silme talebi, consent versiyonlama
8. ⏳ docs/modules/finos/KVKK_COMPLIANCE.md — son kullanıcı için açıklama

## Test plan

```python
class KVKKDataExportTests:
    def test_user_can_export_own_data(self):  # GET /me/data
    def test_export_includes_all_related_records(self):
    def test_export_excludes_other_users_data(self):
    def test_audit_log_records_export(self):

class KVKKDeletionTests:
    def test_user_can_request_own_deletion(self):  # DELETE /me/data
    def test_deletion_creates_pending_request(self):
    def test_admin_can_approve_deletion(self):
    def test_approved_deletion_anonymizes_records(self):
    def test_rejected_request_keeps_data(self):

class KVKKConsentTests:
    def test_consent_version_tracked(self):
    def test_consent_update_audit_logged(self):

class KVKKBreachTests:
    def test_breach_claim_creates_security_incident(self):
    def test_critical_incidents_flag_kvkk_notification(self):
```

## Riskler

1. **Anonymize vs Delete:** KVKK silme ≠ DB DELETE. Bazı veriler audit/yasal
   sebeplerle 5 yıl saklanır (KVKK madde 7). Çözüm: soft delete + PII alanlarını
   anonymize et (full_name → "Anonim Kullanıcı", email → null, vs.).
2. **Cascade etkisi:** Bir user silinince invoice'lar, task'lar, audit log'lar
   ne olacak? Bizim yaklaşım: FK ON DELETE SET NULL + PII anonymize.
3. **Performans:** /me/data endpoint'i tüm tabloları tarayabilir. Limit + paginate.
4. **Audit:** Her KVKK işlemi audit_log'a yazılmalı (kim, ne zaman, neden).
