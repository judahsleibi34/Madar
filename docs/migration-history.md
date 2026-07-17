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
- `049_expand_tenant_site_member_roles.sql` is pending and must not be described
  as applied.
- `050_restrict_authenticated_privileged_writes.sql`,
  `051_bind_public_sites_to_projects.sql`, and
  `052_publish_validated_builder_schema.sql` are repository migrations pending
  isolated staging validation and operator application.

Production independently retains the customer-only
`tenant_site_memberships_role_check`, confirming the role-expansion SQL has not
been applied there.

The pending role migration was originally introduced with the conflicting
prefix `047`. Because notification outbox owns the verified production identity
`047` and `048` is also applied, the unapplied role migration was renamed to
`049` in both repository trees without changing its SQL.

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
