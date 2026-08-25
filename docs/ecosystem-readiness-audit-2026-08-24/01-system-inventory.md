# System inventory

## Source state

| Checkout | Branch | HEAD | Upstream/divergence | Worktree |
| --- | --- | --- | --- | --- |
| `/home/madar/saas/Madar` | `main` | `0eaa9edd297d2fd6618d50ae5dfc4b08c94ba1df` | `origin/main`, no divergence observed | Clean tracked tree |
| `/home/madar/saas/Madar-dev` | `builder-backend` | same | `origin/builder-backend`, no divergence; local `main` also same | Clean tracked tree before reports |

Both remotes are the same GitHub repository. The most recent commit is merge `0eaa9ed`; the preceding history includes the monorepo-path move. Production contains no unexpected tracked edits. Ignored operational content includes `.env`, root `backend/` durable storage, and generated dependencies/build output. Development also has ignored legacy root `backend/`, `frontend/`, `scripts/`, mobile dependencies and build output.

## Running Madar topology

| Environment | Service | Exposure | Runtime status |
| --- | --- | --- | --- |
| Production | `madar-frontend` | `127.0.0.1:3000 -> 8080` | healthy |
| Production | `madar-backend` | `127.0.0.1:8001 -> 8000` | healthy |
| Production | `madar-redis` | `127.0.0.1:6379` | healthy |
| Production | parser, remote-ingestion, calendar-sync, notification workers | internal Docker networks only | healthy |
| Development | frontend/backend | `127.0.0.1:3001`, `127.0.0.1:8002` | healthy but stale images |
| Development | Redis/workers | internal/loopback as Compose defines | healthy but stale images |

`ss -ltnp` confirmed that 3000, 3001, 8001, 8002 and 6379 bind only to loopback. PostgreSQL is external Supabase PostgreSQL 17. It is not a local container. Production runtime containers explicitly receive an empty `SUPABASE_DB_URL`; application database access uses Supabase HTTP credentials. Direct PostgreSQL credentials remain operator-only.

## Services and schedules

- `madar-auto-deploy.timer`: active, every two minutes, persistent.
- `madar-auto-deploy.service`: oneshot as user/group `madar`; root `ExecStartPre` runs `web/scripts/prepare_production_storage.sh`.
- `cloudflared`: active. Journal evidence shows the Madar API origin at loopback 8001; safe external HTTPS requests to frontend/API succeeded.
- No Madar backup systemd timer or user cron entry exists.
- No Nginx host service is required for Madar; Nginx runs inside the frontend container.

## Storage and backups

| Host path | Purpose | Size | Mode/owner |
| --- | --- | ---: | --- |
| `Madar/backend/uploads` | public builder assets | 63 MiB | dir `0755`, files observed `0644`, UID/GID 65534 |
| `Madar/backend/private_uploads` | datasets | 156 KiB | same |
| `Madar/backend/private_generated_charts` | private charts | 18 MiB | same |
| `Madar/backend/avatar_uploads` | avatar mirror | 5.2 MiB | same |
| `/home/madar/backups/madar-20260823T111402Z` | latest complete local backup | 87 MiB | directory `0700`, files `0600` |

The latest backup has a completion marker, a readable custom-format PostgreSQL archive with 1,059 TOC entries, and 92/92 valid SHA-256 checksums. It includes 68 builder assets, 3 private uploads, 8 generated artifacts and 10 avatars.

## Host state

- Uptime: approximately 3 days 17 hours during collection.
- Memory: 7.2 GiB total, 3.2 GiB available; swap 4 GiB total, 1.8 GiB used at final collection.
- Root filesystem: 456 GiB total, 120 GiB used, 318 GiB available; inode use 14%.
- Failed systemd units: none at collection.
- Docker: images 26.73 GiB; build cache 81.21 GiB, of which 65.89 GiB was reported reclaimable. Madar backup root totaled 365 MiB; journals totaled 655.4 MiB.
- Production Madar containers consume roughly 560 MiB combined at idle. Resource caps exist on every service.

Only Madar-specific resources were enumerated. Host-wide Docker totals were used solely for shared capacity risk; unrelated containers were not audited.
