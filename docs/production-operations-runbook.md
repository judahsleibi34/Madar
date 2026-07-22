# Production operations, recovery, and release runbook

This is an operator checklist, not evidence of deployment. Migrations 054–057
are operator-verified as manually applied in the current production database;
manual SQL Editor execution may not appear in the Supabase CLI ledger.
Migrations 058–065 remain environment-specific deployment candidates with no
production application claim in this repository task. No production restore
drill was run, no real notification was sent, and no shared database was changed.

## Release and migration gate

1. Record the release commit, current image digests, current migration ledger, and rollback owner.
2. Approve RPO/RTO and complete a fresh backup with `scripts/backup_madar.sh`; verify it with `scripts/verify_backup.sh` and copy it to encrypted off-host storage.
3. Restore that backup into a disposable isolated target following `backup-restore-runbook.md`. Do not proceed until readiness, tenant isolation, private-artifact access, file checksums, and representative application workflows pass.
4. Apply every migration missing from the isolated staging ledger in order. For the current repository this may include 058–065; verify the actual schema as well as the ledger. Run `python3 scripts/check_migrations.py` before and after. Never edit an applied migration.
5. Run `python3 backend/scripts/verify_rls_grants.py` with a read-only staging catalog connection. Confirm exact service-role function execution, safe `search_path`, authenticated privileged writes denied, and cross-tenant paths denied.
6. Run backend tests and `pip check` in the locked image; run frontend lock check, lint, tests, build, theme audit, edge audit, runtime-only dependency audit, and the isolated E2E safety guard.
7. Run the staging workflow inventory in `isolated-full-stack-testing.md`. Preserve redacted evidence and delete the disposable fixture boundary afterward.
8. Review readiness degradation causes. Production must not enable local generated execution without the isolated guard, remote ingestion without enforced pinned egress, or in-process parsing as if it were isolated.
9. Set `APP_ENV=production` explicitly. Enable calendar routes only with `CALENDAR_FEATURE_ENABLED=true` after migrations 061–065 and the calendar RLS verifier pass. Enable provider sync only with exact HTTPS `PUBLIC_API_URL` and `FRONTEND_PRIMARY_URL`, a protected calendar credential secret, configured provider credentials, and the sync worker.
9. Approve the release, migration window, forward-fix owner, rollback decision deadline, and customer communications plan.

## Deployment order

1. Put application writes into the operator-approved maintenance posture if the migration plan requires it.
2. Take and verify the pre-migration backup; record its ID and freshness marker.
3. Apply reviewed pending migrations once through the normal migration runner and verify the ledger. This document does not authorize applying them from a developer shell.
4. Deploy Redis, backend, notification worker, and frontend using reviewed immutable images. Ensure durable upload/generated-artifact volumes are mounted before backend readiness is allowed.
5. Configure `NOTIFICATION_WORKER_REQUIRED=true`, `NOTIFICATION_WORKER_ENABLED=true`, and the internal worker health URL only after fake-transport staging validation and real SMTP/web-push credentials are supplied through the secret manager.
6. Configure metrics authentication, backup freshness marker, exact CSP API origin, trusted proxy list, TLS-only HSTS decision, storage disk floor, quota defaults, and log collection.
7. Verify `/health/live`, `/health/ready`, protected `/health/metrics`, worker `/health` and `/metrics`, frontend headers, Redis, storage write/free-space, queue age/depth, cleanup backlog, quota reservations, and backup age.
8. Run non-mutating smoke checks plus approved namespaced production canaries only if operations has explicitly authorized them. Do not reuse staging fixtures or send customer notifications.
9. End maintenance posture, monitor error/latency/queue/disk signals, and keep the prior image and verified backup available through the rollback window.

## Rollback and incident response

For an application-only regression, redeploy the recorded prior image if it remains schema-compatible. After a migration begins, prefer a reviewed forward repair. Restore data only when corruption/destructive change is confirmed, incident command accepts the RPO loss window, and the exact backup has passed an isolated restore. Stop writes before data recovery; preserve logs, image/commit IDs, migration ledger, correlation/security event IDs, queue metrics, and backup manifests. Never delete dead-letter rows, unknown files, or audit evidence merely to clear an alert.

Severity-one triggers include suspected cross-tenant access, credential exposure, unauthorized privileged function execution, destructive storage cleanup, unavailable verified backups, or sustained readiness failure. Contain the affected capability, rotate exposed credentials, preserve evidence, assign incident commander/security/communications owners, document the timeline, and require post-incident corrective tests before reopening.

## Notification queue operations

The worker claims bounded batches, uses leased rows, retries with bounded exponential jitter, and lets the database transition exhausted rows to `dead`. `internal`, `email`, and `web_push` are the only accepted channels. Disabled/unconfigured SMTP is a visible delivery failure; it is never recorded as sent. Watch queue depth, oldest pending age, failed, dead, sent, worker last-poll time, and worker health. On backlog: verify provider configuration and health, stop enqueue amplification if necessary, keep one healthy worker pool, and allow leases to expire before recovery. Requeue dead work only through a reviewed idempotent operator procedure after the root cause is corrected; there is intentionally no bulk-delete shortcut.

## Storage, quotas, and retention

Builder assets and private/generated artifacts must use the explicit durable mounts in Compose; private artifacts are served only through authenticated routes. Run asset cleanup dry-run first:

```bash
docker compose run --rm --no-deps backend python scripts/cleanup_builder_assets.py --limit 100
docker compose run --rm --no-deps backend python scripts/reconcile_storage.py --limit 100
```

Review counts and database/storage health before scheduling the corresponding `--apply` form through the approved operations job. Cleanup deletes only registered, unreferenced, retention-expired assets in bounded batches and never unknown unmanaged files. Storage reconciliation releases expired reservations; usage must never be manually forced negative. Investigate quota/accounting drift before increasing limits. Refuse uploads when the disk floor or tenant/user quota is reached. Back up registry rows and file volumes together.

## Parsing, generated execution, and remote ingestion

Generated code is disabled by default and requires `AI_ISOLATED_WORKER_ENABLED=true`; the subprocess worker has resource and protocol controls. Spreadsheet/CSV/JSON parsing remains bounded but in the web process. `PARSER_ISOLATED_WORKER_ENABLED` is therefore not a deployable completion flag until a real worker service exists, and production readiness must remain degraded for this gap. Remote URL ingestion stays disabled unless an egress layer pins validated DNS resolution, revalidates redirects, blocks private/reserved ranges, and sets `REMOTE_INGESTION_EGRESS_ENFORCED=true`. Do not override either guard to make readiness green.

The generated worker forces OpenBLAS, OpenMP, MKL, NumExpr, VecLib, and BLIS
to one thread before numerical imports. It keeps a sanitized structured protocol,
bounded stderr, CPU/address-space/file/process limits, a temporary working
directory, and an environment allowlist. A dedicated worker UID/container is
still recommended before broad production enablement.

## Credential rotation

Keep database/service-role, auth provider, SMTP, push, metrics, backup encryption, and session/CSRF secrets in the deployment secret manager, never images or logs. Rotate one credential class at a time using dual-key overlap where supported, restart only dependent services, verify readiness and a fake/non-customer transaction, revoke the old credential, then record owner/time/scope. Treat service-role or session-signing exposure as an incident and invalidate affected sessions/tokens according to the auth-provider procedure.

## Quarterly restore drill record

Record: date; operator/approver; source commit and image digests; backup ID/time/age/size; checksum result; isolated target ID; migration baseline; restore start/end; measured RPO/RTO; database/file counts; RLS/private-artifact/application checks; failures; corrective owners/dates; destruction time for the isolated target. A manifest verification alone is not a restore drill.

## Billing limitation

Billing remains manual/beta. No payment gateway, checkout provider, billing webhook adapter, automated paid entitlement rollout, invoice/refund/chargeback/subscription reconciliation, or customer portal exists. Existing manual behavior must remain unchanged and must not be advertised as automated billing. A payment gateway remains an intentionally deferred product, legal, security, and operational decision.
