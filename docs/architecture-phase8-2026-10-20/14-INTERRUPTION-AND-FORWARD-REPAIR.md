# Native generic interruption and drift evidence

The disposable-only adapter rediscoveres exact Git objects and reuses the
existing LockedMigrationExecutor. An exclusive fsynced attempt reservation
precedes execution. Failed, completed or killed attempts cannot automatically
replay. Every connection requires loopback plus the exact synthetic ownership
marker; no production endpoint/credential is accepted by its CLI wrapper.

Native tests cover one/two/three future migrations, transaction rollback,
competing advisory lock, bounded schema-row lock wait, missing backup, wrong
origin, routine denial for coordinated/destructive SQL and duplicate execution.
A real child process is SIGKILLed immediately after COMMIT151. Its surviving
journal still says applying/running, while a fresh connection observes151 and152
has not run. The consumed attempt rejects. A separate lost-response test requires
an inspected151→152 remainder plan on a fresh attempt. Neither permits replay of
production approval or represents full protected forward-repair acceptance.

`migration_drift.py` reuses the existing structural aggregation, initially extracted unchanged. Native search-
path shadowing reproduction then required a transaction-local pg_catalog path
for both the historical helper and generic observer. It performs a bounded
read-only snapshot of identity/schema/catalog/roles/grants. Root history evidence
must be supplied independently; it never learns a missing SQL ledger from the
live schema number. Missing/mismatched baseline, origin, catalog or hashes
reject; no repair or mark-as-applied operation exists. Protocol functions are
called only after their catalog fingerprint matches the expected baseline.
A changed function that would raise if called is refused before execution.
Existing writer transactions are refused without committing/rolling them back.
Native metadata-change tests pass. OID-sensitive catalog hashes compare the
same cluster; restored clusters need independently validated semantic acceptance.

These are NATIVE DATABASE/SERVICE tests. Full protected146→150 guest execution,
provider private acceptance, independent handoff, proxy/boot recovery and reboot
at each operation boundary remain NOT TESTED this phase. Historical guest
installation/reboot evidence is not promoted to this missing combined proof.
