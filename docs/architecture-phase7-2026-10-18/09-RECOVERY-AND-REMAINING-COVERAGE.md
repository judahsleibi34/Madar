# Recovery, application coverage and operational limits

## What restoration proves

The fresh native150 acceptance harness restores an independently authenticated
synthetic148 database/roles/object archive into a separate cluster, verifies
rows/sequences and owner/grant/RLS/definer fingerprints, applies captured149/150
SQL, compares preserved Auth/Storage/business data, then starts fresh accepted
images and exercises the real providers/application/workers. Its executed result
is recorded separately in`fresh-schema150-acceptance.md`. This is a useful
restored-application test, not the protected146→150 release coordinator.

The source archive deliberately contains no unfinished deletion requests. It
therefore cannot prove restoration/reconciliation of uncertain in-flight external
deletion effects. A schema150 backup containing durable effect intents, the new
provider journal, original role preimages and recovery authorization metadata
still needs independent restored-application acceptance. Restored queue state is
not permission to replay consumed approval or restart an incompatible worker.

The new adapter preserves original roles-only DDL separately from temporary
NOLOGIN state and authenticates that archive under its maintenance boundary.
Ordinary production backup/replica/restore integration is missing. No current
production backup was created, exported, restored or deleted in this phase.
No newly implemented archive method is reported as an end-to-end backup success.

## PITR and object consistency

Earlier phases' PostgreSQL WAL/PITR and independent restore evidence remains
available in their reports. No new full application/object-aware PITR, damaged-WAL
matrix or off-host recovery was completed here. The KVM guest has independent VM
storage, but shares staging's physical host; it is not an off-host DR target.
Production RPO≤15minutes and RTO≤4hours remain uncertified objectives.

A complete future test must preserve database/role/object/configuration/intent
checkpoints together. Recover before147, between committed migrations, and after150;
verify compatible source/protocols and retained maintenance restrictions each
time. Compare tenant-owned object metadata to bytes and classify missing,
unreferenced, restored-historical and incomplete-upload objects. Never infer that
PostgreSQL WAL alone restores deleted object bytes, and never delete unexplained
extra objects automatically. Quarantine and independently authorize reconciliation
where ownership or provider outcome is uncertain.

## Failure response remains forward-only after incompatible commits

The actual guest installation/reboot scope is documented in
`02-ISOLATED-PRIVILEGED-VM.md`; source/model interruption tests and that privileged
scope must not be combined into an invented complete operational rehearsal.
Missing/corrupt preimages, unknown writers, incomplete backups, stale grants or
unproven committed schema require continued maintenance and independent recovery.
Schema147 revokes legacy delivery paths;149 revokes legacy outbox paths;150
requires deletion protocol2. Restoring old grants or old workers is not rollback.
Lost COMMIT response requires exact-cluster reconnect and state verification.
No blanket retry, stale approval replay or automatic historical data restore is
authorized.

## Product, observability and performance boundaries

Backend/native CI retains reservation creation/reactivation/capacity, stock/order
allocation/rollback, simulated payment/refund/replay, tenant-resource rejection,
delivery/outbox/deletion ownership and calendar version/authorization regressions.
Gateway behavior uses synthetic responses; no payment/refund transaction or real
gateway credential was used. Native SQL checks are not complete product UI tests.
The existing browser smoke covers native MFA admission, secure cookies, privileged
access/refresh, anonymous denial and mobile login accessibility. It does not
establish complete forms/builder/catalog/checkout/recurrence workflows.

The new read-only status command verifies private journal history and reports
pending effects/barrier conflict. It explicitly does not certify current database
or service state. Adapter exceptions/logging use bounded operation categories;
raw private preimages and secrets are not public metrics. Four loopback
notification-observer pipeline tests passed in CI, using isolated test signals
and destinations. This is not installation of production alerts or new native
controller-alert delivery. Production destinations remain untouched.

No new representative paired performance benchmark was run and no general
speedup, production capacity, p99 or SLO claim is made. Staging remains constrained
by fourvCPU,5.4GiBRAM and HDD-backed storage. Guest resources were limited to
onevCPU/1GiB and its shutdown preceded the new full stack. The fresh acceptance
wrapper requires8GiBfree and2,200MiBavailable before preparation, fixed loopback
ports and bounded container limits. Transient artifact-import memory and actual
service states are retained privately; successful synthetic acceptance cannot
establish production capacity.

P1 remains complete protected operational integration and independent recovery.
P2 includes object-aware/off-host PITR, broader browser/tenant workflows,
cross-process cache consistency, native alert delivery and representative paired
benchmarks. P3 enterprise/scaling expansion remains deferred. None justifies a
new broker, orchestration platform or architecture rewrite at this boundary.
