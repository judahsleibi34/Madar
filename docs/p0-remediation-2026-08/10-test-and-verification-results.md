# Test and verification results

## Madar backend

The complete hermetic run collected 956 tests. Initial result was 945 pass and 11 errors. Ten errors were caused by the deliberately minimal test container omitting repository-level migration/deployment files; each passed when the exact referenced directory/file was mounted read-only. The remaining parser timeout passed on three consecutive isolated reruns.

Effective product result: **956 covered, all passed after correcting the harness mounts**.

Coverage includes auth, AAL2/admin safety, tenant isolation, builder/publication, forms/tests, reservations, asset/storage accounting, billing/entitlements, notifications/calendar, parser/remote ingestion, readiness, and new runtime DB-credential propagation checks.

No external network attempt was observed in the hermetic suite.

## Madar frontend

Result: **735 passed, 2 failed, 1 skipped** across 117 test files. The runner was interrupted only after it printed the complete failure summary and failed to terminate on its own.

Both failures are the previously known Page Builder collision/rendering assertions:

- saved two-column row alignment;
- authored under-text artwork logical Y position.

No P0 frontend file was modified. These are pre-existing and outside P0 unless a later DB/runtime change affects builder behavior.

## Briefedly backend

- Full unit/API integration suite: **136 passed, 0 failed** (4 warnings).
- P0-specific AI transport/migration/security header subset after minimal-diff cleanup: **33 passed, 0 failed** (3 warnings).
- PostgreSQL locking/concurrency/tenant-constraint suite on disposable tmpfs DB: **9 passed, 0 failed** (1 warning).

Warnings were framework deprecations and a synthetic-test JWT key-length warning; no production secret was involved.

## Briefedly frontend

- Unit tests: **5 passed, 0 failed**.
- Production frontend build: **passed**, 1,840 modules transformed.

## Database/migration/role tests

- Briefedly production dump restore: pass.
- Five-revision production-clone upgrade: pass.
- Fresh zero-to-head: pass.
- Empty-clone downgrade/forward upgrade: pass.
- Alembic at-head rerun: pass.
- Role-preparation rerun: pass.
- Runtime positive CRUD: pass.
- Runtime negative DDL/admin assertions: pass.
- Composite workspace FK negative assertion: pass.
- Backup-role dump/list: pass after correcting an invalid `/dev/null` harness target.
- Legacy role finalization and old-identity login failure on clone: pass.
- Madar checksum verification: pass.
- Madar partial schema/files restore: pass.
- Madar full raw restore: blocked by missing provider-specific Supabase Vault support.

## Static/config checks

- `git diff --check`: pass.
- Briefedly production and development Compose rendering: pass with synthetic env fixtures; no credential values recorded.
- Runtime env inspection used key presence/state only.
- Modified-source P0 tests pass.
- Repository-wide Black/flake8 is not a clean existing gate: 47 pre-existing files would be reformatted and flake8’s 79-column rule conflicts with the repository’s Black output. No broad formatting remediation was performed.

## Unsafe/skipped tests

- No real Gmail account/OAuth flow.
- No customer record creation/deletion.
- No production migration or role change.
- No live Ollama request because the final authenticated gateway is unavailable.
- No Mailcow backup/restore without a maintenance-approved supported procedure.
- No destructive production failover test.
