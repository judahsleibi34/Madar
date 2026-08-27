# Remaining findings and blockers

## P0 before customer exposure

1. **MADAR-BILL-001 / G15:** run the read-only entitlement inventory and obtain an authorized explicit mapping for all 11 tenants. Test each mapped capability and public-site continuity; do not restore permissive fallback.
2. **MADAR-DEPLOY-001/002 / G16:** add the backup-first locked migration executor, install the blue/green framework only in staging, and complete every switch/interruption/rollback fault drill before production installation.
3. **MADAR-DR-001 / G18:** wait for dedicated drives, activate encrypted off-host replication using `15-future-backup-drive-activation.md`, then complete and time a replacement-host restore.
4. **MADAR-DATA-001 / G22:** implement a durable deletion request/job state with idempotent steps for auth, database, buckets/host files, notification/analytics/audit retention and integration credentials; expose a redacted completion report.

## P1 before broader launch

- Backfill existing avatar storage objects and reconcile/account for abandoned replacement objects.
- Run authenticated two-tenant staging E2E for hostname, publication, quiz attempt, form submission, assets, reservations, workers and direct capability APIs.
- Decide whether SMTP is a launch capability. Configure and test it or keep it visibly disabled.
- Install and test alert delivery, backup freshness checks, storage reconciliation, capacity thresholds and worker failure hooks.
- Perform a controlled production storage permission migration after backup/UID/GID verification.
- Validate Redis recreated from tracked Compose and verify fail-closed rate limiting during outage.

## P2/P3

- Introduce distinct published asset namespace/signed preview migration.
- Add staging concurrency/DST/provider tests and soak/load tests.
- Reduce the large frontend chunks and monitor build cache; perform only operator-approved controlled pruning.
- Expand typed configuration inventory, build lifecycle saga, and standardize legacy API envelopes.
- Incrementally split oversized backend/builder modules; leave unreleased mobile/OCR/Drive/WhatsApp work out of readiness remediation.
