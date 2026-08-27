# Notifications and workers

## Architecture

Database transaction helpers create outbox events alongside form/reservation/calendar changes. Resolution fans events out into durable `notification_deliveries`; workers claim with leases, retry retryable failures, mark terminal/dead outcomes and use deduplication keys. Push delivery revalidates active tenant membership, installation and subscription ownership. Provider endpoints are DNS/IP validated against SSRF. Logout/revocation removes push bindings.

Implemented preference pairs are:

| Category | Channels |
| --- | --- |
| `calendar` | in-app, push, email |
| `reservations` | in-app, push |
| `forms` | in-app, push |
| `general` | in-app, push |

Migration 080 enforces these pairs and unique `(tenant,user,category,channel)`. No override rows currently exist, so defaults are enabled. VAPID is configured, five active push subscriptions exist, and production has delivered 12 internal plus 3 web-push deliveries.

## Production blocker

SMTP variables are absent from production. All three email delivery attempts are dead with sanitized code `smtp_not_configured`; zero email deliveries succeeded. The worker and `/health/ready` still report healthy/ready because the queue dead threshold permits this and readiness does not require SMTP. This is real production evidence, not an optional-code observation.

Configure authenticated TLS SMTP, validate sender/domain policy, send controlled staging messages, exercise 4xx retry/5xx terminal behavior, and define alerting for any dead delivery. If email is intentionally not part of launch, prevent email rows from being enqueued and remove email claims from UI/docs until configured.

## Worker/isolation state

Parser and remote-ingestion workers are active, non-root and healthy. The parser has no egress and a read-only private-upload mount; the remote worker has egress but no application environment file, DB/OAuth/SMTP secrets or host mounts. Result/time/body limits exist across both hops. Calendar and notification workers are active with resource caps and rotated logs.

During a short August 23 upstream connectivity event, notification worker logs recorded 29 metrics, 28 delivery, 27 resolution, 27 reminder and 26 archive batch failures; all were `ConnectError` and stopped afterward. Process probes stayed healthy. Alerts and dependency-aware worker health are required.

G11 is **FAIL (High)** until the channel contract and readiness state match actual deliverability.
