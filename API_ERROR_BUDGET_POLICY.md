# Alpha Quantum - API Error Budget Policy

Tarih: 21 Mart 2026  
Kapsam: Sprint 2.2 (`S-224`, `T-224-1`)

## SLO Tanımı

- Kapsam: `/api/v1/*` endpointleri
- Ölçüm penceresi: Son 24 saat (varsayılan)
- Hedef başarı oranı: `>=99.0%`
- Error budget: `<=1.0%`

## Ölçüm Scripti

```bash
./venv/bin/python scripts/api_error_budget_report.py --lookback-hours 24 --target-success-ratio 99.0
```

## Durum Yorumu

- `PASS`: Başarı oranı hedefi karşılandı, release devam edebilir.
- `FAIL`: Hedef altında, release bloke edilir ve incident değerlendirmesi başlatılır.

## Örnek Çıktı

```text
ERROR_BUDGET_REPORT status=PASS lookback_hours=24 total=820 success_count=815 server_error_count=2 success_ratio=99.39% target=99.00% budget_used=0.61% budget_allowed=1.00%
```

## Operasyon Kuralları

1. Üst üste 2 ölçümde `FAIL` alınırsa P2 incident açılır.
2. `success_ratio < 98.0%` ise doğrudan P1 olarak eskale edilir.
3. Haftalık trend raporu sprint review çıktısına eklenir.
