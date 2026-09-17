# Performance, load, capacity, and resilience test plan

Status: **READY** for isolated execution after SLO approval; never run against customer production.

## Test environment and pass criteria

Use production images/config shape, disposable production-engine databases at realistic schema/cardinality, synthetic non-private content, bounded test object storage, Redis and instrumented workers. Record hardware, image digest, schema, dataset, concurrency, duration and all saturation metrics. Define thresholds before execution. Initial engineering proposals are p95 below 500 ms for ordinary APIs, error rate below 1% excluding deliberate throttles, zero cross-tenant response/mutation, queue age below five minutes under admitted steady load, no unbounded memory/disk/connection growth, and recovery within the approved service objective after dependency return.

## Madar workloads

- login/refresh/logout, dashboard and tenant switching;
- builder draft autosave, revision conflicts, publication and public-site route/cache/ETag;
- public forms/tests and simultaneous reservations;
- small/large/chunked uploads, quota reservation/release/replacement and orphan cleanup;
- notification/calendar fan-out, retries/dead letters and worker restart;
- analytics write/read, dataset/chart generation, parser and remote-ingestion isolation.

## Briefedly workloads

- auth/session/CSRF/workspace switching;
- synthetic Gmail search/pagination/import with duplicate, partial and malformed MIME cases;
- thread/message reads, job enqueue/claim/lease/heartbeat/retry;
- concurrent report generation through a controlled Ollama stub and later Node B;
- export, retention and deletion with worker interruption/recovery.

## Isolation/noisy-neighbor scenarios

Run a heavy Tenant/Workspace A alongside ordinary B. Measure B latency/errors/queue delay while A exhausts each admitted quota: API tokens/concurrency, DB connections, Redis buckets, uploads/storage, publication, notifications/calendars, imports/jobs and AI tokens. Assert B cannot be denied beyond the approved global-overload policy and A receives explicit throttling, bounded queueing or cancellation. Exercise concurrent guessed cross-tenant IDs throughout.

## Failure injection

In disposable infrastructure only: unavailable/slow DB, Redis, Ollama, SMTP/provider stub, worker kill during lease, tunnel/proxy unavailable, DNS failure, nearly full synthetic filesystem, stale schema, corrupt/malformed model response, process restart and duplicate retry. Verify fail-closed security, transaction/idempotency, no completed status on partial work, graceful recovery and actionable signals.

## Node B benchmark suite

After commissioning, inventory exact CPU/RAM/NVMe/GPU/VRAM/driver/model checksum. Benchmark approved models across representative prompt/input/output sizes; concurrency 1..N; cold/warm load; p50/p95/p99 latency; tokens/sec; VRAM/RAM/CPU/temperature/power; gateway overhead; timeout/restart/model-missing behavior; and API/worker fairness. Stop at safe thermal/resource thresholds. Results choose worker concurrency and admission quotas; RTX 4060 alone does not prove capacity.

## Certification output

Publish raw aggregate metrics without customer content, thresholds, pass/fail, bottleneck, maximum safe admitted load, recommended limits, headroom and next capacity trigger. A test is invalid if it used mocks for the boundary being certified or omitted production-like schema/network/resource controls.
