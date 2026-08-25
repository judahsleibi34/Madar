# Observability and truthful health

## Endpoint model

- `GET /health/live`: process liveness only.
- `GET /health/version`: release SHA, build timestamp and schema compatibility range; no secrets.
- `GET /health/ready`: core readiness for database, Redis, required storage/configuration and worker state. Optional dependencies are reported without automatically taking down core service.
- `GET /health/diagnostics`: protected with the existing metrics access policy; adds uncached readiness and channel delivery aggregates.

Readiness now reports deployment identity, schema compatibility, database, Redis, storage probes, workers, backup freshness/status, AI availability and notification channel states. It does not expose recipients, message bodies, keys or configuration values.

Provider-neutral scripts/systemd templates cover dead delivery, repeat deploy failure, stale/failed backup, disk/build-cache thresholds, reconciliation failure, Redis and worker failure. They log a safe event and may call an explicitly configured executable hook. No external alert provider or credential was invented.

## Residual operational work

Before launch, configure an approved receiver, test each alert end to end, set ownership/escalation windows, and establish external probes for liveness/public-site/login. A healthy process is not considered sufficient release validation.
