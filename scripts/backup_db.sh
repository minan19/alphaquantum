#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB_PATH="${AQ_DATABASE_PATH:-$ROOT_DIR/alpha_quantum.db}"
BACKUP_DIR="${1:-$ROOT_DIR/backups}"
STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_FILE="$BACKUP_DIR/alpha_quantum_${STAMP}.db"

if ! command -v sqlite3 >/dev/null 2>&1; then
  echo "ERROR: sqlite3 not found in PATH" >&2
  exit 1
fi

if [[ ! -f "$DB_PATH" ]]; then
  echo "ERROR: database file not found: $DB_PATH" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"

sqlite3 "$DB_PATH" ".timeout 5000" ".backup '$BACKUP_FILE'"

echo "BACKUP_OK file=$BACKUP_FILE source=$DB_PATH"
