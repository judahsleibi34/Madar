#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

root_usage="$(df --output=pcent / | tail -1 | tr -cd '0-9')"
inode_usage="$(df --output=ipcent / | tail -1 | tr -cd '0-9')"
cache_bytes="$(docker system df --format '{{json .}}' 2>/dev/null | python3 -c '
import json,sys,re
total=0
for line in sys.stdin:
  row=json.loads(line)
  if row.get("Type") == "Build Cache":
    value=str(row.get("Size") or "0B")
    match=re.fullmatch(r"([0-9.]+)([kMGT]?B)", value)
    if match:
      total=int(float(match.group(1))*{"B":1,"kB":1000,"MB":1000**2,"GB":1000**3,"TB":1000**4}[match.group(2)])
print(total)
')"
disk_limit="${MADAR_DISK_ALERT_PERCENT:-80}"
inode_limit="${MADAR_INODE_ALERT_PERCENT:-80}"
cache_limit="${MADAR_BUILD_CACHE_ALERT_BYTES:-53687091200}"
status=0
(( root_usage < disk_limit )) || { "$(dirname "$0")/madar_alert_hook.sh" disk_threshold "root_percent=$root_usage"; status=1; }
(( inode_usage < inode_limit )) || { "$(dirname "$0")/madar_alert_hook.sh" inode_threshold "root_percent=$inode_usage"; status=1; }
(( cache_bytes < cache_limit )) || { "$(dirname "$0")/madar_alert_hook.sh" docker_build_cache_threshold "bytes=$cache_bytes"; status=1; }
printf 'disk_percent=%s inode_percent=%s build_cache_bytes=%s\n' "$root_usage" "$inode_usage" "$cache_bytes"
exit "$status"
