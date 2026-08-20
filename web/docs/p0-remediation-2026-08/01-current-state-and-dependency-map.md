# Current state and dependency map

## Repository baseline

| Repository | Branch | HEAD at start | Initial state |
|---|---|---|---|
| `/home/madar/saas/Madar` | `main` | `22e7c94c46ab0fe2df7c23e681495991ecfc1a3d` | clean |
| `/home/madar/saas/Madar-dev` | `builder-backend` | `22e7c94c46ab0fe2df7c23e681495991ecfc1a3d` | audit package untracked |
| `/home/madar/saas/Briefedly` | `main` | `7c5adaccac61008a8006b36180ed5fdccf72e62a` | clean |
| `/home/madar/saas/Briefedly-dev` | `Saliba-Branch` | `7c5adaccac61008a8006b36180ed5fdccf72e62a` | clean |
| `/home/madar/saas/Sleibi` | `main` | `d0f1e535ce3a3d9f68301c6f378fd2386b674e38` | clean |
| Mailcow | `master` | `2ac4b1deaee50e1284d644cecc16dcb0b37e67e2` | pre-existing modified/untracked configuration; preserved |

## Madar direct database dependency

Runtime API, notification worker, and calendar worker receive shared application environment today. Static call-graph review found no runtime Python consumer of the direct PostgreSQL URL. Normal runtime data access uses Supabase/PostgREST with anon/service-role credentials. Direct PostgreSQL is consumed only by operator tooling:

- database backup and restore;
- RLS/grant verification;
- website-settings tenant verification;
- migration and rehearsal commands.

The parser and remote-ingestion workers do not need or receive the direct DB URL or Supabase service-role credential. The proposed production model removes direct PostgreSQL from API and runtime workers and retains an operator-only credential for reviewed backup/migration/verification operations.

Madar readiness does not require a direct PostgreSQL login; it validates the application’s Supabase-facing dependencies and storage configuration.

## Madar credential flow

```text
Browser -> public/anon Supabase interface
Backend/API -> Supabase service role -> PostgREST/RPC/Auth/Storage
Notification/calendar workers -> service role -> application RPC/tables
Operator backup/migration tooling -> direct PostgreSQL operator credential
Parser/remote ingestion -> no DB/admin credential
```

Affected direct-URL key names include `SUPABASE_DB_URL` and operator aliases used by backup/restore tooling. Production and historical environment copies must be updated or securely retired during rotation.

## Briefedly current production

- Live Alembic revision: `d8c6b4a2f190`.
- Source head: `c8e5f1a3b647` (five revisions ahead).
- Live runtime DB role: `briefedly_app`.
- Current role flags: superuser, create-database, create-role, replication, and bypass-RLS are all enabled.
- The same role owns the database, public schema, and application tables.
- No production worker is running.
- Production backend/frontend containers were created on 2026-08-02 and are older than current source.
- Live Ollama configuration is unauthenticated HTTP to a Tailscale address and is rejected by current production validation.
- Production contains real data. Aggregate-only verification found 2 users, 2 workspaces, 2 connections, 141 threads, 173 messages, 5 import jobs, 2 reports, and 4 report sources.
- Eight checked composite workspace-ownership mismatch aggregates were zero.

## Five pending Briefedly revisions

The isolated rehearsal covered the revision chain from `d8c6b4a2f190` to `c8e5f1a3b647`, including:

- durable background jobs and leases;
- session and OAuth nonce persistence;
- shared rate-limit buckets;
- private export artifacts/privacy job support;
- composite workspace ownership constraints and supporting integrity changes.

The composite constraints accepted current aggregate-verified production relationships and rejected a synthetic cross-workspace child row.

## External dependencies blocking production

```text
Off-host backup provider/credential: absent
Authenticated HTTPS Ollama gateway/token: absent
Supabase rotation authority: not available locally
Mailcow maintenance window: not approved/scheduled
```

## Additional credential-bearing host database

`/home/madar/saas/database` defines a separate PostgreSQL instance bound to a Tailscale address. Its administrator role is a full superuser; the database is currently empty and no application consumer was identified. Its hardcoded password was accidentally rendered during this remediation and must be rotated. This instance is separate from Madar’s Supabase database and Briefedly’s database.
