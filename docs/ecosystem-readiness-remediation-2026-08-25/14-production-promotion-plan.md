# Production promotion plan

This is an operator checklist, not authorization to deploy. Production was not modified during remediation.

## Release acceptance

- [ ] All P0 items in `12-remaining-findings.md` are closed or explicitly accepted by the authorized launch owner.
- [ ] Record development and intended production SHA; verify working trees clean and no remote divergence/manual patch.
- [ ] Review every remediation commit and repeat secret scanning; record approvers.
- [ ] Run the complete supported backend suite (1003 tests at this remediation SHA), focused quiz/MFA/entitlement/notification/deploy/backup/storage/readiness suites, frontend unit/lint/build, migration mirror checker and Compose resolution from the exact candidate SHA.
- [ ] Build backend/frontend/worker images tagged with full SHA; capture digests, build timestamp and SBOM; prove `/health/version` and Docker labels match.
- [ ] Verify production configuration with `runtime_config` without printing values; email/AI/integration availability must match product claims.

## Commercial/data prerequisites

- [ ] Run `report_entitlement_migration.py` read-only; obtain an authorized canonical state for every one of the 11 tenants.
- [ ] Rehearse mappings on a disposable production-like database and test every direct API capability, quota and existing public site.
- [ ] Inventory/backfill existing avatars into storage accounting and reconcile totals against files/buckets.
- [ ] Implement and drill durable multi-provider deletion workflow, or retain G22 as an explicit launch blocker.

## Staging release drill

- [ ] Provision blue/green Compose targets and atomic proxy switch using reviewed Node 1 paths/ports.
- [ ] Prove active target remains serving during candidate build/start/validation failures.
- [ ] Exercise image build, backend, frontend, worker, DB, Redis, storage, false-health and switch failures.
- [ ] Interrupt/reboot during every durable phase and confirm state-machine recovery.
- [ ] Confirm known-bad SHA suppression and explicit manual retry/reset.
- [ ] Capture pre-migration backup and verify format/TOC/checksums/freshness.
- [ ] Acquire migration lock; verify migration 082 checksum; apply on disposable copy; rerun; prove schema state 82 and all RPC adversarial cases.
- [ ] Prove old code/new schema and new code/old schema compatibility declared by release metadata.
- [ ] Prove post-switch rollback routes to retained digest without rebuilding; do not reverse migration 082.

## Security and tenant smoke

- [ ] Admin with factor requires challenge; admin without factor is enrollment-only; provider failure denies; exact AAL2 required for remove; recovery drill recorded.
- [ ] CSRF, CORS (including error responses), secure/HttpOnly/SameSite cookies and Redis fail-closed rate limiting pass.
- [ ] Two authenticated tenants cannot read/change each other’s users, assets, builder projects, publications, forms, attempts, reservations, analytics, notifications or integrations.
- [ ] Public GET/search contains zero answer/rubric/scoring keys; forged/expired/replayed/wrong-publication/wrong-tenant quiz calls fail.
- [ ] Hostname resolves exactly one tenant/site/project/publication; body/chrome/assets/ETag all use that snapshot.
- [ ] Draft asset requires same-tenant auth and no-store; published asset remains available.

## Operations and recovery

- [ ] Production storage ownership/modes validated; one-time repair rehearsed; no recursive chown in timer hot path.
- [ ] Redis runtime matches Compose tmpfs/maxmemory/noeviction/health settings and rate-limit outage policy.
- [ ] Notification workers running; email explicitly disabled or provider test succeeds; dead/pending age alerts delivered.
- [ ] Backup, verify, reconciliation, capacity and worker timers installed only after review; failure hooks deliver to approved receiver.
- [ ] Dedicated backup media activation checklist complete; recent encrypted off-host copy verified.
- [ ] Full isolated replacement-host restore completed with measured RPO/RTO and signed validation.
- [ ] Disk/build-cache/storage/database growth thresholds and non-destructive operator response verified.
- [ ] Cloudflare ingress/host/trusted-proxy configuration sanitized review complete; development route is not accidentally public.

## Controlled production switch

- [ ] Freeze overlapping deploys; confirm lock and known-good durable release record.
- [ ] Generate and verify immediate pre-deploy backup.
- [ ] Start inactive candidate; verify expected SHA/schema, DB, Redis, storage, workers, frontend and public-site smoke.
- [ ] Apply only the rehearsed locked expand migration when its prerequisites pass; on failure prefer forward repair and retain safe traffic target.
- [ ] Atomically switch traffic; observe login/public sites/forms/reservations/assets/notifications and error/latency metrics.
- [ ] Mark known-good only after observation. Retain previous digests and do not prune during the launch window.
- [ ] If acceptance fails, switch traffic to the retained compatible target; record incident and suppress the bad SHA.
