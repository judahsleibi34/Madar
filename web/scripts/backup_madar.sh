#!/usr/bin/env bash
# Keep this tracked LF-only: it is executed by Linux from cross-platform checkouts.
set -Eeuo pipefail
IFS=$'\n\t'
umask 077

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >&2; }
require() { command -v "$1" >/dev/null 2>&1 || die "required command not found: $1"; }
support="$(dirname "$0")/backup_support.py"
: "${MADAR_PROVIDER_BACKUP_REQUIRED:=true}"
export MADAR_PROVIDER_BACKUP_REQUIRED

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
  "builder-assets:${MADAR_BUILDER_ASSETS_DIR:-${MADAR_STORAGE_ROOT:-/app}/uploads}"
  "private-uploads:${MADAR_PRIVATE_UPLOADS_DIR:-${MADAR_STORAGE_ROOT:-/app}/private_uploads}"
  "generated-artifacts:${MADAR_GENERATED_ARTIFACTS_DIR:-${MADAR_STORAGE_ROOT:-/app}/private_generated_charts}"
  "avatars:${MADAR_AVATARS_DIR:-${MADAR_STORAGE_ROOT:-/app}/avatar_uploads}"
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
require pg_restore
require psql
require sha256sum
require cp
require python3
require flock
# Validate all sources before dumping; never manufacture a missing file set.
for entry in "${paths[@]}"; do
  [[ -d "${entry#*:}" ]] || die "required backup source is not a directory: ${entry%%:*}"
  python3 "$support" inventory "${entry#*:}"
done
[[ "${MADAR_PROVIDER_BACKUP_REQUIRED:-false}" =~ ^(true|false)$ ]] || die "invalid provider backup policy"
if [[ "${MADAR_PROVIDER_BACKUP_REQUIRED:-false}" == true ]]; then
  [[ -n "${SUPABASE_URL:-}" && -n "${SUPABASE_SERVICE_KEY:-}" ]] || die "provider backup credentials required"
fi
mkdir -p "$MADAR_BACKUP_DIR"
python3 - "$MADAR_BACKUP_DIR" "$support" <<'PY'
import importlib.util, pathlib, sys
spec = importlib.util.spec_from_file_location('backup_support', sys.argv[2])
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m.real_path(pathlib.Path(sys.argv[1]))
PY
[[ ! -L "$MADAR_BACKUP_DIR/.backup.lock" ]] || die "backup lock must not be a symlink"
exec 9>"$MADAR_BACKUP_DIR/.backup.lock"
flock -n 9 || die "another backup or replication is running"
mkdir -p "$work_path/files"
cleanup_incomplete() {
  if [[ -d "$work_path" ]]; then
    rm -rf --one-file-system "$work_path"
  fi
}
trap cleanup_incomplete EXIT
log "backup.start destination=$backup_path"
if [[ "${MADAR_PROVIDER_BACKUP_REQUIRED:-false}" == true ]]; then
  python3 "$support" provider-before "$work_path"
fi
pg_dump --format=custom --no-owner --no-acl \
  --file="$work_path/database.dump"
pg_restore --list "$work_path/database.dump" >/dev/null

for entry in "${paths[@]}"; do
  name="${entry%%:*}"
  source_path="${entry#*:}"
  [[ -d "$source_path" ]] || die "required backup source is not a directory: $name"
  mkdir -p "$work_path/files/$name"
  cp -a "$source_path/". "$work_path/files/$name/"
done

if [[ "${MADAR_PROVIDER_BACKUP_REQUIRED:-false}" == true ]]; then
  python3 "$support" provider-after "$work_path" "$backup_name"
fi
database_version="$(psql --no-psqlrc --tuples-only --no-align --command='show server_version')"
schema_version="$(psql --no-psqlrc --tuples-only --no-align --command="select schema_version from public.application_schema_state where contract_key='core'")"
public_tables="$(psql --no-psqlrc --tuples-only --no-align --command="select count(*) from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='public' and c.relkind='r'")"
export MADAR_BACKUP_PUBLIC_TABLES="$public_tables"
release_sha="${MADAR_RELEASE_SHA:-unknown}"
build_timestamp="${MADAR_BUILD_TIMESTAMP:-unknown}"
cat >"$work_path/backup.env" <<EOF
MADAR_BACKUP_FORMAT=3
MADAR_BACKUP_CREATED_AT=${timestamp}
MADAR_BACKUP_CONTENTS=database,builder-assets,private-uploads,generated-artifacts,avatars
EOF
python3 - "$work_path/manifest.json" "$backup_name" "$timestamp" "$release_sha" "$build_timestamp" "$database_version" "$schema_version" <<'PY'
import json,sys,os
manifest = {
  "backup_id": sys.argv[2],
  "created_at": sys.argv[3],
  "status": "complete",
  "format_version": 3,
  "script_version": "2026-08-25.1",
  "release": {"git_sha": sys.argv[4], "build_timestamp": sys.argv[5]},
  "database": {"server_version": sys.argv[6], "schema_version": sys.argv[7], "dump": "database.dump", "format": "postgres_custom"},
  "file_sets": ["builder-assets", "private-uploads", "generated-artifacts", "avatars"],
  "configuration": {"values_included": False, "required_inventory": "CONFIGURATION-INVENTORY.txt"},
  "checksums": "SHA256SUMS"
}
manifest['retention_managed'] = True
manifest['database']['public_tables'] = int(os.environ['MADAR_BACKUP_PUBLIC_TABLES'])
manifest['recovery'] = {
  'provider_objects_required': os.getenv('MADAR_PROVIDER_BACKUP_REQUIRED') == 'true',
  'platform_recovery_proven': False,
  'local_builder_assets_meaning': 'legacy public uploads; provider objects are separate',
}
with open(sys.argv[1], "x", encoding="utf-8") as handle:
    json.dump(manifest, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
cat >"$work_path/MANIFEST.txt" <<EOF
Madar backup: ${backup_name}
Created: ${timestamp}
Release SHA: ${release_sha}
Build timestamp: ${build_timestamp}
PostgreSQL: ${database_version}
Schema contract: ${schema_version}
Status: complete
EOF
cat >"$work_path/CONFIGURATION-INVENTORY.txt" <<'EOF'
Secret values are intentionally excluded. Restore requires separately escrowed:
- Madar environment file and encryption/token secrets
- Supabase project/database/auth/storage configuration and credentials
- Cloudflare tunnel credentials and sanitized ingress mapping
- SMTP/VAPID/OAuth credentials for enabled channels
- systemd unit installation and immutable release state/manifest
EOF
printf 'completed_at=%s\n' "$timestamp" >"$work_path/BACKUP_COMPLETE"
(
  cd "$work_path"
  find . -type f ! -name SHA256SUMS -print0 | LC_ALL=C sort -z | xargs -0 sha256sum >SHA256SUMS
  sha256sum --check --strict SHA256SUMS >/dev/null
)
python3 "$support" verify "$work_path"
mv -T "$work_path" "$backup_path"
trap - EXIT
log "backup.complete destination=$backup_path"
if [[ -n "${MADAR_BACKUP_FRESHNESS_MARKER:-}" ]]; then
  [[ "$MADAR_BACKUP_FRESHNESS_MARKER" = /* ]] || die "MADAR_BACKUP_FRESHNESS_MARKER must be an absolute path"
  python3 "$support" publish "$backup_path"
fi
python3 "$support" retain "$MADAR_BACKUP_DIR" "$backup_path" >&2
printf '%s\n' "$backup_path"
