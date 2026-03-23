import unittest

from fastapi import HTTPException

from app.config import Settings
from app.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    validate_security_settings,
    verify_password,
)


class SecurityTests(unittest.TestCase):
    def test_password_hash_roundtrip(self) -> None:
        hashed = hash_password("StrongPass123")
        self.assertTrue(verify_password(hashed, "StrongPass123"))
        self.assertFalse(verify_password(hashed, "wrong-password"))

    def test_token_roundtrip(self) -> None:
        token = create_access_token(
            user_id=7,
            username="admin",
            role="admin",
            secret="test-secret",
            expire_minutes=5,
        )
        payload = decode_access_token(token, secret="test-secret")

        self.assertEqual(payload["sub"], "admin")
        self.assertEqual(payload["role"], "admin")
        self.assertEqual(payload["uid"], 7)
        self.assertIn("jti", payload)

    def test_token_expired(self) -> None:
        token = create_access_token(
            user_id=1,
            username="admin",
            role="admin",
            secret="test-secret",
            expire_minutes=-1,
        )

        with self.assertRaises(HTTPException) as context:
            decode_access_token(token, secret="test-secret")

        self.assertEqual(context.exception.status_code, 401)

    def test_token_invalid_payload_raises_401(self) -> None:
        token = "aW52YWxpZA.aW52YWxpZA.aW52YWxpZA"
        with self.assertRaises(HTTPException) as context:
            decode_access_token(token, secret="test-secret")
        self.assertEqual(context.exception.status_code, 401)

    def test_validate_security_settings_blocks_unsafe_prod(self) -> None:
        insecure_prod = Settings(
            app_name="Alpha Quantum",
            app_version="1.0.0",
            environment="production",
            log_level="INFO",
            allow_all_cors=False,
            cors_origins=[],
            cors_allow_credentials=False,
            database_path="alpha_quantum.db",
            jwt_secret="change-this-secret",
            access_token_expire_minutes=120,
            enable_demo_users=False,
            auth_rate_limit_window_seconds=60,
            auth_rate_limit_max_attempts=5,
            auth_rate_limit_backend="memory",
            auth_rate_limit_redis_url="redis://127.0.0.1:6379/0",
            auth_rate_limit_fail_open=True,
            auth_users="ops:ops-pass:admin",
            connector_worker_enabled=False,
            connector_worker_poll_interval_seconds=15,
            connector_worker_retry_backoff_seconds=60,
            connector_worker_max_retries=3,
            connector_worker_leader_lock_enabled=True,
            connector_worker_lease_seconds=30,
            connector_worker_heartbeat_seconds=10,
        )

        with self.assertRaises(RuntimeError):
            validate_security_settings(insecure_prod)

    def test_validate_security_settings_blocks_missing_auth_users_in_prod(self) -> None:
        insecure_prod = Settings(
            app_name="Alpha Quantum",
            app_version="1.0.0",
            environment="production",
            log_level="INFO",
            allow_all_cors=False,
            cors_origins=[],
            cors_allow_credentials=False,
            database_path="alpha_quantum.db",
            jwt_secret="secure-secret",
            access_token_expire_minutes=120,
            enable_demo_users=False,
            auth_rate_limit_window_seconds=60,
            auth_rate_limit_max_attempts=5,
            auth_rate_limit_backend="memory",
            auth_rate_limit_redis_url="redis://127.0.0.1:6379/0",
            auth_rate_limit_fail_open=True,
            auth_users="",
            connector_worker_enabled=False,
            connector_worker_poll_interval_seconds=15,
            connector_worker_retry_backoff_seconds=60,
            connector_worker_max_retries=3,
            connector_worker_leader_lock_enabled=True,
            connector_worker_lease_seconds=30,
            connector_worker_heartbeat_seconds=10,
        )

        with self.assertRaises(RuntimeError):
            validate_security_settings(insecure_prod)


if __name__ == "__main__":
    unittest.main()
