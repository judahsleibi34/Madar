# Full-system audit executive summary

Audit window: 2026-08-18 UTC
Scope: Madar production/development, Briefedly production/development, Sleibi, Mailcow, host OS, Docker, systemd, databases, networking, Cloudflare-facing endpoints, backups, deployment, privacy, and recovery.
Method: read-only static review, runtime metadata inspection, aggregate-only read-only SQL, public DNS/TLS/HTTP probes, and repository-local tests. No load test, customer mutation, migration, restart, rebuild, or deployment was performed.

## Overall posture

- **Security posture: NO-GO for sensitive production use.** Strong application-level controls exist, especially in current Madar tenant/publication code and current Briefedly workspace/OAuth code, but three confirmed critical credential/database trust failures dominate the result.
- **Production readiness: 4.0/10.** Madar is technically closer to a controlled beta than Briefedly, but neither is ready for sensitive paying customers on this host.
- **Reliability posture: weak.** Backups are manual/local/stale, restore has not been proven, external alerting is absent, and Briefedly production lacks its worker and current schema.
- **Privacy posture: insufficient for real sensitive data.** Data inventories and some lifecycle code exist, but effective deletion/retention depends on workers and operator processes that are not deployed or proven.

Finding counts: **3 Critical, 9 High, 15 Medium, 7 Low**.

## Top ten risks

1. Madar's backend receives a direct PostgreSQL superuser connection string in addition to its service-role credential.
2. Briefedly's application database role is a PostgreSQL superuser with role/database/replication/bypass-RLS powers.
3. During this audit, several live credential values were unintentionally rendered in the controlled tool transcript; all affected credentials require incident handling and rotation.
4. There is no scheduled, encrypted, off-host, coherently restorable backup covering database, assets, mail, configuration, and secrets.
5. Briefedly production is an old, unhardened runtime: the worker is absent and the database is behind five migrations.
6. Current Briefedly source rejects the configured production Ollama HTTP/Tailscale URL; the next deployment is likely to fail at startup.
7. Briefedly's database container receives unrelated application, encryption, Gmail, and AI secrets.
8. The `madar` host identity combines interactive access, sudo, Docker root-equivalence, source ownership, and deployment authority.
9. Madar deployment does not run migrations, reject untracked files, or gate success on readiness; rollback rebuilds rather than selecting an immutable known-good image.
10. There is no external monitoring/alert pipeline for availability, disk, workers, queues, backups, certificates, or tunnels.

## Top ten strengths

1. Current Madar critical-table grants were verified: authenticated users retain read access where needed but not direct privileged writes.
2. Madar tenant/project/publication lookups are consistently tenant-qualified and duplicate-aware in the reviewed routes.
3. Madar publication activation is revision-aware and database-atomic; cache/ETag identity includes publication context.
4. Madar request-size, multipart, rate-limit, CSRF, exact-origin CORS, cookie, and log-redaction controls are substantial.
5. Madar upload validation rejects SVG/HTML/script content, checks document structure, reserves quota atomically, and isolates document parsing.
6. Briefedly's current code has durable DB sessions, CSRF, workspace-scoped dependencies, and composite tenant ownership constraints.
7. Briefedly Gmail provider operations require owner/admin authority; OAuth state is expiring, hashed, durable, and one-time.
8. Briefedly encrypts refresh tokens and treats imported email as hostile input in structured evidence-backed AI prompts.
9. Production application ports bind to loopback; Cloudflare fronts the SaaS sites, reducing direct-origin bypass.
10. Sleibi is genuinely static, has no backend/API calls/payment flow, passes its source validation, and has a restrictive CSP.

## Direct answers

- **Is Madar safe for real customers?** Not yet. **CONDITIONAL GO** only for a tightly limited, non-sensitive beta after all P0 credential and backup actions, with explicit risk acceptance. **NO-GO** for sensitive business data now.
- **Is Briefedly safe for private business email?** **NO-GO.** Its production runtime, worker, schema, database privileges, deployment compatibility, backups, and monitoring must be corrected first.
- **Is the server sufficiently hardened?** **NO-GO as a sensitive multi-tenant production host.** Loopback binding is good, but privilege concentration, unverified effective firewall/SSH state, Docker-socket consumers, floating legacy services, and absent monitoring remain blockers.
- **Can we recover from catastrophic server loss?** No defensible recovery path was demonstrated. The effective recovery point for a complete Madar backup is 2026-07-31; later dumps omit assets. No off-host copy, Mailcow backup, current Briefedly production backup, or restore drill was found.

## Immediate blockers

1. Treat the audit transcript credential disclosure as an incident; rotate/revoke exposed Supabase and shared-database material without reusing values.
2. Remove database-superuser credentials from both applications and provision least-privilege roles.
3. Create and verify an off-host encrypted full-system backup before further production change.
4. Reconcile Briefedly production safely: preflight Ollama transport, back up, migrate in staging, deploy the worker, then deploy immutable current images with rollback.
5. Add basic external uptime/disk/worker/queue/backup/tunnel/certificate alerting.

## Go/no-go summary

| Target | Use case | Decision | Conditions |
|---|---|---:|---|
| Madar | Limited beta | CONDITIONAL GO | P0 credentials/DB roles/backups, alerting, readiness fix, known beta data only |
| Madar | Paying customers | NO-GO | P0/P1 complete; restore drill; deploy rollback; privacy workflows |
| Madar | Sensitive business data | NO-GO | Above plus penetration/tenant regression and formal incident/privacy operations |
| Briefedly | Developer testing | GO | Synthetic/dev accounts only; dev isolation maintained |
| Briefedly | Trusted beta | NO-GO | Reconcile prod worker/schema/runtime and all P0/P1 controls first |
| Briefedly | Real private Gmail | NO-GO | Least privilege, backup/restore, worker, retention, Ollama transport, monitoring |
| Briefedly | Enterprise email | NO-GO | Above plus formal security/privacy/IR controls and independent assessment |
| Server | Production host | NO-GO | P0/P1 infrastructure, backup, separation, firewall verification, monitoring |
