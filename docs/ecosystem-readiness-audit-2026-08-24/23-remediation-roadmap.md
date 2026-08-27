# Remediation roadmap

## P0 — Before any production customer exposure

### P0.1 Remove public quiz answers and disable unsafe test mode

- Findings: MADAR-FORM-001.
- Subsystem/files: public schema serializers and submission route in `web/backend/routes/public_site_routes.py`; builder quiz schema/runtime; migrations for attempts.
- Approach: immediately strip all answer/scoring fields from public responses and hide/disable test claims. Then implement private versioned answer snapshots, server attempt state/deadline/randomization/scoring and idempotent finalize.
- Dependencies: product policy for focus-loss and retakes; migration design.
- Tests: unauthenticated schema/form redaction, DevTools/direct API bypass, replay/concurrent finalize, expired attempt, publication-version pinning.
- Deployment: redaction code can be backward-compatible first; migrate attempts before enabling UI.
- Verification: zero public response contains answer keys; backend is authoritative for result.

### P0.2 Stop automatic promotion until deployment/rollback is proven

- Findings: MADAR-DEPLOY-001, MADAR-DEPLOY-002.
- Subsystem/files: `web/deployment/bin/*`, systemd timer/drop-in, Compose, CI.
- Approach: operator-approved pause of auto-promotion; build/publish immutable SHA images, retain prior digests, add schema compatibility preflight, candidate environment and atomic traffic switch. Add circuit breaker/backoff.
- Dependencies: release registry, migration classification, maintenance/traffic design.
- Tests: build failure, old/new DB combinations, backend never ready, reboot at each phase, storage failure, tunnel remains on old target, successful rollback.
- Deployment: install changes only in a maintenance window; no report authorizes systemd changes.
- Verification: two clean staging promotions and injected failures recover automatically to verified prior service.

### P0.3 Make commercial authorization canonical and fail closed

- Findings: MADAR-BILL-001, MADAR-AI-001.
- Subsystem/files: `entitlement_service.py`, catalog, billing/admin migration tooling, tenant subscription constraints.
- Approach: review/migrate all 11 tenants, represent approved grandfathering explicitly, deny missing/ambiguous state for mutations/new use, add one-active-base constraint and narrow public-site grace.
- Dependencies: commercial decisions and customer migration mapping.
- Tests: every capability across active/past_due/suspended/cancelled/grace/missing/duplicate/dependency-down; storage/user allowances under concurrency.
- Deployment: migration/backfill first with dry-run report, then strict code; keep published-site grace monitored.
- Verification: every tenant has explainable canonical state; missing state returns controlled denial.

### P0.4 Enforce admin MFA fail-closed

- Findings: MADAR-AUTH-001, MADAR-AUTH-002.
- Subsystem/files: `auth_routes.py`, `mfa_routes.py`, admin readiness/security settings.
- Approach: no-factor admin enters enrollment-only session, lookup failure denies, factor removal requires exact AAL2, verify/recover through audited break-glass process.
- Dependencies: inventory of production admins and recovery owner.
- Tests: no factor, provider failure, AAL1, AAL2, replay, factor removal, support-session denial, break-glass audit.
- Deployment: enroll all admins before strict switch; preserve emergency recovery.
- Verification: readiness checks actual required-admin enrollment; no normal admin cookies without challenge/enrollment gate.

### P0.5 Establish a recoverable off-host point

- Findings: MADAR-DR-001.
- Subsystem/files: backup scripts, new timer/monitor, provider backup/export, secret/config escrow.
- Approach: scheduled encrypted generation, physically/logically separate destination, completion/freshness alerts, provider-compatible full restore and clean-host rebuild.
- Dependencies: approved destination/key custody and compatible Supabase target.
- Tests: corrupt/incomplete backup rejection, destination unavailable/full, full restore/auth/files/tenant isolation/workers.
- Deployment: start with non-destructive copy; set approved RPO/RTO and retention.
- Verification: latest off-host generation restored into isolated working Madar inside RTO.

### P0.6 Align notification claims with delivery reality

- Findings: MADAR-NOTIFY-001, MADAR-OBS-001.
- Subsystem/files: production environment, notification worker/readiness, SMTP delivery.
- Approach: configure TLS SMTP and sender or stop enqueueing/hide email; require channel-specific readiness and dead-letter alerts.
- Dependencies: provider/DNS credentials and deliverability policy.
- Tests: controlled staging send, 4xx retry, 5xx/dead, unsubscribe/preferences, duplicate protection, provider outage.
- Deployment: no real customer message during validation without approval.
- Verification: zero unexplained dead rows and synthetic channel monitor succeeds.

## P1 — Before broader production launch

### P1.1 Close storage lifecycle and permissions

- Findings: MADAR-ASSET-001, MADAR-STORAGE-001/002/003.
- Components: asset routes/registry, quota RPCs, avatar routes, cleanup timer, host prep.
- Approach: schedule reconciliation, incorporate avatars, authenticated drafts/published namespace, restrictive group modes, remove per-timer recursive chown.
- Tests: process death after reservation, replacement/delete, two concurrent uploads, quota edge, symlink/path, cleanup idempotency.
- Deployment: dry-run and compare DB/files/bucket before first cleanup; back up first.
- Verification: zero overdue assets/reservations, counters reconcile, private files unreadable to unrelated host user.

### P1.2 Restore green deterministic release gates and rebuild dev

- Findings: MADAR-TEST-001, MADAR-DEV-001.
- Components: collision-padding renderer, worker timeout tests, Compose/dev workflow.
- Approach: fix layout regression; give worker tests deterministic startup budgets; bake SHA into all images and require recreate.
- Tests: full backend/frontend twice on clean current image; compare dev `/version` to Git.
- Deployment: rebuild development only; production through revised release process.
- Verification: all suites green and dev/prod artifacts identify intended SHA.

### P1.3 Make health/alerts reflect customer service

- Findings: MADAR-OBS-001, MADAR-CACHE-001, MADAR-PERF-001.
- Components: readiness, worker probes, metrics/alerts, Redis, host capacity.
- Approach: channel/provider dependency status, backup age, last successful worker operation, explicit Redis memory/mount, disk/cache thresholds.
- Tests: stop Redis/provider/worker, create stale backup/dead message, fill staging disk/cache threshold.
- Deployment: add external failure-domain monitor before changing readiness semantics.
- Verification: every injected failure alerts and readiness behavior matches documented policy.

## P2 — Near-term hardening

- MADAR-PUB-001: unify bootstrap/full response on one publication serializer; snapshot regression test and cache identity.
- MADAR-DATA-001: durable deletion saga/outbox for Auth, database, buckets, host files, analytics/audit retention and export; per-object verification report.
- MADAR-PERF-001: split PageBuilder/Three/CSS, profile Supabase call counts, paginate large lists, stage 100-tenant load/queue soak.
- Calendar/reservation: add DST matrices, native exclusion feasibility, provider revocation/outage and concurrent RPC integration tests.
- Privacy: approve explicit IP/user-agent, notification, analytics, audit and backup retention schedules.

## P3 — Longer-term engineering quality

- MADAR-CODE-001/API-001: decompose route monoliths into domain services/repositories and generated API contracts; standard cursor/error envelopes.
- MADAR-CONFIG-001: typed centralized settings, checked environment schema, remove aliases/legacy paths and correct dev public-link base.
- MADAR-SUPPLY-001: upgrade Expo-supported mobile chain before release; add SBOM, image/source attestations and CI secret/dependency scanning.
- Archive/supersede multi-system and target-state docs so operators see only current Madar Node-1 truth.
