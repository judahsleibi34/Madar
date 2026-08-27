#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'
: "${MADAR_BACKUP_FRESHNESS_MARKER:?MADAR_BACKUP_FRESHNESS_MARKER is required}"
read -r _timestamp backup_path <"$MADAR_BACKUP_FRESHNESS_MARKER"
[[ "$backup_path" = /* && -d "$backup_path" ]] || { echo "invalid latest-backup marker" >&2; exit 1; }
exec "$(dirname "$0")/replicate_backup_offhost.sh" "$backup_path"
