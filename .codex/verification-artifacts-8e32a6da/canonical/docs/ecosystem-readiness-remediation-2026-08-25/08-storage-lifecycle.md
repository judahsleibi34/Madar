# Storage and asset lifecycle remediation

## Changes

- Reconciliation is dry-run by default, uses a nonblocking lock, caps batches at 500, scopes tenant/ownership, rejects escaped paths, streams hashes, rechecks references/status immediately before deletion, and reports eligible/deleted/skipped/missing/hash-mismatch metrics.
- Scheduling templates exist but are not installed. Destructive production cleanup was not run.
- New avatars reserve quota before upload, finalize after compare-and-swap profile update, roll back files/accounting on failure, and release the replaced object. Concurrent replacements cannot both overwrite the same prior avatar.
- Storage processes use restrictive umask; provisioning defaults to 0700 directories/0600 files. Recursive ownership repair was removed from the two-minute deploy path and replaced by explicit initial/repair behavior.
- `/uploads` now distinguishes published references from draft/unreferenced assets. A published referenced asset remains cacheable/public; a draft asset requires authenticated same-tenant ownership and is returned private/no-store. Lookup failure fails closed.

## Remaining work

Existing pre-remediation avatars are not represented in storage accounting; inventory/backfill must run before promotion. Cross-service failure after deleting an old avatar can still require reconciliation. The compatibility URL namespace remains, so a later expand/migrate/contract release should introduce an explicit published namespace and signed authenticated previews without breaking existing published links. Production permission changes require a verified backup, exact UID/GID validation and a controlled one-time repair—not an indiscriminate recursive timer.
