#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
WEB_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
# No host /etc,controller directory,daemon socket,DB or credentials are mounted.
/usr/bin/docker --host unix:///var/run/docker.sock run --rm --network none \
  --hostname madar-policy-native --user 0:0 --read-only --memory=192m --cpus=0.5 --pids-limit=64 \
  --label madar.rehearsal=root-policy-filesystem \
  --tmpfs /etc/madar:rw,noexec,nosuid,nodev,size=1m,mode=700 \
  --env MIGRATION_POLICY_NATIVE_FILESYSTEM=1 --env PYTHONDONTWRITEBYTECODE=1 \
  --env PYTHONPATH=/test-repository:/test-repository/backend/tests \
  --env MADAR_TEST_REPOSITORY_ROOT=/test-repository \
  --volume "$WEB_ROOT:/test-repository:ro" \
  --entrypoint python "${BACKEND_TEST_IMAGE:-madar-backend-test}" \
  -m unittest test_migration_policy_filesystem -v
