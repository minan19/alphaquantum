import time
import unittest

from app.auth_limiter import (
    AuthAttemptLimiter,
    RedisAuthLimiterBackend,
    build_auth_attempt_limiter,
)


class _FakeRedis:
    def __init__(self) -> None:
        self._values: dict[str, int] = {}
        self._expires: dict[str, float] = {}

    def get(self, key: str) -> str | None:
        self._purge(key)
        value = self._values.get(key)
        if value is None:
            return None
        return str(value)

    def incr(self, key: str) -> int:
        self._purge(key)
        current = int(self._values.get(key, 0)) + 1
        self._values[key] = current
        return current

    def expire(self, key: str, seconds: int) -> bool:
        self._expires[key] = time.time() + max(1, seconds)
        return True

    def delete(self, key: str) -> int:
        self._values.pop(key, None)
        self._expires.pop(key, None)
        return 1

    def ping(self) -> bool:
        return True

    def close(self) -> None:
        return None

    def _purge(self, key: str) -> None:
        expires_at = self._expires.get(key)
        if expires_at is None:
            return
        if time.time() >= expires_at:
            self._values.pop(key, None)
            self._expires.pop(key, None)


class _BrokenBackend:
    def is_allowed(self, key: str, *, window_seconds: int, max_attempts: int) -> bool:
        raise RuntimeError("backend_down")

    def register_failure(self, key: str, *, window_seconds: int, max_attempts: int) -> None:
        raise RuntimeError("backend_down")

    def register_success(self, key: str) -> None:
        raise RuntimeError("backend_down")

    def close(self) -> None:
        raise RuntimeError("backend_down")


class AuthLimiterTests(unittest.TestCase):
    def test_blocks_after_max_attempts(self) -> None:
        limiter = AuthAttemptLimiter(window_seconds=60, max_attempts=2)
        key = "127.0.0.1:admin"

        self.assertTrue(limiter.is_allowed(key))
        limiter.register_failure(key)
        self.assertTrue(limiter.is_allowed(key))
        limiter.register_failure(key)
        self.assertFalse(limiter.is_allowed(key))

    def test_success_resets_failure_counter(self) -> None:
        limiter = AuthAttemptLimiter(window_seconds=60, max_attempts=2)
        key = "127.0.0.1:admin"

        limiter.register_failure(key)
        limiter.register_success(key)
        self.assertTrue(limiter.is_allowed(key))

    def test_redis_backend_shares_state_between_instances(self) -> None:
        redis_client = _FakeRedis()
        backend_a = RedisAuthLimiterBackend(
            redis_url="redis://unused",
            redis_client=redis_client,
            key_prefix="aq:test",
        )
        backend_b = RedisAuthLimiterBackend(
            redis_url="redis://unused",
            redis_client=redis_client,
            key_prefix="aq:test",
        )
        limiter_a = AuthAttemptLimiter(window_seconds=60, max_attempts=2, backend=backend_a)
        limiter_b = AuthAttemptLimiter(window_seconds=60, max_attempts=2, backend=backend_b)

        key = "127.0.0.1:admin"
        self.assertTrue(limiter_a.is_allowed(key))
        limiter_a.register_failure(key)
        self.assertTrue(limiter_b.is_allowed(key))
        limiter_b.register_failure(key)
        self.assertFalse(limiter_a.is_allowed(key))

    def test_fail_open_and_fail_closed_behavior(self) -> None:
        key = "127.0.0.1:admin"
        fail_open_limiter = AuthAttemptLimiter(
            window_seconds=60,
            max_attempts=2,
            backend=_BrokenBackend(),
            fail_open=True,
        )
        self.assertTrue(fail_open_limiter.is_allowed(key))
        fail_open_limiter.register_failure(key)
        fail_open_limiter.register_success(key)
        fail_open_limiter.close()

        fail_closed_limiter = AuthAttemptLimiter(
            window_seconds=60,
            max_attempts=2,
            backend=_BrokenBackend(),
            fail_open=False,
        )
        with self.assertRaises(RuntimeError):
            fail_closed_limiter.is_allowed(key)

    def test_factory_unknown_backend_falls_back_to_memory(self) -> None:
        limiter = build_auth_attempt_limiter(
            window_seconds=60,
            max_attempts=2,
            backend_mode="unknown",
            redis_url=None,
            fail_open=True,
        )
        key = "127.0.0.1:admin"
        self.assertTrue(limiter.is_allowed(key))
        limiter.register_failure(key)
        self.assertTrue(limiter.is_allowed(key))


if __name__ == "__main__":
    unittest.main()
