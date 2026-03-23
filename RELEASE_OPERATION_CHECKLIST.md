# Alpha Quantum - Release Operation Checklist

Tarih: 21 Mart 2026  
Kapsam: Sprint 2.2 (`S-223`, `T-223-1`)

## Release Gate (Zorunlu)

1. Security CI geçişi zorunlu:
   - Workflow: [security-gate.yml](/Users/mustafainan/alpha-quantum/.github/workflows/security-gate.yml)
2. Aşağıdaki komutlar local veya CI ortamında yeşil olmalı:

```bash
./venv/bin/bandit -c security/bandit.yaml -r app -ll
./venv/bin/pip-audit -r requirements.txt
./venv/bin/python -m unittest discover -s tests -v
./venv/bin/python scripts/security_smoke.py
```

## Pre-Release Kontrol Listesi

- [ ] `main/master` branch güncel ve merge koşulları sağlandı
- [ ] Migration planı kontrol edildi (`/api/v1/admin/migrations/status`)
- [ ] Backup alındı (`./scripts/backup_db.sh`)
- [ ] Restore dry-run başarılı (`./scripts/restore_dry_run.sh <backup_file>`)
- [ ] API error budget raporu PASS

## API Error Budget Kontrolü

```bash
./venv/bin/python scripts/api_error_budget_report.py --lookback-hours 24 --target-success-ratio 99.0
```

PASS değilse release bloke edilir.

## Post-Release Kontrol Listesi

- [ ] `/api/v1/health` endpointi 200 dönüyor
- [ ] Kritik auth akışı doğrulandı (`login/refresh/logout`)
- [ ] Audit log akışı aktif
- [ ] İlk 30 dakika hata/latency gözlemi tamamlandı

## Rollback Kriteri

1. P1 incident oluşursa rollback değerlendirmesi anında başlatılır.
2. Auth veya veri bütünlüğü etkisi varsa rollback önceliklendirilir.
3. Rollback sonrası kök neden analizi (RCA) 24 saat içinde tamamlanır.
