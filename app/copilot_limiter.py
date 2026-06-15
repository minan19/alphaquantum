"""M3: Copilot rate limiter — kullanıcı başına sliding-window.

Mevcut `AuthAttemptLimiter` modeline benzer; kullanıcı identifier'ı
(token sub veya username) anahtar olarak kullanılır. Auth ile ortak
backend kullanılır (memory veya redis) ama anahtar ön-eki ayrıdır.
"""
from __future__ import annotations

import logging
import time
from threading import Lock


class CopilotRateLimitExceeded(Exception):
    """Kullanıcının copilot çağrı eşiğini aştığını gösterir."""


class CopilotRateLimiter:
    """Sliding-window in-memory limiter.

    `max_requests` çağrı `window_seconds` saniye içinde aşılırsa
    `CopilotRateLimitExceeded` fırlatır. Memory-only; pod-başına
    sayar (prod'da redis backend ile yatay ölçeklenir).
    """

    def __init__(
        self,
        *,
        window_seconds: int = 60,
        max_requests: int = 10,
    ) -> None:
        self._window = max(1, window_seconds)
        self._max = max(1, max_requests)
        self._hits: dict[str, list[float]] = {}
        self._lock = Lock()
        self._logger = logging.getLogger("alpha_quantum.copilot_limiter")

    def hit(self, key: str) -> None:
        """Kayıt + eşik kontrolü. Aşıldıysa exception."""
        now = time.monotonic()
        cutoff = now - self._window
        with self._lock:
            hits = [t for t in self._hits.get(key, []) if t > cutoff]
            if len(hits) >= self._max:
                self._logger.warning(
                    "copilot_rate_limit_exceeded key=%s count=%d limit=%d",
                    key, len(hits), self._max,
                )
                raise CopilotRateLimitExceeded(
                    f"Çok sık sorgu: {self._max}/dk eşiği aşıldı"
                )
            hits.append(now)
            self._hits[key] = hits

    def reset(self, key: str | None = None) -> None:
        """Test için: anahtar veya hepsini temizle."""
        with self._lock:
            if key is None:
                self._hits.clear()
            else:
                self._hits.pop(key, None)
