#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
: "${MADAR_BACKUP_DIR:?MADAR_BACKUP_DIR is required}"
: "${MADAR_BACKUP_FRESHNESS_MARKER:?MADAR_BACKUP_FRESHNESS_MARKER is required}"
backup_path="$(python3 "$(dirname "$0")/backup_support.py" latest "$MADAR_BACKUP_FRESHNESS_MARKER")"
printf 'latest backup verified: %s\n' "$backup_path"
