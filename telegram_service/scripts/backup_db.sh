#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

source "$SCRIPT_DIR/backup.env"

DB_CONTAINER="${DB_CONTAINER:-telegram_service-db-1}"
DB_NAME="${DB_NAME:-telegram_service}"
DB_USER="${DB_USER:-telegram}"
BACKUP_DIR="${BACKUP_DIR:-/opt/master_stack/app/telegram_service/backups}"
RETENTION_KEEP="${RETENTION_KEEP:-14}"
BACKUP_PASSPHRASE="${BACKUP_PASSPHRASE:-}"

if [[ -z "$BACKUP_PASSPHRASE" ]]; then
  echo "BACKUP_PASSPHRASE is required" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"

if ! [[ "$RETENTION_KEEP" =~ ^[0-9]+$ ]]; then
  echo "RETENTION_KEEP must be a non-negative integer" >&2
  exit 1
fi

timestamp="$(date +%Y%m%d_%H%M%S)"
base_name="${DB_NAME}_${timestamp}"
plain_dump="$BACKUP_DIR/${base_name}.dump"
enc_dump="$BACKUP_DIR/${base_name}.dump.gpg"

cleanup() {
  rm -f "$plain_dump"
}
trap cleanup EXIT

docker exec "$DB_CONTAINER" pg_dump -Fc -U "$DB_USER" "$DB_NAME" >"$plain_dump"

printf '%s' "$BACKUP_PASSPHRASE" | gpg --batch --yes --pinentry-mode loopback --passphrase-fd 0 -c -o "$enc_dump" "$plain_dump"

rm -f "$plain_dump"
trap - EXIT

meta_tmp="$BACKUP_DIR/last_backup.json.tmp"
meta_file="$BACKUP_DIR/last_backup.json"

cat <<META >"$meta_tmp"
{
  "timestamp": "${timestamp}",
  "database": "${DB_NAME}",
  "container": "${DB_CONTAINER}",
  "user": "${DB_USER}",
  "backup_file": "$(basename "$enc_dump")",
  "backup_dir": "${BACKUP_DIR}"
}
META

mv -f "$meta_tmp" "$meta_file"

if [[ "$RETENTION_KEEP" -gt 0 ]]; then
  mapfile -t backups < <(ls -1t "$BACKUP_DIR"/*.dump.gpg 2>/dev/null || true)
  if [[ ${#backups[@]} -gt "$RETENTION_KEEP" ]]; then
    for old in "${backups[@]:$RETENTION_KEEP}"; do
      rm -f "$old"
    done
  fi
fi

echo "Backup created: $enc_dump"
