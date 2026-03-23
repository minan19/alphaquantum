import tempfile
import time
import unittest
from pathlib import Path

from app.auth_service import AuthService
from app.config import Settings
from app.identity_repository import IdentityRepository
from app.migration_manager import MigrationManager


class AuthServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._temp_dir.name) / "auth_test.db"
        self.settings = Settings(
            app_name="Alpha Quantum",
            app_version="1.0.0",
            environment="development",
            log_level="INFO",
            allow_all_cors=False,
            cors_origins=[],
            cors_allow_credentials=False,
            database_path=str(self._db_path),
            jwt_secret="test-secret",
            access_token_expire_minutes=30,
            enable_demo_users=False,
            auth_rate_limit_window_seconds=60,
            auth_rate_limit_max_attempts=5,
            auth_rate_limit_backend="memory",
            auth_rate_limit_redis_url="redis://127.0.0.1:6379/0",
            auth_rate_limit_fail_open=True,
            auth_users="admin:admin12345:admin",
            connector_worker_enabled=False,
            connector_worker_poll_interval_seconds=15,
            connector_worker_retry_backoff_seconds=60,
            connector_worker_max_retries=3,
            connector_worker_leader_lock_enabled=True,
            connector_worker_lease_seconds=30,
            connector_worker_heartbeat_seconds=10,
        )
        self.repo = IdentityRepository(str(self._db_path))
        migrations_dir = Path(__file__).resolve().parent.parent / "migrations"
        self.migration_manager = MigrationManager(str(self._db_path), str(migrations_dir))
        self.migration_manager.apply_all()
        self.service = AuthService(self.repo, self.settings)

    def tearDown(self) -> None:
        self.migration_manager.close()
        self.repo.close()
        self._temp_dir.cleanup()

    def test_bootstrap_and_authenticate(self) -> None:
        user = self.service.authenticate("admin", "admin12345")
        self.assertIsNotNone(user)
        assert user is not None
        self.assertEqual(user.role, "admin")

    def test_refresh_rotate_and_revoke(self) -> None:
        user = self.service.authenticate("admin", "admin12345")
        assert user is not None

        refresh = self.service.create_refresh_token(user.id)
        rotated = self.service.rotate_refresh_token(refresh)
        self.assertIsNotNone(rotated)
        assert rotated is not None
        new_refresh, rotated_user = rotated

        self.assertEqual(rotated_user.id, user.id)
        self.assertIsNone(self.service.rotate_refresh_token(refresh))

        self.service.revoke_refresh_token(new_refresh, reason="logout")
        self.assertIsNone(self.service.rotate_refresh_token(new_refresh))

    def test_user_and_role_crud(self) -> None:
        role = self.service.create_role(name="auditor", description="Audit role")
        self.assertEqual(role["name"], "auditor")

        created = self.service.create_user(
            username="alice",
            password="alicePass123",
            role="auditor",
            is_active=True,
        )
        self.assertEqual(created["username"], "alice")

        updated = self.service.update_user(
            int(created["id"]),
            role="viewer",
            is_active=False,
        )
        self.assertEqual(updated["role_name"], "viewer")
        self.assertEqual(int(updated["is_active"]), 0)

        self.service.delete_user(int(created["id"]))
        self.assertIsNone(self.repo.get_user_by_id(int(created["id"])))

        self.service.delete_role(int(role["id"]))
        self.assertIsNone(self.repo.get_role_by_name("auditor"))

    def test_default_permission_matrix(self) -> None:
        admin = self.service.authenticate("admin", "admin12345")
        assert admin is not None

        self.assertTrue(
            self.service.user_has_permissions(
                admin.id,
                [
                    "manage_users",
                    "manage_roles",
                    "read_finance",
                    "read_market",
                    "read_global_intel",
                    "read_procurement",
                    "approve_procurement",
                    "read_feasibility",
                    "write_feasibility",
                    "read_international",
                    "write_international",
                ],
            )
        )

    def test_password_rotate_and_access_token_revoke(self) -> None:
        created = self.service.create_user(
            username="bob",
            password="bobPass123",
            role="viewer",
            is_active=True,
        )
        bob_id = int(created["id"])

        bob = self.service.authenticate("bob", "bobPass123")
        assert bob is not None

        self.service.rotate_password(
            actor=bob,
            target_user_id=bob_id,
            current_password="bobPass123",
            new_password="bobPass999",
        )

        self.assertIsNone(self.service.authenticate("bob", "bobPass123"))
        self.assertIsNotNone(self.service.authenticate("bob", "bobPass999"))

        self.service.revoke_access_token(
            jti="jti-123",
            exp=int(time.time()) + 3600,
            reason="logout",
        )
        self.assertTrue(self.service.is_access_token_revoked("jti-123"))

    def test_user_company_scope_assignment_and_check(self) -> None:
        created = self.service.create_user(
            username="scope_user",
            password="scopePass123",
            role="manager",
            is_active=True,
            company_scopes=["ABC Holding", "Delta Lojistik"],
        )
        user_id = int(created["id"])

        profile = self.service.authenticate("scope_user", "scopePass123")
        assert profile is not None
        self.assertEqual(profile.scope_mode, "multi")
        self.assertEqual(set(profile.company_scopes), {"ABC Holding", "Delta Lojistik"})
        self.assertTrue(self.service.user_has_company_scope(user_id, "abc holding"))
        self.assertFalse(self.service.user_has_company_scope(user_id, "Unknown Co"))

        self.service.update_user(
            user_id,
            role=None,
            is_active=None,
            company_scopes=["*"],
        )
        profile_after = self.service.get_user_profile_by_id(user_id)
        assert profile_after is not None
        self.assertEqual(profile_after.scope_mode, "holding")
        self.assertEqual(profile_after.company_scopes, ["*"])


if __name__ == "__main__":
    unittest.main()
