# Alpha Quantum - Backup / Restore Runbook

Tarih: 21 Mart 2026  
Kapsam: Sprint 2.2 (`S-221`, `T-221-1`, `T-221-2`)

## Amaç

- SQLite veritabanı için standart backup akışı sağlamak
- Restore dry-run ile geri dönüş uygulanabilirliğini doğrulamak

## Ön Koşullar

- `sqlite3` yüklü olmalı
- Proje kök dizininde çalışılmalı
- Veritabanı dosyası erişilebilir olmalı (`AQ_DATABASE_PATH` veya varsayılan `alpha_quantum.db`)

## 1) Backup Alma

Komut:

```bash
./scripts/backup_db.sh
```

Özel backup dizini ile:

```bash
./scripts/backup_db.sh ./backups
```

Beklenen çıktı örneği:

```text
BACKUP_OK file=/path/backups/alpha_quantum_20260321_170500.db source=/path/alpha_quantum.db
```

## 2) Restore Dry-Run

Komut:

```bash
./scripts/restore_dry_run.sh ./backups/<backup_file>.db
```

Opsiyonel dry-run hedef dosyası:

```bash
./scripts/restore_dry_run.sh ./backups/<backup_file>.db ./tmp/restore_dry_run.db
```

Beklenen çıktı örneği:

```text
RESTORE_DRY_RUN_OK db=/path/tmp/restore_dry_run.db tables=15 users_table=1 migrations_table=1
```

## 3) Doğrulama Kontrol Listesi

1. Backup dosyası oluştu mu?
2. Restore dry-run başarılı mı?
3. `users` ve `schema_migrations` tabloları mevcut mu?
4. Backup ve dry-run çıktıları operasyon kaydına işlendi mi?

## 4) Sıklık

- Günlük otomatik backup önerilir
- Haftalık restore dry-run zorunlu önerilir

## 5) Operasyonel Notlar

- Backup dosyaları yetkisiz erişime kapalı dizinde tutulmalı
- En son çalışan backup doğrulanmadan release onayı verilmemeli
- Kritik release öncesi aynı gün ek backup alınmalı
