#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'
umask 077

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >&2; }
require() { command -v "$1" >/dev/null 2>&1 || die "required command not found: $1"; }

DRY_RUN=0
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1
[[ $# -le $DRY_RUN ]] || die "usage: $0 [--dry-run]"

: "${MADAR_BACKUP_DIR:?MADAR_BACKUP_DIR is required}"
: "${MADAR_DATABASE_URL:?MADAR_DATABASE_URL is required}"
[[ "$MADAR_BACKUP_DIR" = /* ]] || die "MADAR_BACKUP_DIR must be an absolute path"
[[ "$MADAR_BACKUP_DIR" != "/" ]] || die "MADAR_BACKUP_DIR must not be /"

timestamp="${MADAR_BACKUP_TIMESTAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
[[ "$timestamp" =~ ^[0-9]{8}T[0-9]{6}Z$ ]] || die "invalid MADAR_BACKUP_TIMESTAMP"
backup_path="${MADAR_BACKUP_DIR%/}/madar-${timestamp}"
[[ ! -e "$backup_path" ]] || die "backup destination already exists: $backup_path"

paths=(
  "builder-assets:${MADAR_BUILDER_ASSETS_DIR:-/app/builder-assets}"
  "private-uploads:${MADAR_PRIVATE_UPLOADS_DIR:-/app/private-uploads}"
  "generated-artifacts:${MADAR_GENERATED_ARTIFACTS_DIR:-/app/private_generated_charts}"
  "avatars:${MADAR_AVATARS_DIR:-/app/avatars}"
)

if (( DRY_RUN )); then
  printf 'backup_path=%s\n' "$backup_path"
  printf 'pg_dump --format=custom --no-owner --no-acl --file=%s/database.dump <MADAR_DATABASE_URL>\n' "$backup_path"
  for entry in "${paths[@]}"; do
    printf 'copy %s -> %s/files/%s\n' "${entry#*:}" "$backup_path" "${entry%%:*}"
  done
  printf 'sha256 manifest -> %s/SHA256SUMS\n' "$backup_path"
  exit 0
fi

require pg_dump
require sha256sum
require cp
mkdir -p "$backup_path/files"
log "backup.start destination=$backup_path"
pg_dump --dbname="$MADAR_DATABASE_URL" --format=custom --no-owner --no-acl \
  --file="$backup_path/database.dump"

for entry in "${paths[@]}"; do
  name="${entry%%:*}"
  source_path="${entry#*:}"
  [[ -d "$source_path" ]] || die "required backup source is not a directory: $name"
  mkdir -p "$backup_path/files/$name"
  cp -a "$source_path/". "$backup_path/files/$name/"
done

cat >"$backup_path/backup.env" <<EOF
MADAR_BACKUP_FORMAT=1
MADAR_BACKUP_CREATED_AT=${timestamp}
MADAR_BACKUP_CONTENTS=database,builder-assets,private-uploads,generated-artifacts,avatars
EOF
(
  cd "$backup_path"
  find . -type f ! -name SHA256SUMS -print0 | LC_ALL=C sort -z | xargs -0 sha256sum >SHA256SUMS
)
log "backup.complete destination=$backup_path"
printf '%s\n' "$backup_path"
