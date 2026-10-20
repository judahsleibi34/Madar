# Measured scope and operational evidence

No production speedup,capacity,SLO,RPO/RTO or coordinated-release downtime claim
is made. No production load or service interruption was performed.

| Observation | Measured environment/source | Result / limitation |
|---|---|---|
| Source plan generation | Node2,22f9 source,452 tooling files |4.667s,single observation,application-only150→150,no SQL/authority |
| Expanded tooling plan | Node2,c3d6 source,488 tooling files |5.521s,single observation,no missing required inputs;not a controlled speed comparison |
| Real CI archive capture/OCI verification | Node2,9932 artifact,462,845,660bytes |6.965s,no import or protected operation |
| Native maintenance component restore | Four-vCPU/HDD staging VM |Three successful observations13.011s,13.004s,15.923s across evolving diagnostic attempts;not a benchmark distribution |
| Native maintenance component restore | GitHub91a run |8.963s,independent roles/owners/ACL/data/sequence/object-byte restore;no metadata activation or replica |
| Generic source/native rehearsal | GitHub91a run |64cases,96.561s;overlapping source/parser/policy/native cases,not64production executions |
| Backend full suite | GitHub91a run |4,305 discovered,3,436passed,869conditional skips,52.894s;skips are not passes |
| Full-provider operation | Exact-source native acceptance artifact |Read its elapsed_seconds and runtime/image identities;fresh synthetic genesis,not current-data protected maintenance |

The shared staging VM had four vCPUs,5,402MiB RAM and roughly11–12GiB free disk.
Its retained provider stacks and evidence were preserved. Small owned network-none
clusters/component containers were resource bounded and removed only after label
verification. No physical-node restart or unrelated staging cleanup occurred.
The full-provider pipeline uses dedicated disposable GitHub runners sequentially,
with a private global staging lease,fixed per-component CPU/RAM/PID/logging bounds,
8GiB disk and2,200MiB available-memory preconditions,private database networks and
loopback-only HTTP/TLS/provider ingress. It stops its owned stack after acceptance.

Bounded phase events identify captured SQL version/hash,image import,provider
bootstrap,application acceptance,deletion and browser stages. Sanitized failure
reports expose exception class,phase,diagnostic hash,optional fixed failure category
and bounded runtime identity/health—not raw SQL,provider logs,credentials or MFA
state. Test credentials and unfinished work remain in private owned paths.
Completion is published only after observed owned-service shutdown.

Existing read-only maintenance status is historical journal observation and never
issues authority. Production alert destinations were not activated. A complete
collector/alert/retry/recovery path and protected-controller operational metrics
remain separate unfinished work. No percentile statistics are inferred from these
small/component observations.
