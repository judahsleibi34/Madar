#!/usr/bin/env bash
set -euo pipefail
# Verified disposable-only successor. Original147..149 assertions run unchanged.
RUN_DELETION_INTEGRITY=true RUN_SCHEMA149_ADMISSION=true RUN_SCHEMA148_ADMISSION=true RUN_BUSINESS_INTEGRITY=true RUN_OUTBOX_INTEGRITY=true \
 exec bash "$(dirname -- "${BASH_SOURCE[0]}")/rehearse_migration_147.sh"
