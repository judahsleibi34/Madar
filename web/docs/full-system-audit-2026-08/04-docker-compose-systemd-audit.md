# Docker, Compose, systemd, and deployment audit

## Container security

Madar's current Compose posture is strong: non-root UID 65534 for application workers, read-only roots, `cap_drop: ALL`, no-new-privileges, resource limits, healthchecks, bounded log rotation, loopback publishing, an internal parser network, and separated egress worker. Redis is digest-pinned and bounded. Writable paths are limited to intended uploads/charts/avatar storage.

Current Briefedly source has comparable hardening, but production runtime does not match it. The production backend/frontend have writable root filesystems, missing cap drops/no-new-privileges, the frontend runs as root, and the worker is absent. Development matches source more closely. This is operational drift, not merely a code-review concern.

Sleibi is read-only and capability-reduced; Nginx still starts as root to bind/drop privileges but has only the specific capabilities it needs. Mailcow necessarily uses broader privileges. Ofelia and the Mailcow Docker API proxy can reach the Docker socket; Portainer mounts it read-write. A compromised Docker-socket consumer is a host-root path even when the socket is mounted read-only.

Nginx Proxy Manager uses `latest`; the shared PostgreSQL uses floating `postgres:17`; Portainer/NPM/shared DB lack the hardening baseline used by the SaaS stacks. Their checked-in port declarations do not match runtime publishing, indicating undocumented manual drift.

## Compose separation

Madar prod/dev have distinct ports, Redis, networks, containers, and storage mounts. Briefedly prod/dev have distinct DB volumes/networks/ports. No dev hostname was found in the Cloudflare public set. However, environment files reuse some third-party/Ollama configuration, and both Briefedly environments target the same Tailscale Ollama endpoint. Production DB receives the entire backend env file, unnecessarily importing unrelated high-value secrets.

## systemd and timers

Madar and Sleibi auto-deploy timers run every two minutes. Briefedly's timer is disabled despite the unit being installed/preset. Cloudflare DDNS and tunnel services exist. Historical journals show repeated two-minute deploy/DDNS failures and cloudflared DNS/start failures without an external alert path.

Cloudflared runs as root with no meaningful systemd sandboxing. Its current config is root-only, but several historical config copies are 644. Older copies show HTTP origins for Madar and a Mailcow HTTPS origin with `noTLSVerify: true`; the exact current ingress file could not be read. Tunnel credential JSON is mode 400 and account certificate 600.

## Deployment reconstruction

### Madar

Timer → systemd service as `madar` → `/usr/local/sbin/madar-auto-deploy` → `/home/madar/docker_auto.sh` → fetch/compare main → hard reset to `origin/main` → build → Compose up → shallow root-URL checks. It rejects tracked dirt but not untracked files, performs no migration step, uses mutable local image builds, and does not gate on `/health/ready`. Rollback resets/rebuilds the old commit, so recovery depends on network/build reproducibility and schema compatibility.

### Briefedly

Installed but disabled timer → lock → require fully clean tree → fast-forward → build → start DB → `alembic upgrade head` → start stack → health. It is stronger than Madar on locking and cleanliness but leaves the repository/database advanced after migration failure and has no automatic old-image rollback. It also only reconciles when Git SHA changes, so runtime drift can persist indefinitely.

### Sleibi

Timer → lock/cleanliness/fast-forward → validation/build/restart/health → rollback to previous commit and rebuild on failure. This is the safest of the three, though it still grants repository content deployment authority through the Docker-equivalent `madar` user.

## Key cross-layer conclusions

- Strong checked-in Compose controls do not protect Briefedly because the running containers predate them.
- Loopback publishing successfully prevents SaaS direct-origin bypass.
- The `madar` account and Docker socket are the dominant host escalation boundary.
- Deployment correctness is not continuously reconciled; Git SHA equality is not equivalent to runtime/config/image equality.
