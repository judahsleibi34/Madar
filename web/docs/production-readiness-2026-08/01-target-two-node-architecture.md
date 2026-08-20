# Target two-node architecture

## Constraints

Node A is the current single failure domain and runs SaaS, Mailcow, databases, builds, tunnels, and root-equivalent management surfaces. Node B is known only as a 14th-generation Intel Core system with RTX 4060, 16 GB DDR4, and a 500 GB SSD. Exact CPU, VRAM, NIC, disk, firmware, thermal, and power facts remain `BLOCKED BY HARDWARE` until commissioning.

## Model comparison

| Model | Advantages | Risks and limits | Decision |
|---|---|---|---|
| A. Node A primary SaaS + mail; Node B AI/staging/restore | minimal production movement; GPU isolated from Node A | preserves the largest blast radius and Node A memory/build pressure; mail and SaaS still fail together | useful commissioning state, not target |
| B. Node B primary SaaS/worker; Node A mail/legacy | isolates privileged Mailcow from SaaS; more CPU/RAM; eliminates builds from Node A | AI and customer apps share Node B; one SSD; migration risk; exact hardware unknown | viable after commissioning and P0 |
| C. Staged hybrid | Node B begins as AI/staging/monitoring/restore; after certification, SaaS moves to B and Node A becomes mail-focused | more phases and temporary duplication; requires disciplined identity and backup handling | **recommended** |

## Recommended target

```text
Internet
  |-- Cloudflare application hostnames -> tunnel on Node B -> SaaS frontends/APIs
  |-- SMTP/IMAP DNS and NAT -----------> Node A -> Mailcow
  |
router -> managed-capable switch
          |-- Node A: Mailcow, mail storage, mail-specific tunnel/edge if required
          |-- Node B: Madar/Briefedly app + workers, Briefedly PostgreSQL/Redis,
                      authenticated HTTPS Ollama gateway + localhost Ollama,
                      monitoring collector and controlled staging

rotating encrypted drives: independent of both nodes; one disconnected/off-site
external service: uptime and backup-failure notification independent of both nodes
```

### Node A target role

- Mailcow and only its justified mail ingress.
- Mail-focused monitoring exporters and backup source.
- No general developer build workload.
- Portainer/NPM/shared PostgreSQL retained only until consumers are proven and a separate decommission is approved.
- Not the only recovery copy and not assumed to be a hot standby.

### Node B target role

- Immutable Madar and Briefedly frontend/API/worker images.
- Local Briefedly PostgreSQL and its bounded backup/PITR lane.
- Ollama bound to loopback/internal network behind authenticated HTTPS; GPU access granted only to the model service.
- Monitoring collector with authenticated dashboards; external uptime remains outside both nodes.
- Staging and restore drills use explicit maintenance/resource windows and cannot share production credentials or volumes.

## Security boundaries

- Node A and B are mutually untrusted peers on the LAN. Host firewalls and Tailscale grants allow named flows only.
- Mailcow compromise must not yield Node B SSH, Docker, database, backup-delete, or Ollama administration.
- Ollama accepts only gateway traffic. Backend/worker authenticate to the gateway; Tailscale identity is an additional boundary, not the bearer-token replacement.
- Staging uses separate databases, OAuth projects, secrets, networks, storage, cookies, and hostnames.
- Backup credentials create new encrypted generations but should not delete retained history. Restore credentials are offline/break-glass.

## Capacity placement

Node A currently shows meaningful swap use and should stop doing frequent application builds. Node B's 16 GB is plausible for SaaS plus one bounded model workload, but not proven. Commissioning must measure idle OS/container use, model VRAM/RAM, concurrent inference, thermals, disk latency, and failure behavior. If ordinary SaaS latency cannot remain within SLO during model saturation, AI must be concurrency-capped or moved to a third/hosted provider; customer API must win resource contention.

## Migration stages

1. Hardware/firmware/burn-in and clean OS.
2. Identities, SSH, firewall, Tailscale grants, encrypted local filesystem, monitoring.
3. Staging-only immutable deployment and isolated restore drills.
4. Authenticated HTTPS Ollama gateway and benchmark certification.
5. P0 closure on Node A without moving workloads.
6. Backup of known-good P0 state; rehearse Node B migration with copied non-live data.
7. Move stateless SaaS services, then Briefedly DB in a separate maintenance boundary.
8. Switch Cloudflare application ingress after local and overlay smoke tests; retain known-good Node A images only for the defined rollback window.
9. After observation, remove SaaS secrets/data from Node A and disposition legacy services.

No step is authorized merely by this design.
