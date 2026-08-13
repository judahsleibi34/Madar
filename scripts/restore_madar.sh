#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'
umask 077

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
DRY_RUN=0
[[ "${1:-}" == "--dry-run" ]] && { DRY_RUN=1; shift; }
[[ $# -eq 1 ]] || die "usage: $0 [--dry-run] BACKUP_DIRECTORY"
backup_path="$1"
: "${MADAR_DATABASE_URL:?MADAR_DATABASE_URL (backup source identity) is required}"
: "${MADAR_RESTORE_DATABASE_URL:?MADAR_RESTORE_DATABASE_URL is required}"
[[ "$MADAR_DATABASE_URL" != "$MADAR_RESTORE_DATABASE_URL" ]] || die "restore target must differ from backup source"
[[ "${MADAR_RESTORE_CONFIRM_ISOLATED:-}" == "YES" ]] || die "set MADAR_RESTORE_CONFIRM_ISOLATED=YES after verifying the target is isolated"
case "$MADAR_RESTORE_DATABASE_URL" in
  *localhost*|*127.0.0.1*|*host.docker.internal*|*test*|*staging*) ;;
  *) die "restore target is not recognizably isolated; use a local/test/staging host" ;;
esac

"$(dirname "$0")/verify_backup.sh" "$backup_path"
targets=(
  "builder-assets:${MADAR_RESTORE_BUILDER_ASSETS_DIR:?required}"
  "private-uploads:${MADAR_RESTORE_PRIVATE_UPLOADS_DIR:?required}"
  "generated-artifacts:${MADAR_RESTORE_GENERATED_ARTIFACTS_DIR:?required}"
  "avatars:${MADAR_RESTORE_AVATARS_DIR:?required}"
)
for entry in "${targets[@]}"; do
  target="${entry#*:}"
  [[ "$target" = /* && "$target" != "/" ]] || die "restore paths must be absolute and must not be /"
  [[ ! -e "$target" || -d "$target" ]] || die "restore path is not a directory: $target"
done

if (( DRY_RUN )); then
  printf 'pg_restore --exit-on-error --single-transaction --clean --if-exists --no-owner --no-acl --dbname=<MADAR_RESTORE_DATABASE_URL> %s/database.dump\n' "$backup_path"
  for entry in "${targets[@]}"; do
    printf 'copy %s/files/%s -> %s\n' "$backup_path" "${entry%%:*}" "${entry#*:}"
  done
  exit 0
fi

command -v pg_restore >/dev/null 2>&1 || die "required command not found: pg_restore"
pg_restore --dbname="$MADAR_RESTORE_DATABASE_URL" --exit-on-error --single-transaction \
  --clean --if-exists --no-owner --no-acl "$backup_path/database.dump"
for entry in "${targets[@]}"; do
  name="${entry%%:*}"
  target="${entry#*:}"
  mkdir -p "$target"
  cp -a "$backup_path/files/$name/". "$target/"
done
printf 'restore completed; run application and schema verification against the isolated target\n'
