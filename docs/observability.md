# Madar observability

Madar exposes three separate operational signals:

- `GET /health/live` proves that the API process can answer HTTP.
- `GET /health/ready` verifies required dependencies and returns `status: ready` or `status: degraded`.
- `GET /health/metrics` emits Prometheus text. When `METRICS_TOKEN` is set it requires `Authorization: Bearer <token>`; without a token it is loopback-only.

The metrics endpoint uses route templates, HTTP method, and status class only. It also reports bounded queue counts, expired-asset cleanup backlog, active quota reservations, disk usage, backup age, and parser/AI guard state. Operational database counts are capped at 5,000 per scrape. Do not add tenant IDs, user IDs, email addresses, filenames, subdomains, raw URLs, or exception messages as labels. JSON application logs use a validated correlation ID and an allowlist of operational fields; arbitrary log messages are redacted.

Production/test logging keeps `httpx` and `httpcore` at `WARNING`. Successful
`/health/live` access entries are filtered, while failed health checks remain
visible. Access logging removes every query string before formatting, including
calendar OAuth callbacks. Uvicorn startup/error output, security events,
correlation IDs, worker failures, and the durable database audit trail remain
enabled. Unexpected application exceptions return a sanitized JSON 500 with an
`X-Request-ID`; internal exception types are logged once without bodies, query
values, cookies, tokens, or authorization headers.

## Required production configuration

Set `NOTIFICATION_WORKER_REQUIRED=true`, `NOTIFICATION_WORKER_ENABLED=true`, and an internal-only `NOTIFICATION_WORKER_HEALTH_URL` when the worker is deployed. Set `BACKUP_FRESHNESS_REQUIRED=true`, `BACKUP_FRESHNESS_MARKER` to the marker written by the verified backup job, and choose an operator-approved `BACKUP_MAX_AGE_SECONDS`. Protect metrics with a randomly generated `METRICS_TOKEN` and keep it out of images and source control.

## Initial alert thresholds

These defaults are conservative starting points and require operator approval against measured traffic:

- API readiness is degraded for two consecutive probes: page the operator.
- `madar_http_errors_total`: alert on a sustained five-minute increase, grouped by route.
- notification queue depth over `NOTIFICATION_QUEUE_MAX_DEPTH=1000`: urgent investigation.
- oldest notification over `NOTIFICATION_QUEUE_MAX_AGE_SECONDS=900`: urgent investigation.
- any dead notification (`NOTIFICATION_QUEUE_MAX_DEAD=0`): investigate the channel and configuration; never delete it merely to clear the alert.
- free space below `STORAGE_DISK_FREE_FLOOR_BYTES=2147483648`: readiness fails and uploads are refused.
- backup marker older than `BACKUP_MAX_AGE_SECONDS=129600`: readiness fails when backup freshness is required.

Scrape the API metrics endpoint and the notification worker's internal `/metrics` endpoint from the private service network. No paid telemetry provider is required. An external Prometheus-compatible collector and alert dispatcher remain deployment responsibilities.
