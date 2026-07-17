# Production Applied-Migration Record

This document records only operator-verified, non-sensitive migration facts. It
is not executable and does not replace the production migration ledger.

## Verified July 17, 2026

The production `supabase_migrations.schema_migrations` ledger contains:

| Version | Name | State |
|---|---|---|
| `047` | `create_notification_outbox` | Applied |
| `048` | `add_terms_acceptance` | Applied |
| `049` | `expand_tenant_site_member_roles` | Applied manually; operator verified |
| `050` | `restrict_authenticated_privileged_writes` | Applied manually; operator verified |
| `051` | `bind_public_sites_to_projects` | Applied manually; operator verified |
| `052` | `publish_validated_builder_schema` | Applied manually; operator verified |
| `053` | `remove_residual_authenticated_privileges` | Pending; not applied |

Production verification after 049–052 found that `authenticated` still held
`REFERENCES`, `TRIGGER`, and `TRUNCATE` on `public.builder_projects`. Migration
053 is the pending corrective reset to authenticated `SELECT` only on
`public.users`, `public.builder_projects`, and `public.website_settings`.

Codex did not apply migration 053. Do not mark it applied until an operator
verifies the production ledger after deployment.

## Repository migrations not yet verified as applied

| Version | Name | State |
|---|---|---|
| `053` | `remove_residual_authenticated_privileges` | Pending |

This entry is a deployment candidate, not a claim about live database state.
