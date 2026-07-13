# Production Applied-Migration Record

This document is a manual, non-executable operational record. It is not a SQL
migration and must not contain credentials, connection strings, row data, or
sensitive database output.

## Verified historical migrations

- `040_create_builder_reservations.sql`: the principal schema change has been
  verified by the presence of `public.builder_reservations`.
- `040_add_user_email_verification_status.sql`: the principal schema changes
  have been verified by the presence of `public.users.email_verified` and
  `public.users.email_verified_at`.

Object presence does not by itself verify every statement in those migrations.
Indexes, triggers, row-level-security settings, policies, grants, revocations,
comments, and backfill outcomes should be verified separately with read-only
PostgreSQL catalog queries.

Update this record after each future production migration is applied and
verified. Record only non-sensitive facts such as the migration filename,
deployment commit, verification date, change-ticket reference, and verification
status.
