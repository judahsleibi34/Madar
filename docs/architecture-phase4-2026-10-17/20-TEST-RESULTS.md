# Executed tests and failures

| Command/scope | Result |
| --- | --- |
| Preview full backend at3ab2bd50, run_tests_no_external_network.py |3782collected,3033PASS,749SKIP;47.839s; no external attempts/sites |
| Successor full backend at5e5c0c3e |3814collected,3044PASS,770SKIP;45.183s; no external attempts/sites |
| Focused migration/controller boundary |41PASS |
| Forward repair execute path |11PASS |
| Artifact verification |12PASS; two regressions FAIL against9a89f4b6 |
| Exact CI-source shell guard |4PASS |
| Fresh artifact safety |6PASS |
| Provider/readiness/forward focused scope |24PASS |
| Historical exposure audit |2PASS |
| Calendar route+batch |45PASS |
| Successor queue/worker/deletion unit scope |48PASS |
| Native148 rehearsal |66PASS,0skip |
| Native149 complete rehearsal |109executions PASS,0skip;22 business cases repeated on149 |
| Frontend npm test -- --maxWorkers=2 |233files,1713PASS,1SKIP;118.73s |
| Frontend lint and production same-origin build |PASS |
| Native calendar two-process permission change |PASS; baseline stale/candidate masked |
| Native501-event candidate workload |180measured requests,0errors; baseline3probes fail500 |
| Provider role crash/drain/restart/explicit recovery |PASS;16.317s |
| Loopback alert pipeline |PASS;503retry, dedup and recovery |

Native command: `sudo -n env BACKEND_TEST_IMAGE=madar-schema136-preparation-test:working bash web/scripts/rehearse_migration_148.sh`; successor uses149 script.
Source commands: check_dependency_locks.py, check_migrations.py,
check_migration_transitions.py, check_forward_release.py, check_secret_hygiene.py,
and git diff --check all passed. Historical013/014 duplicate-content warnings
remain; no new migration validation error.

Observed failures were retained and distinguished: original SQL consistency
regressions19pass/2fail; original outbox five invariant failures; baseline501
calendar500/provider414; first new CI-source test had an eager default-path bug
(corrected); two mistyped local module names caused import errors (correct command
41pass); disposable fixture source/mount permissions and missing fields/role
attributes were corrected without weakening assertions. Conditional skips are
not passes. Final exact-source CI results after source freeze are in PR updates.
