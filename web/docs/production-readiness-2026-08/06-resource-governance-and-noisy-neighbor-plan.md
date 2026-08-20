# Resource governance and noisy-neighbor plan

## Shared-resource control matrix

| Resource | Existing control | Required tenant/user/global control | Saturation behavior and metric |
|---|---|---|---|
| API concurrency | container/PID limits; route limits | reverse-proxy connection/body/time limits; per-tenant expensive-route concurrency | 429/503 with retry guidance; active/queued/latency |
| DB connections | application pools/provider limits | per-service pool and DB role connection limit; reserve operator capacity | fail closed, bounded timeout; pool wait/connections |
| Redis | separate prod/dev, memory cap | ACL plus key namespace/TTL/cardinality budget | rate controls fail closed; memory/evictions/errors |
| builder save/publish | revision/size/capability checks | one publish per project and bounded per-tenant global publishes | conflict/429; duration, queue, schema bytes |
| forms/reservations/events | body/rate/idempotency/RPC locks | IP + tenant/site global budgets and spam circuit breaker | reject before durable work; accepted/rejected/latency |
| uploads/storage | size and atomic quota reservation | user, tenant, file-count, daily-ingress, concurrent-upload quotas | fail before write; reserved/used/orphans/disk |
| parser/OCR | isolated worker/resource bounds | per-tenant queue slots, file-cost units, global worker cap | queued/dead/timeout; CPU/RAM/time and fairness |
| remote ingestion | egress worker/URL policy | per-tenant URL/byte/time budget; global outbound concurrency | fail closed/retry; bytes/host/error class |
| notifications/calendar | durable claim/retry/dead | per-tenant fan-out cap and fair claim; provider quota budget | backoff/dead-letter; oldest age/dead/provider errors |
| Gmail imports | bounded scope/messages and durable job | per-workspace active job and daily message/byte budget | queue or 429; Gmail quota, imported/skipped/failed |
| Briefedly worker | leases/idempotency | fair scheduling across workspace, job-type concurrency pools | no monopolization; wait/lease/retry by workspace hash |
| Ollama | timeout/retry only | per-workspace/user daily tokens, one/few concurrent calls, global queue | controlled retry/degraded report; tokens/latency/VRAM |
| disk/log/WAL/mail | some log limits | filesystem thresholds, build-cache policy, mail/WAL/backup budgets | stop noncritical writes before DB/mail; bytes/inodes/growth |
| CPU/RAM | Madar limits; gaps elsewhere | hard service reservations/limits; production priority over AI/build/staging | shed AI/build first; throttling/OOM/swap/PSI |

## Fairness design

- Every expensive job carries immutable tenant/workspace and initiating-user identity.
- Scheduler limits both global concurrency and per-tenant in-flight count. Round-robin or oldest-per-tenant selection prevents one tenant filling every worker slot.
- Retries retain tenant accounting and use exponential backoff with jitter; poison work reaches a bounded dead state.
- Quota reservation precedes work, commit follows success, release is idempotent on failure/cancel.
- Administrative jobs use a separately bounded lane, not an unlimited priority bypass.
- Metrics label tenants only by non-reversible bounded identifiers or cardinality-safe cohorts; never email/domain/content.

## Recommended initial limits

Exact numbers are `READY` for benchmark selection, not claims. Establish them from Node B tests. Start conservatively: one report job per workspace, a small global Ollama concurrency, one import per connection/workspace, one publish per project, and bounded upload/parser queues. Define explicit maximum wait and request size before launch.

## Tests

1. One heavy tenant saturates uploads, imports, reports, notifications, and publication while a second performs ordinary actions.
2. Assert second-tenant p95 and error rate remain within declared SLO.
3. Kill worker/Redis/DB/Ollama; assert bounded waits, correct retry, no duplicate quota, no cross-tenant claim.
4. Cancel/retry jobs across lease expiry and process restart.
5. Drive disk to synthetic warning/critical thresholds on a disposable filesystem; verify alerts and safe refusal.
6. Verify label cardinality and logs contain no customer content.

No production load testing is authorized.
