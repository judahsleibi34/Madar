#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

[[ $# -ge 1 && $# -le 2 ]] || { echo "usage: $0 FULL_GIT_SHA [--manual-retry]" >&2; exit 64; }
sha="$1"
retry="${2:-}"
[[ "$sha" =~ ^[0-9a-f]{40}$ ]] || { echo "a full lowercase Git SHA is required" >&2; exit 64; }
[[ -z "$retry" || "$retry" == "--manual-retry" ]] || { echo "unsupported option: $retry" >&2; exit 64; }

repo="$(cd "$(dirname "$0")/../.." && pwd -P)"
runtime_root="${MADAR_STAGING_RUNTIME_ROOT:-/tmp/madar-pre-go-stage}"
env_file="$runtime_root/staging.env"
[[ -f "$env_file" ]] || { echo "missing staging environment: $env_file" >&2; exit 1; }
[[ -d "$runtime_root/storage/uploads" ]] || { echo "staging storage is not prepared" >&2; exit 1; }

set -a
# shellcheck disable=SC1090
. "$env_file"
set +a
export SUPABASE_URL="http://127.0.0.1:15430"
export MADAR_PRODUCTION_REPO="$repo"
export MADAR_DEPLOY_STATE_ROOT="$runtime_root/state/releases"
export MADAR_ENV_FILE="$env_file"
export MADAR_COMPOSE_OVERRIDE="$repo/web/staging/docker-compose.slot.yml"
export MADAR_STORAGE_ROOT="$runtime_root/storage"
export MADAR_TRAFFIC_SWITCH_COMMAND="$repo/web/deployment/bin/madar-switch-traffic"
export MADAR_TRAFFIC_SWITCH_DRIVER="file-proxy"
export MADAR_ACTIVE_TARGET_FILE="$runtime_root/state/active-target.json"
export MADAR_RELEASE_OBSERVE_SECONDS="${MADAR_RELEASE_OBSERVE_SECONDS:-10}"

arguments=("$sha")
[[ "$retry" == "--manual-retry" ]] && arguments=("--manual-retry" "$sha")
exec python3 "$repo/web/deployment/bin/madar-release-deploy" "${arguments[@]}"
