#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

root_usage="$(df --output=pcent / | tail -1 | tr -cd '0-9')"
inode_usage="$(df --output=ipcent / | tail -1 | tr -cd '0-9')"
IFS=' ' read -r memory_total memory_available < <(free -b | awk '/^Mem:/ {print $2, $7}')
IFS=' ' read -r swap_total swap_used < <(free -b | awk '/^Swap:/ {print $2, $3}')
memory_usage=$(( (memory_total - memory_available) * 100 / memory_total ))
swap_usage=0
(( swap_total == 0 )) || swap_usage=$(( swap_used * 100 / swap_total ))
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
disk_warning="${MADAR_DISK_ALERT_PERCENT:-80}"
disk_critical="${MADAR_DISK_CRITICAL_PERCENT:-90}"
inode_warning="${MADAR_INODE_ALERT_PERCENT:-80}"
inode_critical="${MADAR_INODE_CRITICAL_PERCENT:-90}"
memory_warning="${MADAR_MEMORY_ALERT_PERCENT:-80}"
memory_critical="${MADAR_MEMORY_CRITICAL_PERCENT:-90}"
swap_warning="${MADAR_SWAP_ALERT_PERCENT:-60}"
swap_critical="${MADAR_SWAP_CRITICAL_PERCENT:-85}"
cache_warning="${MADAR_BUILD_CACHE_ALERT_BYTES:-107374182400}"
cache_critical="${MADAR_BUILD_CACHE_CRITICAL_BYTES:-161061273600}"
status=0
check_threshold() {
  local event="$1" value="$2" warning="$3" critical="$4"
  if (( value >= critical )); then
    "$(dirname "$0")/madar_alert_hook.sh" "$event" "severity=critical value=$value"
    status=2
  elif (( value >= warning )); then
    "$(dirname "$0")/madar_alert_hook.sh" "$event" "severity=warning value=$value"
    (( status >= 1 )) || status=1
  fi
}
check_threshold disk_threshold "$root_usage" "$disk_warning" "$disk_critical"
check_threshold inode_threshold "$inode_usage" "$inode_warning" "$inode_critical"
check_threshold memory_threshold "$memory_usage" "$memory_warning" "$memory_critical"
check_threshold swap_threshold "$swap_usage" "$swap_warning" "$swap_critical"
check_threshold docker_build_cache_threshold "$cache_bytes" "$cache_warning" "$cache_critical"
printf 'disk_percent=%s inode_percent=%s memory_percent=%s swap_percent=%s build_cache_bytes=%s\n' \
  "$root_usage" "$inode_usage" "$memory_usage" "$swap_usage" "$cache_bytes"
exit "$status"
