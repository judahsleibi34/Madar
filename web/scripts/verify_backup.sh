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
[[ "$format" == "1" || "$format" == "2" || "$format" == "3" ]] || die "unsupported backup format"
if [[ "$format" == "2" || "$format" == "3" ]]; then
  [[ -f "$backup_path/BACKUP_COMPLETE" ]] || die "missing backup member: BACKUP_COMPLETE"
fi
if [[ "$format" == "3" ]]; then
  for member in manifest.json MANIFEST.txt CONFIGURATION-INVENTORY.txt; do
    [[ -f "$backup_path/$member" ]] || die "missing backup member: $member"
  done
  python3 - "$backup_path/manifest.json" <<'PY' || die "manifest validation failed"
import json,re,sys
with open(sys.argv[1], encoding="utf-8") as handle:
    manifest=json.load(handle)
assert manifest.get("format_version") == 3
assert manifest.get("status") == "complete"
assert re.fullmatch(r"madar-[0-9]{8}T[0-9]{6}Z", manifest.get("backup_id", ""))
assert manifest.get("database", {}).get("dump") == "database.dump"
assert manifest.get("checksums") == "SHA256SUMS"
assert manifest.get("configuration", {}).get("values_included") is False
PY
fi
(
  cd "$backup_path"
  sha256sum --check --strict SHA256SUMS >/dev/null
) || die "checksum verification failed"
command -v pg_restore >/dev/null 2>&1 || die "required command not found: pg_restore"
pg_restore --list "$backup_path/database.dump" >/dev/null || die "database dump TOC is unreadable"
printf 'backup verification passed: %s\n' "$backup_path"
