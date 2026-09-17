# Madar operational runbooks

These runbooks describe the immutable blue/green design validated on Node 1. They do not authorize production changes. Before acting, identify the active release from the durable release state and preserve evidence. Never print environment values or tokens.

## Common first response

1. Confirm the alert timestamp, release SHA, tenant identifier, and request ID where available.
2. Inspect `/health/live`, `/health/ready`, `/health/version`, and the protected operational diagnostics.
3. Read the Madar container logs and durable release record; do not restart unrelated services.
4. Preserve the active known-good slot until the cause and schema compatibility are known.
5. Verify recovery with both dependency health and a synthetic product flow.

## Login failure

- Symptom/alert: login errors, rate-protection unavailable, or auth component degraded.
- Diagnose: check API readiness, Redis, auth-provider reachability, CORS/CSRF rejection logs, and request IDs.
- Safe action: restore Redis/auth connectivity; do not disable rate limits, CSRF, MFA, or cookie security.
- Recovery: use the retained release only when the incident correlates with a release and schema compatibility permits it.
- Escalate: any cross-account session, administrator bypass, or unexplained token acceptance.
- Verify: normal synthetic login succeeds; malicious Origin and invalid CSRF fail; rate limiting remains distributed and fail-closed.

## Administrator MFA recovery

- Symptom/alert: verified administrator cannot reach AAL2 or is enrollment-only.
- Diagnose: confirm identity through the approved operator process, factor state upstream, session state, and audit events.
- Safe action: revoke sessions upstream, perform upstream identity recovery, and force re-enrollment. There is no application bypass.
- Escalate: identity cannot be independently verified, audit evidence is missing, or factor ownership is ambiguous.
- Verify: AAL1 cannot access privileged routes or remove a factor; exact AAL2 succeeds; recovery and re-enrollment are audited.

## Database outage or migration failure

- Symptom/alert: readiness database/schema failure or migration executor non-zero exit.
- Diagnose: PostgreSQL health, connections, `application_schema_state`, migration phase record, checksum manifest, and advisory lock.
- Safe action: stop promotion, keep active traffic on the known-good slot, and restore database availability. Never auto-reverse migrations 082/083.
- Recovery: continue an interrupted expand migration only after checksum/state review; otherwise use an explicit forward repair.
- Escalate: partial migration with unknown state, checksum mismatch, or no compatible running release.
- Verify: exact schema and checksums, RLS/grants, integrity queries, readiness, and representative auth/publication/deletion flows.

## Redis outage

- Symptom/alert: readiness Redis failure; protected endpoints return service unavailable.
- Diagnose: slot-local Redis health, memory/maxmemory policy, cgroup limit, and queue age.
- Safe action: restore the slot-local Redis container. Never switch to a permissive in-process limiter.
- Escalate: eviction, corruption, repeated OOM, or security-sensitive routes accept traffic while Redis is unavailable.
- Verify: readiness recovers and login, reset, MFA, forms, reservations, quiz, upload, analytics, and admin protection remain rate limited.

## Storage or publication failure

- Symptom/alert: storage readiness/reconciliation failure, upload error, or tenant cannot publish.
- Diagnose: mount identity, free space, UID/GID/mode, reconciliation dry-run, project/asset ownership, and bound publication identity.
- Safe action: restore the reviewed mount and permissions using the explicit repair command; never recursively chown on a timer or delete from a dry-run report.
- Escalate: ownership ambiguity, cross-tenant reference, path traversal/symlink, or published/draft namespace mismatch.
- Verify: runtime write probe, private draft denial, published asset retrieval, same-snapshot chrome/body, and quota reconciliation.

## Reservation failure

- Symptom/alert: booking errors or suspected overlap.
- Diagnose: request ID, tenant/calendar/slot, database constraints, timezone, notification coupling, and integration state.
- Safe action: restore the dependency; do not manually insert a booking or weaken exclusion/concurrency controls.
- Escalate: more than one winner for an exclusive slot or cross-tenant calendar access.
- Verify: high-contention probe produces exactly one winner and all losers receive the controlled conflict response.

## Notification or worker failure

- Symptom/alert: worker unavailable, dead delivery growth, or oldest queue age threshold.
- Diagnose: protected metrics, worker health/release SHA, Redis/DB, channel state, retry class, and dead-letter reason.
- Safe action: restart only the affected worker after its dependencies recover. SMTP remains disabled until genuine configuration exists.
- Escalate: duplicate delivery, cross-tenant delivery, permanent configuration failures retry indefinitely, or backlog does not drain.
- Verify: worker health and last-success advance; disabled channels create no poison work; transient failures retry boundedly.

## Deletion worker failure

- Symptom/alert: stuck lease, manual intervention, verification mismatch, or oldest job threshold.
- Diagnose: protected request status, phase, attempts, safe error code, lease, retained classes, and provider state.
- Safe action: restore the provider/dependency and allow idempotent retry. Never forge state or mark a request complete manually.
- Escalate: target is not frozen, verification mismatch persists, ownership is ambiguous, or an irreversible auth deletion occurred early.
- Verify: each step and final verification report is complete; retained policy classes are explicit; unrelated tenants remain intact.

## Deployment or rollback failure

- Symptom/alert: candidate failure, bad-SHA suppression, switch failure, or rollback failure.
- Diagnose: durable phase/history, active-target file, known-good record, image digest labels, schema compatibility, and slot health.
- Safe action: before switch, destroy only the candidate. After switch, restore known-good workers and switch back using retained immutable images.
- Recovery: use `--manual-retry` only after the cause is understood. Do not rebuild historical source or reverse destructive migrations.
- Escalate: active target is unavailable, schema is incompatible with known-good code, switch state is ambiguous, or rollback exhausts retries.
- Verify: target file and proxy agree, known-good `/health/version` matches its digest record, all required workers are healthy, and the failed SHA is suppressed.

## Disk, inode, or Docker cache pressure

- Symptom/alert: reviewed warning/critical threshold crossed.
- Diagnose: `df -h`, `df -i`, Docker disk inventory, backup/upload/database/log sizes, and retained release list.
- Safe action: expire only policy-eligible logs/cache and invoke the dry-run-first cache tool. Preserve running and known-good rollback images.
- Escalate: critical threshold, database/storage growth unexplained, or cleanup would remove recovery artifacts.
- Verify: headroom returns below warning, active/known-good images resolve to recorded digests, and backups still verify.

## Alert and recovery verification

Every incident closes only after the provider-neutral alert sink records recovery evidence, public and protected probes pass, queue age stabilizes, and the operator records the release/schema identity and commands used. Production activation steps remain in the controlled promotion plan.
