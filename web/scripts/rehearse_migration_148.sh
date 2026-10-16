#!/usr/bin/env bash
set -euo pipefail
# One disposable PostgreSQL:146→147 ownership tests,147→148 rollback/upgrade,
# then native reservation, inventory/order and simulated payment races.
RUN_BUSINESS_INTEGRITY=true exec bash "$(dirname -- "${BASH_SOURCE[0]}")/rehearse_migration_147.sh"
