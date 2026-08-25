# Database migration state

- Starting schema: 81.
- Ending schema: 83.
- Applied: `082_create_public_quiz_attempts.sql` and `083_create_entitlement_mapping_and_deletion_lifecycle.sql`.
- Engine: PostgreSQL 17 (provider-managed production database).

Before migration, backup `madar-20260825T154321Z` was generated with format 3 manifest, schema/release metadata, completion marker, secret-free configuration inventory, and checksums. Re-verification passed all checksums and `pg_restore --list` TOC parsing.

The exact 81→82→83 sequence, rerun behavior, checksums, and lock contention had already passed on disposable PostgreSQL 17. Production migration used the locked executor and durable migration record. An initial executor container could not traverse the protected backup directory and exited before database access; retry under the owning host UID passed. Migrations were not reversed.

Application readiness and `application_schema_state` through the production API report schema 83. Migration mirrors remain 83/83 with zero errors and only the documented historical duplicate-content warnings for migrations 13/14.

No commercial tenant mapping was applied.
