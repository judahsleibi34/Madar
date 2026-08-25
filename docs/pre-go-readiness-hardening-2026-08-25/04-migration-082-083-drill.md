# Migration 082/083 drill

## Result

**PASS.** A disposable PostgreSQL 17 database was rehearsed from schema 81 through 82 and 83.

The executor verifies the exact migration manifest/checksum, expected current schema, verified pre-migration backup, compatibility declaration, and advisory lock. It writes durable phase state and exits non-zero on invalid conditions. Unknown failures are not silently retried and destructive migrations are not automatically reversed.

## Evidence

- 81 -> 82 -> 83 completed.
- Schema 83 rerun behaved safely.
- A held migration lock caused controlled refusal.
- Migration mirrors reported 83/83 with zero errors.
- `application_schema_state` matched the expected target.
- Quiz attempt RPCs, deletion lifecycle tables, subscription constraints, RLS, grants, indexes, and uniqueness were checked.
- Old-code/new-schema and new-code/old-schema combinations were allowed only when declared compatible.
- Retained rollback schema compatibility is attested before traffic reversal.

The only migration-checker notice is the known historical numbering overlap at migrations 013/014; mirror contents are identical. Migrations 082 and 083 are expand-style and are never automatically reversed. If application validation fails after them, the safe recovery is a compatible retained release or explicit forward repair.
