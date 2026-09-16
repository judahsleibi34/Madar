# Schema-099 local candidate correction verification

Verified locally on 2026-09-16 in `D:/Madar-release-099`, starting from clean
commit `8e32a6da6bc97f3251eca9eb2f00e82f85c70f24`. The correction is a new commit.

The operator reported production application schema and Supabase ledger at 096,
with 097/098/099 objects absent. This run did not access production, deploy, or
run `supabase db push`. Current target is 099; pending sequence is 097, 098, 099.
Historical R0.2 retains its original target 097.

## Corrections

The reconciler selects an explicit migration version and enforces canonical
checksum and mirror parity, candidate identity, linked project identity, final
coordinator completion and live schema/health, ledger ordering, exact operator
confirmation, immutable private per-version audit records, and the host deploy
lock. Repeats preserve audit bytes and never repair twice. Remote-only ledger
rows participate in the ahead-of-target guard.

The disposable 097 harness uses a quoted heredoc and a psql variable for its
concurrent order assertion. Migration 098 now checks the actual
`tenants.lifecycle_state` column and rejects null surfaces; its two canonical
copies and both release manifests were updated together. SQL and release
manifest LF attributes make checksum bytes stable across Windows and Linux.
Migration 097 and 099 canonical content remains unchanged.

## Passed local checks

- Official Linux backend workflow command against the Docker test image:
  1,323 tests passed; external attempts and sites both empty.
- PostgreSQL 17 disposable 097 rehearsal, including concurrent assertions.
- `rehearse_migration_099.sh`: clean install of all 99 migrations and
  096 -> 097 -> 098 -> 099 upgrade, asserting each schema transition.
- Preservation of all existing variant, product, order-item and inventory
  movement fields; new presentation defaults; 098 website/store increments
  and invalid-surface refusal; 099 color normalization, commercial variant
  preservation, constraint refusal and atomic invalid-swatch refusal.
- Migration-tree parity, migration transitions, dependency locks and tracked
  secret hygiene validators. Only the two documented historical duplicate
  migration-content warnings remain.
- Frontend lint, 154 test files (941 passed, one skipped), dependency audit
  (zero vulnerabilities), production API origin and bundle checks, and
  production frontend Docker image build.
- Backend Docker test image build and installed dependency consistency check.
- Git diff whitespace review.

## Unavailable mandatory release gate

The intended protected production and isolated-E2E configuration files are not
available in this workspace. `check_production_config.py` against the available
example inputs reported missing production settings; this does not validate
intended production configuration. Policy section R requires resolving this
gate before declaring production readiness. Host-specific and live production
checks were not performed. This candidate has passed the listed local code,
build and database checks, but release eligibility remains blocked until the
operator validates the intended configuration and applicable environment gates.
