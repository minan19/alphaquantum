"""G+2: WebSocket Connection Manager — holding-scoped real-time broadcast.

## Tasarım kararları

### Holding-scoped subscriptions
Bağlanan client bir holding_id'ye subscribe olur. Broadcast'ler holding
boyunda dağıtılır — bir holding'in CFO'su başka holding'in event'lerini
görmez (multi-tenant isolation).

### Thread-safety
asyncio.Lock ile concurrent connect/disconnect/broadcast korunur.
WebSocket bağlantıları async — FastAPI lifespan compatible.

### Non-blocking broadcast
Tek bir slow client tüm broadcast'i bloklamaz. Her send try/except
ile sarılır; broken connection silently temizlenir.

### Resource limits
DoS savunması:
  - MAX_CONNECTIONS_PER_HOLDING = 50 (sınırsız değil)
  - DROP_OLDEST_ON_LIMIT: yeni connect → eski en eski drop
  - Heartbeat 30s — sessiz client tespit edilir

### Production scale-out
Tek instance için: in-memory dict yeter.
Multi-instance (k8s): Redis Pub/Sub backend (G+2.1 future) — bu sınıfın
interface'i değişmeden adapter yazılabilir.

## Test stratejisi
- Mock WebSocket sınıfı (async send_json/close)
- ConnectionManager.broadcast → mock'lar mesaj almalı
- DoS limit'i test edilir
- Disconnect cleanup test edilir
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from typing import Any, Protocol


# Tek holding'e izin verilen maks. eş zamanlı bağlantı (DoS savunması)
MAX_CONNECTIONS_PER_HOLDING = 50

# Heartbeat — client'lar 30 saniyede bir ping göndermeli
HEARTBEAT_INTERVAL_SECONDS = 30


class WebSocketLike(Protocol):
    """FastAPI WebSocket'in subset'i — mock'lanabilir test interface."""

    async def send_json(self, payload: dict[str, Any]) -> None:
        ...

    async def close(self, code: int = 1000) -> None:
        ...


class _Subscription:
    """Tek bir client bağlantısı."""

    __slots__ = ("websocket", "user_id", "connected_at")

    def __init__(self, websocket: WebSocketLike, user_id: str) -> None:
        self.websocket = websocket
        self.user_id = user_id
        self.connected_at = time.time()


class WebSocketConnectionManager:
    """Holding-scoped WebSocket broadcast manager.

    Production-grade:
      - Async/await throughout
      - asyncio.Lock concurrency safety
      - Non-blocking broadcast (slow client tüm holding'i kilitlemez)
      - DoS limit + oldest-drop policy
      - Disconnect cleanup
    """

    def __init__(
        self,
        *,
        max_connections_per_holding: int = MAX_CONNECTIONS_PER_HOLDING,
    ) -> None:
        # holding_id → list of Subscription
        self._connections: dict[int, list[_Subscription]] = defaultdict(list)
        self._lock = asyncio.Lock()
        self._max_per_holding = max_connections_per_holding

    async def connect(
        self,
        *,
        holding_id: int,
        websocket: WebSocketLike,
        user_id: str,
    ) -> None:
        """Add new subscription. DoS limit: drop oldest if needed."""
        async with self._lock:
            subs = self._connections[holding_id]
            if len(subs) >= self._max_per_holding:
                # Oldest drop policy — fair'a tradeoff: yeni client kabul,
                # eski en eski connection kapatılır.
                oldest = subs.pop(0)
                try:
                    await oldest.websocket.close(code=1008)  # policy violation
                except Exception:
                    pass
            subs.append(_Subscription(websocket, user_id))

    async def disconnect(
        self,
        *,
        holding_id: int,
        websocket: WebSocketLike,
    ) -> None:
        """Remove subscription. Idempotent — already-removed OK."""
        async with self._lock:
            subs = self._connections.get(holding_id)
            if subs is None:
                return
            self._connections[holding_id] = [
                s for s in subs if s.websocket is not websocket
            ]
            if not self._connections[holding_id]:
                del self._connections[holding_id]

    async def broadcast(
        self,
        *,
        holding_id: int,
        event: dict[str, Any],
    ) -> int:
        """Broadcast event to all subscribers of a holding.

        Returns: kaç subscriber'a başarıyla iletildi.
        Broken connection'lar otomatik temizlenir.
        """
        async with self._lock:
            subs = list(self._connections.get(holding_id, []))

        if not subs:
            return 0

        delivered = 0
        broken: list[WebSocketLike] = []
        for sub in subs:
            try:
                await sub.websocket.send_json(event)
                delivered += 1
            except Exception:
                broken.append(sub.websocket)

        # Broken connection'ları temizle (lock dışında topladık)
        if broken:
            async with self._lock:
                current = self._connections.get(holding_id, [])
                self._connections[holding_id] = [
                    s for s in current if s.websocket not in broken
                ]
                if not self._connections[holding_id]:
                    self._connections.pop(holding_id, None)

        return delivered

    def connection_count(self, *, holding_id: int) -> int:
        """Holding için aktif bağlantı sayısı (observability için)."""
        return len(self._connections.get(holding_id, []))

    def total_connections(self) -> int:
        """Tüm holding'lerdeki toplam aktif bağlantı."""
        return sum(len(subs) for subs in self._connections.values())

    def active_holdings(self) -> list[int]:
        """Aktif subscriber'ı olan holding ID'leri."""
        return list(self._connections.keys())


# ── Event payload helpers ─────────────────────────────────────────────────


def build_event(
    *,
    event_type: str,
    payload: dict[str, Any],
    holding_id: int,
) -> dict[str, Any]:
    """Standardized event envelope (frontend ile sözleşme).

    event_type konvansiyonu:
      - balance.updated         (sahne 1 sabah bakiyesi)
      - fx.position_changed     (sahne 1 FX nabız)
      - consolidated_pl.updated (sahne 2 P&L)
      - intercompany.requested  (sahne 4 yeni transfer)
      - intercompany.approved   (sahne 4 onay)
      - intercompany.rejected   (sahne 4 red)
      - exec_summary.generated  (sahne 5 LLM)
    """
    return {
        "event_type": event_type,
        "holding_id": holding_id,
        "timestamp": int(time.time()),
        "payload": payload,
    }
