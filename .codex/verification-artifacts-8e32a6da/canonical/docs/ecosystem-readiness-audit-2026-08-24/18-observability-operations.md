# Observability and operations

## Existing capability

Backend and workers emit structured JSON events with timestamps, levels, sanitized error types and tenant/user/object identifiers where relevant. HTTP responses carry `X-Request-ID`; safe external probes confirmed it on errors and readiness. Security events and many admin/publish/member changes are written to audit logs. Docker logs rotate. Deployment events are in systemd journal. Health separates process liveness from a broader backend readiness endpoint.

An operator can usually locate:

- login failures through auth/security events;
- publish failures through builder events plus request ID;
- reservation/form notification production through outbox/delivery states;
- deployment failure through the auto-deploy journal.

## Gaps

- No external monitor/alert destination, dashboard or on-call response evidence was found.
- Readiness is false-green for backup (`disabled`) and email (three dead, SMTP absent). Worker process health was green during repeated upstream `ConnectError` batches.
- Queue readiness uses configurable thresholds, so a small number of permanently dead messages can coexist with ready without a channel-specific alarm.
- The public readiness endpoint exposes component names/status but no release SHA/image identity.
- Deployment logs are detailed but do not create a durable release record with target/prior image, schema compatibility, approver and rollback result.
- Tenant-level support diagnostics are dispersed across application, worker, DB and deploy logs. There is no documented query/runbook for the five example incidents.
- No evidence of retention/PII review for application/audit logs or notification payload history.

## Required operational views

Build dashboards/alerts for login/auth provider errors, publish latency/failures, reservation/form error rates, queue depth/oldest/dead by channel, worker last successful dependency poll, backup age/off-host age, schema/release identity, disk/swap/build cache, tunnel 5xx and deployment state. Provide request-ID and tenant-ID search without exposing payload PII. Add tested runbooks for login outage, one-tenant publish failure, double-book report, email stop and failed release.

G19 is **FAIL** for unattended customer production, despite good structured logging foundations.
