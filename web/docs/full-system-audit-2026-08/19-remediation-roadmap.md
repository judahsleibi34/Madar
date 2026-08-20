# Remediation roadmap

## P0 — Immediate, before continued sensitive production use

### AUDIT-SEC-001 — Credential incident response

- **What:** rotate/revoke every credential displayed in the audit transcript; restrict transcript access; inspect provider/audit logs; revoke affected sessions.
- **Affected:** Supabase/Madar, shared PostgreSQL, environment/Compose consumers.
- **Likely components:** secret store/env files, Supabase DB/API keys, shared DB roles, Compose services.
- **Regression risk:** high—rotation can break auth/storage/DB connectivity.
- **Tests:** old credentials fail; new least-privilege connections pass; signup/login/storage/readiness and deployment smoke tests.
- **Deployment:** staged credential overlap only where provider supports it; never log values; record owners/completion.
- **Dependencies:** coordinate with MADAR-DB-001 and BRF-DB-001 to avoid rotating into the same excessive privilege.

### MADAR-DB-001 and BRF-DB-001 — Least-privilege database roles

- **What:** remove superuser credentials from app processes; split owner/migrator/runtime roles and per-worker scopes.
- **Affected:** both SaaS apps and PostgreSQL/Supabase.
- **Likely components:** DB role/grant SQL, secret injection, Compose, migration/deploy scripts, readiness.
- **Regression risk:** high—hidden table/function/sequence privileges may break workflows.
- **Tests:** full auth/tenant/Gmail/job/storage/billing suites, grant assertions, negative DDL/role/cross-schema tests, migration under migrator only.
- **Deployment:** inventory SQL calls; create roles; shadow/test in staging; rotate app; revoke superuser last; monitor permission errors.
- **Dependencies:** credential incident response and verified backup.

### DR-001 — Establish recoverability

- **What:** make an immediate verified encrypted off-host backup, then schedule/alert DB+assets+mail+config/secret recovery sets and PITR where appropriate.
- **Affected:** host, both SaaS apps, Mailcow, Cloudflare configuration.
- **Likely components:** backup scripts/timers, off-host object store, encryption/KMS, restore automation, monitoring.
- **Regression risk:** medium—backup I/O/locks/storage cost; restores are isolated.
- **Tests:** checksum plus full isolated restore and representative application/tenant/private-file checks.
- **Deployment:** capture image/commit/schema; throttle; separate credentials; immutable retention.
- **Dependencies:** owner-approved RPO/RTO and storage/provider.

### BRF-OPS-001 and BRF-DEP-001 — Safe Briefedly production reconciliation

- **What:** select secure Ollama transport; back up; preflight current image/config; rehearse five migrations; deploy current hardened backend/frontend/worker and verify head.
- **Affected:** Briefedly, PostgreSQL, Ollama/Tailscale, Cloudflare.
- **Likely components:** `config.py`, env, Compose, Dockerfiles, Alembic, systemd deploy.
- **Regression risk:** high—startup incompatibility, schema lock/compatibility, OAuth/report flow.
- **Tests:** startup preflight, migration clone, sessions/CSRF/OAuth/import/report/retention/export/delete, worker leases, headers, Ollama outage.
- **Deployment:** maintenance window, immutable images, pre-migration backup, expand/contract compatibility, rollback decision tree.
- **Dependencies:** BRF-DB-001, BRF-SEC-001, DR-001.

## P1 — Before onboarding real sensitive customers

### BRF-SEC-001 — Per-service secret minimization

Use distinct DB/app/worker secrets; remove Gmail/encryption/application values from DB. Regression test DB startup, app/worker connectivity, OAuth and token decrypt. Deploy with secret rotation and runtime presence-only inspection.

### HOST-SEC-001 and DOCKER-002 — Host/CI privilege separation

Remove human interactive users from Docker, create root-owned constrained deployment service, per-app runtime users, and eliminate/minimize Docker socket consumers. Pin/harden or decommission Portainer/NPM/shared DB. Test deployment without sudo/Docker membership and attempt unauthorized socket/host access.

### DEP-MADAR-001 and DEP-BRF-001 — Transactional deployment program

Build signed immutable images in CI, require clean/signed commits, preflight config/schema, lock, use backward-compatible migrations, gate on readiness, retain known-good digests, and reconcile runtime drift. Inject failures at build, migration, start, readiness, and rollback stages in staging.

### OBS-001 and MADAR-READY-001 — Monitoring/readiness

Deploy off-host metrics/log/uptime and alert routes; make Madar readiness stable and backup-aware; add Briefedly worker/job readiness. Test every alert with controlled synthetic failure. Avoid paging on a two-second flaky remote schema scan.

### MADAR-ADMIN-001 — Deterministic admin bootstrap/recovery

Replace identity/ID migrations with an explicit audited bootstrap/break-glass procedure; create at least two protected admins; rehearse zero-to-head with reordered synthetic users. Migration history may remain immutable, but rebuild orchestration must neutralize unsafe bootstrap behavior.

### PRIV-001 — Privacy lifecycle program

Approve data-class retention and subprocessor/location inventory. Build comprehensive export/deletion and tenant/submitter controls across DB/files/cache/queues/providers/backups; deploy monitored cleanup workers; create incident/privacy request runbooks. Test against a restored production-shaped dataset.

### NET-001, SSH-001, MAIL-001, CF-001 — Perimeter verification/hardening

Obtain root-only effective firewall/SSH state; perform external dual-stack scan; restrict unnecessary mail/admin/legacy ports; harden cloudflared service; establish SMTP relay/egress solution and DMARC enforcement path. Stage remote-access changes with console/fallback access.

### MADAR-UPLOAD-001 — Hostile-content isolation

Add quarantine/AV/CDR, attachment/cookie-less delivery, safe image/video normalization, and disposable no-network OCR/parser workers without app secrets. Run a malicious corpus, bomb/timeout, polyglot, active-PDF, parser crash, and cross-tenant tests.

## P2 — Near term

- Fix Madar renderer failures/hanging test process and require green CI/browser E2E.
- Deploy Briefedly headers/HSTS and PKCE/revocation retry.
- Correct Briefedly plan fields before any entitlement use.
- Add Docker/cache/log/WAL/mail storage policy and separate/limit high-growth filesystems.
- Minimize browser-persisted builder data and add user/device purge.
- Normalize configuration copies/modes and automate source/runtime drift reports.
- Add Python/image vulnerability scanning, SBOM/signing, and historical-secret revocation register.
- Add Redis ACL/auth or remove host publishing.

## P3 — Longer-term architecture

- Split large Madar routers into bounded application services and policy-backed loaders.
- Build cell/tenant blast-radius reduction: function-specific workers/roles/storage domains.
- Version Sleibi mutable assets and formalize legacy-service ownership.
- Create granular tenant recovery/soft-delete capability instead of full-database restore.
- Formalize SLOs/error budgets, capacity tests, incident exercises, and annual independent security assessment.
- Before future Chatbot/OCR/Drive/WhatsApp: tenant-owned encrypted connections, least scopes, isolated ingestion/parsing, quotas, deletion, audit, prompt-injection tests, and subprocessor review.

## Quick wins

1. Enable and alert Madar backup freshness marker.
2. Add HSTS/CSP/frame/permissions/no-store to Briefedly edge.
3. Pin Sleibi/NPM/shared-DB image digests.
4. Remove `immutable` caching from Sleibi mutable config.
5. Normalize old env/dump/config backup permissions.
6. Add disk/inode, certificate-expiry, and external uptime alerts.
7. Correct stale `priorify-backend` identity.
8. Document/disable the Briefedly timer until the controlled reconciliation window.
9. Create a dead-delivery/job operational dashboard using existing metadata.
10. Capture root-only SSH/firewall evidence and an external IPv6 scan.
