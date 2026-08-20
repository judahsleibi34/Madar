# Madar Production-Readiness Review

Review date: 2026-07-13  
Repository: `D:\Madar`  
Review mode: evidence-first, read-only for production data and infrastructure

## 1. Executive Summary

**Verdict: Not ready.**

Madar has a comparatively strong application-security foundation: backend-owned sessions, origin and CSRF defenses, server-side tenant context, bounded uploads, published-schema isolation, optimistic revision checks, atomic publish and reservation functions, rate limiting, and meaningful builder data-safety tests. The local frontend and backend test suites pass.

The platform should not launch yet because the deployable state is not reproducible or fully verified, queued notification work has no consumer, paid billing is intentionally unavailable in production, generated AI code can be enabled in an in-process sandbox with no hard timeout, and there is no current evidence of tested backup/restore and rollback procedures.

### Finding count

| Severity | Confirmed findings |
|---|---:|
| Critical | 0 |
| High | 5 |
| Medium | 18 |
| Low | 6 |

Suspected risks and unverified controls are listed separately and are not counted as confirmed vulnerabilities.

### Top five launch blockers

1. **H-01 - Migration/deployment state is not reproducible or remotely verified.** The worktree replaces tracked migration versions with untracked files, the prior real push encountered a duplicate `040` ledger key, and the safe dry-run could not authenticate.
2. **H-02 - Notification outbox jobs have no worker.** Reservation confirmation/status emails can remain pending forever.
3. **H-03 - No current backup/restore/rollback evidence.** The prior production operations documents are deleted in the current worktree and no automation or restore test is present.
4. **H-04 - Production payment activation is unavailable.** Checkout records a manual request and the webhook returns `503` in production.
5. **H-05 - Generated Python can be executed in-process if a production flag is enabled.** The code acknowledges that no hard timeout can be enforced.

### Strongest areas

- Cookie-based auth uses `HttpOnly`, production-secure cookies, signed session activity, refresh handling, origin validation, and signed double-submit CSRF tokens (`backend/services/auth_service.py:85`, `backend/services/request_security.py:166`).
- Tenant access is resolved from the authenticated local user plus active membership, not a client tenant ID (`backend/services/tenant_service.py:10`). Builder writes explicitly reject admin account-access sessions.
- Builder project reads and writes are tenant-scoped, bounded, revision-aware, and publishing uses a locked atomic database function (`backend/routes/builder_routes.py:1043`, `supabase/migrations/045_add_platform_safety.sql:78`).
- Public runtime responses use only `published_schema`; draft preview is a separate authenticated/local path (`backend/routes/public_site_routes.py:1077`, `frontend/src/components/PageBuilder/runtime/TenantSiteRuntime.jsx:561`).
- Uploads validate size, extension and magic bytes, generate random names, and enforce resolved path boundaries (`backend/routes/builder_routes.py:878`, `backend/routes/user_routes.py:41`).
- Tests cover auth hardening, tenant-aware builder routes, publishing, reservations, account lifecycle, notification outbox primitives, corrupt draft preservation, cross-tab revisions, and transient drag/resize commits.

### Largest unknowns

- Live Postgres grants, RLS policies, function ownership and storage policies could not be queried: the catalog checker had no Postgres connection URL.
- The Supabase migration dry-run could not authenticate, so local SQL was not compared with the actual remote execution plan.
- No restore drill, browser E2E suite, load test, screen-reader/keyboard session, real email-delivery test, or production observability evidence exists in the repository.
- CDN/TLS/reverse-proxy configuration outside this repository was not available; headers or monitoring could exist externally but cannot be credited without evidence.

## Verification Record

| Check | Result |
|---|---|
| `npm run lint` | Pass with 3 React hook dependency warnings in `TenantSiteRuntime.jsx:840`, `:858`, and `:892` |
| `npm test` | Pass: 23 files, 111 tests; jsdom warns that `window.open` is not implemented |
| `npm run theme:audit` | Pass (also run by build) |
| `npm run build` | Pass; chunk-size warning and large CSS/media artifacts |
| Backend `pytest -q` | Pass: 326 tests and 46 subtests; 31 dependency deprecation warnings |
| Backend compile | Pass; one third-party `ipywidgets` syntax warning |
| `pip check` | Pass: no broken requirements |
| `npm audit --omit=dev --json` | Pass: 0 production dependency advisories across 22 production packages |
| Python vulnerability audit | Not run: `pip-audit` is not installed |
| Migration mirror check | Pass: 48 files per tree; warnings for identical historical `013`/`014` |
| Supabase CLI | Installed `2.101.0`; newer `2.109.1` reported available |
| `supabase migration list` | Local/remote version numbers `001` through `048` aligned; names/content were not proven |
| `supabase db push --dry-run --include-all` | Unverified: temporary login-role authentication failed; stopped without applying changes |
| Live RLS catalog checker | Unverified: no `SUPABASE_DB_URL`/equivalent available |
| `npm run test:e2e` | Fail as a usable E2E suite: no Playwright config/tests; it discovers Vitest files and ends with no tests |

No database reset, real push, migration, record mutation, storage deletion, browser-storage clearing, or production-affecting action was performed by this review.

## 2. Architecture Map

### Repository responsibilities

| Path | Responsibility | Notes |
|---|---|---|
| `frontend/` | React 19 SPA built by Vite 8 | npm lockfile; Node 22 Docker image; CI uses Node 20 |
| `frontend/src/App.jsx` | Root session, language, theme and route composition | Route families are lazy-loaded |
| `frontend/src/routes/` | Public, tenant runtime, user workspace and admin route boundaries | UI guards are secondary to backend auth |
| `frontend/src/components/PageBuilder/` | Builder core, workspace, tabs, previews, public runtime and data workspace | Several very large modules and CSS bundles |
| `frontend/src/i18n/`, `frontend/src/content/` | Centralized locale resources and content modules | Coverage is incomplete; hardcoded and corrupt Arabic remains |
| `frontend/src/utils/apiClient.js` | Credentialed API transport, CSRF header and single-flight refresh | Access/refresh tokens are not stored in browser storage |
| `backend/app.py` | FastAPI application, middleware and router composition | Synchronous Supabase client work runs in FastAPI threadpool |
| `backend/routes/` | Auth, user, admin, billing, builder and public HTTP handlers | Some handlers contain substantial business logic |
| `backend/services/` | Auth, tenant, audit, rate limit, readiness, notification, billing and storage services | Primary trusted business boundary |
| `backend/data_analysis/` | Upload parsing, cleaning, analysis, visualization and AI analysis | CPU/memory-heavy parsing remains in API process |
| `backend/tests/` | Backend unit/route tests | Extensive mocked coverage; no live RLS suite in CI |
| `database/migrations/` | Application migration mirror | Must match Supabase tree by logical content |
| `supabase/migrations/` | Supabase CLI migration source | 48 current files in working tree |
| `scripts/check_migrations.py` | Local migration mirror/order validator | Recognizes the historical `004`/`005` naming swap |
| `docker-compose.yml` | Redis, backend and frontend local/container topology | No worker or container health checks |
| `.github/workflows/frontend-check.yml` | Only CI workflow | Builds frontend only |

No Edge Functions, cron definitions, scheduler, message broker beyond Redis rate limiting, or outbox worker were found.

### Runtime map

```text
Browser
  -> nginx/Vercel SPA
  -> React route family
  -> apiClient (cookies + X-CSRF-Token)
  -> reverse proxy /api
  -> FastAPI CORS, body-limit, origin and CSRF middleware
  -> route authentication / TenantContext / admin policy
  -> Supabase Auth (anon client) and PostgREST/Storage (service client)
  -> Postgres tables, RLS and SECURITY DEFINER RPCs

Public visitor
  -> /site/:subdomain/* React runtime
  -> GET /public/sites/:subdomain
  -> resolved website_settings tenant
  -> latest non-archived published builder project
  -> published_schema only
```

### Requested lifecycle map

1. **Entry:** public React routes render marketing/auth pages; `/site/:subdomain` renders tenant sites; workspace routes require hydrated user state.
2. **Authentication:** FastAPI calls Supabase Auth, writes access/refresh cookies, returns a CSRF token, and refreshes through `/auth/refresh`.
3. **Frontend/API:** `apiClient` sends `credentials: include`; unsafe methods attach the signed CSRF token.
4. **Supabase:** backend anon client handles user-auth operations; service-role client performs privileged table/storage work after backend authorization.
5. **Project load/save:** backend selects `builder_projects` by both UUID and trusted `tenant_id`; frontend normalizes schema, saves local backups, and PUTs with `expected_revision`.
6. **Draft sync:** localStorage uses a per-user/project key, a backup key, timestamps/revisions and `BroadcastChannel`; busy/dirty editors queue external drafts.
7. **Publish:** backend revalidates schema, URL, routes, IDs and entitlement, then calls `publish_builder_project_atomic` with expected revision.
8. **Published render:** public endpoint resolves tenant/site and returns published schema; React runtime renders it independently of editor drafts.
9. **Files:** avatars go to the public Supabase `avatars` bucket; builder images go to tenant-scoped local public storage; datasets/charts remain private and auth-scoped.
10. **Tenant separation:** authenticated local user `tenant_id` plus active `tenant_memberships` row forms `TenantContext`; each sensitive query adds the trusted tenant filter.
11. **Admin access:** system admins have MFA policy and explicit account-access code/session workflows; builder write/admin helpers reject impersonation context.
12. **Trust boundaries:** browser input, public tenant content, upload bytes, provider callbacks and generated AI code are untrusted. FastAPI authorization and database/RPC constraints are trusted; live RLS remains unverified.

### Ownership and maintainability pressure

- `PageBuilder.jsx` is about 190 KB, `DataAnalysisWorkspace.jsx` about 104 KB, `FormsTab.jsx` about 93 KB, and `TenantSiteRuntime.jsx` about 76 KB. State, rendering, persistence and business rules are coupled.
- `backend/routes/public_site_routes.py` combines tenant auth, site resolution, form validation, reservation idempotency/cancellation and notifications.
- `backend/routes/builder_routes.py` combines schema validation, files, reservations, projects, submissions and publishing.
- Builder schemas are correctly shared through helper modules, but editor/runtime/form-preview rendering still duplicates behavior. Divergence risk is high without cross-render contract tests.

## 3. Data Flow Map

### Account creation

```text
Signup form -> POST /auth/signup -> rate limit + password/terms validation
  -> Supabase Auth identity -> pending local user/onboarding rows
  -> verification email -> provider confirmation
  -> provision_verified_account RPC -> tenant + membership + active user
  -> HttpOnly session cookies
```

### Builder save and publish

```text
Editor action -> transient UI state -> one project commit
  -> debounced local primary + previous-draft backup
  -> PUT /builder/projects/:id {expected_revision, draft_schema}
  -> TenantContext + tenant/project filter
  -> revision compare -> draft_revision + 1

Publish -> route/ID/URL/schema/entitlement validation
  -> publish_builder_project_atomic
  -> row lock + expected revision
  -> copy draft_schema to published_schema
  -> public endpoint reads published_schema only
```

### Public form/reservation

```text
Published form -> public rate limit + honeypot + timing check
  -> resolve published project and declared form/block
  -> field and JSON bounds
  -> builder_form_submissions OR atomic builder reservation RPC
  -> notification_outbox pending row
  -X no deployed worker consumes email rows
```

### Storage

```text
Avatar -> authenticated owner -> <=5 MB + magic bytes -> random file
  -> public avatars/users/:auth_id/* -> public read

Builder image -> active tenant writer -> <=25 MiB + magic bytes
  -> local uploads/tenant_:tenant_id/builder_assets/:random -> constrained public route

Dataset -> authenticated matching user/tenant -> bounded multipart upload
  -> private_uploads/tenant_:tenant/user_:user -> parser/analysis -> private chart route
```

## 4. Security Findings

### H-01 - Migration state is not reproducible or fully verified

- **Severity/confidence:** High / confirmed
- **Evidence:** current `git status`; `scripts/check_migrations.py`; prior CLI error `schema_migrations_pkey version=040`; failed dry-run.
- **Affected flow:** deployment, schema changes, rollback.
- **Cause:** tracked `040` and `044`-`046` files are deleted while renumbered `044`-`048` files are untracked in both migration trees. Version listing aligns, but names/content on remote were not established. A previous real push tried to reinsert version `040` after its SQL objects already existed.
- **Failure scenario:** a fresh checkout omits untracked migrations, or another environment applies different SQL under a version already recorded remotely, causing partial deployment or a blocked release.
- **Fix:** freeze schema changes; reconcile the ledger using a documented, non-destructive migration-history repair approved for the exact remote state; commit both mirrored trees and validator changes; never rewrite already-applied SQL.
- **Verify:** clean-clone mirror check, hashes by logical migration, `supabase migration list`, catalog/version-name query, and authenticated `db push --dry-run --include-all` showing no unexpected operations.

### H-05 - Production can be configured to execute generated Python in-process

- **Severity/confidence:** High / confirmed configuration hazard
- **Evidence:** `backend/data_analysis/ai/settings.py:103`, `backend/data_analysis/ai/sandbox.py:63`, `:87`, `:90`.
- **Affected flow:** AI data analysis.
- **Cause:** production defaults `AI_ALLOW_LOCAL_EXEC` off, which is good, but no startup/readiness rule forbids turning it on. The sandbox calls `exec`; its own comment states an in-process hard timeout is impossible.
- **Failure scenario:** a production misconfiguration enables generated code. AST restrictions reduce ordinary abuse but do not provide OS isolation, memory limits or a killable timeout; crafted/generated workloads can exhaust or compromise the API process.
- **Fix:** make production startup fail when local exec is enabled. Run generated code only in an ephemeral no-network worker/container with CPU, memory, process, filesystem and wall-clock limits; prefer predefined non-code plans.
- **Verify:** production config test, adversarial sandbox suite, forced infinite/large-memory tasks terminated outside the API process, and network/filesystem denial tests.

### M-01 - General web responses lack required security headers

- **Severity/confidence:** Medium / confirmed
- **Evidence:** `frontend/nginx.conf:1`, `frontend/vercel.json:1`, `backend/app.py:52`.
- **Affected flow:** every frontend and API response.
- **Cause:** no repository configuration sets CSP, HSTS, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy` or frame protection. Only private chart responses are hardened (`backend/data_analysis/routes/visualization_routes.py:25`).
- **Failure scenario:** clickjacking and a larger blast radius for an injection or compromised dependency; MIME/referrer/browser-feature defenses are absent.
- **Fix:** define headers at the actual edge/proxy, start with report-only CSP, use nonces/hashes where needed, and add route-specific cache policy.
- **Verify:** integration test and deployed `curl -I`; CSP violation reporting before enforcement.

### M-02 - Two legacy SECURITY DEFINER functions have unsafe defaults

- **Severity/confidence:** Medium / confirmed
- **Evidence:** `supabase/migrations/004_create_get_tables_function.sql:1`; `006_create_get_columns_function.sql:1`, `:19`.
- **Affected flow:** anonymous/authenticated database RPC metadata access.
- **Cause:** `get_tables` and `get_columns` are `security definer` without explicit `SET search_path`; `get_columns` is granted to `anon` and `authenticated`, and no later revocation was found.
- **Failure scenario:** callers enumerate the full public schema. The missing safe search path violates the project requirement for all definer functions and increases object-shadowing risk.
- **Fix:** add a new forward migration that revokes unnecessary execution and recreates/alters functions with a minimal explicit search path and qualified identifiers. Do not edit historical files.
- **Verify:** live `pg_proc.proconfig`, owner and ACL query; anon/authenticated RPC denial tests.

### M-03 - Live RLS and storage policy state is unverified

- **Severity/confidence:** Medium / confirmed verification gap
- **Evidence:** `backend/scripts/verify_rls_grants.py:1` exited because no Postgres URL was available; local migration review only.
- **Affected flow:** all tenant records and storage.
- **Cause:** repository SQL enables RLS and has generally scoped policies, but the actual remote catalog, grants, function ACLs and storage policies were not read.
- **Failure scenario:** migration drift or a manual dashboard change leaves effective production access broader than source control.
- **Fix:** provide read-only catalog credentials in a protected CI/manual launch job; extend the checker to all user-facing tables, functions and storage policies.
- **Verify:** catalog output archived as a deployment artifact plus anon/authenticated cross-tenant integration tests.

### L-01 - Password policy only enforces length

- **Severity/confidence:** Low / confirmed
- **Evidence:** `backend/services/password_policy.py:6`.
- **Affected flow:** signup, reset, password change and tenant visitor registration.
- **Cause:** 8 to 1024 characters are accepted; no breached-password screening is evidenced.
- **Risk:** users can select common compromised passwords, although provider rate limits, MFA and secure sessions reduce impact.
- **Fix:** reject known-compromised passwords using a privacy-preserving service or local corpus; allow long passphrases and avoid arbitrary composition rules.
- **Verify:** shared frontend/backend policy tests and compromised-password cases.

### L-08 - Remote dataset SSRF defense has a DNS rebinding gap if enabled

- **Severity/confidence:** Low / suspected, not enabled by default
- **Evidence:** `backend/data_analysis/io/data_reading.py:627`, `:685`, `:705`.
- **Affected flow:** optional remote dataset import.
- **Cause:** host IPs are validated, then `requests` resolves the hostname again for the connection. Redirects are revalidated and private IPs are blocked, which is otherwise strong.
- **Failure scenario:** a hostile DNS answer changes between validation and connection.
- **Fix:** keep feature disabled until connection is pinned to a validated address with hostname/TLS verification, or proxy through an allowlisted fetch service.
- **Verify:** DNS-rebinding test and private/metadata endpoint denial through redirects.

### Security strengths and negative findings

- No service-role key reference was found in frontend source or tracked build configuration. Tracked env files do not contain observed secret values; repository history was not exhaustively scanned.
- No `dangerouslySetInnerHTML`, dynamic SQL, shell command execution, unrestricted SVG/HTML upload, or public draft endpoint was found.
- CORS is credentialed but restricted to configured exact origins (`backend/app.py:93`).
- Public form and reservation payloads are bounded; spreadsheet exports sanitize formula cells (`backend/routes/public_site_routes.py:399`, `backend/services/spreadsheet_security.py`, `DataAnalysisWorkspace.jsx:1491`).
- Remote datasets are disabled by default, HTTPS-only by default, redirect-limited, size-limited and private-address filtered.

## 5. Frontend Findings

### M-07 - The declared browser E2E test command is not a working suite

- **Evidence:** `frontend/package.json:13`; no `playwright.config.*` or E2E files. `playwright test` crawls Vitest tests and ends with `No tests found`.
- **Impact:** registration, session refresh, two-tab editing, drag/resize, publish, public submission, mobile navigation and keyboard use are not verified in a real browser.
- **Fix/verify:** add a Playwright config with a dedicated `e2e/` test directory and deterministic test environment; make zero tests fail CI; cover the launch-critical journeys.

### M-08 - No application or tenant-runtime error boundary

- **Evidence:** no `ErrorBoundary`, `componentDidCatch` or `getDerivedStateFromError` in `frontend/src`; root composition in `frontend/src/App.jsx:621` only uses Suspense.
- **Impact:** a rendering exception can blank the entire workspace or a customer-published site with no recovery UI or report identifier.
- **Fix/verify:** route-family boundaries plus a narrow runtime section boundary; test thrown lazy/runtime components and retry/navigation recovery.

### M-09 - Public runtime has stale-closure lint warnings

- **Evidence:** `TenantSiteRuntime.jsx:840` omits `activePage`, `:858` omits `isPublicRuntime`, and `:892` omits `goToPage`.
- **Impact:** route, authentication or page navigation effects can use stale state after in-place navigation.
- **Fix/verify:** stabilize callbacks or include dependencies; add route-transition and auth-state regression tests; lint with warnings treated as errors in CI.

### M-10 - Modal keyboard/focus management is incomplete

- **Evidence:** `PageDeleteConfirmModal.jsx:18`, `SubscriptionStatusModal.jsx:25`, and `PageBuilderModals.jsx:75` set dialog roles but have no initial focus, focus trap, Escape handling or focus restoration.
- **Impact:** keyboard and screen-reader users can move behind the modal or lose their place.
- **Fix/verify:** a shared accessible dialog primitive; keyboard-only tests for open, Tab/Shift+Tab, Escape and return focus. Existing global focus rings and reduced-motion rules are strengths.

### M-11 - Arabic output is incomplete and in places corrupt

- **Evidence:** mojibake at `frontend/src/components/MainPages/BasePlansPage.jsx:209`, `CustomPlanPage.jsx:75`, `backend/data_analysis/assisted/assisted_analysis.py:26`, and `backend/data_analysis/core/analysis_core.py:88`; many UI messages remain hardcoded in `PageBuilder.jsx:742`, `:2080`, `:2091` and `PageBuilderModals.jsx:89`.
- **Impact:** Arabic users see unreadable text or English-only builder status/errors despite the centralized locale/content system.
- **Fix/verify:** move product UI strings into the canonical i18n/content schema, repair source encoding, and add a repository-wide mojibake/static-literal audit plus Arabic flow snapshots.

### M-12 - Production assets and CSS are oversized

- **Evidence:** build output: `vendor-three` 523.59 KB (131.28 KB gzip), PageBuilder CSS 528.41 KB (64.97 KB gzip), main CSS 975.07 KB (124.70 KB gzip), `madar_header.svg` about 1.21 MB (912 KB gzip), and a JPEG about 1.54 MB.
- **Impact:** slow first load and route transitions on mobile; CSS parse/match cost affects every route.
- **Fix/verify:** optimize/rasterize the logo where appropriate, responsive image variants, remove legacy/duplicate CSS, split builder CSS by route, and set bundle budgets. Measure Lighthouse/Web Vitals on mid-tier mobile.

### M-13 - Core frontend modules are too large

- **Evidence:** `PageBuilder.jsx` ~190 KB, `DataAnalysisWorkspace.jsx` ~104 KB, `FormsTab.jsx` ~93 KB, `TenantSiteRuntime.jsx` ~76 KB.
- **Impact:** reviewability, rerender analysis, merge conflict rate and behavior parity suffer; one change has a broad regression surface.
- **Fix/verify:** extract state-machine/domain hooks and renderer contracts incrementally behind current tests; do not rewrite persistence schemas.

### M-16 - Published tenant sites have static document metadata

- **Evidence:** `frontend/index.html:1` has only `<title>Madar>` and no description/Open Graph fields; `TenantSiteRuntime.jsx` does not update document metadata. `robots.txt` and `sitemap.xml` are static for `madarportal.com`.
- **Impact:** every tenant site has weak/incorrect SEO and social previews; client rendering may not be indexed consistently.
- **Fix/verify:** tenant-aware title/description/canonical/OG metadata and server/edge rendering or prerendering strategy; tenant sitemap/robots policy; crawler tests.

### L-02 - Legacy POST aliases exist for reads

- **Evidence:** `backend/routes/user_routes.py:142`, `admin_profile_routes.py:46`.
- **Impact:** expands CSRF/routing surface and perpetuates ambiguous API semantics; aliases are excluded from schema.
- **Fix:** deprecate with telemetry and remove only after client usage is proven zero.

### L-03 - Browser payloads expose internal IDs

- **Evidence:** `backend/services/auth_service.py:251` returns local `id`, `auth_id` and `tenant_id`.
- **Impact:** low-value metadata disclosure and temptation for clients to rely on identifiers; trusted authorization still ignores them.
- **Fix:** return only identifiers required by current UI and retain backend ownership checks.

## 6. Backend Findings

### H-02 - Notification outbox has no deployed consumer

- **Severity/confidence:** High / confirmed
- **Evidence:** `claim_notifications` is defined only at `backend/services/notification_outbox_service.py:179`; enqueue calls exist in builder/public-site flows; `docker-compose.yml:1` contains only Redis, backend and frontend.
- **Affected flow:** reservation confirmation, cancellation/status email and any queued email/web-push delivery.
- **Failure scenario:** API reports successful reservation work while pending outbox rows are never sent. There is no retry/dead-letter visibility or worker health signal.
- **Fix:** implement an independently deployable idempotent worker using claim/finish RPCs, bounded exponential retry, terminal dead-letter state, metrics and graceful shutdown. Add it to deployment and readiness.
- **Verify:** integration test enqueue -> claim -> send -> finish, crash-after-send idempotency, retry/dead-letter behavior and alert on oldest pending age.

### H-04 - Production billing cannot activate paid access

- **Severity/confidence:** High / confirmed if paid plans are in launch scope
- **Evidence:** `backend/routes/billing_routes.py:68` returns `checkout_available: false`; `:126` webhook returns `503` in production at `:139`.
- **Affected flow:** plan checkout, entitlement activation, renewals and payment state changes.
- **Failure scenario:** users select advertised plans but cannot pay; access remains pending/manual, or operational staff attempt unsafe manual changes.
- **Fix:** either explicitly launch as manual-request beta with no payment claims, or integrate a provider-hosted checkout and cryptographically verified, replay-safe webhook before paid launch.
- **Verify:** provider sandbox E2E for success/failure/refund/cancel/replay/out-of-order events and entitlement reconciliation.

### M-04 - Readiness omits critical dependencies and containers have no health checks

- **Evidence:** `backend/services/readiness_service.py:189` checks database/auth/schema/Redis/local directories/admin MFA only; `docker-compose.yml` has no `healthcheck` and `depends_on` is start-order only.
- **Impact:** a deployment can be "ready" with broken SMTP, missing outbox worker, invalid AI/provider config or unavailable billing. Frontend can start before backend is healthy.
- **Fix/verify:** distinguish required/optional capabilities, add worker/SMTP probes and container/orchestrator health checks, then test degraded modes.

### M-05 - Production observability is insufficient

- **Evidence:** no Sentry/OpenTelemetry/metrics integration or request/correlation middleware found; logging is stdlib event strings; no alert rules or dashboards in repo. Audit logging exists and sanitizes metadata (`backend/services/audit_service.py:43`).
- **Impact:** cross-service failures, latency, 5xx spikes, outbox backlog, auth attacks and tenant-specific incidents are difficult to diagnose.
- **Fix/verify:** structured JSON logs with request ID and tenant-safe context, exception monitoring, RED metrics, audit-log retention, dashboards and alert tests. Never log tokens or raw form data.

### M-14 - CPU/memory-heavy data parsing runs in the API process

- **Evidence:** `backend/data_analysis/io/data_reading.py:148` calls pandas/openpyxl synchronously and `:248` contains the worker TODO; upload limits are spread across body middleware and data service.
- **Impact:** crafted or merely complex spreadsheets can occupy a FastAPI worker, consume memory and degrade unrelated users. The in-process AI execution concern compounds this.
- **Fix/verify:** resource-limited worker queue, consistent effective size limits, per-tenant concurrency limits and cancellation; load tests with compressed/complex workbooks.

### M-15 - Public form submissions lack idempotency and lifecycle policy

- **Evidence:** forms insert directly at `backend/routes/public_site_routes.py:1173`; reservations have request-hash/idempotency handling around `:1289`, but forms do not. `builder_form_submissions` has statuses but no retention/deletion policy in migrations.
- **Impact:** network retries can create duplicate submissions/notifications; sensitive form data can remain indefinitely.
- **Fix/verify:** optional idempotency key with tenant/project/form/request hash, duplicate-safe response, explicit retention/erasure policy and audited admin deletion/archive workflow.

### M-17 - Backend dependency builds are not fully reproducible

- **Evidence:** `backend/requirements.txt` mixes exact pins with unpinned `pandas`, `numpy`, `openai`, `google-genai`, etc.; Docker uses plain `pip install`; frontend Docker and CI use `npm install` rather than `npm ci` (`backend/Dockerfile:5`, `frontend/Dockerfile:10`, workflow `:24`).
- **Impact:** the same commit can resolve different transitive code; rollback and vulnerability triage become unreliable.
- **Fix/verify:** lock all production Python transitive versions with hashes and use immutable installs; use `npm ci`; generate SBOMs and scan both ecosystems in CI.

### Endpoint matrix

The application registers 103 method/path decorators, including 12 compatibility aliases. `/api` is a frontend proxy prefix and is stripped before FastAPI. The table groups endpoints only where authentication, validation, tables and side effects are identical; every registered route family is represented.

| Method/path(s) | Auth and authorization | Input/validation | Tables/storage and side effects | Rate/failure/security notes |
|---|---|---|---|---|
| `GET /`, `GET /` server-status | Public | none | none | 200 static; duplicate route ownership should be cleaned |
| `GET /health/live` | Public | none | none | Liveness only |
| `GET /health/ready` | Public | none | readiness checks | 503 when a checked dependency fails; incomplete dependency set |
| `GET /uploads/tenant_{tenant_id}/builder_assets/{filename}` | Public published asset | positive tenant; exact random filename regex and extension | tenant local file | 404 on invalid/missing; path boundary enforced |
| `POST /auth/signup` | Public | Pydantic email, password policy, terms, normalized plan/subdomain | Supabase Auth, users, pending onboarding, verification attempts | auth limit; compensating cleanup; provider failures mapped |
| `GET /auth/email-verification/status` | Signed pending context or provider token | bounded context | Auth/users/onboarding | avoids arbitrary email lookup |
| `POST /auth/email-verification/resend` | Pending context | optional email must match context | verification attempts, email provider | rate/anti-enumeration behavior |
| `POST /auth/email-verification/clear-context` | Public browser context | none | clears pending cookie only | origin checked |
| `POST /auth/login` | Public | email/password | Auth/users/security settings/audit | auth rate limit; generic invalid credentials; MFA branch |
| `GET /auth/user_status` | Session | active local user | users/membership | no refresh; 401 on expiry |
| `POST /auth/refresh` | Refresh cookie | signed cookies/activity | Auth/users | single-flight client; rotates session/CSRF |
| `PUT /auth/password/change` | Active user | current password + shared new policy | Auth/audit | reauthenticates canonical email; session update |
| `POST /auth/log_out` | Cookie session optional | none | clears auth/CSRF/activity cookies | local Supabase session revocation is not evidenced |
| `POST /auth/forgot-password` | Public | generic payload; canonical email and durable nonce | reset requests/Auth email | rate limit and enumeration resistance |
| `POST /auth/password-reset` | Provider recovery token + durable request token | password policy, claim RPC | Auth/reset requests/audit | one-time claim/finish; 503 on provider failure |
| `GET /auth/mfa/status`, `GET /auth/mfa/factors` | Active user | none | Auth MFA/security settings | provider failure mapped |
| `POST /auth/mfa/enroll`, `POST /auth/mfa/enroll/verify` | Active user | bounded factor/code | Auth MFA/security/audit | enrollment state checks |
| `DELETE /auth/mfa/factors/{factor_id}` | Active user | bounded factor; last-factor policy | Auth MFA/security/audit | ownership by authenticated provider session |
| `POST /auth/mfa/login/challenge`, `POST /auth/mfa/login/verify` | Signed pending MFA cookie | factor/challenge/code | Auth MFA/users/audit | 5-minute pending context; issues final cookies |
| `GET /users/{user_id}/info`, legacy `POST` | Matching regular user | path ID must match session | users/features | 403 mismatch; legacy excluded from schema |
| `PUT /users/{user_id}/profile` | Matching regular user | Pydantic + canonical email restrictions + URL validation | users/Auth/audit | rejects partial unsafe email updates |
| `POST /users/{user_id}/avatar` | Matching regular user | <=5 MB, PNG/JPEG/WebP magic bytes | public avatars bucket/users | upload rate; rollback new file on DB failure |
| `GET/PUT /website/settings`, `/users/{user_id}/website/settings` | Active tenant member; path user must match | normalized subdomain, URLs, field lengths | website_settings | trusted tenant key; duplicate aliases |
| `POST /billing/checkout`, `/users/{user_id}/billing/checkout` | Active tenant member/matching user | plan literals; protected fields ignored | features/audit | records pending manual request only |
| `GET /billing/current` | Active tenant member | none | features | tenant-scoped |
| `POST /billing/webhook` | Shared secret only outside production | typed event, constant-time secret compare | billing events/features/audit | always 503 in production by design |
| `GET /notifications` | Regular user | bounded page/limit filters | user_notifications/events | user-scoped pagination |
| `POST /notifications/{id}/read`, `/notifications/read-all` | Regular user | ID | user_notifications | user filter; idempotent update behavior |
| `GET /notifications/push-public-key` | Public | none | none | exposes only public VAPID key |
| `POST/DELETE /notifications/push-subscriptions` | Regular user | typed endpoint/keys | web_push_subscriptions | user/tenant scoped |
| `GET /admin/profile/info`, legacy `POST`; `PUT /admin/profile/profile`; `POST /admin/profile/avatar` | System admin, MFA policy | profile/avatar validation | users/Auth/avatars/audit | separate admin checks |
| `GET /admin/users`; `PATCH /admin/users/{id}/user-type`; `DELETE /admin/users/{id}` | System admin | pagination/type/target safeguards | users/Auth/memberships/audit | last-admin and self/target safety in service/RPC |
| `POST /admin/billing/features` | System admin | typed tenant/plan/payment state | features/audit | explicit privileged activation |
| `POST /admin/account-access/generate`, `/verify`, `/end` | System admin + MFA; target grant/session | email/code; attempt/expiry limits | access requests/sessions/audit/email | signed HttpOnly access cookie; builder writes prohibited |
| `POST /builder/assets/upload` | Active tenant builder writer | bounded image bytes/magic | tenant builder asset file/audit | upload rate; random non-overwrite name |
| `GET /builder/reservations`, `GET /builder/reservations/{id}` | Active tenant member | limit <=100/status/project filters | reservations | tenant-scoped, bounded |
| `PATCH /builder/reservations/{id}/status` | Builder writer | status literal | reservations/audit/outbox | enqueue can silently remain pending without worker |
| `GET/POST /builder/projects` plus `/users/{user_id}/builder/projects` aliases | Active member for read; writer for create | pagination; name/slug/schema <=2 MB and URL validation | builder_projects/audit | tenant-scoped; alias user must match |
| `GET/PUT/DELETE /builder/projects/{project_id}` plus user aliases | member read; writer update; owner/admin archive | UUID, expected revision, schema/status restrictions | builder_projects/audit | tenant filter; conflict on stale revision; DELETE is soft archive |
| `GET /builder/projects/{project_id}/form-submissions[/{id}]` plus aliases | Active tenant member | bounded pagination/status | form_submissions | project + tenant filters |
| `PUT .../form-submissions/{id}` plus alias | Builder writer | status literal | form_submissions/audit/notifications | tenant/project/submission filter |
| `POST .../publish`, `POST .../unpublish` plus aliases | Builder writer + active entitlement | expected revision, validated schema/subdomain | builder_projects/features/audit; atomic publish RPC | 409 conflict; publish never trusts client tenant/status |
| `POST /public/contact` | Public | name/phone/message bounds | contacts | public rate limit; service insert |
| `POST /public/sites/{subdomain}/auth/register`, `/login` | Public tenant visitor | normalized tenant, email/password | Auth/users/tenant_site_memberships | auth rate limit; visitor account kind |
| `GET .../auth/status`, `POST .../auth/logout` | Tenant visitor session | tenant membership | users/site membership; cookie clear | tenant-specific membership check |
| `GET /public/sites/{subdomain}` | Public | normalized subdomain | website_settings/builder_projects | public limit; returns published schema only |
| `POST /public/sites/{subdomain}/forms/{form_id}/submissions` | Public; optional visitor context | published form existence, honeypot/time, field/type/size validation | form_submissions | public submission limit; no idempotency |
| `POST /public/sites/{subdomain}/events` | Public | published block, payload limits, idempotency, reservation timing | reservations via RPC/outbox | replay-safe reservations, signed cancel token |
| `POST /public/reservations/{id}/cancel` | Public possession of token | signed/hashed token and expiry | reservations/outbox | atomic RPC; rate limited |
| `POST /users/{user_id}/data/read`, `/export`, `/upload` | Matching active tenant user | private scoped path or bounded CSV/XLS/XLSX | private uploads; parsed/export data | workspace/upload rate; body/parser bounds |
| Eight `POST /users/{user_id}/cleaning/*` routes: `inspect`, `prepare-report`, `statistics`, `missing-report`, `quality-report`, `column-types`, `apply`, `export` | Matching active tenant user | private path + typed action list | private dataset, generated CSV | workspace rate; synchronous pandas |
| `GET .../analysis/catalog`; `POST .../analysis/run`, `/assist`, `/ai` | Matching active tenant user | typed request; plan/column/result bounds | private data, AI usage daily/provider | workspace + AI quota; local exec must remain off in prod |
| `POST .../visualization/columns/profile`, `/create`; `GET .../charts/{chart_id}` | Matching active tenant user | private path, chart config/path validation | private charts | generation rate; private no-store/CSP response headers |

Common failures are Pydantic `422`, safe `4xx` application errors, `409` conflicts and `503` dependencies. Route code generally logs error type rather than provider details. Several broad `except` blocks intentionally suppress implementation details, but request IDs are absent.

## 7. Database and Supabase Findings

### Important table inventory

| Table | Purpose and key/tenant ownership | Constraints/indexes | RLS/effective source policy |
|---|---|---|---|
| `users` | integer PK; Supabase `auth_id`; primary/current `tenant_id` | unique auth ID and normalized email | enabled; own-row policies; backend service for privileged work |
| `contacts` | public contact inbox; integer PK | timestamps | RLS enabled and anon/auth grants revoked in `005`; service insert |
| `tenants` | integer `tenant_id` PK | name/domain fields | member-select policy via membership |
| `tenant_memberships` | bigint PK; tenant/user/auth FKs | unique `(user,tenant)` and `(auth,tenant)`; tenant/auth indexes | same-tenant authenticated select |
| `website_settings` | integer PK; unique tenant site config | unique tenant and legacy user linkage | tenant-member select/insert/update; anon revoked |
| `features` | bigint PK; tenant entitlement | unique full-platform/individual plan indexes; billing-state index | authenticated tenant read only; service writes |
| `builder_projects` | UUID PK; tenant FK; draft/published JSON and revisions | unique `(tenant,slug)`; tenant/status/slug indexes | tenant member CRUD policies; backend adds tenant filters |
| `builder_form_submissions` | UUID PK; tenant/project/form | tenant/project/form/submitted indexes | tenant-member select; service writes public data |
| `builder_reservations` | UUID PK; tenant/project/block | slot, idempotency and cancellation hash indexes | anon/auth revoked; service-only; atomic RPCs |
| `audit_logs` | UUID PK; nullable tenant/actor | tenant/actor/action/target indexes | service-only |
| `user_security_settings` | user PK/auth ID | MFA indexes | service-only |
| `admin_account_access_requests/sessions` | UUID PKs; admin and target FKs | token/expiry/admin/target indexes | service-only |
| `ai_usage_daily` | bigint PK; user/tenant/date | unique user/date, tenant/date index | service-only RPC increments/reservations |
| `notification_events`, `user_notifications` | UUID event/delivery rows; tenant/user FKs | event-user unique and unread indexes | service-only; backend user filters |
| `web_push_subscriptions` | UUID PK; user/tenant | active user index | service-only |
| `tenant_site_memberships` | bigint PK; visitor user/tenant/auth | unique user-tenant and auth-tenant | service-only |
| `email_verification_attempts` | UUID PK; hashed email/auth | requested-time indexes | service-only |
| `pending_account_onboarding` | UUID PK; user/auth/tenant | unique user/auth/tenant, expiry index | service-only; provisioning RPC |
| `password_reset_requests` | UUID PK; user, hashed nonce | user/date and pending/expiry indexes | service-only; claim/finish RPCs |
| `billing_webhook_events` | UUID PK; provider event | unique provider/event; status index | service-only; atomic billing RPC |
| `notification_outbox` | UUID PK; tenant/user; channel/status/payload | dedup and pending/available indexes, retention timestamp | service-only claim/finish RPCs |

Source migrations show RLS enabled on the user-facing tables and modern definer functions use `set search_path = public` plus explicit ACL revocation. Live state remains unverified (M-03).

### L-05 - Historical migration duplication and ordering debt

- `013_fix_tenant_relationships.sql` and `014_fix_tenant_relationships.sql` are content-identical; the validator warns but accepts them.
- Logical `004`/`005` names are swapped between historical trees and handled specially by `scripts/check_migrations.py`.
- **Risk:** operator confusion and fragile history tooling, not an active schema defect by itself.
- **Recommendation:** preserve applied history, document immutable hashes/names, and make the validator output the historical mapping explicitly.

### L-06 - Historical migration assigns user 1 as the only admin

- **Evidence:** `supabase/migrations/026_set_user_1_as_admin.sql:1` promotes ID 1 and demotes all other users.
- **Risk:** environment-dependent bootstrap behavior and loss of pre-existing admin roles when first applied. Later last-admin safeguards reduce current risk.
- **Recommendation:** do not edit applied SQL; document provenance and ensure current admin roster is verified through read-only launch checks. Future environments need explicit secure bootstrap.

### Schema/data-integrity observations

- Publish, billing events, account provisioning, password-reset claims, outbox claims and reservations have transaction/RPC support.
- Builder archive is a soft status transition, avoiding destructive project deletion.
- Cascade deletes exist from tenant/project to submissions/reservations and from users to membership/security rows. No production delete was executed; deletion workflows require backup and retention review.
- Large JSONB builder schemas are bounded to 2 MB in the API. Querying inside these documents is limited, but rendering/serialization cost remains a frontend concern.
- No rollback migrations are provided. For Supabase, rollback should be forward-fix plus restore procedures, not history rewrite.

## 8. Authentication and Authorization Matrix

| Action | Anonymous | Tenant visitor | Tenant member | Tenant owner/admin | System admin | Admin account-access session |
|---|---:|---:|---:|---:|---:|---:|
| Read marketing/public published site | Yes | Yes | Yes | Yes | Yes | Yes |
| Submit published form/reservation | Yes, limited | Yes, limited | Yes | Yes | Yes | Yes |
| Read tenant visitor private runtime area | No | Own site membership | No unless site member | No unless site member | No implicit bypass | No implicit bypass |
| Read own account/profile | No | Visitor status only | Yes | Yes | Yes (admin profile) | Target context where explicitly allowed |
| Read tenant projects/submissions/reservations | No | No | Active membership | Yes | No implicit cross-tenant access | Read access only where allowed |
| Create/update project and upload builder assets | No | No | `member`/`admin`/`owner` | Yes | Only through own tenant role | **Explicitly denied** |
| Archive project | No | No | No | Owner/admin | No implicit bypass | **Denied** |
| Publish/unpublish | No | No | Writer role + entitlement | Yes + entitlement | No implicit bypass | **Denied** |
| Change tenant billing | No | No | Submit own pending request | Submit own pending request | Explicit admin endpoint | No implicit bypass |
| Manage all users/admin roles | No | No | No | No | Yes + MFA policy | No |
| Generate/verify account-access code | No | No | No | No | Yes + MFA | Existing session may end itself |

Trusted enforcement is in `require_regular_user`, `TenantContext`, builder write/admin helpers, system-admin/MFA services, tenant filters and service-only/RLS database access. Hidden frontend routes are not credited as authorization.

Tenant switching is **not implemented**: `users.tenant_id` is treated as primary/current tenant and there is no switch endpoint/UI. Multi-membership schema exists, so adding switching later must use a server-validated active membership and session-bound current tenant.

Auth capabilities not present: OAuth/social login, magic-link login as a user-facing flow, invitations and general tenant switching. These are not launch defects unless promised product features.

## 9. Production Operations Findings

### H-03 - Backup, restore and rollback are not evidenced

- **Severity/confidence:** High / confirmed repository gap
- **Evidence:** current worktree deletes `docs/production-backup-restore.md`, `docs/production-launch-checklist.md`, `docs/migration-history.md` and related setup files; no backup job, restore drill or rollback automation is present.
- **Affected flow:** incident response, bad migration, accidental deletion, tenant recovery.
- **Failure scenario:** a data-loss or bad-release incident occurs and the team cannot demonstrate recovery point, recovery steps, storage restore or tested rollback.
- **Fix:** establish Supabase PITR/backup retention, export policy, storage backup, encryption/access controls, scheduled restore drills, deploy rollback and forward-migration recovery runbooks. Keep secrets out of docs.
- **Verify:** restore a sanitized backup into an isolated environment, reconcile row/object counts and application health, record drill evidence and owner approvals.

### M-06 - CI is too narrow and installs are not deterministic

- **Evidence:** `.github/workflows/frontend-check.yml:11` only installs and builds frontend; no lint, unit tests, backend tests, migration mirror check, security scan, container build or E2E. It uses Node 20 while Docker builds with Node 22.
- **Impact:** passing CI does not mean tested/auth-safe/migration-safe; runtime drift can appear only at deployment.
- **Fix/verify:** matrix or ordered jobs for clean install, theme/lint/test/build, backend tests/compile/pip check, migration check, image build, secret/SCA scan and gated E2E; align Node/Python versions.

### M-18 - File lifecycle and storage usage are unmanaged

- **Evidence:** avatar replacement attempts old-file cleanup, but builder asset upload at `backend/routes/builder_routes.py:878` has no delete/garbage-collection path tied to project archive/schema replacement. No storage quota/usage monitor exists.
- **Impact:** orphan assets accumulate indefinitely and can increase cost; public URLs remain usable after content removal.
- **Fix/verify:** reference inventory, tenant quotas, delayed mark-and-sweep with audit/restore window, storage metrics and explicit owner delete endpoint. Never infer deletion from a single failed save.

### Operational launch gaps

- No request ID, exception tracker, metrics exporter, dashboard, uptime probe, alert rules, outbox backlog alert, email bounce/delivery monitor or storage usage alert.
- Compose binds frontend/backend to localhost, which is sensible behind a proxy, but TLS, proxy trust, HSTS and deploy topology are external/unknown.
- Redis rate limiting is fail-closed by default in production and readiness rejects disabled/fail-open configuration; this is strong.
- Readiness writes temporary files into storage directories. This verifies local permissions but not Supabase avatar bucket or actual public URL reachability.
- There is no explicit worker shutdown/drain strategy because the worker itself is absent.

## 10. End-to-End Flow Findings

| # | Flow and code path | Expected result / trusted boundary | Weakness or missing verification |
|---:|---|---|---|
| 1 | Registration: `/signup` -> `SignUpPage` -> `POST /auth/signup` -> Auth/users/onboarding | pending user verifies, then atomic tenant/membership provisioning | No real provider/browser E2E; SMTP/readiness gap; current signup changes are dirty |
| 2 | Login: `/login` -> `POST /auth/login` -> MFA or cookies | generic failure, secure cookies, active verified user | Browser cookie attributes/cross-origin deployment not tested end-to-end |
| 3 | Reset: forgot/reset pages -> durable nonce + provider recovery token | one-time claim and password update | Provider callback E2E and email delivery unverified |
| 4 | Create project: dashboard/builder -> `POST /builder/projects` | trusted tenant, schema bounded | Browser/API/DB E2E absent |
| 5 | Edit project: `PageBuilder.jsx` state -> local draft -> PUT revision | complete schema retained, revision increments | Large module; only mocked/unit coverage |
| 6 | Add all elements: factory/actions/renderers | stable ID and editor/runtime parity | No exhaustive all-element contract/browser test |
| 7 | Drag/resize: pointer transient frames -> one release commit | geometry and section height atomic | Unit safety test exists; no browser pointer/touch/RTL test |
| 8 | Autosave: debounce -> local backup -> remote queue | dirty work preserved | Real offline/quota/tab-close behavior not tested |
| 9 | Reload recovery: primary/backup parser | corrupt raw data preserved, not replaced | Strong unit tests; manual browser verification missing |
| 10 | Two tabs: BroadcastChannel/storage -> dirty/busy queue | stale/self updates rejected | Strong revision unit test; server-side two-tab conflict journey absent |
| 11 | Preview: authenticated/local draft runtime | preview reflects draft without public leak | Preview route/token and all components lack browser E2E |
| 12 | Publish: validation -> atomic RPC | only published schema becomes public | Live RPC/migration/RLS state unverified |
| 13 | Update published site: edit draft -> republish expected revision | prior public version remains until successful atomic publish | No rollback/version restore UI; E2E absent |
| 14 | Submit form: public runtime -> validated insert | bounded tenant/project/form submission | no idempotency/retention; duplicate retry possible |
| 15 | View submission: responses/data route -> tenant filter | member-only scoped view and safe export | no cross-tenant live integration or browser test |
| 16 | Upload: avatar/builder/data paths | bounded magic-checked/scoped object | no malware scan, quota, orphan GC or live storage policy test |
| 17 | Delete/archive: DELETE project -> status archived | no physical project data deletion | no restore-from-archive workflow/E2E; storage remains orphaned |
| 18 | Logout: `/auth/log_out` -> cookies cleared -> UI resets | protected backend rejects further calls | provider refresh-token global revocation behavior not evidenced |
| 19 | Admin access: MFA admin -> code -> signed target session | audited, expiring, builder writes denied | email/provider E2E and break-glass runbook absent |
| 20 | Tenant switching | not supported | schema permits memberships but no trusted switch flow; do not expose UI until implemented/tested |

## 11. Test Coverage Gaps

Priority order is based on authorization and data-loss risk, not percentage.

1. **Live migration/RLS/storage suite:** clean schema apply, catalog ACLs for every table/function/bucket, anon/auth/service behavior, cross-tenant guessed IDs.
2. **Migration ledger test:** local version/name/hash versus a sanitized remote ledger, including the `040` conflict and logical mirror mapping.
3. **Browser auth journeys:** signup/verification, login/MFA, refresh race, disabled/deleted user, reset, logout and cross-origin cookie/CSRF behavior.
4. **Browser builder journey:** create, all element types, text/form editing, pointer and touch drag/resize, undo/redo, save, two-tab conflict, reload recovery, preview, publish and update.
5. **Published runtime isolation:** prove local draft and unpublished backend changes never affect anonymous site responses; test runtime exception recovery.
6. **Notification worker:** claim concurrency, provider timeouts, crash/retry, deduplication, dead-letter and backlog alert. No worker tests can be end-to-end until a worker exists.
7. **Billing provider:** signed webhook, replay, payload mismatch, out-of-order event, refund/cancel and reconciliation.
8. **Forms:** duplicate retry/idempotency, malicious strings, formula export, retention/erasure, spam timing, rate-limit behavior and notification escaping.
9. **Uploads:** real bucket policies, MIME spoof, polyglot/complex image, quota, cross-tenant guessed paths, rollback and GC safety.
10. **Resource/load tests:** complex XLS/XLSX, concurrent analysis, 2 MB builder schemas, large project serialization/rerenders and public traffic.
11. **Accessibility:** keyboard-only auth/builder/publish, dialog focus, screen-reader labels/live errors, 200% zoom, RTL, reduced motion and contrast.
12. **Deployment smoke:** image builds, `/live`, `/ready`, headers, asset caching, SPA routes, TLS, observability event and rollback.

Existing backend tests are broad but frequently mock Supabase; they do not prove live RLS. Existing frontend tests are valuable unit/jsdom tests, not full browser tests.

## 12. Remediation Roadmap

### Phase A: Launch blockers

| Work | Files/systems | Dependencies and regression risk | Verification | Complexity |
|---|---|---|---|---|
| Reconcile migration ledger and commit reproducible trees | both migration trees, `scripts/check_migrations.py`, remote migration ledger | requires read-only catalog/ledger evidence and explicit Supabase procedure; highest schema risk | clean clone, hashes, dry-run, isolated apply, catalog diff | Large |
| Establish backup/restore/rollback | Supabase project settings, storage, deployment and new runbooks | environment owners and retention/privacy policy; restore must be isolated | recorded restore drill and rollback exercise | Large |
| Deploy notification worker and visibility | outbox service, new worker entrypoint, compose/deploy, readiness | email/push providers; duplicate-send risk | crash/retry/dedup/dead-letter integration tests | Large |
| Decide launch billing mode | billing routes/content or provider integration | product/legal/provider decision; entitlement risk | manual-beta copy audit or provider sandbox E2E | Large |
| Make local AI exec impossible in prod | AI settings/sandbox/readiness/deploy | isolated worker if AI code remains; analysis compatibility | startup rejection and adversarial worker tests | Medium |
| Verify all live RLS/function/storage ACLs | verification scripts and protected launch job | read-only DB access; avoid leaking catalog secrets | archived passing catalog + cross-tenant tests | Medium |

### Phase B: Production stability

| Work | Files/systems | Risk | Verification | Complexity |
|---|---|---|---|---|
| Complete readiness/health and observability | readiness, app middleware, compose/deploy | avoid exposing sensitive component detail | degraded dependency tests, dashboards and synthetic alerts | Medium |
| Resource-isolate parsing/analysis | data analysis services and worker | job compatibility and cancellation | resource-limit/load tests | Large |
| Form idempotency and retention | public site route, new forward migration, admin workflows | schema/behavior compatibility | retry, privacy and cleanup tests | Medium |
| Error boundaries and publish/runtime recovery | App/routes/runtime | avoid hiding programming errors | thrown-component and retry tests | Small |
| Fix hook closures and complete real E2E | runtime, Playwright config/tests, CI | route/auth regressions | lint zero warnings and browser journeys | Medium |
| Storage quotas and safe GC design | upload routes/storage jobs | accidental deletion is unacceptable | dry-run reference report, delayed deletion, restore test | Large |

### Phase C: Performance and UX

| Work | Files/systems | Risk | Verification | Complexity |
|---|---|---|---|---|
| Asset/CSS budgets and image optimization | Vite, assets, builder/legacy CSS | visual/theme regressions | visual snapshots, bundle budgets, Lighthouse/Web Vitals | Medium |
| Accessible dialog primitive and keyboard audit | modals/shared components | focus regressions | keyboard + axe/screen-reader tests | Medium |
| Repair Arabic and centralize product strings | i18n/content and data-analysis output | translation/context accuracy | mojibake audit, locale snapshots, RTL flows | Medium |
| Tenant metadata/SEO | runtime, index/edge/server layer | caching and tenant isolation | crawler/OG/canonical tests | Medium |

### Phase D: Maintainability

| Work | Files/systems | Risk | Verification | Complexity |
|---|---|---|---|---|
| Split builder/runtime/data modules behind stable contracts | large PageBuilder modules | high regression if attempted as rewrite | characterization tests, small extraction patches | Large |
| Thin public/builder route modules into services | backend route/service boundaries | transaction/error mapping | route contract and service unit tests | Medium |
| Lock dependencies and create SBOM/security jobs | requirements, Dockerfiles, workflow | native package compatibility | clean image builds and SCA | Medium |
| Deprecate legacy aliases and duplicate status routes | route clients and backend | unknown client use | access telemetry and deprecation window | Small |
| Document immutable migration history/admin bootstrap | migration docs | no runtime risk | reviewer/operator sign-off | Small |

No remediation should modify persistence, authorization or migration behavior until its regression tests and remote-state evidence exist.

## 13. Production Launch Checklist

Legend: PASS is evidenced now; FAIL blocks launch; UNVERIFIED requires external/manual evidence.

| Area | Status | Launch evidence required |
|---|---|---|
| Security design/code review | FAIL | H-05, M-01 and M-02 resolved; threat-model sign-off |
| Authentication unit/route tests | PASS | local suites pass |
| Authentication browser/provider flow | UNVERIFIED | real signup/MFA/reset/refresh/logout journey |
| Authorization code paths | PASS | server tenant/admin helpers and filters reviewed |
| Cross-tenant integration | UNVERIFIED | real DB guessed-ID matrix |
| RLS/grants/functions | UNVERIFIED | live catalog checker across all objects |
| Storage policy/isolation | UNVERIFIED | live bucket/object policy tests |
| Data preservation unit tests | PASS | corrupt draft, backup, revisions and interaction tests pass |
| Full builder browser flow | FAIL | working Playwright suite including all element types |
| Published draft isolation in code | PASS | published-schema-only route reviewed |
| Published runtime E2E/recovery | FAIL | anonymous isolation and error-boundary tests |
| Form validation/export safety | PASS | bounded server validation and spreadsheet sanitization reviewed |
| Form idempotency/retention | FAIL | duplicate-safe contract and data lifecycle |
| Upload validation | PASS | size/type/magic/path checks reviewed |
| Upload lifecycle/quota | FAIL | safe GC/quota/monitoring |
| Migration mirror | PASS with warnings | local validator passes |
| Remote migration plan | FAIL | authenticated no-op/expected dry-run and ledger reconciliation |
| Database backup and PITR | UNVERIFIED | settings/retention evidence |
| Restore drill | FAIL | recorded isolated restore |
| Deployment rollback | FAIL | tested application and forward-schema rollback procedure |
| Frontend lint | PASS with warnings | zero hook warnings required |
| Frontend unit tests | PASS | 111 pass |
| Backend tests | PASS | 326 pass + 46 subtests |
| Build/theme audit | PASS with warning | bundle budget accepted or remediated |
| Dependency health | FAIL | Python SCA and deterministic locks; npm prod audit already clean |
| CI release gate | FAIL | frontend/backend/migrations/security/E2E/image jobs |
| Rate limiting | PASS in code | production Redis and proxy IP configuration smoke test |
| Email delivery | FAIL | outbox worker and provider delivery/bounce monitoring |
| Billing | FAIL for paid launch | provider flow or explicit manual-beta scope |
| Health checks | FAIL | orchestrator probes for all required services |
| Structured logging/request IDs | FAIL | correlated, redacted logs |
| Error/performance monitoring | FAIL | tracker, metrics, dashboards and alerts |
| Incident response/on-call | FAIL | owners, severity process and exercise |
| Accessibility | FAIL | dialog fixes and keyboard/screen-reader audit |
| Performance | FAIL | asset budgets plus frontend/load measurements |
| Legal/terms acceptance storage | PASS in source | migration `048` must first be reconciled and verified remotely |

## 14. Final Recommendation

**Madar should not launch to general production users in its current state.** The appropriate verdict is **Not ready**, not "high-risk and should not launch," because no confirmed critical cross-tenant exposure, credential leak, public draft leak or current data-loss bug was found, and the application has strong underlying security and data-safety mechanisms.

Before launch, the team must:

1. reconcile and verify migration history without rewriting applied migrations;
2. prove backup/restore and rollback;
3. deploy and monitor the notification worker;
4. choose and verify either an honest manual-beta billing mode or real signed provider billing;
5. prohibit in-process generated code in production;
6. verify live RLS/function/storage ACLs;
7. create a real browser E2E release gate and production observability baseline.

The large-module refactors, deeper CSS optimization, legacy alias removal and broader SEO work can wait if performance budgets and product scope explicitly permit them. The accessibility dialog defects, corrupt Arabic, runtime error boundary, form idempotency and security headers should be completed during production-stability work, before a broad public launch.

What remains unverified must not be treated as secure by absence of evidence: live database policy state, remote migration content, provider email/payment behavior, infrastructure headers/TLS, backup restore, cross-tenant integration, browser cookie behavior, performance under load and keyboard/screen-reader usability.
