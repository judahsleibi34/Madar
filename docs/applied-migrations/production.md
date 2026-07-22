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
| `053` | `remove_residual_authenticated_privileges` | Applied; operator-reported production baseline |
| `054` | `add_form_submission_idempotency` | Applied manually; operator verified |
| `055` | `create_builder_asset_registry` | Applied manually; operator verified |
| `056` | `add_storage_quota_accounting` | Applied manually; operator verified |
| `057` | `add_project_site_permissions` | Applied manually; operator verified |

Production verification after 049–052 found residual privileges on
`public.builder_projects`; migration 053 is now part of the operator-reported
production baseline. Manual SQL Editor application may not be represented in
the Supabase CLI ledger, so operators must verify both schema effects and the
environment-specific ledger independently.

## Repository migrations not yet verified as applied

| Version | Name | State |
|---|---|---|
| `058`–`060` | Site-member assignment and record-access hardening | Repository only; production state unverified |
| `061`–`064` | Calendar platform and task reminders/recurrence | Repository only; production state unverified |
| `065` | Secure single-use calendar OAuth state | Repository only; production state unverified |

This entry is a deployment candidate, not a claim about live database state.
