# Read-only operational evidence

The source planner emits bounded canonical inventory/plan JSON with observed
origin supplied explicitly,pending SQL,risk,compatibility,source hashes,trusted
input hashes/modes and missing gates. It never connects to a database or issues
authority. Generic drift observations contain only schema/system identity,
catalog digest and validated protocol integers;private role values remain inside
PostgreSQL. Missing expected root history blocks rather than learning a baseline.

Native attempts reuse the existing executor journal,including source,SQL hashes,
from/to schemas,phase and commit observations. The disposable adapter reserves
one consumed attempt before execution. A killed process can leave applying while
the actual schema advanced;operators must inspect both,not infer rollback from a
failed process. No observer changes state,clears maintenance or repairs history.

CI preserves source plans and native coverage reports. An explicit BLOCKED report
is not full staging acceptance. Fixture logs are private and bounded;failure
codes do not print database credentials. Rehearsals pin the local Docker socket
and positively owned resources. Production journals/credentials remain private.

The existing four loopback notification observer checks run in backend CI. New
end-to-end migration-alert delivery,duplicate/recovery notifications,production
collector installation and production destinations were NOT TESTED/NOT ENABLED
by this phase. Do not claim alert delivery from a JSON signal alone. See the
remaining roadmap for the P2 pipeline work and the P1 controller integration
needed to emit authoritative operation events.
