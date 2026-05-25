"""Alpha Quantum API router modules.

Bu paket, app/api.py'nin domain-bazlı router'lara ayrıştırılma yolculuğunu
barındırır. Modülerizasyon "strangler fig" pattern ile yapılıyor:

1. _deps.py — tüm helper fonksiyonlar (engine accessors, scope checks, audit)
2. <domain>.py — her domain için (auth, crm, finance, vb.) ayrı router
3. app/api.py — geçiş döneminde geri kalanı tutar; sonunda sadece include eder

Migration sırası (S-371+):
  ✓ A5.1: _deps.py extraction
  ⏳ A5.2: schedule + reports router (en küçük, deneme)
  ⏳ A5.3: auth router (16 endpoint)
  ⏳ A5.4: crm router (10 endpoint)
  ⏳ A5.5: collections + financial_instruments router (S-323/342/343)
  ⏳ A5.6: notifications + delivery_log router (S-334/343)
  ⏳ A5.7: dashboard + comparison router (S-311/313)
  ⏳ A5.8: finance router (11 endpoint)
  ⏳ A5.9: procurement + feasibility + tender router
  ⏳ A5.10: holdings + international + ecosystem router
  ⏳ A5.11: market + connectors router
  ⏳ A5.12: admin + audit router
  ⏳ A5.13: api.py boşaltma (sadece include + legacy redirect'ler)
"""
