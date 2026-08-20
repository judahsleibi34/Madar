# Findings register

Counts: **3 Critical, 9 High, 15 Medium, 7 Low**. Confidence terms: Confirmed, Highly likely, Potential, Needs runtime verification.

## AUDIT-SEC-001 — Live credentials appeared in the audit transcript

Severity: **CRITICAL**
Confidence: **Confirmed**
System: Cross-system
Category: Secrets / Incident

### Location and evidence

The audit tool transcript rendered several colon-delimited Madar Supabase entries when an intended key-only transform did not match them, and later rendered the hardcoded shared-Postgres password while reading Compose. Values are intentionally omitted here.

### Scenario, impact, and likelihood

Anyone with transcript access could use the still-valid material for database/API access. Impact includes complete Madar/Supabase compromise and shared-DB compromise; likelihood depends on transcript access but exposure is actual.

### Existing mitigation

Transcript is within the controlled audit channel; no value is in report files. Current file permissions remain restrictive.

### Recommended remediation and verification

Restrict/preserve minimal incident evidence; rotate/revoke all displayed Supabase DB/service/anon and shared-DB credentials; update consumers through change control; revoke relevant sessions; search provider/audit logs for misuse. Verify old credentials fail and new credentials retain only least privilege.

## MADAR-DB-001 — Backend holds direct PostgreSQL superuser credentials

Severity: **CRITICAL**
Confidence: **Confirmed**
System: Madar
Category: Database / Credential blast radius

### Location and evidence

`/home/madar/saas/Madar/.env`, Compose `env_file`, runtime `madar-backend`; read-only connection reported `current_user=postgres` on PostgreSQL 17.6.

### Scenario, impact, and likelihood

Backend RCE, dependency compromise, env disclosure, or SSRF-to-command chain yields all Supabase schemas/roles and bypasses tenant RLS. Impact is complete cross-tenant/auth/storage compromise. Credential is present in every backend process, so likelihood after backend compromise is high.

### Existing mitigation

Container is non-root/read-only/capability-dropped; public routes have strong authorization. These do not constrain database superuser use.

### Recommended remediation and verification

Remove the URL from app env. Provision function-specific LOGIN roles with only required schema/RPC privileges, TLS requirements, short rotation, and connection limits. Confirm `rolsuper/rolcreaterole/rolcreatedb/rolreplication/rolbypassrls=false` and run tenant/security tests.

## BRF-DB-001 — Briefedly application DB role is superuser

Severity: **CRITICAL**
Confidence: **Confirmed**
System: Briefedly
Category: Database / Least privilege

### Location and evidence

Production PostgreSQL role metadata for `briefedly_app` shows SUPERUSER, CREATEDB, CREATEROLE, REPLICATION, and BYPASSRLS.

### Scenario, impact, and likelihood

An app compromise can read/change all private email, create roles/databases, bypass constraints/policies, and establish persistence. The credential is necessarily available to the app. Impact is total Briefedly DB compromise.

### Existing mitigation

Loopback/internal network, app authentication, and empty current production customer tables reduce present exposure, not launch risk.

### Recommended remediation and verification

Create separate owner/migrator/application roles; app gets CRUD only on required objects and no DDL/role/replication/bypass powers. Rotate password and verify role flags, default privileges, schema ownership, and all tests/migrations.

## DR-001 — No scheduled off-host coherent backup or proven restore

Severity: **HIGH**
Confidence: **Confirmed**
System: All
Category: Reliability / Disaster recovery

### Location and evidence

Local `/home/madar/backups`, Madar backup scripts/runbook, Briefedly DB-only script; no backup timer, off-host copy, Mailcow backup, current Briefedly prod dump, PITR, or restore-drill record. Latest verified full Madar set is 2026-07-31.

### Scenario, impact, and likelihood

Disk loss, ransomware, host compromise, corruption, or operator deletion destroys primary and local backups together. Impact ranges from weeks of Madar data loss to complete Briefedly/mail loss; hardware/host failures are credible.

### Existing mitigation

Madar's full backup format is sound and one old set passed checksums; later DB-only dumps exist.

### Recommended remediation and verification

Deploy encrypted immutable/off-host DB+assets+mail+config+secret backups with retention/PITR and alerts. Restore quarterly to isolated infrastructure and measure actual RPO/RTO through application tests.

## BRF-OPS-001 — Briefedly production is stale and missing its worker

Severity: **HIGH**
Confidence: **Confirmed**
System: Briefedly
Category: Runtime drift / Privacy / Reliability

### Location and evidence

Runtime has DB/backend/frontend only; worker absent. Backend/frontend lack current hardening. DB revision `d8c6b4a2f190` is five migrations behind head `c8e5f1a3b647`; five current tables are absent.

### Scenario, impact, and likelihood

Imports, reports, retention, OAuth/rate cleanup, export, and deletion jobs never run; API can enqueue work that stays pending. Privacy promises become false. This occurs deterministically.

### Existing mitigation

Production tables are currently empty; development worker/head work. Checked-in Compose includes intended worker/hardening.

### Recommended remediation and verification

Back up; rehearse migrations; resolve Ollama preflight; deploy immutable current DB/backend/frontend/worker; verify job lease/heartbeat, retention, export/delete, security headers, and schema head; add drift reconciliation.

## BRF-DEP-001 — Current source rejects deployed Ollama URL

Severity: **HIGH**
Confidence: **Confirmed**
System: Briefedly
Category: Deployment / AI transport

### Location and evidence

Runtime `OLLAMA_BASE_URL` is HTTP to a Tailscale IPv4 address. `backend/app/core/config.py:179-192` rejects non-loopback HTTP in production.

### Scenario, impact, and likelihood

Next deploy reaches current code and fails settings initialization, leaving backend/worker down after DB migrations may already have run. It is a deterministic config/code mismatch.

### Existing mitigation

Old runtime accepts the URL; Tailscale encrypts network transport.

### Recommended remediation and verification

Use authenticated validated HTTPS or a local authenticated proxy/sidecar; preflight current image with production-shaped redacted config before migration. Verify startup, certificate/auth failure closed, and Ollama outage/recovery.

## BRF-SEC-001 — Database container receives unrelated high-value secrets

Severity: **HIGH**
Confidence: **Confirmed**
System: Briefedly
Category: Secrets / Container isolation

### Location and evidence

Production Compose applies `backend/.env.production` to PostgreSQL. Presence-only inspection shows app secret, encryption key, Google client secret, Ollama URL, and job/admin material available to DB container.

### Scenario, impact, and likelihood

A PostgreSQL/container escape, extension, support dump, or diagnostic exposes Gmail and encryption/application material unrelated to DB function. Impact crosses DB, OAuth, and sessions.

### Existing mitigation

Container is internal-networked and not host-published.

### Recommended remediation and verification

Give DB only POSTGRES variables via a distinct 600/root-owned env/secret. Use per-service Docker secrets/credential files. Inspect runtime env names to prove minimization.

## HOST-SEC-001 — One host identity collapses developer, deploy, secret, and root boundaries

Severity: **HIGH**
Confidence: **Confirmed**
System: Linux host
Category: Privilege separation

### Location and evidence

`madar` owns source/secrets/backups/deploy scripts and belongs to sudo, Docker, adm. Docker is root-equivalent. Timers deploy as this user.

### Scenario, impact, and likelihood

SSH key theft, malicious dependency/repository content, or app-adjacent user compromise can mount host root via Docker and take all SaaS/mail data. Impact is total host compromise.

### Existing mitigation

Only root/madar are interactive; home is 750; app containers are often non-root.

### Recommended remediation and verification

Separate human operator, root-owned deploy agent, and per-app runtime identities; remove interactive users from Docker; use a constrained CI/deploy API and immutable images. Verify group/sudoers and attempt documented privilege-boundary tests.

## DEP-MADAR-001 — Madar deployment is non-atomic and does not manage schema/readiness

Severity: **HIGH**
Confidence: **Confirmed**
System: Madar
Category: Deployment reliability

### Location and evidence

`/usr/local/sbin/madar-auto-deploy`, `/home/madar/docker_auto.sh`: hard reset/build/up, tracked-dirt check only, no migration, root-URL checks, rebuild rollback.

### Scenario, impact, and likelihood

Untracked overrides survive; new code starts against old schema; partial build/up leaves mixed versions; rollback fails because old dependencies/images changed. Repository compromise executes with Docker-equivalent authority.

### Existing mitigation

Tracked dirt is checked and a previous SHA is recorded; application images/containers have healthchecks.

### Recommended remediation and verification

Require fully clean tree, signed immutable image digest, explicit schema preflight/migration, compatibility window, readiness gate, deployment lock, and old-image rollback. Test failures at each step in staging.

## OBS-001 — No external monitoring or actionable alerts

Severity: **HIGH**
Confidence: **Confirmed**
System: All
Category: Observability / Incident readiness

### Location and evidence

No collector/dashboards/external uptime/error/backup/disk/cert/tunnel/worker alert stack found. Madar metrics exist but are uncollected; dead/failed jobs and historic timer/tunnel failures exist.

### Scenario, impact, and likelihood

Outages, disk fill, worker death, failed backups, mail failure, or credential abuse persist until a user notices. Delayed detection increases loss and recovery time.

### Existing mitigation

Health endpoints, structured logs, journald, Docker health, and app audit tables exist.

### Recommended remediation and verification

Collect metrics/logs off-host; alert on availability, latency, disk/inodes, DB, workers/queues, backup age, tunnel, mail, certs, and Ollama. Run alert-fire drills and record ownership/escalation.

## MADAR-ADMIN-001 — Admin bootstrap is identity/order dependent

Severity: **HIGH**
Confidence: **Confirmed**
System: Madar
Category: Authentication / Recovery

### Location and evidence

Migrations `023_add_user_type_to_users.sql` and `026_set_user_1_as_admin.sql` embed an email then force ID 1 admin/demote others. Production has one admin and ID 1 is admin.

### Scenario, impact, and likelihood

On rebuild/import with different insertion order, an unintended first user becomes global admin and intended admins are demoted. Loss of sole admin also blocks recovery.

### Existing mitigation

Current admin routes require AAL2 and protect the last admin.

### Recommended remediation and verification

Remove identity-specific bootstrap from rebuild path; use explicit one-time operator ceremony with verified auth ID, dual approval/audit, and multiple break-glass admins. Rehearse zero-to-current migration with synthetic reordered users.

## PRIV-001 — Data retention/deletion/export are not operationally complete

Severity: **HIGH**
Confidence: **Confirmed**
System: Madar and Briefedly
Category: Privacy / Data lifecycle

### Location and evidence

Madar lacks comprehensive self-service account/tenant export/deletion and category retention for forms/reservations/analytics/browser/backups. Briefedly current privacy jobs exist but production worker/schema do not.

### Scenario, impact, and likelihood

Customers/submitters cannot reliably exercise deletion/export; raw mail or form data persists beyond claims; backup/provider copies remain. This becomes certain once sensitive customers request lifecycle actions.

### Existing mitigation

Admin deletion, feature exports, asset/notification cleanup, Briefedly current privacy code, and legal gap documentation exist.

### Recommended remediation and verification

Approve retention matrix and request process; implement cross-store manifests, monitored jobs, provider revocation, backup aging, submitter/tenant controls, and audit evidence. Test deletion/export on restored production-shaped data.

## NET-001 — Effective firewall policy is unverified and UFW state conflicts

Severity: **MEDIUM**
Confidence: **Needs runtime verification**
System: Host networking
Category: Firewall / IPv6

### Location and evidence

`/etc/default/ufw` says DROP/IPv6 enabled; `/etc/ufw/ufw.conf` says `ENABLED=no`; root-only UFW/nft/iptables reads failed. Multiple mail/admin/SSH ports listen on all IPv4/IPv6.

### Scenario, impact, and likelihood

Operators assume filtering that is absent or Docker bypasses it; unexpected services become Internet reachable, particularly on IPv6.

### Existing mitigation

SaaS ports are loopback; public mail probes show only intended mail/web reachable from tested paths.

### Recommended remediation and verification

Root capture of complete v4/v6 rules and Docker chains plus external dual-stack scan; document allowlist and default policies. Verify after every Docker/firewall change.

## SSH-001 — Effective SSH hardening is unknown and base defaults are permissive

Severity: **MEDIUM**
Confidence: **Needs runtime verification**
System: SSH
Category: Host access

### Location and evidence

Base `sshd_config` enables X11 and does not explicitly disable root key login, passwords, TCP/agent forwarding, or set idle/allowlist limits. Root-only cloud-init drop-in prevented `sshd -T`.

### Scenario, impact, and likelihood

Password/root/forwarding exposure broadens brute-force and post-key-theft movement on a root-equivalent `madar` account.

### Existing mitigation

KbdInteractive is off; key file modes are good; SSH is the only public host-management port observed.

### Recommended remediation and verification

Obtain `sshd -T`; enforce keys only, no root, disable unused forwarding/X11, allowlist users, reduce attempts, add idle policy and brute-force monitoring. Verify a second session before rollout.

## MAIL-001 — Mail exposure and deliverability policy need hardening

Severity: **MEDIUM**
Confidence: **Confirmed**
System: Mailcow/DNS/network
Category: Mail security/reliability

### Location and evidence

Ports 110/143 and direct 8080/8443 are globally listening; DMARC is `p=none`; outbound TCP/25 to Gmail MX timed out. Mailcow backup absent.

### Scenario, impact, and likelihood

Legacy protocol/admin brute force increases attack surface; spoofed Madar mail is not rejected by policy; outbound queues can accumulate indefinitely under ISP block.

### Existing mitigation

Relay restrictions are sound, TLS 1.2+ for Dovecot, valid cert, SPF `mx -all`, DKIM, submission/IMAPS available, Mailcow netfilter.

### Recommended remediation and verification

Restrict/disable unused plaintext-capable/admin ports; progress DMARC after report monitoring; arrange SMTP relay/ISP unblock; alert on queue/cert/disk; back up Mailcow. Verify with external mail/TLS/DNS tests.

## CF-001 — Cloudflared privilege/config hygiene is weak

Severity: **MEDIUM**
Confidence: **Confirmed**
System: Cloudflare integration
Category: Privilege / Configuration

### Location and evidence

Cloudflared runs root without systemd sandboxing. Several historical configs are 644; old mail ingress used `noTLSVerify:true`. Historical journal shows repeated DNS/start failure.

### Scenario, impact, and likelihood

Cloudflared compromise gains host root; readable stale routing aids reconnaissance; unverified mail-origin TLS enables local interception after host/network compromise.

### Existing mitigation

Credential JSON is 400/current config 600; app origins are loopback; public proxy TLS/HSTS works.

### Recommended remediation and verification

Run dedicated unprivileged user with systemd hardening; normalize backup modes/retention; validate current ingress; use trusted origin cert or pinning instead of no-verify. Test tunnel fail/restart alerts.

## DOCKER-001 — Docker cache/log growth can exhaust the shared disk

Severity: **MEDIUM**
Confidence: **Confirmed**
System: Docker/host
Category: Resource exhaustion

### Location and evidence

79.29 GiB build cache, ~63.28 GiB reclaimable; 27.87 GiB images; several legacy/Mailcow/Briefedly DB containers lack explicit JSON log rotation. All share root filesystem.

### Scenario, impact, and likelihood

Repeated two-minute builds, mail, WAL, or logs fill disk, corrupt writes, and stop DB/mail/apps together.

### Existing mitigation

321 GiB currently free; Madar logs/resources are bounded.

### Recommended remediation and verification

Alert at staged thresholds; scheduled reviewed cache/image retention; rotate all logs; separate/limit DB/mail/Docker/upload filesystems. Verify growth dashboards and low-disk behavior.

## DOCKER-002 — Legacy containers use floating tags, weak hardening, and Docker socket power

Severity: **MEDIUM**
Confidence: **Confirmed**
System: Portainer/NPM/shared DB/Mailcow
Category: Container/supply chain

### Location and evidence

NPM `latest`, shared `postgres:17`, tag-only Sleibi Nginx; Portainer Docker socket RW; Mailcow scheduler/API proxy socket access; missing read-only/cap/resource baselines.

### Scenario, impact, and likelihood

Compromise or surprise image update yields Docker/host control or service drift.

### Existing mitigation

Primary SaaS images mostly digest-pinned; runtime NPM/Portainer ports are not broadly published.

### Recommended remediation and verification

Assign ownership/purpose; pin digests; minimize/remove Docker socket; harden or decommission legacy services; scan images/SBOM. Verify runtime digest/config against inventory.

## DEP-BRF-001 — Briefedly deployment lacks safe post-migration rollback and drift reconciliation

Severity: **MEDIUM**
Confidence: **Confirmed**
System: Briefedly
Category: Deployment

### Location and evidence

Auto-deploy migrates before full stack health; failure leaves repo/schema advanced; no immutable old image rollback; runs only on SHA change; timer currently disabled.

### Scenario, impact, and likelihood

Migration succeeds then app fails; old app may be schema-incompatible and runtime remains broken. Current stale containers demonstrate reconciliation failure.

### Existing mitigation

Locking, full cleanliness check, fast-forward only, and health check exist.

### Recommended remediation and verification

Preflight image/config, backup, backward-compatible expand/contract migrations, immutable digests, post-deploy readiness, automatic old-image rollback when schema-compatible, and periodic drift check.

## MADAR-READY-001 — Readiness is timing-sensitive and backup-blind

Severity: **MEDIUM**
Confidence: **Confirmed**
System: Madar
Category: Health/readiness

### Location and evidence

`/health/ready` alternated `schema: unavailable`/503 and ready/200; all required table probes separately succeeded. Schema probes share a two-second budget. `backup_freshness=disabled`; Docker checks `/health/live`.

### Scenario, impact, and likelihood

Healthy deployment appears failed or degraded; actual stale backup remains green; automation either ignores readiness or causes false rollback.

### Existing mitigation

Components are explicit and cached; worker/queue/isolation checks are meaningful.

### Recommended remediation and verification

Use one lightweight schema-version query with calibrated timeout; enable backup marker; make deployment/orchestrator gate on readiness with retry/hysteresis. Chaos-test each dependency.

## MADAR-UPLOAD-001 — Hostile documents are served inline without AV/CDR

Severity: **MEDIUM**
Confidence: **Confirmed**
System: Madar builder/storage
Category: File security

### Location and evidence

Builder accepts PDF/DOC/DOCX after structural/magic checks and can return them inline from the API origin. No AV/CDR/transcode was found.

### Scenario, impact, and likelihood

Tenant uploads active/malicious document; visitor/admin browser or vulnerable parser is attacked. Same-origin delivery increases impact if a browser content-sniff/plugin issue occurs.

### Existing mitigation

Size/ZIP/path/magic checks, `nosniff`, generated paths, tenant ownership, isolated parser, no SVG/HTML/JS.

### Recommended remediation and verification

Serve risky documents as attachment from cookie-less origin; AV/CDR/quarantine; safe image/video decode/transcode; sandbox OCR. Test polyglots, bombs, active PDFs, parser crash, and cross-tenant access.

## MADAR-BROWSER-001 — Unpublished tenant content persists in browser storage

Severity: **MEDIUM**
Confidence: **Confirmed**
System: Madar frontend
Category: Privacy / XSS impact

### Location and evidence

31 frontend files use localStorage and 11 sessionStorage; builder recovery stores substantial schema/content scoped by user/tenant/project.

### Scenario, impact, and likelihood

Shared device, stale browser profile, extension, or same-origin XSS reveals deleted/unpublished content across sessions.

### Existing mitigation

Keys are scoped; recovery is advisory; no dangerous HTML sink found; logout cleanup exists for some state.

### Recommended remediation and verification

Minimize/expire/encrypt recovery, provide device-data purge, avoid full-schema cross-tab broadcasts, and document shared-device risk. Test logout/user-switch/tenant-switch and XSS containment.

## MADAR-TEST-001 — Current frontend regression suite is not green/terminating

Severity: **MEDIUM**
Confidence: **Confirmed**
System: Madar
Category: Quality / Publication reliability

### Location and evidence

`PageBuilder.collisionPadding.renderer.test.jsx` has two failures (two-column alignment; under-text art Y position). Full Vitest run did not terminate/produce a final summary in the audit window.

### Scenario, impact, and likelihood

Saved site layouts render differently and CI may hang or fail, allowing deployment uncertainty.

### Existing mitigation

217 test files cover many security and builder paths; failures are visible, not silently skipped.

### Recommended remediation and verification

Fix behavior/expectations; identify leaked handles; require deterministic CI timeout and full pass before deploy; add visual cross-device E2E snapshots.

## BRF-WEB-001 — Briefedly public security headers are incomplete

Severity: **MEDIUM**
Confidence: **Confirmed**
System: Briefedly
Category: Browser security

### Location and evidence

Public frontend/API responses lack HSTS, CSP, frame restriction, Permissions-Policy, and explicit private/no-store controls; dev/current source has stronger headers.

### Scenario, impact, and likelihood

Clickjacking, weaker XSS defense, downgrade-first-visit risk, and inappropriate caching become more consequential with private email reports.

### Existing mitigation

HTTPS via Cloudflare, `nosniff` and referrer policy on frontend; no dangerous HTML sink found.

### Recommended remediation and verification

Deploy current Nginx/middleware and configure Cloudflare HSTS. Verify public/authenticated/API/error/OPTIONS headers and cookies over HTTPS without breaking OAuth.

## BRF-BILL-001 — Workspace owners/admins can self-select plan code/status

Severity: **MEDIUM**
Confidence: **Confirmed**
System: Briefedly
Category: Billing/entitlements

### Location and evidence

`backend/app/domains/workspaces/routes.py:87-106` accepts `plan_code` and sets `plan_status=selected`; signup also accepts plan code. No payment/entitlement authority is linked.

### Scenario, impact, and likelihood

If product limits later trust these fields, an owner forges a paid plan. Today it creates misleading state even if no capability checks use it.

### Existing mitigation

Only owner/admin can update; billing is not currently implemented.

### Recommended remediation and verification

Treat selection as non-entitling preference with distinct field, or restrict canonical plan/status to verified billing/admin events. Add tests forging codes and expired/missing subscriptions.

## SUPPLY-001 — Historical secrets and mutable image references remain supply-chain debt

Severity: **MEDIUM**
Confidence: **Confirmed**
System: Cross-system
Category: Supply chain / Secrets

### Location and evidence

Briefedly commit `9e9b807...` tracked multiple secret classes; current fingerprints differ. Madar history contains large generated/browser/certificate artifacts. Several legacy images float by tag.

### Scenario, impact, and likelihood

Unrevoked historical provider token or compromised mutable upstream tag enables unauthorized access/build compromise.

### Existing mitigation

Current env files ignored/600; current secret fingerprints changed; primary images/requirements/lockfiles mostly pinned; npm production audits clean.

### Recommended remediation and verification

Provider-side revocation register, history scanner, SBOM/image scan/signature, digest pinning, CI secret scanning. Verify old credentials fail; do not rely on history rewrite.

## BRF-OAUTH-001 — OAuth disconnect can hide provider revocation failure; PKCE absent

Severity: **MEDIUM**
Confidence: **Confirmed**
System: Briefedly
Category: OAuth lifecycle

### Location and evidence

Disconnect catches revocation failure and clears local tokens; no durable retry. Authorization-code flow has strong state but no PKCE.

### Scenario, impact, and likelihood

User believes access revoked while Google's refresh token remains valid after local DB deletion; stolen token can continue mailbox access. PKCE would reduce code interception risk.

### Existing mitigation

Read-only scope, encrypted tokens, one-time state, authenticated callback, local token removal.

### Recommended remediation and verification

Persist revocation-pending state/retry and operator/user status; add PKCE S256; test provider timeout, replay, reauthorization, and stolen-code cases.

## REDIS-001 — Redis relies solely on local/network isolation

Severity: **LOW**
Confidence: **Confirmed**
System: Madar Redis
Category: Defense in depth

### Location and evidence

Redis is loopback/internal only but has no password/ACL/TLS.

### Scenario, impact, and likelihood

Compromised local process/user/container with network reach tampers rate-limit/cache state. No public reach was found.

### Existing mitigation

Loopback publishing, Docker networks, non-authoritative data, protected container.

### Recommended remediation and verification

Add ACL/password or remove host publishing if unnecessary; restrict networks. Verify unauthenticated local denial and fail-closed app behavior.

## CODE-001 — Large Madar routers concentrate security-sensitive complexity

Severity: **LOW**
Confidence: **Confirmed**
System: Madar
Category: Maintainability

### Location and evidence

Builder, calendar, and public-site routers are roughly 95–112 KiB and mix multiple concerns.

### Scenario, impact, and likelihood

Future changes omit tenant/auth/transaction behavior amid complex control flow, increasing regression likelihood.

### Existing mitigation

Strong helpers and extensive tests exist; no current IDOR was confirmed.

### Recommended remediation and verification

Split by bounded context/use case, centralize resource loaders/policies, keep contract/security regression tests and complexity gates.

## API-001 — Product/version identity and server banners are stale/inconsistent

Severity: **LOW**
Confidence: **Confirmed**
System: Both SaaS products
Category: Information disclosure / Operations

### Location and evidence

Briefedly status says `priorify-backend`; local APIs expose Uvicorn/Nginx server headers; root health semantics vary.

### Scenario, impact, and likelihood

Reconnaissance and operator confusion during incident/deployment; limited direct exploitability.

### Existing mitigation

Cloudflare masks some origin detail; request IDs exist.

### Recommended remediation and verification

Use correct service/build digest, consistent liveness/readiness/version metadata, and suppress unnecessary banners. Verify public/local responses.

## SLEIBI-001 — Mutable static config is cached immutable

Severity: **LOW**
Confidence: **Confirmed**
System: Sleibi
Category: Cache reliability

### Location and evidence

Nginx gives `/config/*.js` seven-day `immutable` caching while HTML references stable `config/shop.js`.

### Scenario, impact, and likelihood

Updated merchant/contact/legal content remains stale in returning browsers for a week.

### Existing mitigation

HTML is no-store; static validation and rollback are strong.

### Recommended remediation and verification

Content-hash mutable assets or use revalidation/no-cache for config. Deploy a synthetic change and verify returning-client refresh.

## CONFIG-001 — Duplicate/stale configuration copies create ambiguity

Severity: **LOW**
Confidence: **Confirmed**
System: Cross-system
Category: Configuration management

### Location and evidence

Briefedly env files duplicate Google assignments (empty then populated); multiple Cloudflare/Mailcow/env backups exist with mixed modes; runtime ports differ from NPM/shared-DB Compose.

### Scenario, impact, and likelihood

Different parsers/order or operator copy/restore selects stale/empty/insecure values and causes outage or disclosure.

### Existing mitigation

Current primary secrets are 600; Python dotenv generally uses last assignment.

### Recommended remediation and verification

Single schema-validated source per environment; per-service env allowlists; inventory/expire backup copies; automated runtime-vs-source drift report.

## HOST-PATCH-001 — Microcode/security-update posture is not continuously proven

Severity: **LOW**
Confidence: **Potential**
System: Host
Category: Patch/vulnerability management

### Location and evidence

Kernel reports residual CPU vulnerabilities/missing microcode for one class; a few packages are upgradeable; no firmware/security-update alert evidence.

### Scenario, impact, and likelihood

Known host/CPU vulnerability remains exploitable after local/container foothold. Exact exposure depends on hardware/microcode/package state.

### Existing mitigation

Modern kernel, ASLR, ptrace/link protections, no pending reboot marker.

### Recommended remediation and verification

Review Ubuntu security status, microcode/BIOS, livepatch/reboot policy, and automatic alerting. Record applied CVEs and rerun vulnerability files after reboot.

## LOG-001 — Log rotation, retention, and access are inconsistent

Severity: **LOW**
Confidence: **Confirmed**
System: Host/containers
Category: Logging

### Location and evidence

Madar has bounded Docker logs; older Briefedly/Mailcow/legacy containers rely on defaults; journald is ~575 MiB; no time-based unified retention/off-host integrity.

### Scenario, impact, and likelihood

Disk growth or missing/altered local logs impairs incident investigation.

### Existing mitigation

App redaction/request IDs and restricted home/log membership exist.

### Recommended remediation and verification

Set rotation/retention for every service, forward security events off-host with access control, and test redaction for tokens/email/form data.
