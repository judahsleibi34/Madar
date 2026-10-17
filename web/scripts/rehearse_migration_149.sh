#!/usr/bin/env bash
set -euo pipefail
# Separate unselected successor: all unchanged147/148 native regressions first,
# then149 cutover rollback and adversarial resolver ownership tests.
RUN_SCHEMA148_ADMISSION=true RUN_BUSINESS_INTEGRITY=true RUN_OUTBOX_INTEGRITY=true \
  exec bash "$(dirname -- "${BASH_SOURCE[0]}")/rehearse_migration_147.sh"
