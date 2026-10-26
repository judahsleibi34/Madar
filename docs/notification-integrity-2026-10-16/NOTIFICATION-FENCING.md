# Durable notification claim fencing

## Root cause and decision

Migration073 finish locks a delivery by id but ignores the claimant/lease.
Schema146 therefore accepts attempt1's completion after attempt2 reclaims it.
The new mirrored147 migration adds monotonic `claim_generation`. Protocol2 claim
increments it atomically with the attempt and lease. Protocol2 finish acquires
the row lock, samples **database** time after any wait, and compares id/generation/
processing/live deadline in its UPDATE. Every sent/retry/dead/revoked outcome uses
that same predicate. A stale call raises `notification_delivery_claim_lost` and
changes no row. No application read-before-ack is used. Competing finish calls
have one winner; new claims use SKIP LOCKED. Direct service-role queue writes and
legacy claim/finish RPCs are denied. Resolvers/cleanup remain security-definer.

A worker validates a generation before any provider call, carries it to finish,
and never uses a legacy fallback. Every authorized consumption poll requires protocol2 before resolution
or delivery; restricted standbys do not make business RPCs. Ownership loss and acknowledgement failure have bounded counters;
unknown successful provider outcomes are logged safely, never counted sent or
used to finalize a reminder. A failed acknowledgement never causes an immediate
second send in the same batch.

## Rollout / interruption / rollback

This is a **coordinated, unselected** candidate, exact schema147 and policy none.
The normal automatic executor rejects it; active release146 is unchanged. Neither
this source nor rehearsal authorizes production. A future production operation
needs the existing protected controller's separate reviewed147 admission, exact
images, verified backup, current-data rehearsal, authority and operational approval.

1. Stop old consumers under existing exclusive worker ownership. Drain completed
   sends. Inventory processing rows, including expired ones, and reconcile their
   provider results. Do not blindly requeue uncertain sends to unblock migration.
2.147 refuses if any processing row remains. The access-exclusive table lock
   serializes a legacy claimant racing this check. Schema/DDL/ACL changes commit
   together; refusal or disconnect before commit leaves146 fully usable.
3. Once147 commits, legacy consumers fail closed. A new worker started too early
   fails before any consumption on146. An old in-memory consumer cannot use its
   unfenced finish even if it later resumes. No automatic old-worker restoration
   is safe after147: repair forward with a generation-aware accepted image.
4. Verify schema147, protocol2, RPC grants/queue write restrictions, then activate
   only the new worker generation and verify actual consumption/readiness.
5. A crash after commit/before worker start leaves durable pending work; repeat
   protocol checks and start the accepted workers. Do not replay147 or downgrade
   ACLs/functions. Full backup restore requires fencing all previous consumers.

Unknown legacy processing rows can block the migration intentionally. Resolving
those rows is an independently approved production data operation, not performed
by this change. No historical SQL or prior manifest is rewritten.

## Provider acceptance boundary

Fencing does **not** make SMTP/push exactly once. If a provider accepts a send and
the worker dies or loses its acknowledgement, recovery may attempt it again.
Synthetic process-crash tests deliberately prove two sends for a non-idempotent
provider and one effect for a provider enforcing the same stable delivery-id key.
Existing SMTP/push providers do not promise that idempotency contract. Operational
reconciliation/deduplication remains necessary; no guarantee is invented. Stale
workers cannot corrupt the canonical delivery status despite that external ambiguity.

## Executed first validation

`BACKEND_TEST_IMAGE=madar-schema136-preparation-test:working bash web/scripts/rehearse_migration_147.sh`
on madar-staging: five native upgrade checks PASS (0.059s), seventeen native
fencing/concurrency/process-crash checks PASS (6.855s). The baseline146 defect was
reproduced first, then all four stale outcomes rejected at147. Focused worker/RPC/
preference suite26 PASS (0.059s). An initial focused run omitted the historical
migration fixture mounts and had two FileNotFound errors; adding normal fixture
mounts fixed the command without changing those assertions. No production action.

## Broad regression and standby correction

First full run3662 tests found one real release-standby regression: probing the
new protocol before the recovery-authority poll attempted a business RPC from a
valid READ_ONLY standby. The probe now runs on every authorized consumption poll,
before any auxiliary/resolution/delivery work. Restricted standbys retain existing
healthy/no-business-RPC behavior; active pre147 workers remain unhealthy and do
no work. Existing transition-worker assertions were kept unchanged.

Full hermetic rerun:3662 discovered,705 skips,2957 executed PASS,43.179s;
external attempts/sites empty. The22 additional native checks are conditional
skips there and were separately executed successfully by rehearsal147. Three
release-contract tests verify exact pins, tamper refusal and automatic-executor
rejection of the coordinated manifest. Active release146 and all001–146 SQL stay
byte-for-byte unchanged. No frontend or dependency changes.
