# Observability, alerting, and SLO plan

Status: **READY** for implementation; no production collector or alert route was deployed in this phase.

## Architecture

Use a pull-based metrics collector with authenticated dashboards, bounded local retention, and an external uptime/alert path that does not share Node A's failure domain. Node B may host dashboards and medium-retention metrics after commissioning, but an external checker must still detect loss of both nodes, router, power, DNS, Cloudflare, or Internet access. Logs remain structured, redacted, access-controlled, size-bounded, and separate from metrics; do not label metrics with tenant IDs, email addresses, URLs containing tokens, message subjects, prompts, or customer content.

Recommended components are Prometheus-compatible exporters/collection, Alertmanager-compatible routing, Grafana-compatible dashboards, a log collector only after redaction and retention are specified, node/container exporters without Docker-socket write access, and black-box HTTPS/TLS/DNS probes from outside the site. Component selection is an implementation decision, not approval to deploy it.

## Service-level objectives

Before measurement begins, the product owner and SRE owner must approve availability and latency objectives. Initial engineering proposals—not contractual promises—are: public/API monthly availability 99.9% for paid service, p95 ordinary API latency below 500 ms excluding declared AI/import operations, 99% of durable jobs beginning within five minutes under admitted load, and restore objectives derived from measured drills. Error-budget policy must stop feature rollout when the approved budget is exhausted.

## Required signals and alerts

| Area | Signals | Actionable alert examples |
|---|---|---|
| host | uptime, CPU/load, RAM/swap, temperatures, disk/inodes, SMART/NVMe, OOM, filesystem errors, network | disk/inodes forecast to exhaust; OOM; SMART critical; sustained thermal throttle |
| containers | desired/running/healthy, restart count, CPU/RAM/PIDs, log bytes, image digest | required service absent/unhealthy; restart loop; memory near limit; unbounded log growth |
| Madar | liveness/readiness/startup, error/latency, schema version, DB/Redis/storage, notification/calendar/parser/ingestion queues and dead letters, entitlements | readiness fails; schema mismatch; oldest queue age; dead letter; storage mismatch; billing authority unavailable |
| Briefedly | API/DB revision, worker heartbeat/lease, job state/age, imports/reports/retention/export/deletion, OAuth failures, Ollama latency/errors | no worker heartbeat; stuck lease; job age; OAuth error spike; retention/deletion overdue; Ollama unavailable |
| mail | service health, queue count/oldest age, SMTP failures, certificate age, volume | queue age/size; cert expiry; delivery failure; disk risk |
| backup | last complete success, age, checksum result, off-host/offline copy, restore-drill age | missing completion marker; overdue backup/copy/drill; verification failure |
| perimeter | Cloudflare tunnel, public endpoints, DNS/TLS, intended dual-stack ports, constrained Tailscale reachability | tunnel/down endpoint; DNS drift; certificate expiry; unexpected port |
| AI/Node B | model/checksum, GPU utilization/VRAM/temp, inference latency, queue depth/failures | gateway identity/auth failure; model missing; thermal/VRAM saturation; queue age |

## Readiness semantics

Liveness answers only whether the process event loop can respond. Startup remains false until local initialization completes. Readiness fails closed for required DB/schema, Redis where correctness depends on it, and required writable storage; optional external dependencies are reported as degraded unless the endpoint cannot safely serve admitted work. Queue-worker readiness is independent of API readiness and uses heartbeat plus oldest lease/job age. Backup freshness is an operational signal and should not make every API pod unready during an off-host outage.

Madar development migration 081 introduces a runtime-read-only `application_schema_state` contract. Development readiness now performs one authoritative version read instead of dozens of remote table probes. Production deployment order is migration first, then compatible application, with rollback to the previous image if the application preflight fails. Briefedly must report code version, Alembic revision compatibility, worker identity/heartbeat, and separately the configured Ollama dependency state; `/status` must not be static proof of dependency readiness.

## Alert operations

Every alert requires owner, severity, runbook, deduplication key, minimum duration, recovery notification, and quarterly review. Pages are reserved for customer-impacting or imminent data-loss conditions; tickets cover capacity and maintenance. Test every route without customer content. Retain metrics long enough to calculate approved SLOs and capacity trends, and retain security logs according to the lifecycle matrix rather than indefinitely.

## Verification gates

Validate exporter privilege, label cardinality, redaction, dashboard authentication, alert delivery and recovery, external failure-domain independence, simulated stopped worker, stale backup, low disk, tunnel outage, Ollama outage, and expired-certificate warning in staging. Production rollout requires a change plan and rollback; this document does not authorize it.
