#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

event="${1:-unknown}"
detail="${2:-no-detail}"
logger --tag madar-operations --priority user.err -- "event=$event detail=$detail"
if [[ -n "${MADAR_ALERT_PROVIDER_HOOK:-}" ]]; then
  [[ "$MADAR_ALERT_PROVIDER_HOOK" = /* && -x "$MADAR_ALERT_PROVIDER_HOOK" ]] \
    || { echo "configured alert hook is not an executable absolute path" >&2; exit 1; }
  exec "$MADAR_ALERT_PROVIDER_HOOK" "$event" "$detail"
fi
printf 'Madar alert recorded locally; no external provider hook configured. event=%s\n' "$event" >&2
