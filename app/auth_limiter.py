from __future__ import annotations

from dataclasses import dataclass
import hashlib
import logging
from threading import Lock
from typing import Any, Protocol
import time


@dataclass
class _AttemptState:
    count: int
    window_start: float


class AuthLimiterBackend(Protocol):
    def is_allowed(self, key: str, *, window_seconds: int, max_attempts: int) -> bool:
        ...

    def register_failure(self, key: str, *, window_seconds: int, max_attempts: int) -> None:
        ...

    def register_success(self, key: str) -> None:
        ...

    def close(self) -> None:
        ...


class InMemoryAuthLimiterBackend:
    def __init__(self) -> None:
        self._states: dict[str, _AttemptState] = {}
        self._lock = Lock()

    def is_allowed(self, key: str, *, window_seconds: int, max_attempts: int) -> bool:
        now = time.time()
        with self._lock:
            state = self._states.get(key)
            if state is None:
                return True

            if now - state.window_start >= window_seconds:
                del self._states[key]
                return True

            return state.count < max_attempts

    def register_failure(self, key: str, *, window_seconds: int, max_attempts: int) -> None:
        now = time.time()
        with self._lock:
            state = self._states.get(key)
            if state is None or (now - state.window_start >= window_seconds):
                self._states[key] = _AttemptState(count=1, window_start=now)
                return

            state.count += 1

    def register_success(self, key: str) -> None:
        with self._lock:
            self._states.pop(key, None)

    def close(self) -> None:
        return None


class RedisAuthLimiterBackend:
    def __init__(
        self,
        *,
        redis_url: str,
        key_prefix: str = "aq:auth:rate_limit",
        redis_client: Any | None = None,
    ) -> None:
        self._key_prefix = key_prefix.strip(":") or "aq:auth:rate_limit"
        if redis_client is not None:
            self._client = redis_client
            return

        try:
            import redis  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "Redis backend requested but 'redis' package is not installed."
            ) from exc

        self._client = redis.Redis.from_url(redis_url, decode_responses=True)
        ping = getattr(self._client, "ping", None)
        if callable(ping):
            ping()

    def is_allowed(self, key: str, *, window_seconds: int, max_attempts: int) -> bool:
        count_raw = self._client.get(self._redis_key(key))
        if count_raw is None:
            return True
        try:
            count = int(count_raw)
        except (TypeError, ValueError):
            self._client.delete(self._redis_key(key))
            return True
        return count < max_attempts

    def register_failure(self, key: str, *, window_seconds: int, max_attempts: int) -> None:
        redis_key = self._redis_key(key)
        current = int(self._client.incr(redis_key))
        if current == 1:
            self._client.expire(redis_key, max(1, window_seconds))

    def register_success(self, key: str) -> None:
        self._client.delete(self._redis_key(key))

    def close(self) -> None:
        close = getattr(self._client, "close", None)
        if callable(close):
            close()

    def _redis_key(self, key: str) -> str:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return f"{self._key_prefix}:{digest}"


class AuthAttemptLimiter:
    def __init__(
        self,
        *,
        window_seconds: int,
        max_attempts: int,
        backend: AuthLimiterBackend | None = None,
        fail_open: bool = True,
        backend_name: str | None = None,
    ) -> None:
        self._window_seconds = max(1, window_seconds)
        self._max_attempts = max(1, max_attempts)
        self._backend: AuthLimiterBackend = backend or InMemoryAuthLimiterBackend()
        self._fail_open = fail_open
        self._backend_name = backend_name or self._backend.__class__.__name__
        self._logger = logging.getLogger("alpha_quantum.auth_limiter")

    def is_allowed(self, key: str) -> bool:
        try:
            return self._backend.is_allowed(
                key,
                window_seconds=self._window_seconds,
                max_attempts=self._max_attempts,
            )
        except Exception:
            self._logger.exception(
                "auth_limiter_is_allowed_failed backend=%s key=%s",
                self._backend_name,
                key,
            )
            if self._fail_open:
                return True
            raise

    def register_failure(self, key: str) -> None:
        try:
            self._backend.register_failure(
                key,
                window_seconds=self._window_seconds,
                max_attempts=self._max_attempts,
            )
        except Exception:
            self._logger.exception(
                "auth_limiter_register_failure_failed backend=%s key=%s",
                self._backend_name,
                key,
            )
            if self._fail_open:
                return
            raise

    def register_success(self, key: str) -> None:
        try:
            self._backend.register_success(key)
        except Exception:
            self._logger.exception(
                "auth_limiter_register_success_failed backend=%s key=%s",
                self._backend_name,
                key,
            )
            if self._fail_open:
                return
            raise

    def close(self) -> None:
        try:
            self._backend.close()
        except Exception:
            self._logger.exception("auth_limiter_close_failed backend=%s", self._backend_name)
            if self._fail_open:
                return
            raise


def build_auth_attempt_limiter(
    *,
    window_seconds: int,
    max_attempts: int,
    backend_mode: str,
    redis_url: str | None,
    fail_open: bool,
) -> AuthAttemptLimiter:
    logger = logging.getLogger("alpha_quantum.auth_limiter")
    mode = (backend_mode or "memory").strip().lower()

    backend: AuthLimiterBackend
    resolved_mode = mode

    if mode == "redis":
        if not redis_url:
            if not fail_open:
                raise RuntimeError("Redis rate-limit backend selected but redis URL is empty.")
            logger.warning("auth_limiter_redis_url_missing fallback=memory")
            backend = InMemoryAuthLimiterBackend()
            resolved_mode = "memory_fallback"
        else:
            try:
                backend = RedisAuthLimiterBackend(redis_url=redis_url)
            except Exception:
                if not fail_open:
                    raise
                logger.exception("auth_limiter_redis_init_failed fallback=memory")
                backend = InMemoryAuthLimiterBackend()
                resolved_mode = "memory_fallback"
    elif mode in {"memory", "inmemory"}:
        backend = InMemoryAuthLimiterBackend()
        resolved_mode = "memory"
    else:
        logger.warning("auth_limiter_unknown_backend mode=%s fallback=memory", mode)
        backend = InMemoryAuthLimiterBackend()
        resolved_mode = "memory_fallback"

    limiter = AuthAttemptLimiter(
        window_seconds=window_seconds,
        max_attempts=max_attempts,
        backend=backend,
        fail_open=fail_open,
        backend_name=resolved_mode,
    )
    logger.info(
        "auth_limiter_initialized backend=%s window_seconds=%s max_attempts=%s fail_open=%s",
        resolved_mode,
        max(1, window_seconds),
        max(1, max_attempts),
        fail_open,
    )
    return limiter
