# Business-workload evidence

The new workload uses native authenticated calendar bootstrap with one synthetic
tenant, two users and501 private events. Two API processes use the same provider,
768MiB/.5CPU each, concurrency2; no quotas were increased. Three deterministic
randomized-order pairs were attempted with five warmups and60 measured reads
per successful run. No general application speedup is claimed.

The historical baseline cannot load this workspace: all three initial probes
returned500, before timed collection. Direct provider comparison confirmed a
50-ID filter succeeds200 (2073 query bytes), while501 IDs returns414 (19662
query bytes). There is therefore no valid successful baseline latency or
improvement percentage.

The corrected candidate completed180 measured requests with zero errors and
501 events in every response. Per-run p50:304.049/388.910/395.280ms;
p95:467.333/539.649/515.759ms; throughput:6.122/5.092/5.119requests/s.
All combined calendar responses recompute authorization and report cache misses.
No p99 is reported from these small per-run samples.

The fix batches only the confirmed oversized invitation-review filter into50-ID
requests, preserves tenant/disposition/authorized-event filters, then selects the
global newest50 reviews. Unit tests include foreign tenant/event records and
newest records across multiple batches. This is an availability and correctness
correction, not a speculative query optimization.

The same drill re-proves editor→availability masking. Single-request timings in
that proof are diagnostic and are not benchmark comparisons. Source-overlay
fixtures are explicitly distinguished from fresh CI artifacts. HDD-backed
virtual storage, shared provider CPU and other bounded native tests constrain
these synthetic results. Production throughput/SLOs and larger task/calendar-ID
filter behavior remain unproven. See evidence/calendar-business-workload.json.
