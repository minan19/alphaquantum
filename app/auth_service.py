from __future__ import annotations

import hashlib
import secrets
import time
from typing import Any

from app.config import Settings
from app.identity_repository import IdentityRepository
from app.models import UserProfile
from app.security import hash_password, verify_password


class AuthService:
    def __init__(self, repo: IdentityRepository, settings: Settings) -> None:
        self._repo = repo
        self._settings = settings
        self.bootstrap_identity()

    @property
    def refresh_token_expire_seconds(self) -> int:
        return self._settings.access_token_expire_minutes * 60 * 24

    def bootstrap_identity(self) -> None:
        self._repo.ensure_role("admin", "Full access")
        self._repo.ensure_role("manager", "Operational write access")
        self._repo.ensure_role("viewer", "Read-only access")
        self._bootstrap_permissions()

        seed_users: list[tuple[str, str, str]] = []
        seed_users.extend(self._parse_auth_users(self._settings.auth_users))

        if self._settings.enable_demo_users:
            seed_users.extend(
                [
                    ("admin", "admin123", "admin"),
                    ("manager", "manager123", "manager"),
                    ("viewer", "viewer123", "viewer"),
                ]
            )

        if not seed_users and self._repo.user_count() == 0:
            seed_users.append(("admin", "admin123", "admin"))

        seen_usernames: set[str] = set()
        for username, password, role in seed_users:
            if username in seen_usernames:
                continue
            seen_usernames.add(username)

            existing = self._repo.get_user_by_username(username)
            if existing is None:
                self._repo.create_user(
                    username=username,
                    password_hash=hash_password(password),
                    role_name=role,
                    is_active=True,
                )

        self._repo.ensure_default_company_scopes_for_all_users(["*"])

    def authenticate(self, username: str, password: str) -> UserProfile | None:
        user = self._repo.get_user_by_username(username)
        if user is None:
            return None
        if int(user["is_active"]) != 1:
            return None

        if not verify_password(str(user["password_hash"]), password):
            return None

        return UserProfile(
            id=int(user["id"]),
            username=str(user["username"]),
            role=str(user["role_name"]),
            company_scopes=self._profile_scopes_for_user(int(user["id"])),
            scope_mode=self._scope_mode_for_user(int(user["id"])),
        )

    def get_user_profile_by_id(self, user_id: int) -> UserProfile | None:
        user = self._repo.get_user_by_id(user_id)
        if user is None:
            return None
        if int(user["is_active"]) != 1:
            return None

        return UserProfile(
            id=int(user["id"]),
            username=str(user["username"]),
            role=str(user["role_name"]),
            company_scopes=self._profile_scopes_for_user(int(user["id"])),
            scope_mode=self._scope_mode_for_user(int(user["id"])),
        )

    def create_refresh_token(self, user_id: int) -> str:
        token = secrets.token_urlsafe(48)
        token_hash = self._hash_refresh_token(token)
        expires_at = int(time.time()) + self.refresh_token_expire_seconds

        self._repo.store_refresh_token(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        return token

    def rotate_refresh_token(self, refresh_token: str) -> tuple[str, UserProfile] | None:
        token_hash = self._hash_refresh_token(refresh_token)
        row = self._repo.get_valid_refresh_token(token_hash)
        if row is None:
            return None

        user = self.get_user_profile_by_id(int(row["user_id"]))
        if user is None:
            self._repo.revoke_refresh_token(token_hash, "user_not_active")
            return None

        self._repo.revoke_refresh_token(token_hash, "rotated")
        new_refresh = self.create_refresh_token(user.id)
        return new_refresh, user

    def revoke_refresh_token(self, refresh_token: str, reason: str) -> None:
        token_hash = self._hash_refresh_token(refresh_token)
        self._repo.revoke_refresh_token(token_hash, reason)

    def revoke_all_refresh_tokens_for_user(self, user_id: int, reason: str) -> None:
        self._repo.revoke_all_refresh_tokens_for_user(user_id, reason)

    def revoke_access_token(self, *, jti: str, exp: int, reason: str) -> None:
        self._repo.store_revoked_access_token(jti=jti, expires_at=exp, reason=reason)

    def is_access_token_revoked(self, jti: str) -> bool:
        return self._repo.is_access_token_revoked(jti)

    def list_users(self) -> list[dict[str, Any]]:
        return self._repo.list_users()

    def create_user(
        self,
        *,
        username: str,
        password: str,
        role: str,
        is_active: bool,
        company_scopes: list[str] | None = None,
    ) -> dict[str, Any]:
        user = self._repo.create_user(
            username=username,
            password_hash=hash_password(password),
            role_name=role,
            is_active=is_active,
        )
        self._repo.replace_user_company_scopes(
            int(user["id"]),
            company_scopes or ["*"],
        )
        return user

    def update_user(
        self,
        user_id: int,
        *,
        role: str | None,
        is_active: bool | None,
        company_scopes: list[str] | None = None,
    ) -> dict[str, Any]:
        updated = self._repo.update_user(
            user_id,
            role_name=role,
            is_active=is_active,
        )
        if company_scopes is not None:
            self._repo.replace_user_company_scopes(user_id, company_scopes)
        if int(updated["is_active"]) != 1:
            self._repo.revoke_all_refresh_tokens_for_user(user_id, "user_deactivated")
        return updated

    def delete_user(self, user_id: int) -> None:
        self._repo.delete_user(user_id)

    def rotate_password(self, *, actor: UserProfile, target_user_id: int, current_password: str | None, new_password: str) -> None:
        target = self._repo.get_user_by_id(target_user_id)
        if target is None:
            raise ValueError("User not found")

        is_self = actor.id == target_user_id
        if not is_self and actor.role != "admin":
            raise PermissionError("Only admin can rotate other users passwords")

        if is_self:
            if not current_password:
                raise ValueError("Current password is required")
            if not verify_password(str(target["password_hash"]), current_password):
                raise ValueError("Current password is invalid")
            if verify_password(str(target["password_hash"]), new_password):
                raise ValueError("New password must be different")

        self._repo.rotate_password(target_user_id, hash_password(new_password))
        self._repo.revoke_all_refresh_tokens_for_user(target_user_id, "password_rotated")

    def list_roles(self) -> list[dict[str, Any]]:
        return self._repo.list_roles()

    def get_role(self, role_id: int) -> dict[str, Any]:
        return self._repo.get_role(role_id)

    def create_role(self, *, name: str, description: str) -> dict[str, Any]:
        return self._repo.create_role(name, description)

    def update_role(self, role_id: int, *, name: str | None, description: str | None) -> dict[str, Any]:
        return self._repo.update_role(role_id, name=name, description=description)

    def delete_role(self, role_id: int) -> None:
        self._repo.delete_role(role_id)

    def cleanup_tokens(self) -> None:
        self._repo.cleanup_expired_tokens()

    def list_permissions(self) -> list[dict[str, Any]]:
        return self._repo.list_permissions()

    def role_permissions(self, role_id: int) -> list[str]:
        return self._repo.list_role_permissions(role_id)

    def update_role_permissions(self, role_id: int, permission_names: list[str]) -> list[str]:
        return self._repo.replace_role_permissions(role_id, permission_names)

    def user_has_permissions(self, user_id: int, required_permissions: list[str]) -> bool:
        return self._repo.user_has_permissions(user_id, required_permissions)

    def user_company_scopes(self, user_id: int) -> list[str]:
        scopes = self._repo.list_user_company_scopes(user_id)
        if not scopes:
            return ["*"]
        return scopes

    def user_has_company_scope(self, user_id: int, company_name: str) -> bool:
        return self._repo.user_has_company_scope(user_id, company_name)

    def is_holding_scope(self, user_id: int) -> bool:
        scopes = self.user_company_scopes(user_id)
        return "*" in scopes

    @staticmethod
    def _hash_refresh_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _parse_auth_users(raw: str) -> list[tuple[str, str, str]]:
        users: list[tuple[str, str, str]] = []
        if not raw.strip():
            return users

        for item in raw.split(","):
            entry = item.strip()
            if not entry:
                continue

            parts = [part.strip() for part in entry.split(":")]
            if len(parts) != 3:
                continue

            username, password, role = parts
            if not username or not password or not role:
                continue
            users.append((username, password, role))

        return users

    def _bootstrap_permissions(self) -> None:
        catalog = {
            "read_companies": "Read company and analysis endpoints",
            "run_simulation": "Run simulation and auto update operations",
            "manage_users": "Create/update/delete users",
            "manage_roles": "Create/update/delete roles and assign permissions",
            "view_audit_logs": "Read audit logs",
            "manage_migrations": "Apply or rollback DB migrations",
            "read_finance": "Read finance ledger, cashflow and forecast endpoints",
            "write_finance": "Create finance ledger entries",
            "read_market": "Read market OHLCV and technical analysis endpoints",
            "refresh_market": "Refresh market OHLCV cache from provider",
            "read_global_intel": "Read global banks, World Bank, central bank analysis and reports",
            "read_public_sources": "Read and analyze public institution web sources",
            "prepare_tender_docs": "Prepare tender dossier drafts from specs and institutional rules",
            "read_procurement": "Read procurement requests, evaluations, and purchase orders",
            "write_procurement": "Create procurement requests and submit vendor quotes",
            "approve_procurement": "Create/approve purchase orders from procurement evaluations",
            "read_feasibility": "Read feasibility reports and analyses",
            "write_feasibility": "Generate and persist feasibility reports",
            "read_international": "Read country-based international project reports",
            "write_international": "Create country-based international project plans and reports",
            "read_holdings": "Read holding definitions and onboarding states",
            "manage_holdings": "Create holdings and onboard subsidiaries in bulk",
            "read_connectors": "Read integration connectors, mapping previews, and sync jobs",
            "manage_connectors": "Create integration connectors and dispatch sync jobs",
        }
        for name, description in catalog.items():
            self._repo.ensure_permission(name, description)

        defaults: dict[str, list[str]] = {
            "admin": sorted(catalog.keys()),
            "manager": [
                "read_companies",
                "run_simulation",
                "read_finance",
                "write_finance",
                "read_market",
                "refresh_market",
                "read_global_intel",
                "read_public_sources",
                "prepare_tender_docs",
                "read_procurement",
                "write_procurement",
                "approve_procurement",
                "read_feasibility",
                "write_feasibility",
                "read_international",
                "write_international",
                "read_holdings",
                "manage_holdings",
                "read_connectors",
                "manage_connectors",
            ],
            "viewer": [
                "read_companies",
                "read_finance",
                "read_market",
                "read_global_intel",
                "read_public_sources",
                "read_procurement",
                "read_feasibility",
                "read_international",
                "read_holdings",
                "read_connectors",
            ],
        }

        for role_name, permissions in defaults.items():
            current = self._repo.list_role_permissions_by_name(role_name)
            if not current:
                self._repo.replace_role_permissions_by_name(role_name, permissions)
                continue

            merged = sorted(set(current).union(permissions))
            if set(merged) != set(current):
                self._repo.replace_role_permissions_by_name(role_name, merged)

    def _profile_scopes_for_user(self, user_id: int) -> list[str]:
        scopes = self._repo.list_user_company_scopes(user_id)
        if not scopes:
            return ["*"]
        return scopes

    def _scope_mode_for_user(self, user_id: int) -> str:
        scopes = self._profile_scopes_for_user(user_id)
        if "*" in scopes:
            return "holding"
        if len(scopes) == 1:
            return "single"
        return "multi"
