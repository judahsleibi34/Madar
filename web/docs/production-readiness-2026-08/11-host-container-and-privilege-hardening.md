# Host, container, privilege, and legacy-service hardening

Status: **REQUIRES MAINTENANCE**. This phase changed no host security control.

## Target identities

| Identity | Purpose | Must not possess |
|---|---|---|
| named human operator | SSH and audited sudo for approved operations | shared credentials; routine app secrets; automatic Docker-root access |
| constrained deployer | fetch verified digest, render non-secret config, orchestrate only owned projects | interactive login, broad sudo, Docker API for unrelated stacks, backup keys |
| per-app runtime | execute one service with minimal files/network/secrets | Docker socket, migration/operator credentials, other-app secrets |
| migrator | bounded schema migration during approved deploy | application runtime use, role/database creation, superuser |
| backup identity | read defined recovery sources and append/create remote generations | application mutation, remote historical deletion where storage permits immutability |
| monitoring identity | read exported metrics/health only | container control, customer content, secrets |
| root break-glass | encrypted/offline emergency access with ceremony and audit | routine deployment or daily administration |

Docker group membership is root-equivalent. Prefer rootless Docker for isolated application workloads if volume/network/NVIDIA compatibility is proven. Otherwise expose a narrowly controlled root-owned deployment wrapper or separate Docker context; never proxy an unrestricted Docker socket to a deployer.

## Current high-risk boundaries

- Portainer has a read-write Docker socket and therefore effective host root. Retain only with documented owner/use, Tailscale-restricted authenticated access, MFA if supported, pinned version, bounded logs, and a plan to remove it if CLI/runbooks replace its purpose.
- Mailcow Ofelia and dockerapi containers consume the socket read-only. Read-only Docker API still reveals high-value metadata and may expose implementation vulnerabilities; retain only because Mailcow requires them, pin images, isolate network, and track upstream guidance.
- Nginx Proxy Manager binds public 80/443 and a Tailscale-only management port. Determine every current hostname and certificate consumer before retaining, migrating, or decommissioning.
- The shared PostgreSQL project under `/home/madar/saas/database` binds only through Tailscale in current evidence. Inventory databases/roles/clients before any disposition.
- Mailcow's dirty repository and local configuration are authoritative undocumented state until diff-backed recovery artifacts exist. Never reset it.

## Container baseline

For new/reconciled services: immutable digest; non-root UID/GID; `read_only: true` where feasible; `cap_drop: [ALL]`; `security_opt: [no-new-privileges:true]`; default seccomp/AppArmor; explicit writable mounts/tmpfs; PIDs, CPU and memory limits; healthcheck; bounded local log rotation; internal networks; loopback or Tailscale-only publication; no host PID/network/devices; and no Docker socket. Exceptions require a threat model and owner.

## Host hardening execution gate

Collect effective state read-only first:

```bash
sudo sshd -T
sudo ufw status verbose
sudo nft list ruleset
sudo iptables-save
sudo ip6tables-save
sudo iptables -S DOCKER-USER
sudo ss -lntup
sudo sysctl net.ipv4.ip_forward net.ipv6.conf.all.forwarding
```

Run an authorized external IPv4 and IPv6 TCP/UDP scan from outside the site and reconcile every result to the socket/container/tunnel/NAT inventory. Do not place secrets in command arguments or captured output.

Target allowlist is default-deny inbound: keys-only SSH from explicit administrative Tailscale identities; Cloudflare tunnels make outbound connections; direct SaaS origins stay loopback; Node-to-node DB/backup/monitoring/Ollama ports are identity- and host-filtered; public Mailcow ports are only those required by the approved client/server design. IPv4, IPv6, forwarding, Docker NAT, and `DOCKER-USER` must agree.

Apply SSH/firewall changes in a maintenance window with console/fallback access, two concurrent authenticated sessions, syntax validation, a timed rollback, one bounded rule at a time, and an external re-scan. Never close the control session until a fresh session succeeds.

## Legacy disposition register

| Service | Current purpose/exposure | Decision gate |
|---|---|---|
| Portainer | container administration; Tailscale 9443; Docker socket rw | **migrate/decommission preferred** after ownership/workflow proof |
| Nginx Proxy Manager | public 80/443; Tailscale management; certificate/proxy state | **retain temporarily**, map every consumer, then reduce or replace |
| shared PostgreSQL | legacy/shared DB on Tailscale 5432 | **investigate** clients, data, backups and ownership before decision |
| dormant images/networks/volumes | unknown until dependency-labelled inventory | quarantine from new designs; remove only after two-step owner approval and recoverability proof |

Each final decision records business owner, authentication, image/digest, bind, persistent data, backup/restore, dependency queries and last use. No production service was removed here.
