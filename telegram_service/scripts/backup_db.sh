#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [[ -f "$SCRIPT_DIR/backup.env" ]]; then
  source "$SCRIPT_DIR/backup.env"
fi

DB_HOST="${DB_HOST:-db}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-telegram_service}"
DB_USER="${DB_USER:-telegram}"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_ROOT/backups}"
RETENTION_KEEP="${RETENTION_KEEP:-14}"
BACKUP_PASSPHRASE="${BACKUP_PASSPHRASE:-}"
TG_BOT_TOKEN="${TG_BOT_TOKEN:-}"
TG_BACKUP_CHAT_ID="${TG_BACKUP_CHAT_ID:-}"
TG_SEND_AS_DOCUMENT="${TG_SEND_AS_DOCUMENT:-1}"
TG_CAPTION_PREFIX="${TG_CAPTION_PREFIX:-}"

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
created_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
base_name="${DB_NAME}_${timestamp}"
plain_dump="$BACKUP_DIR/${base_name}.dump"
enc_dump="$BACKUP_DIR/${base_name}.dump.gpg"

cleanup() {
  rm -f "$plain_dump"
}
trap cleanup EXIT

pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -Fc "$DB_NAME" >"$plain_dump"

printf '%s' "$BACKUP_PASSPHRASE" | gpg --batch --yes --pinentry-mode loopback --passphrase-fd 0 -c -o "$enc_dump" "$plain_dump"

rm -f "$plain_dump"
trap - EXIT

meta_tmp="$BACKUP_DIR/last_backup.json.tmp"
meta_file="$BACKUP_DIR/last_backup.json"
file_size_bytes="$(wc -c <"$enc_dump" | tr -d '[:space:]')"
size_mb="$(awk -v bytes="$file_size_bytes" 'BEGIN { printf "%.2f", bytes / 1024 / 1024 }')"

cat <<META >"$meta_tmp"
{
  "timestamp": "${timestamp}",
  "created_at": "${created_at}",
  "database": "${DB_NAME}",
  "container": "${DB_HOST}",
  "user": "${DB_USER}",
  "backup_file": "$(basename "$enc_dump")",
  "backup_dir": "${BACKUP_DIR}",
  "backup_size_bytes": ${file_size_bytes},
  "backup_size_mb": ${size_mb}
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

send_backup_to_telegram() {
  local backup_path="$1"
  local caption
  local response_body
  local http_code
  local curl_exit

  caption="${TG_CAPTION_PREFIX:+${TG_CAPTION_PREFIX} }DB backup OK
db=${DB_NAME}
created_at=${created_at}
file=$(basename "$backup_path")
size=${size_mb}MB"

  if [[ "$TG_SEND_AS_DOCUMENT" != "1" ]]; then
    echo "Telegram upload disabled: TG_SEND_AS_DOCUMENT=$TG_SEND_AS_DOCUMENT"
    return 0
  fi

  response_body="$(mktemp)"

  set +e
  http_code="$({
    curl -sS -o "$response_body" -w '%{http_code}' \
      -X POST \
      -F "chat_id=${TG_BACKUP_CHAT_ID}" \
      -F "caption=${caption}" \
      -F "document=@${backup_path}" \
      "https://api.telegram.org/bot${TG_BOT_TOKEN}/sendDocument"
  })"
  curl_exit=$?
  set -e

  if [[ $curl_exit -ne 0 ]]; then
    echo "Telegram upload failed: curl exit code $curl_exit"
    rm -f "$response_body"
    return 0
  fi

  if [[ "$http_code" -lt 200 || "$http_code" -gt 299 ]]; then
    echo "Telegram upload failed: HTTP $http_code"
    sed -e 's/"description":"[^"]*"/"description":"<redacted>"/' "$response_body" >&2 || true
    rm -f "$response_body"
    return 0
  fi

  rm -f "$response_body"
  echo "Telegram upload completed"
}

if [[ -n "$TG_BOT_TOKEN" && -n "$TG_BACKUP_CHAT_ID" ]]; then
  send_backup_to_telegram "$enc_dump"
else
  echo "Telegram upload skipped: TG_BOT_TOKEN/TG_BACKUP_CHAT_ID not set"
fi

echo "Backup created: $enc_dump"
