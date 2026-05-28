"""Alpha Quantum API — legacy router shell.

A5 strangler-fig migration sonucunda bu dosya neredeyse boş kaldı.
Tüm endpoint'ler `app/routers/<domain>.py` modüllerine taşındı:

- A5.1  _deps.py            (helper accessors)
- A5.2  schedule.py         (4 endpoint, S-312)
- A5.3  auth.py             (16 endpoint, auth + RBAC)
- A5.4  crm.py              (10 endpoint, S-321 + S-333 + S-343 consent)
- A5.5  tasks.py            (4 endpoint, S-322)
- A5.6  collections.py      (7 endpoint, S-323 + S-331 + S-341)
- A5.7  finance.py          (12 endpoint, S-332 + finance engine)
- A5.8  holdings.py         (10 endpoint, holdings + international + ecosystem)
- A5.9  market.py           (11 endpoint, market + global_intel + public_intel)
- A5.10 connectors.py       (9 endpoint, connectors + sync jobs)
- A5.11 procurement.py      (13 endpoint, procurement + feasibility + tender)
- A5.12 notifications.py    (7 endpoint, S-334 + S-343 dispatch)
- A5.12 financial_instruments.py (5 endpoint, S-342)
- A5.13 admin.py            (6 endpoint, migrations + audit)
- A5.13 reports.py          (4 endpoint, signed file exports)
- A5.13 dashboard.py        (7 endpoint, JSON snapshots + legacy HTML UI)
- A5.13 system.py           (8 endpoint, health + legacy + simulation)

Toplam: 133 endpoint, 16 router modülü. Bu dosya artık sadece app/__init__.py
tarafından beklenen `router` symbol'unu sağlar (geçiş döneminde include
edilmeye devam ediyor — boş routes değişiklik gerektirmez).

Gelecekte: app/__init__.py'dan `from app.api import router` kaldırılabilir.
"""
from __future__ import annotations

from fastapi import APIRouter


# Legacy router — empty. Tüm endpoint'ler app/routers/<domain>.py'a taşındı.
# app/__init__.py geçiş döneminde hâlâ include(router) çağırır; boş bir
# APIRouter zarar vermez.
router = APIRouter()
