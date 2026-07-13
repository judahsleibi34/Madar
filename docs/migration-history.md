# Migration History and Numbering Policy

Madar currently keeps the SQL migration history in two parallel trees:

- `database/migrations`
- `supabase/migrations`

Both trees are retained for compatibility with the current development and
deployment process. One tree should eventually be designated as the
authoritative source and the other generated from, or strictly validated
against, it.

## Historical exceptions

The following exceptions are part of the existing migration history and must
not be "fixed" by renaming an already-applied migration.

### Duplicate migration number 040

Both trees contain two different migrations with the `040` prefix:

- `040_add_user_email_verification_status.sql`
- `040_create_builder_reservations.sql`

Both files are merged into the main Git history, and the production schema has
been observed to contain the principal changes from both migrations:
`public.builder_reservations`, `public.users.email_verified`, and
`public.users.email_verified_at`.

Do not rename either historical `040` file. Renaming an applied migration would
make Git history, manual deployment records, and any future migration ledger
disagree. Fresh installations must apply both `040` files.

### Migration 004/005 filename swap

The two trees have a historical filename-number swap:

- `database/migrations/004_enable_rls_policies.sql` matches
  `supabase/migrations/005_enable_rls_policies.sql`.
- `database/migrations/005_create_get_tables_function.sql` matches
  `supabase/migrations/004_create_get_tables_function.sql`.

The paired SQL content must remain identical. This exception should be
preserved until an authoritative migration tree and an explicit baseline plan
are adopted.

### Duplicate tenant-relationship content

`013_fix_tenant_relationships.sql` and
`014_fix_tenant_relationships.sql` currently contain identical SQL in each
tree. They are retained as historical duplicate-content debt and must not be
silently changed or consolidated without checking applied migration records.

## Rules for future migrations

- Every new migration must use a unique numeric prefix.
- Migrations `043` through `045` are now allocated in the development history;
  the next real schema migration must use `046` or higher.
- Do not add no-op SQL migrations solely to document historical numbering.
- Add each migration to both trees with identical filenames and content until
  one tree is formally selected as authoritative.
- Test migrations against both a blank database and a production-like copy
  before production use.
- Update the non-executable applied-migration record after production
  migrations are verified.

Supabase CLI migration automation must not be adopted against this history
without a baseline/import plan. The plan must reconcile the historical
three-digit filenames, the duplicate `040` prefix, the `004/005` swap, and the
actual production schema or migration ledger before automated pushes begin.
