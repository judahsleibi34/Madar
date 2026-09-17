#!/usr/bin/env bash
set -Eeuo pipefail
[[ "${1:-}" == "--confirm" && $# -eq 1 ]] || { echo "usage: $0 --confirm" >&2; exit 64; }
before="$(docker system df --verbose)"
printf '%s\n' "$before"
# Build cache only; images, containers, volumes and active layers are outside
# this command. The age floor protects recent rollback/build investigations.
docker builder prune --force --filter "until=${MADAR_BUILD_CACHE_MIN_AGE_HOURS:-168}h"
docker system df
