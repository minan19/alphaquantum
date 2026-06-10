# Alpha Quantum - Backup / Restore Runbook

Son güncelleme: 10 Haziran 2026
Kapsam: Sprint 2.2 (`S-221`, `T-221-1`, `T-221-2`) + Wave 2 (`D3`)

## Amaç

- SQLite veritabanı için standart, otomatik, retention'lı backup akışı sağlamak.
- Restore dry-run ile geri dönüş uygulanabilirliğini doğrulamak.
- Cron + opsiyonel S3 hedefi ile üretim seviyesi felaket kurtarma sağlamak (D3).

## Ön Koşullar

- `sqlite3` ve `gzip` PATH'te olmalı
- Proje kök dizininde çalışılmalı
- Veritabanı dosyası erişilebilir olmalı (`AQ_DATABASE_PATH` veya varsayılan `alpha_quantum.db`)
- S3 yedekleme için: `aws` CLI + IAM credentials (env / profile)

## 1) Backup Alma

### Tek seferlik

```bash
./scripts/backup_db.sh                  # varsayılan ./backups/{daily,weekly}/
./scripts/backup_db.sh /custom/path     # özel dizin
```

### Çıktı örneği

```text
2026-06-10T07:44:41Z | BACKUP_START source=/.../alpha_quantum.db dest=/.../daily/alpha_quantum_20260610_074441.db
2026-06-10T07:44:41Z | BACKUP_OK    file=/.../daily/alpha_quantum_20260610_074441.db.gz bytes=25182
2026-06-10T07:44:41Z | BACKUP_DONE
```

### Özellikler

- **Hot backup**: `sqlite3 .backup` API'si — WAL-safe, lock yok.
- **gzip -9** sıkıştırma — DB'yi ~%85 küçültür.
- **Retention rotation** — `AQ_BACKUP_KEEP_DAILY` (varsayılan 7) + `AQ_BACKUP_KEEP_WEEKLY` (varsayılan 4).
- **Haftalık snapshot** Pazar günü otomatik (UTC).
- **Bash 3.2 uyumlu** — macOS native bash desteklenir.
- **İdempotent** — aynı dakika içinde tekrar çalıştırılabilir (timestamp saniye düzeyinde).

## 2) Environment Değişkenleri

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `AQ_DATABASE_PATH` | `./alpha_quantum.db` | Kaynak DB |
| `AQ_BACKUP_KEEP_DAILY` | `7` | Saklanacak günlük backup sayısı |
| `AQ_BACKUP_KEEP_WEEKLY` | `4` | Saklanacak haftalık backup sayısı |
| `AQ_BACKUP_S3_BUCKET` | _(boş)_ | Boş bırakılırsa S3 atlanır |
| `AQ_BACKUP_S3_PREFIX` | `alpha-quantum/db/` | S3 key prefix |
| `AQ_BACKUP_AWS_PROFILE` | _(boş)_ | İsteğe bağlı AWS CLI profile |

## 3) Cron Yapılandırması

### Günlük backup (sunucu UTC saatiyle 03:15)

```cron
15 3 * * * cd /opt/alpha-quantum && AQ_BACKUP_S3_BUCKET=alpha-quantum-backups ./scripts/backup_db.sh >> /var/log/aq-backup.log 2>&1
```

### Crontab kurulumu

```bash
crontab -e
# Yukarıdaki satırı yapıştır, kaydet.

# Doğrula:
crontab -l | grep backup_db
```

### Log rotation (systemd journald yoksa)

`/etc/logrotate.d/aq-backup`:
```
/var/log/aq-backup.log {
    weekly
    rotate 12
    compress
    missingok
    notifempty
}
```

## 4) Exit Code'lar

| Code | Anlam |
|---|---|
| `0` | Backup (+ opsiyonel S3 upload) başarılı |
| `1` | Environment / dependency hatası (sqlite3, gzip, DB dosyası yok) |
| `2` | Backup başarısız (sqlite hatası / gzip hatası) |
| `3` | Backup tamam ama S3 upload başarısız (dosya local'de) |

## 5) Restore Dry-Run

```bash
./scripts/restore_dry_run.sh ./backups/daily/alpha_quantum_<timestamp>.db.gz
```

Sıkıştırılmış dosyadan restore:

```bash
gunzip -k ./backups/daily/alpha_quantum_<timestamp>.db.gz
./scripts/restore_dry_run.sh ./backups/daily/alpha_quantum_<timestamp>.db ./tmp/restore_dry_run.db
```

Beklenen çıktı:

```text
RESTORE_DRY_RUN_OK db=./tmp/restore_dry_run.db tables=58 users_table=1 migrations_table=1
```

## 6) Felaket Kurtarma (DR) Senaryosu

### Senaryo: Production DB kaybedildi

1. **Stop** API server:
   ```bash
   systemctl stop alpha-quantum
   ```
2. **En yeni backup'ı bul** (local ya da S3):
   ```bash
   ls -1t /opt/alpha-quantum/backups/daily/ | head -1
   # S3:
   aws s3 ls s3://alpha-quantum-backups/alpha-quantum/db/ | sort | tail -1
   ```
3. **İndir + decompress**:
   ```bash
   aws s3 cp s3://alpha-quantum-backups/alpha-quantum/db/<file>.db.gz /tmp/
   gunzip /tmp/<file>.db.gz
   ```
4. **Doğrula** (smoke):
   ```bash
   sqlite3 /tmp/<file>.db "SELECT COUNT(*) FROM schema_migrations"  # ≥ 33 olmalı
   sqlite3 /tmp/<file>.db "PRAGMA integrity_check"                  # "ok" döndürmeli
   ```
5. **Replace** + restart:
   ```bash
   cp /opt/alpha-quantum/alpha_quantum.db /opt/alpha-quantum/alpha_quantum.db.broken
   mv /tmp/<file>.db /opt/alpha-quantum/alpha_quantum.db
   systemctl start alpha-quantum
   ```
6. **Verify** API health:
   ```bash
   curl -fsS http://localhost:8000/api/v1/health
   ```

### RPO / RTO Hedefleri

| Metrik | Hedef | Gerçek (10 Haziran 2026) |
|---|---|---|
| RPO (max veri kaybı) | ≤ 24 saat | 24 saat (günlük backup) |
| RTO (max kesinti) | ≤ 1 saat | ~15 dk (S3 → local restore) |

## 7) Doğrulama Kontrol Listesi

1. ✅ Backup dosyası oluştu mu? (`ls -la backups/daily/`)
2. ✅ Gzip dosyası ≥ 5 KB mı? (`du -h backups/daily/*.db.gz`)
3. ✅ Restore dry-run başarılı mı? (`./scripts/restore_dry_run.sh ...`)
4. ✅ `users` ve `schema_migrations` tabloları mevcut mu?
5. ✅ Cron çalışıyor mu? (`crontab -l && tail /var/log/aq-backup.log`)
6. ✅ S3 hedef erişilebilir mi? (`aws s3 ls s3://<bucket>/`)
7. ✅ Restore prova ayda 1 yapıldı mı?

## 8) Sıklık

- **Günlük** otomatik backup — zorunlu
- **Haftalık** snapshot (Pazar UTC) — zorunlu
- **Haftalık** restore dry-run — zorunlu
- **Aylık** full DR prova (S3 → temiz host) — önerilen

## 9) Operasyonel Notlar

- Backup dosyaları sadece deployment user'ı tarafından okunabilir (`chmod 600`).
- Cron çalıştırılan user'ın `AQ_BACKUP_AWS_PROFILE` veya `~/.aws/credentials` erişimi olmalı.
- S3 bucket'ta versioning + lifecycle policy önerilir (90 gün STANDARD_IA → 365 gün GLACIER).
- En son çalışan backup doğrulanmadan release onayı verilmemeli.
- Kritik release öncesi aynı gün ek backup alınmalı.

## 10) İzleme

Backup başarısız olursa cron stderr → log dosyasına yazılır. Önerilen alert:

```bash
# /etc/aq/backup-alert.sh
#!/usr/bin/env bash
LAST=$(stat -c %Y /opt/alpha-quantum/backups/daily/*.db.gz 2>/dev/null | sort -n | tail -1)
NOW=$(date +%s)
AGE_HOURS=$(( (NOW - LAST) / 3600 ))
if [[ $AGE_HOURS -gt 36 ]]; then
  curl -X POST "$SLACK_WEBHOOK" -d "{\"text\":\"⚠️ Alpha Quantum backup is $AGE_HOURS hours old!\"}"
fi
```

Cron: `0 12 * * * /etc/aq/backup-alert.sh`
