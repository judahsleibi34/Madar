# Observed architecture — 2026-10-16

Baseline: `876b65e73ea8ceaf398145d8677019184798a95c` (`origin/main`). Dedicated worktree `/home/madar/Madar-architecture-hardening-20261016`; branch `codex/architecture-hardening-20261016`. Existing corrective checkout remains clean and untouched. `main` contains `origin/Saliba-Branch` (200 commits ahead) and `origin/Judah_branch` (13 ahead); main is the current integration baseline.

## Application boundaries

- `web/backend/app.py`: FastAPI modular monolith; routers in `routes/`, domain logic in `services/`, separate entry points in `workers/`. CSRF, CORS, body limits, compression, correlation IDs and timing middleware surround requests.
- `database.py`: shared synchronous HTTP/1.1 Supabase clients; anonymous and service credentials required and distinct. Auth clients isolate mutable SDK session state and disable independent refresh timers. Database access remains PostgREST/RPC; service-role queries can bypass RLS, so server tenant checks remain essential.
- `services/auth_service.py`, `mfa_login_service.py`, `tenant_service.py`, `site_permission_service.py`: authentication, assurance/session binding, tenant context and resource authorization. Existing extensive adversarial tests must remain.
- `entitlement_service.py`: canonical subscriptions/dated ledger plus explicit operator-controlled all-capabilities override. Disabled enforcement is an intentional existing policy with admin holds; this session must not silently change customer commercial assignments.
- Catalog and calendar caches are bounded in-process dictionaries; catalog keys include tenants, calendar also includes user, role and range. Invalidation is process-local; multiple processes can retain old entries until TTL.
- Notification delivery, calendar sync and deletion use existing PostgreSQL RPC queues/leases and dedicated workers. No new broker is warranted without evidence.
- `web/frontend/src/App.jsx`, `appMain.jsx`, `tenantMain.jsx`: React/Vite portal and separate public tenant entry, route loading, API-origin and public-bundle build audits. Vitest/jsdom and Playwright suites exist.
- `web/database/migrations/` and mirrored `web/supabase/migrations/`: immutable historical SQL with checksum-bound release manifests. Current selected source descriptor accepts 144..146, target146. Auth, MFA and Storage remain provider services; changing a PostgreSQL URL cannot replace them.
- Managed asset authorization, quotas and storage delivery are in `asset_registry_service.py`, `builder_asset_storage.py`, `storage_delivery_service.py`, `storage_quota_service.py` and `app.py`. Preserve mediated legacy URLs and no-store private previews.
- AI/data analysis uses explicit services plus parser/remote-ingestion workers; runtime config prohibits local AI execution in production-like environments. No inference deployment is authorized on the shared production host.

## Release and infrastructure observations

Primary is `madar-gpu`, kernel7.0.0-38, ~38GiB RAM, ~25GiB available at discovery; swap was fully allocated. `/home` filesystem had189GiB free. Inspected read-only. Production checkout HEAD `c1d03ce3` differs from serving immutable artifact. Read-only `/var/lib/madar/releases/state.json` reports blue, known-good `b0fdfe049510724c06a04706390cd174ea57a1d1`, observed schema146, no in-progress release or rollback failure. This records state, not a fresh end-to-end production attestation.

Canonical production controller `/opt/madar/control-plane/deployment`; checkout `/srv/madar/production`; runtime state `/var/lib/madar/releases`; secrets `/etc/madar/production.env`. Never invoke production mutators for this session.

Staging `madar-staging` at10.250.250.2: Ubuntu26.04.1, kernel7.0.0-30,4vCPU,5402MiB RAM (~4694MiB available),60GiB disk free. SSH and sudo verified. Existing `madar-staging-data` has healthy PostgreSQL 17 (1GiB cap,0.75CPU) and Redis (256MiB cap,0.25CPU,128MiB maxmemory,noeviction), internal network, no published database ports. Existing data and backups belong to previous staging work and are preserved. SSH is the only externally listening TCP service observed; UFW inactive. VM has no default route or DNS configuration; public registry build failed at DNS resolution. Offline image import is an alternative, not evidence of a fresh locked build.

`web/staging` is explicitly a synthetic Auth/Storage facade and schema81/83 rehearsal; it is not current full Supabase parity. `web/precutover` contains provider overlays with historical schema115 notes; source code and current release descriptor take precedence over those stale notes.

## Validation inventory

CI backend builds a locked Python3.12 test image then runs `scripts/run_tests_no_external_network.py` with unittest discovery and external-network guard. Baseline discovery missed21 top-level pytest-style functions in4 modules (four required monkeypatch fixtures); this branch now collects them and guards against recurrence. CI frontend runs npm ci, lint, Vitest, build and production dependency audit. No coverage or PASS is inferred from merely finding these tests.


## Additional implementation inventory

FastAPI includes explicit auth/MFA/callback, user/password/install, admin/billing,
calendar, ecommerce, builder/public sites, notifications/deletion, learning/academy
and protected data-analysis routers. Six worker entry points exist: notification,
calendar sync, deletion, parser, remote ingestion and generated code. Only the
notification consumer was deployed and exercised in the new native staging.
Existing `observability_service.py` uses request IDs, structured safe-field logs,
route-template/status/method metrics and bounded Server-Timing headers. Middleware
passes matched route templates rather than customer URLs to metric labels. No
redundant Prometheus/Grafana/Loki service was installed. Alert behavior, long-term
metric resource growth and complete queue/storage/backup signal coverage remain
unverified.

React entry separation and route loading are retained. `utils/apiClient.js`,
`services/apiRoutes.js` and PageBuilder API helpers provide existing request/session
behavior; auth and public tenant rendering have dedicated suites. The exact-lock
frontend suite/build and native portal browser flow passed; no frontend source
or bundle-splitting strategy was changed without measured product evidence.

Current native staging topology/resources are in07-INFRASTRUCTURE.md and its
parity limits in08-STAGING-DEPLOYMENT.md. The older synthetic facade remains
intact and explicitly distinct. Database authority and unresolved lease fencing
are in04-DATABASE-INTEGRITY.md. Enterprise connector coverage and Athena tool
boundaries were inventoried only at service-boundary level; no claim of a complete
connector registry or authorized inference deployment is made.
