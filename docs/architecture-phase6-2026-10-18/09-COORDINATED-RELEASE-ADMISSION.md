# Exact146→150 preparation

New DELETION/version7 constant records146→147→148→149→150,with separate
schema-146-150-coordinated.json and migrations-147-150-coordinated.json.
Version follows the existing explicit operation sequence. Active release146,
version5/6 and published001–149 SQL/mirrors remain unchanged. Policy:none;
coordinated;rollback-compatible150only. Automatic manifest loading rejects it.

The successor inspector authenticates bounded regular metadata/SQL on captured
file descriptors,checks mirrors/exact paths/order/checksums,and observes all
three protocol2 contracts. Its quiescence model includes processing deliveries,
outbox,deletion requests,orphan processing steps,all other client sessions
(including idle),prepared transactions and queue locks. Unknown state is rejected.
An inspection result cannot issue authorization,execute SQL or activate workers.

IMPORTANT:the new operation is deliberately UNREGISTERED in the operational
profile registry. Generic existing coordinator paths must not silently skip the
149 fail-closed hooks. `admitted_manifest` rejects unconditionally until the
concrete protected provider/backup/boot/write-handoff integration is implemented
and independently validated. No local PASS packet,caller adapter attribute or
forged receipt turns this preparation into production admission.

Remaining engineering is substantive:maintenance-specific positive probes,
full original-role backup/restore integration,accepted READ_ONLY candidate health
without consuming workers,150 inventory routing,persistent boot recovery and
actual privileged interruption acceptance. These are not merely missing operator
permission. Native SQL and state-machine tests are not protected release proof.

## Legacy backlog compatibility correction

A later native149 diagnostic reproduced2FAIL/1PASS against the first150source
inspector:idle waiting_retry work with a prior external attempt and a pending
legacy tenant request both passed zero-processing quiescence. Published150 cannot
retroactively invent durable provider intent or reconstruct083tenant freeze
preimages. No actual duplicate external harm or production execution was claimed.

The successor preparation now measures legacy_deletion_backlog before EACH
pre150boundary:every request outside completed/completed_with_retained_records/
cancelled_before_execution must be independently reconciled first. No automatic
reset,cancellation,status inference or queue deletion occurs. Terminal cancellation
may legitimately retain pending steps;those historical rows are preserved. At150,
new pending work is not misclassified as legacy. All earlier processing/lease/
lock/session/prepared checks remain. The150provider model requires the same counter.
The operation remains unregistered regardless of positive observations.

Corrected native full rehearsal:187executions PASS,including3legacy149admission
cases and38ownership/upgrade150cases,plus retained business/calendar24at150.
Original native migration150SHA256 remains63d4d0c7af93bd3c3e93158a2e281b41eed23b83bfafd4b3f1ba22313533b722.
This is stricter source admission for an unregistered path,not historicalSQLrepair,
a schema151cutover,or authority to reconcile live requests. Applying150outside the
reviewed controller does not satisfy this additional current-data precondition.
