# Production Applied-Migration Record

This document records only operator-verified, non-sensitive migration facts. It
is not executable and does not replace the production migration ledger.

## Verified July 17, 2026

The production `supabase_migrations.schema_migrations` ledger contains:

| Version | Name | State |
|---|---|---|
| `047` | `create_notification_outbox` | Applied |
| `048` | `add_terms_acceptance` | Applied |
| `049` | `expand_tenant_site_member_roles` | Pending; not applied |

Production also retains `tenant_site_memberships_role_check` with the
customer-only role constraint. This independently supports that the pending
role-expansion migration has not run.

Do not mark version `049` or any later repository migration as applied until an
operator verifies the production ledger after deployment.
