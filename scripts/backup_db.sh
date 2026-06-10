#!/usr/bin/env bash
# Alpha Quantum — SQLite backup script (D3: production-grade)
#
# Features:
#   * Hot backup via sqlite3 .backup (WAL-safe, no file locks)
#   * Gzip compression
#   * Retention rotation: keep N daily + M weekly (default 7d + 4w)
#   * Optional S3 upload (set AQ_BACKUP_S3_BUCKET)
#   * Cron-friendly: stable exit codes, single-line log per phase
#   * Idempotent: safe to invoke multiple times in same minute
#
# Usage:
#   ./scripts/backup_db.sh                  # default ./backups/
#   ./scripts/backup_db.sh /path/to/backups # custom dir
#
# Environment variables:
#   AQ_DATABASE_PATH        — DB path (default ./alpha_quantum.db)
#   AQ_BACKUP_KEEP_DAILY    — daily backups to retain (default 7)
#   AQ_BACKUP_KEEP_WEEKLY   — weekly backups to retain (default 4)
#   AQ_BACKUP_S3_BUCKET     — S3 bucket name (empty = skip upload)
#   AQ_BACKUP_S3_PREFIX     — S3 key prefix (default "alpha-quantum/db/")
#   AQ_BACKUP_AWS_PROFILE   — AWS CLI profile (optional)
#
# Exit codes:
#   0  — backup + (optional) upload succeeded
#   1  — environment / dependency error
#   2  — backup failed
#   3  — upload failed (backup still on disk)
#
# Cron example (daily 03:15 UTC, log to syslog):
#   15 3 * * * /opt/aq/scripts/backup_db.sh >> /var/log/aq-backup.log 2>&1

set -euo pipefail

# ---------- config -----------------------------------------------------------
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB_PATH="${AQ_DATABASE_PATH:-$ROOT_DIR/alpha_quantum.db}"
BACKUP_DIR="${1:-$ROOT_DIR/backups}"
KEEP_DAILY="${AQ_BACKUP_KEEP_DAILY:-7}"
KEEP_WEEKLY="${AQ_BACKUP_KEEP_WEEKLY:-4}"
S3_BUCKET="${AQ_BACKUP_S3_BUCKET:-}"
S3_PREFIX="${AQ_BACKUP_S3_PREFIX:-alpha-quantum/db/}"
AWS_PROFILE_ARG=""
[[ -n "${AQ_BACKUP_AWS_PROFILE:-}" ]] && AWS_PROFILE_ARG="--profile $AQ_BACKUP_AWS_PROFILE"

STAMP="$(date -u +%Y%m%d_%H%M%S)"
DOW="$(date -u +%u)"  # 1..7 (Mon..Sun)
BACKUP_FILE="$BACKUP_DIR/daily/alpha_quantum_${STAMP}.db"
WEEKLY_FILE="$BACKUP_DIR/weekly/alpha_quantum_${STAMP}.db"

# ---------- helpers ----------------------------------------------------------
log() { printf '%s | %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
err() { log "ERROR $*" >&2; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { err "missing command: $1"; exit 1; }
}

# ---------- pre-flight -------------------------------------------------------
require_cmd sqlite3
require_cmd gzip

if [[ ! -f "$DB_PATH" ]]; then
  err "database file not found: $DB_PATH"
  exit 1
fi

mkdir -p "$BACKUP_DIR/daily" "$BACKUP_DIR/weekly"

# ---------- backup -----------------------------------------------------------
log "BACKUP_START source=$DB_PATH dest=$BACKUP_FILE"

if ! sqlite3 "$DB_PATH" ".timeout 5000" ".backup '$BACKUP_FILE'"; then
  err "sqlite3 .backup failed"
  rm -f "$BACKUP_FILE"
  exit 2
fi

if ! gzip -9 "$BACKUP_FILE"; then
  err "gzip failed on $BACKUP_FILE"
  rm -f "$BACKUP_FILE" "$BACKUP_FILE.gz"
  exit 2
fi
BACKUP_FILE="${BACKUP_FILE}.gz"

SIZE=$(wc -c < "$BACKUP_FILE" | tr -d ' ')
log "BACKUP_OK file=$BACKUP_FILE bytes=$SIZE"

# Weekly snapshot on Sunday (DOW=7)
if [[ "$DOW" == "7" ]]; then
  WEEKLY_FILE="${WEEKLY_FILE}.gz"
  cp "$BACKUP_FILE" "$WEEKLY_FILE"
  log "WEEKLY_OK file=$WEEKLY_FILE"
fi

# ---------- retention --------------------------------------------------------
prune_dir() {
  local dir="$1" keep="$2" label="$3" f
  # newest-first list; tail picks files past the keep cutoff.
  # While-read loop is portable to bash 3.2 (macOS) — avoids mapfile (bash 4+).
  ls -1t "$dir"/alpha_quantum_*.db.gz 2>/dev/null \
    | tail -n +"$((keep + 1))" \
    | while IFS= read -r f; do
        [[ -n "$f" ]] || continue
        rm -f "$f"
        log "PRUNE_$label removed=$f"
      done
}

prune_dir "$BACKUP_DIR/daily" "$KEEP_DAILY" "DAILY"
prune_dir "$BACKUP_DIR/weekly" "$KEEP_WEEKLY" "WEEKLY"

# ---------- S3 upload (optional) --------------------------------------------
if [[ -n "$S3_BUCKET" ]]; then
  require_cmd aws
  S3_KEY="${S3_PREFIX}$(basename "$BACKUP_FILE")"
  log "S3_UPLOAD_START bucket=$S3_BUCKET key=$S3_KEY"
  if ! aws s3 cp $AWS_PROFILE_ARG "$BACKUP_FILE" "s3://${S3_BUCKET}/${S3_KEY}" \
       --storage-class STANDARD_IA --only-show-errors; then
    err "S3 upload failed"
    exit 3
  fi
  log "S3_UPLOAD_OK key=$S3_KEY"
fi

log "BACKUP_DONE"
exit 0
