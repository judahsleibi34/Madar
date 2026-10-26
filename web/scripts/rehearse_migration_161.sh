#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
bash "${ROOT_DIR}/web/scripts/rehearse_data_sources_upgrade_136_161.sh"
