# Queue freshness under transaction isolation

On2026-10-20, follow-up to the statistics-cache correction reproduced a separate
source-helper admission defect on actual PostgreSQL17. Refreshing
`pg_stat_activity` does not refresh a REPEATABLE READ or SERIALIZABLE transaction's
view of business tables. An independent writer can commit pending deletion work,
disconnect completely, and leave zero current client sessions while the observer
continues seeing an empty historical queue.

The reproduction used a new network-isolated PostgreSQL container, no published
ports or host database volumes,256MiB/.5CPU server and192MiB/.5CPU client limits.
Four independently created minimal synthetic databases contained the helper's
queue/schema structures and explicitly synthetic constant protocol functions.
This is NATIVE DATABASE evidence about PostgreSQL visibility and the actual
source helper, not full migration149 or business-RPC acceptance. A monitor in
another database confirmed each writer's server backend exited before admission.

| Isolation | Actual committed pending requests | Helper observed | Before correction |
|---|---:|---:|---|
| READ COMMITTED | 1 | 1 | Rejected |
| READ UNCOMMITTED | 1 | 1 | Rejected |
| REPEATABLE READ | 1 | 0 | Incorrectly accepted |
| SERIALIZABLE | 1 | 0 | Incorrectly accepted |

The exact b9d826ee module was retained privately before correction. The first
fixture invocation failed because its image user could not read the private
bind mount; it made no admission observation. Its log is retained. Repeating with
the fixture owner's explicit unprivileged UID produced the table above. Both
owned containers were removed only after positive owner-label checks.

`observe_database_quiescence` now reads actual `transaction_isolation` before
statistics/queue observations and requires READ COMMITTED or READ UNCOMMITTED.
PostgreSQL gives those two levels fresh statement snapshots. Unknown/malformed
values, REPEATABLE READ and SERIALIZABLE fail closed. The helper never changes
the caller's isolation level, commits a transaction, resets a queue or suppresses
a counter. Its existing statistics refresh remains necessary and unchanged.

After correction, all four native cases refuse unsafe admission:READ COMMITTED
and READ UNCOMMITTED see and reject the actual pending request; the stronger
levels refuse before queue observation. Two additional native regression cases
run against the full disposable149 schema in the hosted migration harness. Model
tests retain exact ordering and rejection-before-observation assertions; all
seven admission tests pass locally.

Current concrete provider-adapter SQL opens a fresh psql read-only transaction
for each observation; no persistent operational cursor caller was found. The
cursor helper's unsafe API behavior is still corrected before future integration.
The schema150 profile remains unregistered, the selected descriptor and published
SQL001–150 are unchanged, and no production occurrence or mutation is claimed.

The accepted b9d826ee application/runtime evidence predates this controller-helper
correction. It must keep its original source identity. New source CI/artifacts
are separate evidence and cannot relabel those running images or earlier receipts.
Private native JSON/logs are retained outside Git; no credential or customer
record was used. The isolated fixture is gone and the new PhaseVII application
stack is deliberately stopped with its data retained after successful acceptance.
