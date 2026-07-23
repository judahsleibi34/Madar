# Migration History and Numbering Policy

Madar keeps matching logical migrations in two trees:

- `database/migrations`
- `supabase/migrations`

## Verified production identities

The production `supabase_migrations.schema_migrations` ledger was most recently
verified on July 22, 2026:

- `047_create_notification_outbox.sql` is applied as version `047`, name
  `create_notification_outbox`.
- `048_add_terms_acceptance.sql` is applied as version `048`, name
  `add_terms_acceptance`.
- `049_expand_tenant_site_member_roles.sql` through
  `052_publish_validated_builder_schema.sql` were subsequently applied manually
  and are operator-verified as applied.
- Production privilege verification after those migrations found historical
  `REFERENCES`, `TRIGGER`, and `TRUNCATE` privileges still granted to
  `authenticated` on `public.builder_projects`. Migration 050 revoked DML but
  did not reset these residual privileges.
- `053_remove_residual_authenticated_privileges.sql` is part of the current
  operator-reported production baseline. This repository task did not query or
  change the production ledger.
- `054_add_form_submission_idempotency.sql` through
  `057_add_project_site_permissions.sql` were manually applied and are
  operator-verified in the current production database. SQL Editor execution
  may not appear in the Supabase CLI migration ledger; every new environment
  must still apply and verify these migrations independently.
- `058` through `064` are ledger-recorded and schema-verified in production.
- `065_secure_calendar_oauth_state.sql` and
  `066_normalize_sensitive_object_privileges.sql` were applied from the exact
  repository files and schema-verified on July 22, 2026. Direct `psql`
  application did not write the Supabase ledger, which therefore still ends at
  `064`; no manual ledger row or repair was performed.
- Ledger versions `043` and `044` both record the name
  `create_builder_reservations` and the same statement hash. The production
  schema nevertheless contains the account-lifecycle contract expected by
  repository migration 043 as well as the reservation contract. Preserve this
  historical discrepancy until an explicitly authorized ledger-reconciliation
  procedure is approved.

The role migration was originally introduced with the conflicting
prefix `047`. Because notification outbox owns the verified production identity
`047` and `048` is also applied, the then-unapplied role migration was renamed
to `049` in both repository trees without changing its SQL.

## Historical exceptions

- Database migration `004_enable_rls_policies.sql` corresponds to Supabase
  migration `005_enable_rls_policies.sql`; the get-tables migration has the
  opposite number. Preserve this historical filename swap until a formal
  baseline is established.
- `013_fix_tenant_relationships.sql` and
  `014_fix_tenant_relationships.sql` contain identical historical SQL. The
  migration checker reports this as a warning.

## Rules

- Never rename a migration recorded as applied in production.
- Assign every pending/new migration a unique unused prefix.
- Keep logical migration content synchronized between both trees.
- Update the production record only after operator-verified application.
- Test new migrations on an isolated production-like copy before application.
