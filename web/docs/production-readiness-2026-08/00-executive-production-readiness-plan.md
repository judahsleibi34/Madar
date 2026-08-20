# Executive production-readiness plan

Assessment date: 2026-08-19 UTC. This package describes the system that is live and the work required to launch safely. It is not an approval to deploy.

## Current decision

**PROGRAM STATUS: READY FOR NEXT PHASE.** The planning and bounded development phase is executable; the live sensitive-production posture remains **NO-GO**.

The decisive live blockers remain unchanged: exposed credentials are not revoked, Madar runtime still receives direct privileged PostgreSQL material, Briefedly runtime still uses a superuser and an old five-revision-behind stack without a worker, no physically separate encrypted recovery copy exists, and the real authenticated Ollama route is unavailable. Node B has been purchased but is not commissioned and is not yet evidence.

## Current live evidence

- Node A: four logical i3-6100 CPUs, 7.2 GiB RAM, 4 GiB swap with 1.6 GiB used, one 456 GiB root filesystem at 27%, and 43 running containers.
- Madar is healthy at the Docker liveness level, but `/health/ready` returned 503 with schema reported unavailable while the captured other components were healthy.
- Briefedly production is at Alembic `d8c6b4a2f190`, has no worker, reports `priorify-backend`, and its runtime role still has SUPERUSER, CREATEDB, CREATEROLE, REPLICATION, and BYPASSRLS.
- Latest local recovery points are dated 2026-08-18. They remain on Node A. Mailcow has no coherent recovery point.
- Portainer has a read-write Docker socket. Mailcow Ofelia and Docker API proxy have read-only socket mounts that remain host-sensitive. NPM, Portainer, and the shared PostgreSQL use floating tags.
- Mail ports 110, 143, 8080, and 8443 remain dual-stack listeners pending client and perimeter evidence.

## Recommended two-node outcome

1. Commission Node B first as AI/Ollama gateway, staging, monitoring peer, and restore-validation target.
2. Commission two encrypted rotating backup drives; keep one disconnected and preferably off-site.
3. Validate the real authenticated HTTPS Ollama path.
4. Close P0 on Node A in its own maintenance window.
5. Only then migrate immutable SaaS application/worker services and Briefedly PostgreSQL to Node B. Leave Node A mail-focused and remove legacy services only after dependency proof.

This sequence deliberately avoids combining credential rotation, five migrations, new hardware, network changes, and workload migration into one rollback boundary.

## Development work in this phase

- Madar backup format 2 publishes only a checksum-verified recovery set with a completion record; a failed run never occupies the final recovery path.
- Madar migration 081 adds a runtime-read-only schema contract, and readiness uses one authoritative query instead of dozens of timing-sensitive probes.
- Briefedly source now identifies itself as `briefedly-backend` rather than the stale product name.
- This package defines commissioning, isolation, Google/Gmail verification, backup/DR, monitoring, hardening, CI/CD, privacy, performance, ASVS, incident response, and launch gates.

## Launch posture

| Target | Current decision | Hardest blockers |
|---|---|---|
| Madar controlled beta | NO-GO for expansion | P0 credentials/recovery; readiness migration not live; basic alerts absent |
| Madar paying | NO-GO | P0 plus privacy, deployment, restore, monitoring, tenant certification |
| Madar sensitive | NO-GO | paying gates plus hostile-content isolation and independent penetration test |
| Briefedly development | GO, synthetic data only | no real Gmail/Ollama claim |
| Briefedly private Gmail beta | NO-GO | P0, restricted-scope verification/CASA, worker/schema/runtime, recovery |
| Briefedly paying Gmail | NO-GO | beta gates plus operational SLO/privacy/IR and external assessment |
| Server host | NO-GO for sensitive expansion | privilege separation, perimeter proof, backup, monitoring, Mailcow DR |

The source of truth for closure is `20-master-findings-and-dependency-register.md`; documents and code do not turn a status green without the listed verification evidence.
