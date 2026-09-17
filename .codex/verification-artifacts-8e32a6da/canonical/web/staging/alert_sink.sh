#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

[[ $# -eq 2 ]] || { echo "usage: $0 EVENT DETAIL" >&2; exit 64; }
sink="${MADAR_ALERT_SINK_FILE:-}"
[[ "$sink" = /* && "$sink" != "/" ]] || { echo "MADAR_ALERT_SINK_FILE must be an absolute non-root path" >&2; exit 64; }
[[ ! -L "$sink" ]] || { echo "refusing symlink alert sink" >&2; exit 1; }
mkdir -p "$(dirname "$sink")"
timestamp="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
line="$(python3 -c 'import json,sys; print(json.dumps({"timestamp":sys.argv[1],"event":sys.argv[2],"detail":sys.argv[3]},sort_keys=True))' "$timestamp" "$1" "$2")"
(
  flock -x 9
  printf '%s\n' "$line" >&9
) 9>>"$sink"
chmod 0600 "$sink"
