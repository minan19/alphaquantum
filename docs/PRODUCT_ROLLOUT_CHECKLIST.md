# Alpha Quantum – Paket Bazlı Rollout / Rollback Checklist Şablonu

**Sprint:** 2.3 – Task T-234-1
**Tarih:** 24 Mart 2026
**Owner:** Claude (23martclaude branch)

---

## ROLLOUT CHECKLIST

### 0. Ön Koşullar (Tüm Paketler İçin Ortak)

- [ ] Branch: `main`'den en güncel kod alındı
- [ ] Security gate geçildi: `bandit`, `pip-audit`, `unittest` (29/29)
- [ ] `git log` ile son commit doğrulandı
- [ ] `.env` / ortam değişkenleri kontrol edildi:
  - [ ] `AQ_JWT_SECRET` ≠ `change-this-secret`
  - [ ] `AQ_ENABLE_DEMO_USERS=false`
  - [ ] `AQ_AUTH_USERS` en az bir kullanıcı tanımlı
- [ ] Veritabanı yedeği alındı: `./scripts/backup_db.sh`
- [ ] Yedek dosyası doğrulandı: `./scripts/restore_dry_run.sh ./backups/<backup_file>.db`

---

### Paket A – ERP Çekirdeği Rollout

- [ ] Migration durumu kontrol edildi: `GET /api/v1/admin/migrations/status`
- [ ] Pending migration'lar uygulandı: `POST /api/v1/admin/migrations/apply`
  - [ ] `001_permissions_matrix`
  - [ ] `004_procurement`
  - [ ] `008_holdings_onboarding`
- [ ] Smoke test:
  - [ ] `GET /api/v1/companies` → 200
  - [ ] `GET /api/v1/inventory-engine/critical` → 200
  - [ ] `POST /api/v1/procurement/requests` (test payload) → 201
  - [ ] `POST /api/v1/holdings` (test payload) → 201
- [ ] Rol bazlı erişim doğrulandı: manager tokeniyle scope dışı şirket → 403
- [ ] Audit log aktif: `GET /api/v1/audit-logs` → kayıtlar görünüyor

---

### Paket B – Fintech & Analitik Rollout

- [ ] Migration uygulandı:
  - [ ] `002_finance_ledger`
  - [ ] `003_market_data_cache`
- [ ] Smoke test:
  - [ ] `GET /api/v1/finance-engine/cashflow` → 200
  - [ ] `GET /api/v1/market/analysis?symbol=AAPL` → 200 (veya offline modu aktif)
  - [ ] `GET /api/v1/global/report` → 200
  - [ ] `POST /api/v1/market/intelligence` (test payload) → 200
- [ ] `AQ_MARKET_OFFLINE` / `AQ_MACRO_OFFLINE` değerleri ortama uygun set edildi
- [ ] Backtest endpoint çalışıyor: `GET /api/v1/market/backtest?symbol=AAPL` → 200

---

### Paket C – Global Intel & Ekosistem Rollout

- [ ] **Paket A rollout tamamlandı** (bağımlılık)
- [ ] Migration uygulandı:
  - [ ] `005_feasibility_reports`
  - [ ] `006_international_projects`
  - [ ] `007_user_company_scopes`
  - [ ] `009_connectors_and_sync_queue`
  - [ ] `010_connector_sync_retry_dlq`
  - [ ] `011_connector_worker_leases`
- [ ] Smoke test:
  - [ ] `POST /api/v1/feasibility/report` (test payload) → 201
  - [ ] `POST /api/v1/international/projects` (test payload) → 201
  - [ ] `POST /api/v1/ecosystem/activate/portfolio` (single mode) → 200
  - [ ] `POST /api/v1/connectors` (test payload) → 201
  - [ ] `GET /api/v1/connectors/health/summary` → 200
- [ ] Connector worker yapılandırması:
  - [ ] `AQ_CONNECTOR_WORKER_ENABLED` ortama göre ayarlandı
  - [ ] Leader lock aktif: `AQ_CONNECTOR_WORKER_LEADER_LOCK_ENABLED=true`
- [ ] Company scope izolasyonu test edildi: scoped manager → scope dışı ecosystem → 403

---

### Son Adımlar (Tüm Paketler)

- [ ] `GET /api/v1/health` → `status: ok`, `version` doğru
- [ ] Error budget raporu üretildi: `python scripts/api_error_budget_report.py --lookback-hours 1`
- [ ] Release operation checklist tamamlandı: `RELEASE_OPERATION_CHECKLIST.md`
- [ ] Değişiklik owner'a bildirildi (Mustafa Inan)

---

## ROLLBACK CHECKLIST

### Acil Rollback Kararı Kriterleri

Aşağıdakilerden biri oluşursa **HEMEN rollback başlatılır:**

- Smoke testlerden herhangi biri başarısız
- `GET /api/v1/health` → `status: error` veya 5xx
- Auth/login endpoint çalışmıyor
- Veritabanı migration hata verdi ve otomatik geri alınamadı
- Güvenlik gate geçilemedi (bandit veya pip-audit red)

---

### Rollback Adımları

#### Uygulama Rollback
- [ ] Migration geri alındı: `POST /api/v1/admin/migrations/rollback`
  - Kaç adım geri alınacak `steps` parametresiyle belirt
- [ ] Önceki sürüm kod checkout: `git checkout <previous_commit>`
- [ ] Uygulama yeniden başlatıldı: `uvicorn main:app --reload`
- [ ] `GET /api/v1/health` → 200 doğrulandı

#### Veritabanı Rollback (Kritik)
- [ ] Uygulama durduruldu
- [ ] Yedekten geri yüklendi: `./scripts/restore_dry_run.sh ./backups/<backup_file>.db`
  - Dry-run geçtikten sonra gerçek restore yapıldı
- [ ] Migration durumu yeniden kontrol edildi
- [ ] Uygulama yeniden başlatıldı

#### Doğrulama
- [ ] `GET /api/v1/health` → 200
- [ ] `GET /api/v1/admin/migrations/status` → beklenen migration versiyonu
- [ ] Temel smoke testler geçti (GET /companies, /auth/me, /health)
- [ ] Audit log: rollback kaydı oluştu

#### Olay Kaydı
- [ ] Olay tarihi ve nedenini `GOVERNANCE_REVIEW_NOTE_<YYYY-MM-DD>.md` dosyasına yaz
- [ ] Owner (Mustafa Inan) bilgilendirmesi yapıldı
- [ ] Sonraki adım ve düzeltme planı belirlendi

---

## Referans

- Paket bağımlılıkları: `docs/PRODUCT_PACKAGE_MATRIX.md`
- Backup/restore runbook: `BACKUP_RESTORE_RUNBOOK.md`
- Release checklist: `RELEASE_OPERATION_CHECKLIST.md`
- Sprint: `SPRINT_BACKLOG.md` → S-234
