# Measured results and rejected optimization

Final application candidate27860bf2; baseline876b65e7. Both final pairs use the
same native fixture dataset and shared provider services per pair, PostgreSQL 2 CPU/
768MiB, Auth1CPU/192MiB, API1.5CPU/1280MiB, proxy0.25CPU/64MiB. Three warmups,
60 requests/four clients per endpoint; no CI/smoke/restore/browser load overlaps.
Baseline is measured before candidate, not randomized; this ordering and the
small sample are limitations. Physical VM backing is HDD. These are staging
measurements, not production observations or capacity promises.

## Final pairs

| Run / endpoint | Baseline p50/p95/p99 ms | Candidate p50/p95/p99 ms | p95 change | Errors baseline/candidate |
| --- | --- | --- | --- | --- |
| Final /health/live | 3.527/15.424/22.802 | 3.527/44.249/47.558 | +186.88% | 0/0 |
| Final /auth/user_status | 160.397/242.098/275.864 | 142.479/188.906/207.203 | -21.97% | 0/0 |
| Final /admin/users | 313.408/407.711/477.99 | 306.956/394.681/405.237 | -3.20% | 0/0 |
| Repeat /health/live | 3.308/4.526/4.817 | 3.539/11.914/13.719 | +163.23% | 0/0 |
| Repeat /auth/user_status | 131.56/246.289/259.308 | 153.051/226.857/298.467 | -7.89% | 0/0 |
| Repeat /admin/users | 314.998/420.575/484.704 | 300.279/483.43/602.653 | +14.95% | 0/0 |

Negative change means lower observed candidate latency, not causal proof of an
application optimization. Session-status p95 stayed below250ms in both candidate
runs. Admin p95 ranged394.681..483.430ms and misses the provisional250ms simple-read
target. Health p95 was higher than paired baseline in both final runs, while
remaining11.914..44.249ms. The health tail increase and admin repeat regression
are retained as observed concerns; they are not hidden by an average or declared
fixed. p99 changed direction across runs and is poorly estimated by60 samples.
No overall application performance improvement is established.

## Quota investigation

The clean1CPU PostgreSQL experiment recorded191/202 throttled periods and28.7s
throttled time, with candidate session p95304.596ms. At2CPU the count-query
experiment recorded64/160 throttled periods,2.423s throttled time and229.899ms
session p95. Final first run at2CPU recorded66/159 throttled periods and3.440s
throttled time. Auth had little throttling at1CPU. This supports increasing the
staging PostgreSQL quota, not a production hardware or application speed claim.
Across-run fixture growth and scheduling prevent exact causal attribution of
latency deltas. Cgroup throttled time is aggregate scheduler accounting, not
wall-clock request delay. Query-cost evidence reports only query IDs/calls/costs,
never SQL text. No representative EXPLAIN/ANALYZE workload or new index was added.

## Admin count experiment and backout

Commit595dff8d used count metadata to remove one HTTP read. Contract tests and
native empty-offset pagination passed. At1CPU, paired admin p95 was499.412ms
baseline versus624.897ms candidate; at2CPU391.888ms versus468.463ms (+19.54%).
There was no stable measured benefit. Commit583e066b restores the service exactly
to baseline and retains three pagination/filter/error contracts. Final runs use
that restored implementation. Fewer round trips were not accepted as sufficient
performance evidence. One additional run overlapped CI and is explicitly
discarded from results, with private diagnostic evidence retained on VM.

## Missing measurements

No form submission/reservation mutation/catalog/search/public tenant benchmark,
full frontend waterfall, Redis latency distribution, queue lag, sustained memory
endurance or realistic maximum load was measured. No RPO/RTO target follows from
a17-second component restoration. No production latency or readiness is claimed.
Source JSON in `evidence/` preserves initial,1CPU,2CPU count experiment, final and
repeat results, including throughput/errors/quotas where captured.
