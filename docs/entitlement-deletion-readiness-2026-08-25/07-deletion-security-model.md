# Deletion security model

## Authorization

- Self account closure derives the user ID from the authenticated regular-user session; a caller cannot submit another ID.
- Tenant closure derives tenant/user identity from active membership, requires role `owner`, and requires exact AAL2.
- System-admin scheduling and progress APIs require system-admin authorization and exact AAL2.
- A user cannot self-delete while the sole active owner of a tenant; ownership must be transferred or the tenant closure path used.
- An active final system administrator cannot be deleted. Disabled/non-final administrators can use the audited AAL2 admin workflow.
- Duplicate active requests are rejected by partial unique indexes.

## Tenant isolation and access

Deletion tables are backend-only: RLS is enabled, public/anon/authenticated privileges and function execution are revoked, and only the service role receives table/RPC access. Public status access is restricted to the requester; operator listings are AAL2 protected. Target IDs are snapshot evidence and are never accepted as authority from tenant closure requests.

## Files and providers

Host keys must match `tenant_<id>/user_<id>/<bounded-name>`, remain within an allow-listed root, and must not be symlinks. Provider objects are restricted to known resource kinds and bucket mappings. OAuth/Auth/storage tokens and object contents are excluded from logs, step outputs, metrics, and completion reports.

## Cancellation

Cancellation is allowed only while pending/waiting-retention and before any step completed. It restores captured account/tenant states. Once execution begins, cancellation fails closed; compensating recreation after irreversible provider deletion is intentionally not attempted.
