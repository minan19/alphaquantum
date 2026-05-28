from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Any
import sqlite3

from app._sqlite_helpers import new_row_id
import time


class IdentityRepository:
    def __init__(self, database_path: str) -> None:
        self._lock = Lock()
        self._conn = self._connect(database_path)
        self._ensure_schema()

    @staticmethod
    def _connect(database_path: str) -> sqlite3.Connection:
        path = Path(database_path)
        if path.parent and str(path.parent) != ".":
            path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def close(self) -> None:
        self._conn.close()

    def _ensure_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL DEFAULT '',
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role_id INTEGER NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                FOREIGN KEY(role_id) REFERENCES roles(id) ON DELETE RESTRICT
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_company_scopes (
                user_id INTEGER NOT NULL,
                company_scope TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                PRIMARY KEY (user_id, company_scope),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_user_company_scopes_scope
            ON user_company_scopes(company_scope)
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                expires_at INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                revoked_at INTEGER,
                revoked_reason TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS revoked_access_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                jti TEXT NOT NULL UNIQUE,
                expires_at INTEGER NOT NULL,
                revoked_at INTEGER NOT NULL,
                reason TEXT
            )
            """
        )
        self._conn.commit()

    def ensure_role(self, name: str, description: str) -> None:
        now = int(time.time())
        with self._lock:
            row = self._conn.execute(
                "SELECT id FROM roles WHERE name = ?",
                (name,),
            ).fetchone()
            if row is None:
                self._conn.execute(
                    """
                    INSERT INTO roles(name, description, created_at, updated_at)
                    VALUES(?, ?, ?, ?)
                    """,
                    (name, description, now, now),
                )
            self._conn.commit()

    def list_roles(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, name, description, created_at, updated_at FROM roles ORDER BY id"
            ).fetchall()
            return [dict(row) for row in rows]

    def create_role(self, name: str, description: str) -> dict[str, Any]:
        now = int(time.time())
        with self._lock:
            cursor = self._conn.execute(
                """
                INSERT INTO roles(name, description, created_at, updated_at)
                VALUES(?, ?, ?, ?)
                """,
                (name, description, now, now),
            )
            role_id = new_row_id(cursor)
            self._conn.commit()
        return self.get_role(role_id)

    def get_role(self, role_id: int) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute(
                "SELECT id, name, description, created_at, updated_at FROM roles WHERE id = ?",
                (role_id,),
            ).fetchone()
        if row is None:
            raise ValueError("Role not found")
        return dict(row)

    def update_role(
        self,
        role_id: int,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        now = int(time.time())
        with self._lock:
            current = self._conn.execute(
                "SELECT id, name, description FROM roles WHERE id = ?",
                (role_id,),
            ).fetchone()
            if current is None:
                raise ValueError("Role not found")

            new_name = name if name is not None else str(current["name"])
            new_description = (
                description if description is not None else str(current["description"])
            )

            self._conn.execute(
                "UPDATE roles SET name = ?, description = ?, updated_at = ? WHERE id = ?",
                (new_name, new_description, now, role_id),
            )
            self._conn.commit()

        return self.get_role(role_id)

    def delete_role(self, role_id: int) -> None:
        with self._lock:
            role_row = self._conn.execute(
                "SELECT id FROM roles WHERE id = ?",
                (role_id,),
            ).fetchone()
            if role_row is None:
                raise ValueError("Role not found")

            usage_row = self._conn.execute(
                "SELECT COUNT(*) AS count FROM users WHERE role_id = ?",
                (role_id,),
            ).fetchone()
            if int(usage_row["count"]) > 0:
                raise ValueError("Role is assigned to users")

            self._conn.execute("DELETE FROM roles WHERE id = ?", (role_id,))
            self._conn.commit()

    def get_role_by_name(self, name: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT id, name, description FROM roles WHERE name = ?",
                (name,),
            ).fetchone()
            return dict(row) if row else None

    def ensure_permission(self, name: str, description: str) -> None:
        now = int(time.time())
        with self._lock:
            row = self._conn.execute(
                "SELECT id FROM permissions WHERE name = ?",
                (name,),
            ).fetchone()
            if row is None:
                self._conn.execute(
                    """
                    INSERT INTO permissions(name, description, created_at, updated_at)
                    VALUES(?, ?, ?, ?)
                    """,
                    (name, description, now, now),
                )
            self._conn.commit()

    def list_permissions(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT id, name, description, created_at, updated_at
                FROM permissions
                ORDER BY id ASC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def list_role_permissions(self, role_id: int) -> list[str]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT p.name
                FROM role_permissions rp
                JOIN permissions p ON p.id = rp.permission_id
                WHERE rp.role_id = ?
                ORDER BY p.name ASC
                """,
                (role_id,),
            ).fetchall()
        return [str(row["name"]) for row in rows]

    def list_role_permissions_by_name(self, role_name: str) -> list[str]:
        role = self.get_role_by_name(role_name)
        if role is None:
            raise ValueError("Role not found")
        return self.list_role_permissions(int(role["id"]))

    def replace_role_permissions(self, role_id: int, permission_names: list[str]) -> list[str]:
        role = self.get_role(role_id)
        del role

        unique_names = sorted({name.strip() for name in permission_names if name.strip()})
        missing: list[str] = []
        permission_ids: list[int] = []

        with self._lock:
            for name in unique_names:
                row = self._conn.execute(
                    "SELECT id FROM permissions WHERE name = ?",
                    (name,),
                ).fetchone()
                if row is None:
                    missing.append(name)
                    continue
                permission_ids.append(int(row["id"]))

            if missing:
                raise ValueError(f"Unknown permissions: {', '.join(missing)}")

            now = int(time.time())
            self._conn.execute(
                "DELETE FROM role_permissions WHERE role_id = ?",
                (role_id,),
            )
            for permission_id in permission_ids:
                self._conn.execute(
                    """
                    INSERT INTO role_permissions(role_id, permission_id, created_at)
                    VALUES(?, ?, ?)
                    """,
                    (role_id, permission_id, now),
                )

            self._conn.commit()

        return self.list_role_permissions(role_id)

    def replace_role_permissions_by_name(self, role_name: str, permission_names: list[str]) -> list[str]:
        role = self.get_role_by_name(role_name)
        if role is None:
            raise ValueError("Role not found")
        return self.replace_role_permissions(int(role["id"]), permission_names)

    def user_permissions(self, user_id: int) -> list[str]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT DISTINCT p.name
                FROM users u
                JOIN role_permissions rp ON rp.role_id = u.role_id
                JOIN permissions p ON p.id = rp.permission_id
                WHERE u.id = ? AND u.is_active = 1
                ORDER BY p.name ASC
                """,
                (user_id,),
            ).fetchall()
        return [str(row["name"]) for row in rows]

    def user_has_permissions(self, user_id: int, required_permissions: list[str]) -> bool:
        required = {name.strip() for name in required_permissions if name.strip()}
        if not required:
            return True
        assigned = set(self.user_permissions(user_id))
        return required.issubset(assigned)

    def user_count(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) AS count FROM users").fetchone()
            return int(row["count"])

    def list_users(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT
                    u.id,
                    u.username,
                    u.is_active,
                    u.created_at,
                    u.updated_at,
                    r.id AS role_id,
                    r.name AS role_name,
                    r.description AS role_description
                FROM users u
                JOIN roles r ON r.id = u.role_id
                ORDER BY u.id
                """
            ).fetchall()
            return [dict(row) for row in rows]

    def get_user_by_id(self, user_id: int) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT
                    u.id,
                    u.username,
                    u.password_hash,
                    u.is_active,
                    u.created_at,
                    u.updated_at,
                    r.id AS role_id,
                    r.name AS role_name,
                    r.description AS role_description
                FROM users u
                JOIN roles r ON r.id = u.role_id
                WHERE u.id = ?
                """,
                (user_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT
                    u.id,
                    u.username,
                    u.password_hash,
                    u.is_active,
                    u.created_at,
                    u.updated_at,
                    r.id AS role_id,
                    r.name AS role_name,
                    r.description AS role_description
                FROM users u
                JOIN roles r ON r.id = u.role_id
                WHERE u.username = ?
                """,
                (username,),
            ).fetchone()
            return dict(row) if row else None

    def create_user(
        self,
        *,
        username: str,
        password_hash: str,
        role_name: str,
        is_active: bool = True,
    ) -> dict[str, Any]:
        role = self.get_role_by_name(role_name)
        if role is None:
            raise ValueError("Role not found")

        now = int(time.time())
        with self._lock:
            cursor = self._conn.execute(
                """
                INSERT INTO users(username, password_hash, role_id, is_active, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                (
                    username,
                    password_hash,
                    int(role["id"]),
                    1 if is_active else 0,
                    now,
                    now,
                ),
            )
            user_id = new_row_id(cursor)
            self._conn.commit()

        user = self.get_user_by_id(user_id)
        if user is None:
            raise RuntimeError("User creation failed")
        return user

    def update_user(
        self,
        user_id: int,
        *,
        role_name: str | None = None,
        is_active: bool | None = None,
    ) -> dict[str, Any]:
        user = self.get_user_by_id(user_id)
        if user is None:
            raise ValueError("User not found")

        role_id = int(user["role_id"])
        if role_name is not None:
            role = self.get_role_by_name(role_name)
            if role is None:
                raise ValueError("Role not found")
            role_id = int(role["id"])

        next_is_active = int(user["is_active"])
        if is_active is not None:
            next_is_active = 1 if is_active else 0

        now = int(time.time())
        with self._lock:
            self._conn.execute(
                "UPDATE users SET role_id = ?, is_active = ?, updated_at = ? WHERE id = ?",
                (role_id, next_is_active, now, user_id),
            )
            self._conn.commit()

        result = self.get_user_by_id(user_id)
        if result is None:
            raise RuntimeError("User update failed")
        return result

    def list_user_company_scopes(self, user_id: int) -> list[str]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT company_scope
                FROM user_company_scopes
                WHERE user_id = ?
                ORDER BY company_scope ASC
                """,
                (user_id,),
            ).fetchall()
        return [str(row["company_scope"]) for row in rows]

    def replace_user_company_scopes(self, user_id: int, company_scopes: list[str]) -> list[str]:
        with self._lock:
            user_row = self._conn.execute(
                "SELECT id FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            if user_row is None:
                raise ValueError("User not found")

        normalized_scopes = self._normalize_company_scopes(company_scopes)
        now = int(time.time())

        with self._lock:
            self._conn.execute(
                "DELETE FROM user_company_scopes WHERE user_id = ?",
                (user_id,),
            )
            for scope in normalized_scopes:
                self._conn.execute(
                    """
                    INSERT INTO user_company_scopes(user_id, company_scope, created_at)
                    VALUES(?, ?, ?)
                    """,
                    (user_id, scope, now),
                )
            self._conn.commit()

        return self.list_user_company_scopes(user_id)

    def ensure_user_global_scope(self, user_id: int) -> None:
        with self._lock:
            user_row = self._conn.execute(
                "SELECT id FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            if user_row is None:
                raise ValueError("User not found")

            current = self._conn.execute(
                "SELECT 1 AS found FROM user_company_scopes WHERE user_id = ? LIMIT 1",
                (user_id,),
            ).fetchone()
            if current is not None:
                return

            now = int(time.time())
            self._conn.execute(
                """
                INSERT INTO user_company_scopes(user_id, company_scope, created_at)
                VALUES(?, ?, ?)
                """,
                (user_id, "*", now),
            )
            self._conn.commit()

    def ensure_default_company_scopes_for_all_users(self, default_scopes: list[str] | None = None) -> None:
        target_scopes = self._normalize_company_scopes(default_scopes or ["*"])
        with self._lock:
            rows = self._conn.execute("SELECT id FROM users").fetchall()
            user_ids = [int(row["id"]) for row in rows]

        for user_id in user_ids:
            if self.list_user_company_scopes(user_id):
                continue
            self.replace_user_company_scopes(user_id, target_scopes)

    def user_has_company_scope(self, user_id: int, company_name: str) -> bool:
        normalized_company = company_name.strip().casefold()
        if not normalized_company:
            return False

        scopes = self.list_user_company_scopes(user_id)
        if not scopes:
            return True
        if "*" in scopes:
            return True
        scope_set = {scope.casefold() for scope in scopes}
        return normalized_company in scope_set

    def rotate_password(self, user_id: int, password_hash: str) -> None:
        now = int(time.time())
        with self._lock:
            self._conn.execute(
                "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                (password_hash, now, user_id),
            )
            self._conn.commit()

    def delete_user(self, user_id: int) -> None:
        with self._lock:
            row = self._conn.execute(
                "SELECT id FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            if row is None:
                raise ValueError("User not found")

            self._conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            self._conn.commit()

    def store_refresh_token(
        self,
        *,
        user_id: int,
        token_hash: str,
        expires_at: int,
    ) -> None:
        now = int(time.time())
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO refresh_tokens(user_id, token_hash, expires_at, created_at)
                VALUES(?, ?, ?, ?)
                """,
                (user_id, token_hash, expires_at, now),
            )
            self._conn.commit()

    def get_valid_refresh_token(self, token_hash: str) -> dict[str, Any] | None:
        now = int(time.time())
        with self._lock:
            row = self._conn.execute(
                """
                SELECT id, user_id, token_hash, expires_at, created_at, revoked_at, revoked_reason
                FROM refresh_tokens
                WHERE token_hash = ? AND revoked_at IS NULL AND expires_at > ?
                """,
                (token_hash, now),
            ).fetchone()
            return dict(row) if row else None

    def revoke_refresh_token(self, token_hash: str, reason: str) -> None:
        now = int(time.time())
        with self._lock:
            self._conn.execute(
                """
                UPDATE refresh_tokens
                SET revoked_at = ?, revoked_reason = ?
                WHERE token_hash = ? AND revoked_at IS NULL
                """,
                (now, reason, token_hash),
            )
            self._conn.commit()

    def revoke_all_refresh_tokens_for_user(self, user_id: int, reason: str) -> None:
        now = int(time.time())
        with self._lock:
            self._conn.execute(
                """
                UPDATE refresh_tokens
                SET revoked_at = ?, revoked_reason = ?
                WHERE user_id = ? AND revoked_at IS NULL
                """,
                (now, reason, user_id),
            )
            self._conn.commit()

    def store_revoked_access_token(self, *, jti: str, expires_at: int, reason: str) -> None:
        now = int(time.time())
        with self._lock:
            self._conn.execute(
                """
                INSERT OR IGNORE INTO revoked_access_tokens(jti, expires_at, revoked_at, reason)
                VALUES(?, ?, ?, ?)
                """,
                (jti, expires_at, now, reason),
            )
            self._conn.commit()

    def is_access_token_revoked(self, jti: str) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 AS found FROM revoked_access_tokens WHERE jti = ?",
                (jti,),
            ).fetchone()
            return row is not None

    def cleanup_expired_tokens(self) -> None:
        now = int(time.time())
        with self._lock:
            self._conn.execute(
                "DELETE FROM refresh_tokens WHERE expires_at <= ?",
                (now,),
            )
            self._conn.execute(
                "DELETE FROM revoked_access_tokens WHERE expires_at <= ?",
                (now,),
            )
            self._conn.commit()

    @staticmethod
    def _normalize_company_scope(company_scope: str) -> str:
        normalized = company_scope.strip()
        if not normalized:
            return ""
        if normalized == "*":
            return "*"
        if normalized.upper() in {"ALL", "ALL_HOLDING", "HOLDING", "GLOBAL"}:
            return "*"
        return normalized

    @classmethod
    def _normalize_company_scopes(cls, company_scopes: list[str]) -> list[str]:
        unique_scopes: list[str] = []
        seen: set[str] = set()

        for raw in company_scopes:
            normalized = cls._normalize_company_scope(raw)
            if not normalized:
                continue
            if normalized == "*":
                return ["*"]
            key = normalized.casefold()
            if key in seen:
                continue
            seen.add(key)
            unique_scopes.append(normalized)

        if not unique_scopes:
            return ["*"]
        return unique_scopes
