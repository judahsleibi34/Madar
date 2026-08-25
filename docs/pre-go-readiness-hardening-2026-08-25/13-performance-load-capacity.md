# Performance, load, and capacity

## Bounded staging measurements

| Flow | Requests / concurrency | p50 | p95 | p99 | Throughput | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| API liveness | 500 / 32 | 61.18 ms | 201.32 ms | 1,211.47 ms | 209.65 rps | 0 |
| Frontend | 500 / 32 | 11.63 ms | 118.51 ms | 1,089.10 ms | 363.06 rps | 0 |
| Public site | 100 / 10 | 297.62 ms | 516.04 ms | 1,271.73 ms | 25.31 rps | 0 |

An abuse-oriented public-site run at 500/32 produced 15 success and 485 controlled 429 responses, demonstrating rate limiting rather than application errors. Reservation contention issued 20 parallel claims to one exclusive slot: exactly one was created, 19 received controlled slot-unavailable results, and one record existed afterward.

The full regression suite supplies deterministic concurrency coverage for form/quiz replay and finalize, upload/quota boundaries, avatar replacement, analytics ingestion and pagination, notification/deletion leases, and worker backlog recovery. These results are launch-scale bounded evidence, not a prolonged soak or proof of 1,000-tenant capacity.

## Node 1 snapshot after builds and drills

| Resource | Observation |
| --- | --- |
| Root filesystem | 456 GB total, 148 GB used, 290 GB available (34%) |
| Inodes | 17% used |
| RAM | 7.2 GB total, 4.1 GB used, 3.1 GB available |
| Swap | 4.0 GB total, 3.4 GB used (83%) |
| Docker images | 38.41 GB; 19.77 GB reclaimable |
| Docker build cache | 101.9 GB; 76.53 GB reclaimable |
| Staging artifacts | 306 MB |
| System journal | 679.4 MB |

The reviewed swap warning/critical thresholds are 60%/85%. Docker cache warning is 100 GiB. Root disk, inode, memory, database, upload, backup, log, and cache thresholds are enforced by the provider-neutral capacity checker.

G21 remains PASS WITH CONDITIONS until an operator performs preservation-aware cache cleanup and recovers swap headroom before promotion. Broad `docker system prune -a` is prohibited; active and retained rollback artifacts must be preserved.

The frontend build reports a 521.47 kB Three.js vendor chunk (130.49 kB gzip). It is already separated/lazy and does not justify UI-risking refactoring before launch.
