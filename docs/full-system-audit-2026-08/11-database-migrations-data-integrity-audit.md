# Database, migrations, and data-integrity audit

## Madar PostgreSQL/Supabase

PostgreSQL 17.6, about 21 MiB, 63 public tables, nine active connections, no waiting lock at inspection. Migrations 069–080 and the expected current schema objects were present. Critical role grants were verified directly: `authenticated` has only `SELECT` on reviewed user/project/submission tables and no writes to assets, reservations, subscriptions, or storage accounting; `service_role` owns privileged access.

The application nevertheless has two bypass credentials: Supabase service role and a direct `postgres` superuser URL. Direct superuser access makes all RLS/grant work irrelevant after backend compromise and expands blast radius into Supabase auth/storage/internal schemas.

Production metadata: 10 storage accounts (~291 MB), 95 active storage objects, 95 committed/14 released reservations, one tenant subscription, 27 sent notification-outbox rows, 12 sent/three dead deliveries, four successful task-sync jobs, and 1,901 successful/three failed connection-sync jobs. No customer row content was selected.

Schema probing confirmed readiness-required columns exist. Intermittent schema readiness failure is caused by remote query timeout/concurrency, not missing migration. Autovacuum/dead-tuple health is currently small, but no DB monitoring or capacity alert exists.

Madar migrations are raw SQL duplicated under `database/migrations` and `supabase/migrations`; drift between trees is a recurring maintenance risk. Several historical migrations perform identity-specific data mutation, especially numeric-ID admin bootstrap. A rebuild-from-zero rehearsal is required because current-state equivalence does not prove historical reproducibility.

## Briefedly PostgreSQL

PostgreSQL 17.10, about 12 MiB, no current production customer rows or waiting locks. The configured application role is a superuser and also has CREATEDB, CREATEROLE, REPLICATION, and BYPASSRLS. This is a critical privilege failure.

Current source Alembic graph: 15 revisions, one root, one head `c8e5f1a3b647`. Development DB is at head. Production DB is at `d8c6b4a2f190`, missing sessions/OAuth nonces, tenant-ownership constraints, durable jobs, shared rate-limit buckets, and export artifacts. Running code matches the older schema rather than Git HEAD. The next deploy would attempt five migrations and then fail current Ollama validation unless preflighted.

The tenant-constraint migration is structurally strong: workspace-scoped unique keys plus composite foreign keys prevent cross-workspace connection/thread/message/report/source/job relationships. Upgrade SQL and lock behavior must be rehearsed on a restored copy before production.

## Redis

Madar prod/dev Redis are separate, loopback-published/internal-network services with no password/ACL/TLS. Loopback/Docker isolation is the primary control. Persistence is appropriate for rate-limit/ephemeral state rather than authoritative customer data. Production rate limiting fails closed if Redis is unavailable. Add ACL/auth if untrusted local processes or more tenants share the host.

## Transaction/concurrency assessment

- Madar publication, reservation booking, storage quota, AI tokens, notification claims, and calendar claims use database atomicity/locking and idempotency.
- Briefedly OAuth nonce use, job claim/lease, active-target deduplication, imports, and privacy jobs use database atomicity/constraints.
- High-risk check-then-act remains deployment-level: repository update, migration, container recreation, and health are not one transaction and have incomplete rollback.
