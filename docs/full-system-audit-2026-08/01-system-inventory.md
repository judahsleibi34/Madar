# System inventory and baseline

## Host

Ubuntu 26.04 LTS, Linux 7.0.0-29, x86_64, four Intel i3-6100 logical CPUs, 7.2 GiB RAM, 4 GiB swap. Root filesystem is ext4, 456 GiB total, 116 GiB used (27%), 321 GiB free; inode use 13%. `/tmp` is tmpfs with `nosuid,nodev` but not `noexec`. Journald occupies about 575 MiB. No failed systemd unit was observed at the audit point.

## Git baseline

| Environment | Path | Branch / upstream | HEAD | State |
|---|---|---|---|---|
| Madar production | `/home/madar/saas/Madar` | `main` / `origin/main` | `22e7c94c46ab0fe2df7c23e681495991ecfc1a3d` | clean; recorded refs 0/0 |
| Madar development | `/home/madar/saas/Madar-dev` | `builder-backend` / none | same | clean before reports; report files become untracked |
| Briefedly production | `/home/madar/saas/Briefedly` | `main` / `origin/main` | `7c5adaccac61008a8006b36180ed5fdccf72e62a` | clean; recorded refs 0/0 |
| Briefedly development | `/home/madar/saas/Briefedly-dev` | `Saliba-Branch` / `origin/Saliba-Branch` | same | clean |
| Sleibi | `/home/madar/saas/Sleibi` | `main` / `origin/main` | `d0f1e535ce3a3d9f68301c6f378fd2386b674e38` | clean |
| Mailcow | `/home/madar/mail/mailcow-dockerized` | `master` / `origin/master` | `2ac4b1deaee50e1284d644cecc16dcb0b37e67e2` | dirty before audit |

Mailcow pre-existing changes: four tracked files modified (example certificate/key, Dovecot password verifier, Postfix main configuration) and two untracked configuration backups. No submodules or Git LFS configuration was found in the primary repositories. Remote divergence is against existing local remote refs; no `git fetch` was performed.

## Running application inventory

- Madar production: frontend 3000, API 8001, Redis 6379, notification worker, calendar worker, parser worker, remote-ingestion worker.
- Madar development: frontend 3001, API 8002 and separate Redis/workers.
- Briefedly production: frontend 3010, API 8010, PostgreSQL; **no worker**.
- Briefedly development: frontend 3011, API 8011, PostgreSQL, worker.
- Sleibi: Nginx static service on loopback 3020.
- Mailcow: 18 containers including Nginx, Postfix, Dovecot, Rspamd, SOGo, MariaDB, Redis, Unbound, ClamAV, netfilter, Docker API proxy, and scheduler.
- Other: Portainer, Nginx Proxy Manager, and a shared PostgreSQL 17 container.

There were 43 running containers. Compose projects include `Madar`, `madar_dev`, Briefedly production/development, `Sleibi`, `database`, `nginx`, and Mailcow. No Ollama container runs on this host; both Briefedly environments target a Tailscale address on port 11434.

## Environment classification

| Path/project | Classification | Evidence |
|---|---|---|
| Madar | Production | systemd auto-deploy, public tunnel, production environment, ports 3000/8001 |
| Madar-dev | Development | distinct branch, ports, containers, storage and Redis |
| Briefedly | Production but stale | public tunnel and production DB; runtime predates current Compose/source |
| Briefedly-dev | Development | dev branch, ports, DB and worker |
| Sleibi | Production static | public hostname and independent deploy timer |
| shared `database` / NPM / Portainer | Unknown/legacy infrastructure | running or configured but not documented as an active application dependency |

## Storage consumers

Root has healthy immediate headroom, but Docker accounts for the largest avoidable growth: 27.87 GiB images and 79.29 GiB build cache, of which about 63.28 GiB is reclaimable. Volumes total about 1 GiB. Other material stores are Supabase-hosted Madar PostgreSQL, local Briefedly/Postgres volumes, Mailcow volumes, local upload bind mounts, journald, local backups, and repository build dependencies.

## External dependencies

- Cloudflare DNS/proxy/tunnel; local `cloudflared` runs as root.
- Supabase Auth/PostgreSQL/Storage for Madar.
- Google OAuth, Gmail API, and Google Calendar.
- Microsoft calendar support in Madar code.
- SMTP/Web Push.
- Ollama over Tailscale for Briefedly.
- AI providers in Madar code/config (Gemini/OpenAI/DeepSeek), with generated-code execution disabled in production.
