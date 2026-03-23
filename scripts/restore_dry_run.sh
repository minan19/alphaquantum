#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_BACKUP="${1:-}"
DRY_DB="${2:-$ROOT_DIR/tmp/restore_dry_run.db}"

if ! command -v sqlite3 >/dev/null 2>&1; then
  echo "ERROR: sqlite3 not found in PATH" >&2
  exit 1
fi

if [[ -z "$SOURCE_BACKUP" ]]; then
  echo "USAGE: $0 <backup_file> [dry_run_db_path]" >&2
  exit 1
fi

if [[ ! -f "$SOURCE_BACKUP" ]]; then
  echo "ERROR: backup file not found: $SOURCE_BACKUP" >&2
  exit 1
fi

mkdir -p "$(dirname "$DRY_DB")"
cp "$SOURCE_BACKUP" "$DRY_DB"

TABLE_COUNT="$(sqlite3 "$DRY_DB" "SELECT COUNT(*) FROM sqlite_master WHERE type='table';")"
USERS_COUNT="$(sqlite3 "$DRY_DB" "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='users';")"
MIG_COUNT="$(sqlite3 "$DRY_DB" "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='schema_migrations';")"

if [[ "$TABLE_COUNT" -lt 1 ]]; then
  echo "RESTORE_DRY_RUN_FAIL reason=no_tables db=$DRY_DB" >&2
  exit 1
fi

if [[ "$USERS_COUNT" -lt 1 || "$MIG_COUNT" -lt 1 ]]; then
  echo "RESTORE_DRY_RUN_FAIL reason=missing_core_tables db=$DRY_DB users=$USERS_COUNT migrations=$MIG_COUNT" >&2
  exit 1
fi

echo "RESTORE_DRY_RUN_OK db=$DRY_DB tables=$TABLE_COUNT users_table=$USERS_COUNT migrations_table=$MIG_COUNT"
