# Controlled production promotion readiness

This document is a future operator plan, not authorization to deploy.

## Prerequisites

- [ ] Authorized mapping approved for all 12 production tenants and dry-run reviewed.
- [ ] Dedicated encrypted backup media installed, identity-validated, and current off-host copy verified.
- [ ] Full replacement-host restore drill completed.
- [ ] Node 1 swap reduced below warning and Docker cache cleaned without removing active/known-good images.
- [ ] Retention policy decisions approved and configured.
- [ ] Production environment validated against the 199-key typed catalog.
- [ ] Production alert provider connected and delivery tested.

## Pre-deployment

- [ ] Production source and database are unchanged and backed up.
- [ ] Backup manifest/checksums/completion marker pass freshness verification.
- [ ] Candidate SHA is clean, reviewed, and not marked bad.
- [ ] Backend 1,047-or-higher suite, frontend unit/lint/build, migration parity, secret and dependency scans pass for the candidate.
- [ ] Candidate images resolve to recorded immutable digests and SBOMs.
- [ ] Migration manifest declares expected current/target schema and rollback compatibility.
- [ ] Storage UID/GID/modes and free-space thresholds pass.

## Controlled promotion

- [ ] Acquire release and migration locks.
- [ ] Start inactive candidate without queue consumers or production traffic.
- [ ] Verify liveness, readiness, deep diagnostics, release SHA, schema compatibility, storage, Redis, and worker eligibility.
- [ ] Run locked expand migrations only after verified backup prerequisite.
- [ ] Revalidate schema/RLS/grants and representative auth/publication/quiz/reservation flows.
- [ ] Atomically switch traffic and activate candidate workers in the documented order.
- [ ] Observe alerts, error rate, p95/p99, queue age, DB/Redis/storage, and public-site isolation.
- [ ] Mark known-good only after the observation window.

## Failure response

- [ ] Before switch, destroy only the failed candidate and retain active service.
- [ ] After switch, verify retained schema compatibility, restore retained workers, and switch to retained immutable images.
- [ ] Never rebuild historical source or automatically reverse migrations 082/083.
- [ ] Mark failed SHA with a safe reason and require explicit manual retry.
- [ ] Use forward repair if no old-code/new-schema combination is declared safe.

## Final verification

- [ ] `/health/version` and image labels equal the approved SHA.
- [ ] Tenant isolation, public site, login/MFA, quiz, form, reservation, storage, notification, and deletion probes pass.
- [ ] Production subscriptions match only approved mappings.
- [ ] No recurring error, stale backup, dead delivery, stuck deletion, or capacity alert remains.
