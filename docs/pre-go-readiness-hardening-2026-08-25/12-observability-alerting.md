# Observability and alerting

## Health model

- `/health/live` is process liveness.
- `/health/ready` is promotion-grade readiness for database, Redis, storage, release/schema, and required workers.
- `/health/version` reports immutable release identity.
- Protected diagnostics and metrics expose deeper channel, queue, backup, deployment, deletion, and storage state; unauthorized requests receive 404.

## End-to-end alert harness

The provider-neutral staging sink recorded 12 distinct alert classes in a mode-0600 JSONL file:

`backup_stale`, `bad_sha_suppressed`, `database_readiness_failure`, `dead_notification_delivery`, `deletion_manual_intervention`, `deployment_failure`, `disk_threshold`, `docker_build_cache_threshold`, `redis_failure`, `rollback_failure`, `storage_reconciliation_failure`, and `worker_failure`.

The capacity checker independently delivered a real `swap_threshold` warning at 83% use. Alerts contain release/component/error class metadata and no tokens or customer content.

## External-like probes

The loopback probe runs outside application containers and checks frontend, API liveness/readiness/version, and a synthetic public site. A transport timeout is reported as a status-zero failed observation rather than crashing or being omitted.

Request IDs, tenant-safe identifiers, worker failures, release records, and structured health allow diagnosis of login, publication, reservation, notification, deletion, and deployment incidents. Current response procedures are in `18-operational-runbooks.md`.
