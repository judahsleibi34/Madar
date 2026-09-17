# Observability, reliability, performance, and failure modes

## Observability

Madar has liveness/readiness and token-protected Prometheus-format metrics with bounded route labels, queue/storage/calendar metrics, structured request IDs, security audit records, and Docker log rotation. This is a good instrumentation foundation. No Prometheus collector, dashboard, external uptime monitor, Sentry/tracing, PagerDuty/email alert, disk monitor, backup alert, certificate alert, or tunnel/worker alert was found.

Briefedly has a shallow `/status` endpoint. Current source has job state/heartbeats and controlled logging, but production is older and lacks the worker. Sleibi has a useful `/health`. Mailcow has internal health/netfilter tooling but no evidenced external alerting.

Madar readiness is intermittently false: the `schema` component exceeds a two-second probe budget even though all required tables answer successfully. Local and public requests moments apart returned degraded and ready. Backup freshness is explicitly disabled. Docker health checks liveness rather than readiness, so deploy/runtime orchestration does not see the degradation.

## Reliability findings

- Three Madar notification deliveries are dead and three calendar connection-sync jobs failed; no external alert is wired.
- Briefedly privacy/import/report/retention jobs cannot run because production worker is absent.
- Two-minute timers can repeatedly fail/noise without escalation.
- Cloudflared historically had repeated DNS/start failures before recovering.
- Shared filesystem means disk exhaustion becomes a correlated total outage.
- Runtime drift is not reconciled when Git SHA is unchanged.

## Performance/scalability

Likely first bottlenecks:

1. Remote Supabase/PostgREST round trips and connection limits.
2. Large builder schema parsing/normalization and frontend rendering.
3. Large upload/data-analysis memory and filesystem throughput.
4. Notification/calendar fan-out and external provider latency.
5. Gmail API quota/pagination and local PostgreSQL text growth.
6. Single Ollama workstation/model throughput and 120-second calls.
7. Docker builds/cache on the same disk as DB/mail.

Resource limits exist for Madar/current Briefedly Compose but not all legacy/infra containers. Per-route/user/tenant limits are strong in Madar and present in current Briefedly. No production stress test was performed as required.

## Failure-mode matrix

| Dependency | Madar | Briefedly |
|---|---|---|
| PostgreSQL | hard outage; authz does not fail open | hard outage |
| Redis | rate limit fails closed; degraded | DB rate limiter in current code; stale prod differs |
| Gmail/Google OAuth | calendar/provider degradation, queued retry | import/connect/report degradation, durable retry only in current source |
| Ollama | N/A for core; AI provider errors controlled | reports fail/retry; single-host capacity |
| SMTP/push | durable retry/dead-letter | not primary workflow |
| Cloudflare | public outage; localhost origin remains | same |
| Filesystem | uploads/analysis fail; disk can cascade to host | DB/mail/Docker also affected via shared disk |
| DNS | cloudflared/provider/mail failures | Cloudflare/Gmail/Ollama name failures |

## Minimum alerts

External HTTPS and readiness; API error/latency; disk/inodes; memory/OOM; DB availability/connections/size/WAL; Redis; Docker restart/health; Madar dead/backlogged queues; Briefedly job lease/backlog/worker heartbeat; backup age/verification; Cloudflare tunnel; Mailcow queue/disk/certificate; outbound SMTP; Ollama availability/latency.
