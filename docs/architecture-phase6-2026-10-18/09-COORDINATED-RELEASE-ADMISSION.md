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
