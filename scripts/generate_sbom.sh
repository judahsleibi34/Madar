#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'
umask 077

[[ $# -eq 1 ]] || { printf 'usage: %s ABSOLUTE_OUTPUT_DIR\n' "$0" >&2; exit 2; }
output_dir="$1"
[[ "$output_dir" = /* && "$output_dir" != "/" ]] || { printf 'output directory must be an absolute non-root path\n' >&2; exit 2; }
mkdir -p "$output_dir"
repo_root="$(cd "$(dirname "$0")/.." && pwd -P)"

frontend_tmp="$output_dir/frontend-runtime.cdx.json.tmp.$$"
backend_tmp="$output_dir/backend-pip-inspect.json.tmp.$$"
node_image="node:22-alpine@sha256:16e22a550f3863206a3f701448c45f7912c6896a62de43add43bb9c86130c3e2"
docker run --rm --user "$(id -u):$(id -g)" \
  --volume "$repo_root/frontend:/app:ro" --workdir /app "$node_image" \
  npm sbom --omit=dev --sbom-format=cyclonedx >"$frontend_tmp"
docker compose -f "$repo_root/docker-compose.yml" run --rm --no-deps \
  backend python -m pip inspect --local >"$backend_tmp"
mv "$frontend_tmp" "$output_dir/frontend-runtime.cdx.json"
mv "$backend_tmp" "$output_dir/backend-pip-inspect.json"
printf 'SBOM files written to %s\n' "$output_dir"
