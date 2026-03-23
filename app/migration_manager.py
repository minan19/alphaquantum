from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any
import sqlite3
import time


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    up_path: Path
    down_path: Path


class MigrationManager:
    def __init__(self, database_path: str, migrations_dir: str) -> None:
        self._lock = Lock()
        self._conn = self._connect(database_path)
        self._migrations_dir = Path(migrations_dir)
        self._ensure_schema_table()

    @staticmethod
    def _connect(database_path: str) -> sqlite3.Connection:
        conn = sqlite3.connect(database_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def close(self) -> None:
        self._conn.close()

    def _ensure_schema_table(self) -> None:
        with self._lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at INTEGER NOT NULL
                )
                """
            )
            self._conn.commit()

    def apply_all(self) -> list[int]:
        migrations = self._discover_migrations()
        applied_versions = set(self._get_applied_versions())
        applied_now: list[int] = []

        for migration in migrations:
            if migration.version in applied_versions:
                continue

            sql = migration.up_path.read_text(encoding="utf-8")
            self._apply_script(sql)
            with self._lock:
                self._conn.execute(
                    "INSERT INTO schema_migrations(version, name, applied_at) VALUES(?, ?, ?)",
                    (migration.version, migration.name, int(time.time())),
                )
                self._conn.commit()
            applied_now.append(migration.version)

        return applied_now

    def rollback(self, steps: int = 1) -> list[int]:
        if steps < 1:
            raise ValueError("steps must be >= 1")

        migrations_by_version = {m.version: m for m in self._discover_migrations()}
        applied = self._get_applied_versions()
        targets = sorted(applied, reverse=True)[:steps]
        rolled_back: list[int] = []

        for version in targets:
            migration = migrations_by_version.get(version)
            if migration is None:
                raise ValueError(f"Missing migration files for version {version}")

            sql = migration.down_path.read_text(encoding="utf-8")
            self._apply_script(sql)
            with self._lock:
                self._conn.execute(
                    "DELETE FROM schema_migrations WHERE version = ?",
                    (version,),
                )
                self._conn.commit()
            rolled_back.append(version)

        return rolled_back

    def status(self) -> list[dict[str, Any]]:
        migrations = self._discover_migrations()
        applied_rows = self._get_applied_rows()
        applied_by_version = {int(row["version"]): int(row["applied_at"]) for row in applied_rows}

        status_rows: list[dict[str, Any]] = []
        for migration in migrations:
            applied_at = applied_by_version.get(migration.version)
            status_rows.append(
                {
                    "version": migration.version,
                    "name": migration.name,
                    "applied": applied_at is not None,
                    "applied_at": applied_at,
                }
            )
        return status_rows

    def _discover_migrations(self) -> list[Migration]:
        if not self._migrations_dir.exists():
            return []

        up_files = sorted(self._migrations_dir.glob("*.up.sql"))
        migrations: list[Migration] = []

        for up_file in up_files:
            stem = up_file.name[:-7]  # strip ".up.sql"
            version_raw, _, name = stem.partition("_")
            if not version_raw.isdigit() or not name:
                continue

            down_file = self._migrations_dir / f"{version_raw}_{name}.down.sql"
            if not down_file.exists():
                raise ValueError(f"Missing down migration for {up_file.name}")

            migrations.append(
                Migration(
                    version=int(version_raw),
                    name=name,
                    up_path=up_file,
                    down_path=down_file,
                )
            )

        migrations.sort(key=lambda item: item.version)
        return migrations

    def _get_applied_versions(self) -> list[int]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT version FROM schema_migrations ORDER BY version ASC"
            ).fetchall()
        return [int(row["version"]) for row in rows]

    def _get_applied_rows(self) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(
                "SELECT version, applied_at FROM schema_migrations ORDER BY version ASC"
            ).fetchall()

    def _apply_script(self, script: str) -> None:
        statements = self._split_sql_statements(script)
        if not statements:
            return

        with self._lock:
            try:
                self._conn.execute("BEGIN")
                for statement in statements:
                    self._conn.execute(statement)
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    @staticmethod
    def _split_sql_statements(script: str) -> list[str]:
        statements: list[str] = []
        buffer = ""

        for line in script.splitlines(keepends=True):
            buffer += line
            if sqlite3.complete_statement(buffer):
                statement = buffer.strip()
                if statement:
                    statements.append(statement)
                buffer = ""

        trailing = buffer.strip()
        if trailing:
            statements.append(trailing)

        return statements
