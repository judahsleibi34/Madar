# Madar production launch checklist

Use this only after remediation. Record evidence links, operator, timestamp and exact Git/image/schema identities for every checked item.

## Release approval

- [ ] All P0 findings in `21-findings-register.md` are closed and independently reviewed.
- [ ] Accepted residual P1 risks have named owner, expiry and rollback trigger.
- [ ] Production commit and immutable backend/frontend/worker image digests are recorded.
- [ ] Production and development worktrees contain no unexpected tracked/untracked changes.
- [ ] Development runtime `/version` matches the reviewed development commit; no stale images.
- [ ] Frontend, backend, migration, lint, edge and dependency gates are fully green on the exact release artifact.

## Security and tenancy

- [ ] Every production system admin has a verified MFA factor and enrollment inventory is current.
- [ ] AAL1 and MFA-provider failure cannot issue a normal admin session.
- [ ] Factor removal and every sensitive admin route require exact AAL2.
- [ ] CSRF unsafe-request tests pass for missing/invalid token and untrusted Origin.
- [ ] CORS error responses allow only `https://madarportal.com` and approved aliases.
- [ ] Redis rate limiter is enabled, distributed and verified fail-closed.
- [ ] Disposable two-tenant BOLA suite passes across builder, assets, forms, tests, reservations, calendar, analytics, notifications, exports, integrations and support access.
- [ ] Secret scan is clean; `.env` remains mode 0600; direct PostgreSQL URL is absent from every runtime container.

## Publication, forms and reservations

- [ ] Public schema and form endpoints contain no quiz answer/scoring keys.
- [ ] Test attempts, deadlines, scoring, randomization, replay and concurrent finalization are server-enforced.
- [ ] Product copy states that focus/tab signals are advisory and browser-controlled.
- [ ] Hostname, standard path, tenant, site, project and publication identity tests pass.
- [ ] Explicit homepage and duplicate page ID/route/form rejection tests pass.
- [ ] Bootstrap, header, body and footer use the same publication snapshot and ETag.
- [ ] Draft assets require authorized preview; published asset ownership/reference checks pass.
- [ ] Reservation double-book concurrency test proves one winner for an exclusive slot.
- [ ] Cancellation/idempotency conflict, DST and timezone matrices pass.

## Billing, storage and workers

- [ ] All tenants have reviewed canonical subscription states; missing/malformed states fail closed.
- [ ] Server-side capability matrix passes for active, expired, suspended, cancelled and grace states.
- [ ] Storage counters reconcile with active objects/files/buckets; no overdue reservations/assets.
- [ ] Image limit accepts exactly 25 MiB and rejects 25 MiB + 1 across proxy/middleware/route.
- [ ] Video/document/avatar limits and quota accounting pass; cleanup job is scheduled/monitored.
- [ ] Production storage roots are writable by UID/GID 65534 and unreadable by unrelated host users.
- [ ] Parser, remote-ingestion, calendar-sync and notification workers show correct release SHA and last successful dependency operation.
- [ ] VAPID push staging probe succeeds; preferences and revocation work.
- [ ] SMTP staging probe succeeds, or email is disabled everywhere and not promised/enqueued.
- [ ] Notification queue has no unexplained dead/stuck delivery; alerts were tested.

## Database, deploy and rollback

- [ ] Production PostgreSQL version/schema contract and migration history match the release.
- [ ] Migration trees/checksums and RLS/grant verifier pass against production catalog read-only.
- [ ] All production migrations were rehearsed on a representative provider-compatible clone.
- [ ] Each migration is classified for old/new code compatibility and has reviewed forward repair.
- [ ] Fresh verified off-host backup exists before migration.
- [ ] Candidate images start on isolated target and pass deep plus tenant/publication smoke tests.
- [ ] Traffic switch leaves the old target available until the observation window ends.
- [ ] Auto-deploy success path was demonstrated twice with release records.
- [ ] Build, migration, readiness, reboot and storage failure injections prove the rollback/forward-repair path.
- [ ] Retry circuit breaker prevents repeated two-minute build storms.
- [ ] Cloudflare continues routing only to the verified target; development routes are not exposed.

## Backup, restore and host

- [ ] Latest local backup has completion marker, 100% valid checksums and readable PostgreSQL TOC.
- [ ] Latest encrypted off-host backup is within approved RPO and independently monitored.
- [ ] Retention/prune policy preserves at least one separately controlled known-good generation.
- [ ] Full Supabase-compatible isolated restore passes auth, database, Storage/Vault, private files, workers and tenant isolation.
- [ ] Replacement-host rebuild completes within approved RTO using escrowed configuration and exact image identities.
- [ ] Cloudflare/systemd/Compose/deploy/config/secrets reprovisioning evidence is current.
- [ ] Root disk/inodes, RAM/swap, Docker build cache, logs and backup destination are below alert thresholds.
- [ ] Redis live mount/memory policy matches reviewed Compose.
- [ ] External frontend/API/readiness monitors pass from outside Node 1.
- [ ] Logs show no recurring auth, DB, publish, reservation, queue, SMTP or deployment errors during the observation window.
- [ ] Incident owners and runbooks for login, publish, reservation, notification, deployment and recovery were exercised.

## Final authorization

- [ ] G1-G23 were regraded; no Critical/High blocker remains.
- [ ] Launch owner records `GO`, date/time, release SHA/digests, schema, backup ID and rollback target.
- [ ] Post-launch monitoring window and abort criteria are active.
