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
: "${PGHOST:?PGHOST is required}"
: "${PGPORT:?PGPORT is required}"
: "${PGUSER:?PGUSER is required}"
: "${PGPASSWORD:?PGPASSWORD is required}"
: "${PGDATABASE:?PGDATABASE is required}"
[[ "$MADAR_BACKUP_DIR" = /* ]] || die "MADAR_BACKUP_DIR must be an absolute path"
[[ "$MADAR_BACKUP_DIR" != "/" ]] || die "MADAR_BACKUP_DIR must not be /"

timestamp="${MADAR_BACKUP_TIMESTAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
[[ "$timestamp" =~ ^[0-9]{8}T[0-9]{6}Z$ ]] || die "invalid MADAR_BACKUP_TIMESTAMP"
backup_name="madar-${timestamp}"
backup_path="${MADAR_BACKUP_DIR%/}/${backup_name}"
work_path="${MADAR_BACKUP_DIR%/}/.${backup_name}.incomplete.$$"
[[ ! -e "$backup_path" ]] || die "backup destination already exists: $backup_path"
[[ ! -e "$work_path" ]] || die "backup staging destination already exists: $work_path"

paths=(
  "builder-assets:${MADAR_BUILDER_ASSETS_DIR:-/app/builder-assets}"
  "private-uploads:${MADAR_PRIVATE_UPLOADS_DIR:-/app/private-uploads}"
  "generated-artifacts:${MADAR_GENERATED_ARTIFACTS_DIR:-/app/private_generated_charts}"
  "avatars:${MADAR_AVATARS_DIR:-/app/avatars}"
)

if (( DRY_RUN )); then
  printf 'backup_path=%s\n' "$backup_path"
  printf 'pg_dump --format=custom --no-owner --no-acl --file=%s/database.dump <libpq environment>\n' "$backup_path"
  for entry in "${paths[@]}"; do
    printf 'copy %s -> %s/files/%s\n' "${entry#*:}" "$backup_path" "${entry%%:*}"
  done
  printf 'sha256 manifest -> %s/SHA256SUMS\n' "$backup_path"
  exit 0
fi

require pg_dump
require sha256sum
require cp
mkdir -p "$MADAR_BACKUP_DIR"
mkdir -p "$work_path/files"
log "backup.start destination=$backup_path"
pg_dump --format=custom --no-owner --no-acl \
  --file="$work_path/database.dump"

for entry in "${paths[@]}"; do
  name="${entry%%:*}"
  source_path="${entry#*:}"
  [[ -d "$source_path" ]] || die "required backup source is not a directory: $name"
  mkdir -p "$work_path/files/$name"
  cp -a "$source_path/". "$work_path/files/$name/"
done

cat >"$work_path/backup.env" <<EOF
MADAR_BACKUP_FORMAT=2
MADAR_BACKUP_CREATED_AT=${timestamp}
MADAR_BACKUP_CONTENTS=database,builder-assets,private-uploads,generated-artifacts,avatars
EOF
printf 'completed_at=%s\n' "$timestamp" >"$work_path/BACKUP_COMPLETE"
(
  cd "$work_path"
  find . -type f ! -name SHA256SUMS -print0 | LC_ALL=C sort -z | xargs -0 sha256sum >SHA256SUMS
  sha256sum --check --strict SHA256SUMS >/dev/null
)
mv -T "$work_path" "$backup_path"
log "backup.complete destination=$backup_path"
if [[ -n "${MADAR_BACKUP_FRESHNESS_MARKER:-}" ]]; then
  [[ "$MADAR_BACKUP_FRESHNESS_MARKER" = /* ]] || die "MADAR_BACKUP_FRESHNESS_MARKER must be an absolute path"
  mkdir -p "$(dirname "$MADAR_BACKUP_FRESHNESS_MARKER")"
  marker_tmp="${MADAR_BACKUP_FRESHNESS_MARKER}.tmp.$$"
  printf '%s %s\n' "$timestamp" "$backup_path" >"$marker_tmp"
  mv "$marker_tmp" "$MADAR_BACKUP_FRESHNESS_MARKER"
fi
printf '%s\n' "$backup_path"
