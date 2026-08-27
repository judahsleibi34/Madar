# Performance, scalability and host capacity

## Measured Node 1 state

At final collection, load averages were 1.34/1.45/1.86, root disk was 28% used with 318 GiB free, inode use 14%, and approximately 3.2 GiB RAM was available. Production Madar idle memory was approximately 560 MiB. Services have CPU/memory/PID caps and the root filesystem has ample immediate upload/backup headroom.

Risks:

- 1.8 GiB of 4 GiB swap was in use; cause and peak history were not measured.
- Docker build cache is 81.21 GiB, driven in part by repeated deployments; 65.89 GiB is reclaimable.
- Recursive root `chown` across all stored files every two minutes grows linearly with assets.
- Backup tooling never prunes and local backups share the failure domain/root disk.
- Redis has no maxmemory below its 256 MiB cgroup and uses noeviction.
- Frontend bundles include several very large CSS/JS assets.

## Architecture-level scaling

Synchronous Supabase HTTP calls dominate many large route handlers. Several response/calendar/builder endpoints use bounded limits, but some aggregate/list paths fetch broad rows before Python transformation. Publication schema responses can be large and are revalidated rather than CDN-cached. Public analytics/form/reservation traffic reaches the backend for each action. AI/provider calls are synchronous at the request boundary even where code execution is isolated.

Likely behavior, not load-tested:

| Scale | Assessment |
| --- | --- |
| 10 tenants | Current Node 1 capacity is adequate if deploy storms and external provider failures are controlled. |
| 100 tenants | Needs DB/API latency dashboards, worker throughput tests, cleanup scheduling, queue alerting and bundle/public-cache tuning. |
| 1,000 tenants | Not proven. Single backend instance, single Redis, local storage mounts, synchronous external calls and one-host failure domain are material constraints. |

No disruptive production load test was run. Before broader launch, benchmark staging with realistic publication sizes, concurrent form/reservation idempotency, upload streaming, analytics aggregation, queue backlog and provider latency. Record p50/p95/p99, DB calls/request, worker throughput, memory and disk growth.

G20/G21 are **PASS WITH CONDITIONS** for current small workload only.
