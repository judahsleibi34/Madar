#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
: "${MADAR_BACKUP_FRESHNESS_MARKER:?MADAR_BACKUP_FRESHNESS_MARKER is required}"
: "${MADAR_BACKUP_MAX_AGE_SECONDS:=129600}"
[[ -f "$MADAR_BACKUP_FRESHNESS_MARKER" ]] || die "backup freshness marker is missing"
read -r timestamp backup_path <"$MADAR_BACKUP_FRESHNESS_MARKER"
[[ "$backup_path" = /* && -d "$backup_path" ]] || die "backup marker target is invalid"
age="$(( $(date -u +%s) - $(stat -c %Y "$MADAR_BACKUP_FRESHNESS_MARKER") ))"
(( age >= 0 && age <= MADAR_BACKUP_MAX_AGE_SECONDS )) || die "latest backup is stale"
"$(dirname "$0")/verify_backup.sh" "$backup_path"
printf 'latest backup verified: %s age_seconds=%s timestamp=%s\n' "$backup_path" "$age" "$timestamp"
