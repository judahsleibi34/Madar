# Current architecture

```text
Internet
  -> Cloudflare tunnel/TLS
     -> 127.0.0.1:3000  Nginx static React frontend
     -> 127.0.0.1:8001  FastAPI backend
          -> Supabase Auth/PostgREST/Storage
          -> external PostgreSQL 17 (operator-only direct URL)
          -> internal Redis (rate limits/readiness)
          -> parser worker (internal, no egress, private-upload RO mount)
          -> remote-ingestion worker (bounded egress, no application secrets)
          -> calendar-sync worker
          -> notification worker (outbox/delivery queue, web push/email)
```

Development is a separate Compose project on 3001/8002 with its own Redis and workers. It is not intended to be publicly exposed. Its live containers were created on August 14 while source moved to the August 23 commit; no code bind mount closes that gap.

## Publication path

`builder draft -> tenant-scoped asset registry -> validation -> locking publication RPC -> immutable published_schema/version -> website_settings.published_project_id -> exact hostname/path resolution -> authorized public schema -> React runtime`

Migration 072 and current code enforce one tenant settings row, unique subdomain/standard slug, exact project ownership, explicit homepage, unique pages/routes/forms, revision-aware atomic publication and publication-specific ETags. The site body/chrome endpoint reads the same published snapshot. The lightweight bootstrap endpoint is the exception: it reads mutable `website_settings.brand/logo_url`.

## Data and trust boundaries

- FastAPI uses the Supabase service role and therefore must enforce tenant context in every application query; RLS is enabled on all 64 public tables but service-role access is intentionally privileged.
- Public forms and reservations derive tenant/project identity from the bound published site, not client tenant IDs.
- Reservation creation uses a transaction-scoped advisory lock per tenant/project/block and an idempotency unique index.
- Uploads reserve quota atomically, stream to a random tenant-scoped local path, validate content, copy to private durable storage, register ownership and then commit accounting.
- Remote documents are fetched in a dedicated egress worker and parsed in a separate no-network worker.

## Health layers

- `/health/live`: process liveness.
- `/health/ready`: environment, Supabase database/auth, Redis, storage write probe, schema contract, admin-MFA flag, remote ingestion, workers and queue checks.
- Container worker probes: process HTTP heartbeat, not full provider/database success.
- Backup freshness is implemented but disabled in production.

Current external readiness returned `ready: true`, all enabled components `ok`, AI execution guard `disabled`, and backup freshness `disabled`. This green state does not cover SMTP delivery, full restore capability or deploy rollback.
