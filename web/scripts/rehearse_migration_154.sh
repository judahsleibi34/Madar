#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUN_MIGRATION_154=1 bash "${ROOT_DIR}/web/scripts/rehearse_migration_153.sh"
