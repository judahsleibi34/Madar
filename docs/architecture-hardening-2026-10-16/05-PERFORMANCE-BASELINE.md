# Initial measured staging baseline

Baseline876b65e73ea8ceaf398145d8677019184798a95c; candidate17e8b5ee. Native
PostgreSQL/Auth/REST/Redis,4vCPU/5402MiB dedicated VM, HDD-backed qcow2.
Both APIs1.5CPU/1280MiB; proxies0.25CPU/64MiB; initial Auth0.5CPU,
PostgreSQL0.75CPU. Three warmups,60 requests/four clients per endpoint,
synthetic fixture data; no production traffic/load.

| Endpoint | Baseline p50/p95/p99 ms | Candidate p50/p95/p99 ms | Errors baseline/candidate |
| --- | --- | --- | --- |
| /health/live | 3.441/4.77/6.483 | 3.588/5.763/8.525 | 0/0 |
| /auth/user_status | 311.439/503.91/600.552 | 299.459/477.516/513.322 | 0/0 |
| /admin/users | 671.621/888.368/898.932 | 694.467/903.406/1074.354 | 0/0 |

Raw sanitized evidence: `evidence/performance-initial.json`. The authenticated
session endpoint has a successful-login assertion in the final benchmark tool;
earlier samples used HTTP status only. Initial native smoke established working
sessions, but they are not relabeled as the stronger later assertion.

This covers health/session/admin reads only. Forms, reservations, catalog, search,
public tenant rendering, query plans, Redis/queue latency, full waterfall,
sustained memory growth and supported throughput were NOT benchmarked. RPS in
the JSON is sample completion throughput, not maximum capacity. p99 of60 samples
is near the maximum and cannot establish a stable tail distribution.

The frontend exact production build passed its existing public bundle audit:
4 universal preloads,17 entry chunks,39 renderer chunks,505862 public CSS bytes,
about44MiB complete dist. No route/bundle source changes were made; no browser
page-load before/after speed improvement is claimed.

Subsequent resource tuning, count-query experiment/backout and final pairs are
in06-PERFORMANCE-RESULTS.md. Fixtures grew between rounds, so comparisons across
rounds are observational and not a controlled causal application improvement.
