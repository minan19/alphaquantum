"""G+2: WebSocketConnectionManager tests — holding-scoped broadcast.

Async tests — pytest-asyncio gerek yok, asyncio.run ile çağrılır.
Mock WebSocket sınıfı send_json + close interface'ini implement eder.
"""
import asyncio
import time
import unittest
from typing import Any

from app.websocket_manager import (
    WebSocketConnectionManager,
    build_event,
)


class MockWebSocket:
    """Test fixture — gerçek FastAPI WebSocket interface'inin subset'i."""

    def __init__(self, *, fail_on_send: bool = False) -> None:
        self.received: list[dict[str, Any]] = []
        self.closed = False
        self.close_code: int | None = None
        self._fail_on_send = fail_on_send

    async def send_json(self, payload: dict[str, Any]) -> None:
        if self._fail_on_send:
            raise ConnectionError("simulated broken pipe")
        self.received.append(payload)

    async def close(self, code: int = 1000) -> None:
        self.closed = True
        self.close_code = code


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


class BuildEventTests(unittest.TestCase):
    def test_event_envelope_structure(self) -> None:
        ev = build_event(
            event_type="balance.updated",
            holding_id=1,
            payload={"total": 100.0},
        )
        self.assertEqual(ev["event_type"], "balance.updated")
        self.assertEqual(ev["holding_id"], 1)
        self.assertEqual(ev["payload"], {"total": 100.0})
        # timestamp recent
        self.assertGreater(ev["timestamp"], int(time.time()) - 5)
        self.assertLessEqual(ev["timestamp"], int(time.time()) + 1)


class ConnectionManagerBasicTests(unittest.TestCase):
    def test_initial_state_empty(self) -> None:
        mgr = WebSocketConnectionManager()
        self.assertEqual(mgr.total_connections(), 0)
        self.assertEqual(mgr.active_holdings(), [])
        self.assertEqual(mgr.connection_count(holding_id=1), 0)

    def test_connect_increases_count(self) -> None:
        mgr = WebSocketConnectionManager()
        ws = MockWebSocket()
        _run(mgr.connect(holding_id=1, websocket=ws, user_id="u1"))
        self.assertEqual(mgr.connection_count(holding_id=1), 1)
        self.assertEqual(mgr.total_connections(), 1)
        self.assertIn(1, mgr.active_holdings())

    def test_disconnect_removes(self) -> None:
        mgr = WebSocketConnectionManager()
        ws = MockWebSocket()
        _run(mgr.connect(holding_id=1, websocket=ws, user_id="u1"))
        _run(mgr.disconnect(holding_id=1, websocket=ws))
        self.assertEqual(mgr.connection_count(holding_id=1), 0)
        self.assertEqual(mgr.total_connections(), 0)
        self.assertNotIn(1, mgr.active_holdings())

    def test_disconnect_unknown_is_idempotent(self) -> None:
        mgr = WebSocketConnectionManager()
        ws = MockWebSocket()
        # Hiç connect edilmedi — disconnect rahatlıkla geçmeli
        _run(mgr.disconnect(holding_id=99, websocket=ws))
        self.assertEqual(mgr.total_connections(), 0)


class BroadcastTests(unittest.TestCase):
    def test_broadcast_delivers_to_all_subscribers(self) -> None:
        mgr = WebSocketConnectionManager()
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()
        _run(mgr.connect(holding_id=1, websocket=ws1, user_id="u1"))
        _run(mgr.connect(holding_id=1, websocket=ws2, user_id="u2"))

        event = build_event(
            event_type="balance.updated",
            holding_id=1,
            payload={"x": 1},
        )
        delivered = _run(mgr.broadcast(holding_id=1, event=event))

        self.assertEqual(delivered, 2)
        self.assertEqual(len(ws1.received), 1)
        self.assertEqual(len(ws2.received), 1)
        self.assertEqual(ws1.received[0]["event_type"], "balance.updated")

    def test_broadcast_scoped_to_holding(self) -> None:
        """Holding 2 abonesi Holding 1 broadcast almaz (isolation)."""
        mgr = WebSocketConnectionManager()
        ws_h1 = MockWebSocket()
        ws_h2 = MockWebSocket()
        _run(mgr.connect(holding_id=1, websocket=ws_h1, user_id="u1"))
        _run(mgr.connect(holding_id=2, websocket=ws_h2, user_id="u2"))

        _run(mgr.broadcast(
            holding_id=1,
            event=build_event(event_type="test", holding_id=1, payload={}),
        ))

        self.assertEqual(len(ws_h1.received), 1)
        self.assertEqual(len(ws_h2.received), 0)  # tenant isolation

    def test_broadcast_no_subscribers_returns_zero(self) -> None:
        mgr = WebSocketConnectionManager()
        delivered = _run(mgr.broadcast(
            holding_id=999,
            event=build_event(event_type="x", holding_id=999, payload={}),
        ))
        self.assertEqual(delivered, 0)

    def test_broken_connection_cleaned_up_silently(self) -> None:
        """Slow/broken client tüm broadcast'i bloklamaz, otomatik temizlenir."""
        mgr = WebSocketConnectionManager()
        broken = MockWebSocket(fail_on_send=True)
        healthy = MockWebSocket()
        _run(mgr.connect(holding_id=1, websocket=broken, user_id="u_broken"))
        _run(mgr.connect(holding_id=1, websocket=healthy, user_id="u_ok"))

        delivered = _run(mgr.broadcast(
            holding_id=1,
            event=build_event(event_type="x", holding_id=1, payload={}),
        ))

        # Sadece healthy aldı
        self.assertEqual(delivered, 1)
        self.assertEqual(len(healthy.received), 1)
        self.assertEqual(len(broken.received), 0)

        # Cleanup: broken artık listede yok
        self.assertEqual(mgr.connection_count(holding_id=1), 1)


class DoSLimitTests(unittest.TestCase):
    def test_max_per_holding_drops_oldest(self) -> None:
        mgr = WebSocketConnectionManager(max_connections_per_holding=3)
        ws_a = MockWebSocket()
        ws_b = MockWebSocket()
        ws_c = MockWebSocket()
        ws_d = MockWebSocket()
        _run(mgr.connect(holding_id=1, websocket=ws_a, user_id="a"))
        _run(mgr.connect(holding_id=1, websocket=ws_b, user_id="b"))
        _run(mgr.connect(holding_id=1, websocket=ws_c, user_id="c"))

        # 4. connect → en eski (a) drop edilmeli
        _run(mgr.connect(holding_id=1, websocket=ws_d, user_id="d"))

        self.assertEqual(mgr.connection_count(holding_id=1), 3)
        # ws_a kapatıldı
        self.assertTrue(ws_a.closed)
        self.assertEqual(ws_a.close_code, 1008)  # policy violation
        # Sonraki broadcast b, c, d'ye gider — a'ya gitmez
        _run(mgr.broadcast(
            holding_id=1,
            event=build_event(event_type="x", holding_id=1, payload={}),
        ))
        self.assertEqual(len(ws_a.received), 0)
        self.assertEqual(len(ws_b.received), 1)
        self.assertEqual(len(ws_c.received), 1)
        self.assertEqual(len(ws_d.received), 1)


class ConcurrentSafetyTests(unittest.TestCase):
    def test_concurrent_connects_thread_safe(self) -> None:
        """50 paralel connect — son count tutarlı, race condition yok."""
        mgr = WebSocketConnectionManager(max_connections_per_holding=100)

        async def connect_many() -> None:
            sockets = [MockWebSocket() for _ in range(50)]
            await asyncio.gather(*[
                mgr.connect(holding_id=1, websocket=ws, user_id=f"u{i}")
                for i, ws in enumerate(sockets)
            ])

        _run(connect_many())
        self.assertEqual(mgr.connection_count(holding_id=1), 50)


if __name__ == "__main__":
    unittest.main()
