#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'
umask 077

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
[[ $# -eq 1 ]] || die "usage: $0 VERIFIED_BACKUP_DIRECTORY"
backup_path="$(realpath -- "$1")"
: "${MADAR_OFFHOST_MOUNT:?MADAR_OFFHOST_MOUNT is required}"
: "${MADAR_OFFHOST_VOLUME_ID:?MADAR_OFFHOST_VOLUME_ID is required}"
: "${MADAR_BACKUP_AGE_RECIPIENTS_FILE:?MADAR_BACKUP_AGE_RECIPIENTS_FILE is required}"
mount_path="$(realpath -- "$MADAR_OFFHOST_MOUNT")"
[[ "$mount_path" = /* && "$mount_path" != / ]] || die "off-host mount must be an absolute non-root path"
mountpoint --quiet "$mount_path" || die "configured off-host destination is not a mounted filesystem"
findmnt --noheadings --output TARGET --target "$mount_path" | grep -Fx -- "$mount_path" >/dev/null \
  || die "configured path is not the mount root; refusing local-root fallback"
[[ -f "$mount_path/.madar-backup-volume" ]] || die "backup volume identity marker is missing"
[[ "$(tr -d '\r\n' <"$mount_path/.madar-backup-volume")" == "$MADAR_OFFHOST_VOLUME_ID" ]] \
  || die "backup volume identity does not match"
[[ -r "$MADAR_BACKUP_AGE_RECIPIENTS_FILE" ]] || die "age recipients file is unreadable"
command -v age >/dev/null || die "required command not found: age"
command -v tar >/dev/null || die "required command not found: tar"
"$(dirname "$0")/verify_backup.sh" "$backup_path"
required_bytes="$(du -sb "$backup_path" | awk '{print $1}')"
free_bytes="$(df --output=avail -B1 "$mount_path" | tail -1 | tr -d ' ')"
(( free_bytes > required_bytes * 2 )) || die "off-host destination has insufficient free space"
destination="$mount_path/madar-encrypted"
install -d -m 0700 "$destination"
name="$(basename "$backup_path").tar.age"
temporary="$destination/.${name}.incomplete.$$"
final="$destination/$name"
[[ ! -e "$final" ]] || die "encrypted off-host generation already exists"
trap 'rm -f -- "$temporary" "$temporary.sha256"' EXIT
tar --directory="$(dirname "$backup_path")" --create --file=- "$(basename "$backup_path")" \
  | age --recipients-file "$MADAR_BACKUP_AGE_RECIPIENTS_FILE" --output "$temporary"
digest="$(sha256sum "$temporary" | awk '{print $1}')"
printf '%s  %s\n' "$digest" "$(basename "$final")" >"$temporary.sha256"
mv "$temporary" "$final"
mv "$temporary.sha256" "$final.sha256"
(cd "$destination" && sha256sum --check --strict "$(basename "$final.sha256")" >/dev/null)
trap - EXIT
if [[ "${MADAR_OFFHOST_PRUNE:-NO}" == "YES" ]]; then
  find "$destination" -maxdepth 1 -type f \( -name 'madar-*.tar.age' -o -name 'madar-*.tar.age.sha256' \) \
    -mtime "+${MADAR_OFFHOST_RETENTION_DAYS:-35}" -delete
else
  find "$destination" -maxdepth 1 -type f -name 'madar-*.tar.age' \
    -mtime "+${MADAR_OFFHOST_RETENTION_DAYS:-35}" -print
fi
printf 'encrypted off-host backup created: %s\n' "$final"
