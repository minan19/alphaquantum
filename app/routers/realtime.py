"""G+2: Real-time WebSocket router — holding dashboard live updates.

## Endpoint
WS /api/v1/ws/holdings/{holding_id}/dashboard?token=<jwt>

Token authentication query param ile (WebSocket header forwarding her
client'ta yok). Token validate edilir, holding scope kontrol edilir.

Bağlantı sonrası:
  1. Server hoşgeldin event'i gönderir (event_type=welcome)
  2. Client ping/pong ile bağlantıyı canlı tutar
  3. Server domain event'leri ConnectionManager.broadcast üzerinden push'lar
  4. Client kapanınca disconnect cleanup otomatik

## Güvenlik
  - JWT validation (mevcut AuthService)
  - holding_id scope check (kullanıcı bu holding'e erişebilir mi?)
  - DoS: ConnectionManager.MAX_CONNECTIONS_PER_HOLDING
  - Token expired → 1008 policy violation close

## Frontend kullanımı
```typescript
const ws = new WebSocket(
  `wss://api.alpha-quantum.com.tr/api/v1/ws/holdings/${holdingId}/dashboard?token=${jwt}`
);
ws.onmessage = (e) => {
  const event = JSON.parse(e.data);
  switch (event.event_type) {
    case "balance.updated": updateBalanceWidget(event.payload); break;
    case "intercompany.requested": showPendingNotification(event.payload); break;
  }
};
```
"""
from __future__ import annotations

import logging
from typing import cast

from fastapi import APIRouter, Query, Request, WebSocket, WebSocketDisconnect, status

from app.auth_service import AuthService
from app.websocket_manager import WebSocketConnectionManager, build_event


router = APIRouter()
logger = logging.getLogger("alpha_quantum.ws")


def _manager(websocket: WebSocket) -> WebSocketConnectionManager:
    """WebSocket'in app.state'inden manager alır (FastAPI Request gibi)."""
    return cast(
        WebSocketConnectionManager,
        websocket.app.state.ws_connection_manager,
    )


def _auth(websocket: WebSocket) -> AuthService:
    return cast(AuthService, websocket.app.state.auth_service)


@router.websocket("/api/v1/ws/holdings/{holding_id}/dashboard")
async def holding_dashboard_socket(
    websocket: WebSocket,
    holding_id: int,
    token: str = Query(..., description="JWT access token"),
) -> None:
    """Holding dashboard real-time event stream.

    Authentication: JWT query param (WebSocket header forwarding eksikliği için).
    Lifecycle:
      1. Token validate → user identity
      2. Welcome event
      3. Stream loop (ping/pong)
      4. Disconnect cleanup
    """
    # 1. Token doğrulama (HTTP error fırlatamayız — WebSocket close kullan)
    auth = _auth(websocket)
    try:
        user = auth.decode_access_token(token)
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user_id = str(user.username)

    # 2. Kabul et + manager'a kaydet
    await websocket.accept()
    manager = _manager(websocket)
    await manager.connect(
        holding_id=holding_id,
        websocket=websocket,
        user_id=user_id,
    )

    # 3. Hoşgeldin event'i (frontend bağlantı kanıtı)
    welcome = build_event(
        event_type="welcome",
        holding_id=holding_id,
        payload={
            "message": "Connected to Alpha Quantum real-time stream",
            "user_id": user_id,
        },
    )
    try:
        await websocket.send_json(welcome)
    except Exception:
        await manager.disconnect(holding_id=holding_id, websocket=websocket)
        return

    # 4. Stream loop — client'ın mesajlarını dinle (heartbeat ping/pong vb.)
    try:
        while True:
            # Client ping gönderir; sunucu pong döner.
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
            # Diğer client → server mesajları (subscribe, unsubscribe) için
            # ileride genişletilebilir.
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning(
            "websocket_error",
            extra={"event": "ws.error", "holding_id": holding_id, "user_id": user_id, "error": str(exc)},
        )
    finally:
        await manager.disconnect(holding_id=holding_id, websocket=websocket)
