#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
[[ $# -eq 1 ]] || die "usage: $0 BACKUP_DIRECTORY"
backup_path="$1"
[[ -d "$backup_path" ]] || die "backup directory does not exist"

required=(backup.env database.dump SHA256SUMS files/builder-assets files/private-uploads files/generated-artifacts files/avatars)
for member in "${required[@]}"; do
  [[ -e "$backup_path/$member" ]] || die "missing backup member: $member"
done
format="$(sed -n 's/^MADAR_BACKUP_FORMAT=//p' "$backup_path/backup.env")"
[[ "$format" == "1" || "$format" == "2" ]] || die "unsupported backup format"
if [[ "$format" == "2" ]]; then
  [[ -f "$backup_path/BACKUP_COMPLETE" ]] || die "missing backup member: BACKUP_COMPLETE"
fi
(
  cd "$backup_path"
  sha256sum --check --strict SHA256SUMS >/dev/null
) || die "checksum verification failed"
printf 'backup verification passed: %s\n' "$backup_path"
