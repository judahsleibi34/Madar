# Separate notification outbox successor — schema149

This branch is separate from the schema148 integration preview. Five native
ownership checks fail on148: superseded sent/failed/dead completion, obsolete
channel-policy resolution, and expired-owner completion. A stale resolver could
suppress successor work or clear its lease. Delivery fencing147 does not fence
this separate queue.

Mirrored149 is a new, unselected, coordinated148→149 candidate, policy none.
It preserves001–148 and active release.json. Existing146→148 admission does not
authorize149. The ordinary automatic migration loader rejects this manifest.

The new outbox generation and database-clock lease are checked under row locks
by claim_v2, resolve_v3 and finish_v2. Resolution checks ownership again after
materialization; expiry rolls back inserted deliveries and status together.
Legacy materialization is an owner-only helper; its public name rejects, and
legacy RPC/direct queue UPDATE/DELETE privileges remain revoked. Existing INSERT
enqueuers and security-definer retention cleanup remain supported.

The successor worker requires delivery protocol2 AND outbox protocol2 before
any scheduler/resolver/delivery/cleanup work. It rejects148 without fallback.
Generation identity follows success/failure paths; lost acknowledgement cannot
undo committed resolution or finalize a reminder after lost ownership.
External provider acceptance remains outside the delivery acknowledgement
transaction: duplicate external delivery remains possible. No exactly-once claim.

147's delivery UPDATE revocation also broke the retained deletion workflow's
direct queue cancellation.149 provides stop_deletion_notification_work, deriving
subject scope from the actual frozen deletion request. It checks original lease
owner, claim attempt and database-clock expiry before and after queue waits.
Application code passes original claim identity rather than a successor's reread.
No blanket queue permissions are restored. Other deletion-step ownership and
failure-state updates still need a separate comprehensive review.

## Executed validation

- Five native148 baseline checks FAIL, demonstrating the old defect.
- Focused queue/worker/deletion unit suite:48PASS,0skip.
- Final disposable PG17 rehearsal:109 executions, allPASS,0skip:21 coordinated
  source/interrupt tests,5 delivery-upgrade,18 delivery-fencing,22 business on148,
  5 outbox-upgrade,16 outbox-fencing/cancellation,22 business repeated on149.
- Real connections test expiry/reclaim, concurrent finish/resolve, row-lock wait,
  expiry during materialization, crash/restart, lost response, all terminal
  outcomes, legacy/direct mutation denial, enqueue/cleanup, user/tenant scope,
  wrong deletion claim and unfreezed/expired subject denial.
- Migration mirrors/checksums, transition, forward-release, dependency locks,
  tracked-secret hygiene and whitespace validation pass.

Commands:

```sh
sudo -n env BACKEND_TEST_IMAGE=madar-schema136-preparation-test:working \
  bash web/scripts/rehearse_migration_149.sh
python3 web/scripts/check_migrations.py
python3 web/scripts/check_migration_transitions.py
python3 web/scripts/check_forward_release.py
```

Initial native fixture failures (pending work left by preceding business tests,
synthetic service role missing BYPASSRLS, missing Auth identity) were corrected
without weakening SQL/ACL assertions. The final marked disposable database is
separate from retained staging; owned temporary containers are removed. No real
payment, email/push or production database operation was performed.

## Rollout and unresolved gates

This is READY FOR CODE REVIEW, not a production release. Stop/fence every old
notification resolver and deletion worker/supervisor, drain database sessions
and reconcile ALL processing outbox rows, including expired claims. Never reset
provider-uncertain deliveries to unblock admission.149 refuses processing outbox.
Before commit SQL rollback retains148; after commit use accepted149-aware images
and forward repair. Do not restart unfenced workers or restore old grants.

A future separately reviewed admission must bind149 source/images, all worker
owners, provider writer lifecycle, backup/restore/replica support, data
preservation, boot/reentry and fresh independent operation authorization. Existing
148 controller/backup acceptance does not imply149 support. No full native
Auth/Storage/PostgREST149 stack or149 production artifact was accepted here.
No production mutation, billing activation, merge or deployment is authorized.
