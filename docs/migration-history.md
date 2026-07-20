# Migration History and Numbering Policy

Madar keeps matching logical migrations in two trees:

- `database/migrations`
- `supabase/migrations`

## Verified production identities

The production `supabase_migrations.schema_migrations` ledger was verified on
July 17, 2026:

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
- `054_add_form_submission_idempotency.sql`,
  `055_create_builder_asset_registry.sql`,
  `056_add_storage_quota_accounting.sql`, and
  `057_add_project_site_permissions.sql` are repository-only pending migrations.
  They were not applied to production or any shared database by this task.

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
