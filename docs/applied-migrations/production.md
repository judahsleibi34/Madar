# Production Applied-Migration Record

This document records only operator-verified, non-sensitive migration facts. It
is not executable and does not replace the production migration ledger.

## Verified July 22, 2026

The production `supabase_migrations.schema_migrations` ledger contains versions
`001` through `064`. The following schema state was verified independently of
the ledger:

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
| `058`–`064` | Site-member hardening and calendar platform | Applied; ledger and schema verified |
| `065` | `secure_calendar_oauth_state` | Applied from the repository on 2026-07-22; schema verified; ledger absent |
| `066` | `normalize_sensitive_object_privileges` | Applied from the repository on 2026-07-22; ACL contract verified; ledger absent |

Production verification after 049–052 found residual privileges on
`public.builder_projects`; migration 053 is now part of the operator-reported
production baseline. Manual SQL Editor application may not be represented in
the Supabase CLI ledger, so operators must verify both schema effects and the
environment-specific ledger independently.

## July 22 ACL correction operation

Before the write, operators created and checksum-verified the private logical
backup `madar-acl-20260722T183500Z/production-pre-065-066.dump`. Its custom
archive listing was readable and included the core identity, tenant, builder,
form, and calendar tables. The backup retains ACL metadata needed for privilege
rollback and is stored outside the repository.

Migration 065 added the tenant/user/calendar/provider-bound, expiring,
single-use OAuth state table and service-role-only consume RPC. Migration 066
removed browser-role `MAINTAIN`, `TRUNCATE`, `REFERENCES`, and `TRIGGER`
privileges; reduced service-role table privileges to backend CRUD; normalized
owned sequences to `USAGE, SELECT`; removed PUBLIC/browser execution of
protected functions; fixed their search paths; and corrected future-object
defaults for the `postgres` owner. The exact production verifier passed with no
table, sequence, function, RLS, ownership, schema, view, default-ACL, or role
membership mismatch.

The migrations were applied with `psql` using the exact repository SQL, so the
Supabase ledger remains at `064`. No ledger row was inserted and no repair was
performed. Schema evidence, not a fabricated ledger record, is authoritative
for this operation. The historical ledger rows `043` and `044` both contain the
same `create_builder_reservations` name and statement hash, while the account
lifecycle tables and functions expected from repository migration 043 are
present. This historical naming/content discrepancy was not repaired.

Calendar OAuth and calendar synchronization remain disabled pending separately
approved provider configuration. Post-application liveness, database, Redis,
auth, schema, and anonymous auth-status checks passed. Overall readiness remains
degraded because storage and other deployment gates are not yet healthy; the
ACL operation did not change those gates.
