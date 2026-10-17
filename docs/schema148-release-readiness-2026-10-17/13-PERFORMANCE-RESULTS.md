# Measured paired API results — no general speedup established

Baseline4f2c31aea7a10e33d337f506763258afa7e4419c offline source overlay versus final
32c77afd01a012c7d21240316d4a46e52c3cbf14 fresh locked CI image. Same restored synthetic
schema148/native GoTrue/PostgREST/Redis, direct equal-hop internal HTTP. Dedicated
4vCPU/5402MiB VM, rotational virtual disk, API768MiB/1.5CPU each, PostgreSQL512MiB/1CPU,
client96MiB/.5CPU,2 clients.3 randomized pairs(seed148),10 warmups then120 requests
per role/endpoint/pair:2160 measured requests +180 warmups, all HTTP200. Auth reads
assert logged_in=true; anonymous200 cannot count as success. Runtime images and
source/ownership verified before start, no other test-image load allowed. Baseline
API/helper removed after measurement; retained application state preserved.

Values below are medians of the three per-run percentiles, not pooled percentiles.
A positive change is slower. See raw per-pair values, throughput and resource
counters in evidence/paired-benchmark.json.

|Endpoint|Baseline p50 ms|Candidate p50 ms|Baseline p95 ms|Candidate p95 ms|p95 change|Errors|
|---|---:|---:|---:|---:|---:|---:|
|/admin/users|203.353|197.707|309.465|306.429|-0.98%|0|
|/auth/user_status|97.525|97.632|177.873|184.371|+3.65%|0|
|/health/live|1.616|1.750|2.375|2.781|+17.09%|0|

The health read is slower in two pairs and the first candidate health run is
particularly variable. Session p95 also varies; admin differences are small and
mixed. These observations do not establish a reproducible overall speedup or
attribute a causal application regression. No speculative admin-query rewrite,
index or algorithmic optimization was shipped. The candidate admin p95 remains
above the provisional250ms simple-read target in these conditions.

PostgreSQL was throttled in1065/1243 periods(85.7%),72.820s throttled time and
119.137s CPU; neither API recorded CPU throttling. Auth had one throttled period.
This is evidence that the deliberately reduced restored-DB CPU quota constrained
this run; it does not isolate every source of latency. HDD import duration is not
an API benchmark. Resource limits were not increased to manufacture a speedup.

Synthetic dataset stayed exactly49 users,41 tenants,32 projects and41 deliveries
before/after.3 pairs and360 requests per image/endpoint do not establish reliable
p99 or confidence intervals; neither is reported. Build method, local caches,
small dataset, background native services and guest scheduling remain confounders.
No production capacity/SLO or reservation/form/checkout HTTP latency follows.
Frontend lint/build/tests pass; no new bundle-size/loading improvement is claimed.

Next measurement:larger stable representative business workload, alternate quota
profiles with capacity monitoring/randomized order, more independent repetitions,
request/provider/query timing and defensible tail samples. Keep correctness tests
and remove proposed optimizations that fail reproducible validation.
