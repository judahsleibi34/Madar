# Controlled notification-worker cutover

## Inventory and ownership

Read-only inspection found active and retained historical consumers plus
independent supervisors and unrelated workloads. Exact container/image/host/unit
identities and counts are retained privately, excluded from Git. Operators must
remeasure these from the approved private inventory. Docker status alone does
not establish exclusive ownership; unrelated workloads must remain untouched.

`schema148_release.live_consumer_inventory` checks all Docker candidates and
host process/cgroup visibility, including manually launched/docker-exec workers.
The live READ_ONLY candidate PID is a positive visibility control. Unknown
consumers, running/restarting legacy consumers, non-no restart policies, changed
candidate images and ambiguous ownership reject admission. Root policy binds
legacy IDs/images to the actual completed origin. This is not permission to stop
unrelated services or inventory only one Compose project.

A reviewed optional policy may exclude unrelated native SDK consumers only with
immutable measured image/spec and target PostgREST identity, a different HS256
signing authority, no recognized direct database/signing credentials, native
positive control200 and foreign-token401/PGRST301. Different JWT strings or
expired/shared tokens do not prove separation. Unknown signing schemes and
PGRST303 fail closed. See schema148_consumers.py and the seven regression tests.
The native synthetic probe actually returned200 and401/PGRST301. Production
exclusion policy and all supervisor ownership remain unapproved/unproven.

## Execution order under future independent approval

1. Accept exact source/images/controller, current-data evidence and protected
   maintenance scope. Prepare compatible candidate READ_ONLY; it cannot consume.
2. Existing coordinator fences origin write/worker/boot ownership, drains owned
   old workers and establishes maintenance. Wait for provider calls where possible.
3. Resolve any processing deliveries through separately approved reconciliation.
   Every processing row, expired or live, blocks147. Preserve provider evidence.
4. Seal native cluster/schema/consumer/quiescence evidence before backup. Require
   zero other active client transactions, prepared transactions and queue locks.
5. Existing backup/restore/replica gates run. Recheck authority, candidate core,
   consumers and native database before each exact SQL entry147 then148.
6. Verify schema/RPC/grants/preservation, accept target runtime, establish exact
   NORMAL148 authority, promote through the existing coordinator, activate only
   the owned protocol2 consumer and validate actual processing.

Protocol1 SQL works at146; protocol2 active startup requires the new protocol.
READ_ONLY standbys deliberately stay healthy without any business RPC. After147,
legacy claim/finish and direct service-role delivery mutations are denied by DB.
The native suite checks all four stale finish outcomes, lock-wait expiry,
concurrent completion, retries, real process crashes and restart recovery.
A provider may have accepted before a lost acknowledgement: fencing does not
provide exactly-once SMTP/push delivery. No automatic acknowledgement fallback.

Actual source-level actor tests and native SQL/process tests pass. A full
privileged controller install/real host reboot/complete legacy Python image
matrix is not claimed; those integration boundaries remain acceptance gates.

The private inventory includes stopped historical slots. Each target consumer
must be bound to the reviewed legacy policy or independently proven unrelated.
No production unit/container was stopped or reconfigured. Publication review
rejected exporting the raw inventory; the public PR retains only this summary.
