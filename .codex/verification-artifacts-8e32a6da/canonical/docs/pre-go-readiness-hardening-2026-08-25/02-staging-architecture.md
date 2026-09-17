# Staging architecture

## Topology

| Component | Binding / identity | Purpose |
| --- | --- | --- |
| Staging traffic proxy | frontend `127.0.0.1:13000`, backend `127.0.0.1:18001` | Durable blue/green target switch |
| PostgreSQL 17 | `127.0.0.1:15432` | Disposable production-shaped schema rehearsal |
| PostgREST | `127.0.0.1:15431` | Local provider-compatible data API |
| Staging gateway | `127.0.0.1:15430` | Local auth/provider fixture |
| Shared staging Redis | `127.0.0.1:15479` | Control-plane fixtures only |
| Blue slot | backend `8101`, frontend `3100` | Final active release |
| Green slot | backend `8201`, frontend `3200` | Retained inactive release core |

Each release slot has a backend, frontend, parser, remote-ingestion service, and slot-local Redis. Queue consumers run only for the active slot. Worker promotion is fail-safe: the candidate consumers remain stopped until traffic promotion, while rollback restores retained known-good workers before switching.

## Isolation

- All public-facing test ports bind to loopback.
- Compose project names, networks, volumes, runtime directories, storage, database, and Redis are staging-specific.
- External network access is disabled or intercepted in tests.
- Four empty obsolete `madar-green_*` Compose networks were verified to have zero containers and removed during final hygiene.

## Durable state

- Release state: `/tmp/madar-pre-go-stage/state/releases/state.json`
- Traffic target: `/tmp/madar-pre-go-stage/state/active-target.json`
- Alert sink: `/tmp/madar-pre-go-stage/state/alerts.jsonl`
- Backup evidence: `/tmp/madar-pre-go-stage/backups/madar-20260825T093714Z`

These are disposable staging artifacts, not production configuration.

## Final runtime

The active slot is blue at schema 83. Its release SHA is `9a3c67e6058768b71100349b89379b2b6052915a`; the retained green known-good predecessor is `10173d82`. The final backend image digest is `sha256:67ba38a4bfbe0387c7d100b6f68458d768627dfb93d85dbc716563768ca7c134` and the frontend digest is `sha256:0941db55d35246b4e78ecffedafb0ea46b5ed38a43cd9d042a90863db18d38e2`.
