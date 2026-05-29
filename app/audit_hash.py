"""G+4: Audit hash chain — bağımsız denetçi-grade immutability.

## Problem

audit_logs tablosu mevcut: HTTP requests + business events kaydı tutuyor.
Ama kayıtlar **değiştirilebilir** — yetkili biri (veya DB'ye erişen
saldırgan) bir log entry'sini silebilir, içeriğini değiştirebilir.

Enterprise gereklilikler:
- **KVKK madde 12**: veri ihlali tespitinde immutable log
- **ISO 27001 A.12.4**: log integrity zorunluluğu
- **SOC 2 CC7.2**: audit trail integrity
- **Bağımsız denetçi**: "log dokunulmamış mı?" kanıtı zorunlu

## Çözüm: Hash chain (Merkle-style)

Her audit log entry içerir:
  - entry_hash: bu entry içeriğinin SHA-256 hash'i
  - prev_hash: önceki entry'nin entry_hash'i (zincir bağlantısı)

Genesis entry (ilk entry) prev_hash = "0000...0000" (64 sıfır).

## İmmutabilite garantisi

Bir entry değiştirilirse:
  1. O entry'nin entry_hash'i artık içeriğiyle uyuşmaz → tespit
  2. Sonraki entry'nin prev_hash'i artık önceki hash ile uyuşmaz → zincir kırılır
  3. Verify chain: O(N) sorgu, tek bir kırılma noktası tespit edilir

Bu blockchain mimarisi değil (proof-of-work yok) — sadece **integrity
chain**. SQLite seviyesinde write yetkisi olan kullanıcı bir entry
değiştirirse kanıtlar onu yakalar.

## Kanonik representation

Hash hesaplamak için audit entry'ler kanonik JSON'a serialize edilir
(sorted keys, no whitespace, ascii). Bu sayede aynı veri her zaman
aynı hash'i üretir — verify deterministik.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


# Genesis prev_hash: ilk entry için "öncesi yok" sentineli (64 sıfır = SHA-256 boş)
GENESIS_PREV_HASH = "0" * 64


def canonical_payload(entry: dict[str, Any]) -> str:
    """Convert audit entry → canonical JSON string for hashing.

    Sorted keys + no whitespace + ascii → deterministic. Aynı entry
    her zaman aynı string üretir (verify deterministik).

    Hash'e dahil edilen field'lar: tüm audit log content + prev_hash.
    Field'lar:
      - request_id, username, role, method, path, status_code,
        ip_address, user_agent, duration_ms, created_at,
        event_type, event_detail, prev_hash

    Hash'e dahil edilmeyen: id (autoincrement, deterministik değil),
    entry_hash (self-referencing impossible).
    """
    # Hash'lenebilir field'ları seç + None handling
    hashable: dict[str, Any] = {}
    for key in (
        "request_id", "username", "role", "method", "path", "status_code",
        "ip_address", "user_agent", "duration_ms", "created_at",
        "event_type", "event_detail", "prev_hash",
    ):
        value = entry.get(key)
        # None → null in canonical JSON; sayılar normalize
        hashable[key] = value
    return json.dumps(hashable, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def compute_entry_hash(entry: dict[str, Any]) -> str:
    """SHA-256 hash of canonical entry representation.

    Returns 64-char hex string (256 bits).
    """
    canonical = canonical_payload(entry)
    return hashlib.sha256(canonical.encode("ascii")).hexdigest()


def verify_entry(entry: dict[str, Any]) -> bool:
    """Verify single entry: entry_hash matches recomputed hash.

    Returns True if entry is intact, False if content tampered.
    """
    stored_hash = entry.get("entry_hash")
    if not stored_hash:
        return False
    recomputed = compute_entry_hash(entry)
    return stored_hash == recomputed


def verify_chain_link(
    prev_entry: dict[str, Any] | None,
    current_entry: dict[str, Any],
) -> bool:
    """Verify chain link: current.prev_hash == prev.entry_hash.

    Genesis case: prev_entry is None → current.prev_hash must be GENESIS_PREV_HASH.
    """
    if prev_entry is None:
        # Genesis: prev_hash must be sentinel
        return current_entry.get("prev_hash") == GENESIS_PREV_HASH
    expected_prev = prev_entry.get("entry_hash")
    actual_prev = current_entry.get("prev_hash")
    return expected_prev == actual_prev
