# Madar Full Codebase Review — July 2026

## 1. Executive Summary

Madar has a substantial, test-backed application foundation: cookie-based authentication, CSRF and origin defenses, tenant-aware backend authorization, rate limiting, audit events, a revision-aware Page Builder, public forms and reservations, and readiness checks are all implemented. The Page Builder persistence work is notably stronger than the older architecture: explicit project routes, server-first hydration, semantic schema identity, deterministic normalization, single-flight saves, recovery isolation, bounded three-way rebase, and backend-authoritative publishing are present and covered by focused tests.

The repository is **not ready for an unqualified production SaaS deployment**. Ten P1 findings must be addressed or explicitly accepted. The most urgent security issue is a database authorization path: `public.users` remains directly updateable by an authenticated Supabase role, and the own-row policy constrains identity but not columns. A caller able to reach the Supabase data API with public client credentials could set its own `user_type` to `admin`; backend admin authorization then trusts that field. Live reachability was not tested, so this is a high-confidence static vulnerability with a deployment-dependent exploit precondition, not a confirmed live compromise.

Other immediate blockers are a duplicate migration number, anonymous delivery of the entire published schema despite client-only “private page” checks, implicit binding of a subdomain to whichever project was published most recently, direct authenticated mutations that bypass Page Builder backend invariants, missing backup/restore evidence, an outbox without a delivery worker, and billing that is intentionally manual/incomplete.

Finding counts:

- P0: 0 confirmed
- P1: 10
- P2: 18
- P3: 8

Immediate next action: close direct authenticated writes to privileged tables—especially `users` and `builder_projects`—with a reviewed migration, extend the RLS verifier, repair duplicate migration `047`, and add live read-only policy verification in a staging environment before the next deployment.

## 2. Scope and Methodology

The review covered frontend source and routes, backend routers and services, both SQL migration trees, Docker/Compose configuration, tests, scripts, and existing architecture/audit documents. Static searches traced authentication, authorization, direct database mutations, unsafe content handling, storage paths, API contracts, legacy code, and operational configuration. Large-module and bundle metrics were collected. Historical Page Builder findings were rechecked against current source.

Quality gates were run locally and non-destructively:

- frontend ESLint;
- all frontend Vitest tests, using one worker after the default invocation exceeded the command observation window;
- frontend theme audit and production Vite build, directed to `/tmp/madar-audit-dist` so no repository artifact was created;
- backend Docker image build;
- all backend unittests in a temporary `--no-deps` container;
- backend `pip check` in a temporary container;
- migration-tree checker;
- `git diff --check`;
- `npm ls --depth=0`.

Not performed:

- no live database mutation or destructive route was called;
- no migration was applied;
- no production container was started, stopped, or recreated;
- no live RLS/grant verification was run because it requires a real database connection;
- Playwright E2E was inspected but not run because it defaults to a shared published form fixture (`frontend/e2e/published-form-geometry.spec.mjs`);
- dependency CVE databases were not queried, so vulnerability versions require a separate network-approved audit;
- readiness was not called because the task prohibited starting/restarting services and prior runtime state was context only.

## 3. Repository State

- Path: `/home/madar/saas/Madar-dev`
- Branch: `builder-backend`
- HEAD: `18d99fa97a2c6b15c9845536a50ba6fc3976214e` (`fix: stabilize Page Builder users after merge`)
- Latest merge: `9f04eda` (`Merge remote-tracking branch 'origin/main' into builder-backend`)
- Divergence from existing `origin/main`: 4 commits ahead, 0 behind
- Divergence from existing `origin/builder-backend`: 0 ahead, 0 behind
- Submodules: none reported
- Initial working tree: clean

Remote refs were not refreshed, so divergence is relative to the repository's existing remote-tracking refs, exactly as requested.

## 4. System Architecture

Madar is a React 19/Vite 8 single-page frontend with lazy route groups, a FastAPI backend using synchronous Supabase clients, PostgreSQL/Supabase migrations, and Redis-backed rate limiting/readiness. Nginx serves the built frontend. Local filesystem mounts hold avatars, public builder assets, private uploads, and database migration files. The development Compose override isolates Redis and uses ports 3001/8002; production Compose uses 3000/8001 and binds Redis to localhost 6379.

Primary subsystems:

| Subsystem | Actual implementation | Authority / persistence |
|---|---|---|
| Platform auth | Supabase Auth mediated by backend; HttpOnly access/refresh cookies; signed CSRF and activity cookies | Supabase Auth plus `public.users` |
| Tenant authorization | Backend resolves user and active tenant membership | `tenant_memberships` |
| Admin | `user_type=admin`, optional/required AAL2, support account-access sessions | `users`, `user_security_settings`, audit tables |
| Page Builder | Explicit project routes and a large workspace component with core helpers/coordinator | `builder_projects.draft_schema` and `draft_revision` |
| Publish | Backend validates and atomic RPC copies stored draft to published schema | `published_schema`, revision/version fields |
| Public site | Subdomain resolves website settings and latest published tenant project | `website_settings`, `builder_projects` |
| Forms | Published form lookup and durable submission snapshot | `builder_form_submissions` |
| Reservations | Published block lookup, idempotent booking, cancellation token, admin lifecycle | `builder_reservations` |
| Tenant-site accounts | Shared Supabase Auth plus site-membership table and tenant staff fallback | `tenant_site_memberships` |
| Data analysis | User/tenant-scoped private files, deterministic analysis, optional AI planner | local private storage plus backend memory/cache |
| Billing | Manual feature request and development/manual webhook model | `features`, billing event tables/RPCs |
| Notifications | In-app notifications plus durable outbox; some push delivery inline | notification tables; no outbox worker |

The backend holds the service-role key and performs most normal mutations. The frontend does not instantiate a Supabase client, which reduces accidental direct mutation. Database grants nevertheless remain part of the attack surface because Supabase anon credentials are designed to be public client credentials and must not be treated as a security boundary.

## 5. Implemented Feature Inventory

- Public and authenticated route groups, user workspace, admin workspace, Page Builder, public tenant runtime.
- Signup, email verification, login, refresh, logout, forgot/reset/change password.
- Admin MFA enrollment/login/AAL2 protection and last-admin protection.
- Support/admin-account-access sessions with email verification codes, expiry, audit, and route restrictions.
- Tenant membership resolution and user/admin authorization matrices.
- Page Builder project CRUD/archive, project chooser, server hydration, semantic persistence boundary, autosave, recovery, conflict review, publish/unpublish.
- Pages, sections, rows, columns, blocks, responsive direct layout, forms, form submissions, reservations, site users/roles, website chrome, and builder assets.
- Public site, standalone public form, tenant visitor registration/login/logout, reservations and cancellation.
- Data upload, cleaning, visualization, predefined analysis, limited AI planning, exports, private generated charts.
- Manual/beta billing feature selection and transactional webhook-event processing primitives.
- Internal notifications, web-push hooks, durable notification outbox primitives.
- CSRF/origin checks, request-body limits, rate limits, URL/file validation, audit events, readiness checks.

## 6. Feature Completion Matrix

| Feature | Status | Evidence and missing work |
|---|---|---|
| Onboarding | Complete but needs operational hardening | Transactional provisioning and stale-pending cleanup tests exist; production email/restore observability remains limited. |
| Authentication | Complete but needs security hardening | Cookie/CSRF/session protections are strong; direct `users` update grant and modest password policy remain. |
| MFA | Complete for admin controls | AAL2 tests cover sensitive admin routes; deployment policy is readiness-checked. |
| Admin management | Complete but needs DB hardening | Last-admin RPC/trigger and audit exist; DB self-promotion path undermines boundary if direct API is reachable. |
| Tenant management | Partially complete | Membership checks are broad; site membership/project-role semantics are inconsistent. |
| Page Builder editing | Complete but needs operational hardening | Persistence/rebase/recovery are strong; large component, incomplete stable-ID validation, direct DB bypass remain. |
| Autosave/recovery | Complete and production-capable at app layer | 287 frontend tests include reordered-jsonb lifecycle; browser E2E concurrency remains absent. |
| Publish | Complete but needs invariant hardening | Atomic backend RPC exists; raw-versus-normalized publish discrepancy and implicit subdomain project selection remain. |
| Public site | Partially complete | Published-only runtime works; private-page filtering, header/footer parity, cache/version contract are incomplete. |
| Forms | Complete but needs integrity hardening | Validation and snapshots exist; public form submissions lack idempotency and version reporting is weak. |
| Reservations | Complete but needs delivery operations | Collision/idempotency/cancellation tests exist; notification worker is absent. |
| Tenant-site users/roles | Partially complete | CRUD and login work; roles are project-defined but tenant-wide and not server-side permissions. |
| Website settings | Complete but dual-source | Backend validation exists; direct authenticated writes and `siteChrome` overlap remain. |
| Assets | Partially complete | Upload validation and managed-name serving exist; registry, quota, ownership lifecycle, and cleanup do not. |
| Billing | Beta/manual workaround | Checkout stores a manual request; provider checkout is absent and production webhook intentionally unavailable. |
| Notifications | Partially complete | Records and outbox primitives exist; no worker/scheduler delivers queued email jobs. |
| Email | Partially complete | Supabase verification and synchronous admin SMTP exist; reservation/outbox delivery is incomplete. |
| Data analysis | Complete but needs operational hardening | Ownership and export tests are good; parsing remains in web workers and storage retention is absent. |
| AI analysis | Partially complete | Gemini and mock paths exist; OpenAI/DeepSeek explicitly raise “not implemented”; local execution requires isolation. |
| Exports | Complete but needs scale testing | Spreadsheet formula sanitization is tested; resource bounds and large-file E2E remain limited. |
| Admin account access | Complete but needs operational monitoring | Strong route restrictions/audit tests; no external alerting/metrics evidence. |
| Audit logs | Complete at backend path | Sensitive metadata filtering exists; direct database mutations bypass app audit. |
| Rate limiting | Complete but deployment-dependent | Redis fail-closed production behavior is tested; no distributed capacity/load evidence. |
| Migration workflow | Blocked | Checker currently fails on duplicate prefix `047`. |
| Backups/restore | Unknown / missing runtime evidence | README references documents that are not present; no tested restore workflow found. |
| Deployment/readiness | Complete but needs hardening | Readiness checks major dependencies; Compose lacks healthchecks/resources/workers and rollback documentation. |

## 7. Security Architecture

Strong controls include HttpOnly cookies, production `Secure` enforcement, signed session-bound CSRF tokens, origin validation, request-size middleware, Redis rate limits, tenant/user authorization helpers, service-role isolation in the backend, URL scheme validation, rejection of SVG builder assets, path-containment checks, spreadsheet formula neutralization, and audit logging with sensitive-key stripping.

The principal architectural weakness is split enforcement: backend routes are substantially hardened, but historical authenticated database grants allow bypassing those routes. RLS enforces row membership in several tables but does not enforce backend-only business invariants such as immutable role fields, draft revision transitions, publish entitlement, schema validation, client contract, or audit events.

No confirmed P0 was established because live data-API exposure and applied-policy state were not verified. The direct `users` update path is P1 and should be treated as deployment-blocking until disproved by a live read-only grant/policy check.

## 8. Authentication Review

| Lifecycle | Current controls | Assessment |
|---|---|---|
| Signup/verification | Backend-mediated Supabase signup, verified-account synchronization, pending-account lifecycle | Good; signup returns a specific duplicate-email error and may permit account enumeration. |
| Login | Rate limit, audit, email verification/status checks, admin MFA branching | Good at app layer. |
| Cookies | HttpOnly access/refresh; production Secure requirement; configurable SameSite | Good; deployment must keep origin and SameSite settings coherent. |
| CSRF | Signed, session-bound, 15-minute token; header/cookie match; origin validation | Strong for authenticated writes. Public/auth lifecycle exemptions are explicit and tested. |
| Refresh/logout | Refresh replay cache and activity cookie; logout exemption is tested | Good; cache is process-local for a 15-second replay window, so multi-worker semantics should be documented. |
| Password reset/change | Audit events, reset age limit, identity/status validation | Good; password complexity is only minimum length 8. |
| MFA/AAL2 | Admin enrollment/login and sensitive route enforcement; readiness validates production policy | Strong. |
| Site visitors | Same Auth provider/cookies, platform APIs reject non-platform accounts | Boundary is tested; site registration has distinct account lifecycle. |
| Admin account access | Hashed email code, expiry, UA binding, audit, route deny flags | Strong; continue default-deny testing for every new mutation route. |

The backend's `require_system_admin()` in `backend/services/auth_service.py` authorizes exclusively from `user_data.user_type`. That makes database integrity for this field security-critical.

## 9. Authorization and Tenant Isolation

Representative route-family matrix:

| Route family | Auth / user type | Tenant source and ownership | CSRF | Rate/audit observations |
|---|---|---|---|---|
| `/builder/projects*` | Active platform tenant member; writes role-gated | Session user and active membership; project re-filtered by tenant | Required for writes | Upload and public actions rate-limited; mutation audit is incomplete for direct DB bypass. |
| `/builder/projects/{id}/publish` | Tenant context; admin account access denied; entitlement helper | Exact tenant/project and expected revision | Required | Atomic RPC; contract rollout currently configurable. |
| `/builder/projects/{id}/site-members*` | Tenant owner/admin/member rules | Project tenant plus tenant-wide membership table | Required | Role names derive from project schema, creating cross-project drift. |
| Website settings | Platform user and active tenant | Session tenant; compatibility user-id routes still exist | Required for PUT | Backend validation/audit good; RLS direct writes bypass it. |
| Public site/forms/reservations | Anonymous or tenant visitor | Subdomain to tenant, then latest published project | Public POST exemptions | Public rate limits, honeypot/timing, size checks; private page schema still exposed. |
| Data/AI | Regular platform user | Session user, tenant, dataset ownership | Required | Cross-user tests and AI quotas exist. |
| Billing checkout | Regular tenant member | Session user/tenant; user alias checked | Required | Manual-only. |
| Billing webhook | Shared-secret development/manual path | Payload tenant, transactional RPC | Exempt | Production intentionally rejects it. |
| Admin routes | System admin; sensitive mutations AAL2 | Platform-wide | Required | Audit and last-admin tests are strong. |
| Notifications | Authenticated user | Service calls scoped to session user | Required for writes | Public key intentionally public; outbox lacks worker. |

Backend IDOR defenses are generally explicit and covered. The most serious bypasses are at the database grant layer, not in normal route handlers.

## 10. Database, RLS, and Migration Review

Both migration trees contain 49 SQL files. `scripts/check_migrations.py` reports two errors because both contain `047_create_notification_outbox.sql` and `047_expand_tenant_site_member_roles.sql`. It also reports the documented historical identical-content warning for `013`/`014`. The trees are otherwise synchronized for current files.

RLS is enabled on sensitive tables, and several later migrations revoke anonymous access or make service functions service-role-only with fixed `search_path`. Important residual problems:

- `database/migrations/004_enable_rls_policies.sql` grants authenticated `SELECT, INSERT, UPDATE` on `public.users`; `users_update_own` restricts only `auth_id`, not mutable columns.
- `database/migrations/024_create_builder_projects.sql` grants authenticated full CRUD and permits any active member to insert/update. RLS scopes tenants but not revision/publish/content invariants.
- historical `website_settings` grants and member insert/update policies permit direct mutation outside backend validation/audit.
- `backend/scripts/verify_rls_grants.py` lists `users` and `builder_projects` but does not flag their relevant authenticated mutation grants as unsafe; it can therefore pass while these paths remain.
- missing compound indexes are likely for tenant/status/update ordering on builder project listing and tenant/status/publish ordering on public lookup.

No migration was applied and no live catalog was queried. Applied production state, PostgREST exposure, and policy text require staging/production read-only verification.

## 11. Page Builder Review

### Lifecycle assessment

The current canonical flow is coherent: explicit routed ID → exact backend GET → deterministic normalization → React editor state → `getPersistableProject()` → semantic identity/hash → single-flight coordinator → PUT with dispatch-time `expected_revision` → authoritative acknowledgement. A current-generation 409 fetches the exact project, performs deterministic three-way merge, retries once when clean, and latches explicit conflicts otherwise. Recovery is scoped and advisory. Publish preparation drains the coordinator and publishes by expected backend revision; the backend copies its stored draft.

### PB-001 through PB-026 reconciliation

| ID | Status | Current evidence / residual action |
|---|---|---|
| PB-001 semantic schema identity | Completed | Recursive canonical object-key ordering, array significance, semantic equality/hash, reordered-jsonb mounted test. |
| PB-002 display-name page deletion | Completed | Routine cleanup no longer deletes Reports/Orders/Responses by name; only explicit versioned legacy repair remains. |
| PB-003 direct Supabase mutations | Open, P1 | Authenticated builder CRUD remains granted; revoke direct mutation and verify live RLS. |
| PB-004 site-to-project binding | Open, P1 | `get_latest_published_project_for_tenant()` chooses last published project; add explicit website setting/project FK. |
| PB-005 preview base path | Open, P2 | route includes `/projects/:projectId/preview/*`; runtime slices hard-coded `/page-builder/preview`. |
| PB-006 random/time routine repair | Completed | Deterministic path-derived repair; random IDs limited to explicit content creation. |
| PB-007 recovery mutation | Completed | V5 parser validates without destructive normalization and export preserves schema. |
| PB-008 lifecycle metadata in content | Completed | persistable boundary strips server/editor-only fields; remaining `siteChrome` domain overlap is separate. |
| PB-009 header/footer parity | Open, P2 | public runtime calls `renderHeader()`/`renderFooter()` unconditionally for site runtime, ignoring `showHeader/showFooter`. |
| PB-010 project pagination | Open, P2 | backend returns 20 plus `has_more`; `listBuilderProjects()` returns only `projects` and chooser never requests later pages. |
| PB-011 V4 browser authority | Open legacy | Settings/UserDashboard/Archive still contain V4 storage compatibility; isolate/export/remove after product decision. |
| PB-012 website settings vs siteChrome | Open, P2 | brand/contact fields merge from two stores; define ownership and synchronization contract. |
| PB-013 persistence ownership | Partially completed | coordinator owns cloud writes, but PageBuilder retains multiple mirrored refs/effects/recovery state in a 6,231-line component. |
| PB-014 cross-tab full-schema broadcasts | Open, P2 | BroadcastChannel payload includes canonical full schema and local counters; receiver is advisory, but cost/privacy remain. |
| PB-015 stable IDs | Partially completed | page/form/block repair is stronger; sections/rows/columns/fields/workflows/roles lack comprehensive global duplicate validation. |
| PB-016 explicit empty pages | Completed | empty arrays remain empty; starter content is explicit new-project behavior. |
| PB-017 version/cache metadata | Open, P2 | public site returns only schema, omitting project ID/published version; no version-aware cache contract. |
| PB-018 asset registry/lifecycle | Open, P2 | managed upload names validated, but no registry/project reference/garbage collection/quota. |
| PB-019 client contract consistency | Partial | project mutation header exists; enforcement defaults off and coverage does not extend to all related builder mutations. |
| PB-020 large-schema performance | Open, P2 | full canonical serialization/hash/deep operations occur frequently; no incremental identity or measured limits. |
| PB-021 renderer duplication | Open | preview/editor/public rendering logic remains split; parity defects demonstrate drift. |
| PB-022 React hook warnings | Open, P3 | three `TenantSiteRuntime` exhaustive-deps warnings remain. |
| PB-023 query indexes | Open, P2 | listing/public lookup order/filter patterns lack matching compound indexes. |
| PB-024 legacy browser persistence | Open, P3 | V4 and backup cleanup code remains outside canonical builder path. |
| PB-025 bundle size | Open, P3 | builder/global CSS and Three.js chunks are large; global style imports weaken lazy-loading benefit. |
| PB-026 high-fidelity tests | Partial improvement | mounted reordered-jsonb test exists; no safe browser cross-device/RLS/publish concurrency suite. |

### Publish invariant caveat

`builder_routes.py` validates/normalizes a deep copy for publish, then invokes an RPC that copies the raw stored draft. If normalization changes valid legacy content, the validated object and published object can differ. The frontend usually persists normalized drafts, but backend authority should either reject non-canonical drafts or atomically publish the exact validated canonical representation.

## 12. Public Runtime and Tenant-Site Accounts

Subdomain resolution first loads `website_settings`, obtains the tenant, then selects the most recently published project. Public form and reservation lookups use the same helper, so they are internally aligned at a given moment; they are not durably bound to a chosen project. Publishing another tenant project can silently replace the public site and form/reservation namespace.

The anonymous `/sites/{subdomain}` response includes the complete `published_schema`. The React runtime checks `page.visibility` and redirects unauthenticated navigation, but the protected page content is already present in the JSON response. This is not server-side access control. Private/member pages must be filtered or fetched through an authenticated endpoint.

Tenant-site membership is tenant-wide (`tenant_site_memberships`) while management endpoints and valid roles are project-oriented. A project-specific role name can therefore affect the same tenant visitor when a different project becomes public. Role permissions are not enforced as backend authorization; they are primarily content/UI metadata.

Other mismatches:

- runtime hard-codes a preview base different from the routed preview URL;
- header/footer visibility flags are ignored by the public renderer;
- public response omits published version/cache identity;
- standalone form submission version metadata can be absent because public project selection does not include `draft_revision` and should use published version/revision instead;
- archived projects are excluded by `status='published'`, which is correct.

## 13. Frontend Review

Strengths: route groups are lazy, API calls are centralized through `apiFetch`, auth guards distinguish admin/platform/site users, Page Builder core logic has focused pure modules, recovery is scoped, and accessibility-oriented Testing Library tests exist.

Risks:

- `PageBuilder.jsx` is 6,231 lines with extensive state/ref/effect coordination; `DataAnalysisWorkspace.jsx` is 2,958 lines, `PageBuilderFormsTab.jsx` about 2,072, and `TenantSiteRuntime.jsx` 2,041. Changes can cross hidden lifecycle boundaries.
- no React error boundary was found; a render exception can blank an entire route group.
- three hook dependency warnings are unresolved in a security- and routing-sensitive runtime.
- V4 local-storage code and compatibility route behavior coexist with server-first builder state.
- global CSS is very large and builder CSS is broadly imported.
- API errors are generally handled, but multiple compatibility/fallback paths can hide contract drift.

Static CSS totals exceed 56,000 lines. The production build emitted about 1,037.59 kB of global `index` CSS, 540.12 kB of Page Builder CSS, a 523.59 kB Three.js chunk, and a 279.52 kB Page Builder JS chunk. These are performance and maintainability concerns, not correctness failures.

## 14. Backend Review

Strengths: tests cover authorization matrices, CSRF, rate limiting, request limits, audit sanitization, URL validation, spreadsheet security, revision semantics, billing idempotency, reservation collision/idempotency, and readiness. Service helpers centralize many security decisions. Service-role functions commonly revoke public execution and set `search_path`.

Architectural risks:

- routers mix validation, authorization, database queries, notification enqueuing, and response formatting. `builder_routes.py` is 1,898 lines and `public_site_routes.py` 1,524 lines.
- the synchronous Supabase client and synchronous parsing/provider calls run in request workers; CPU/memory-heavy parsing lacks an isolated worker.
- authorization logic is mostly centralized but database grants create a second, weaker policy plane.
- notification delivery, cleanup, and scheduled maintenance have no worker process in Compose.
- exception logging is structured in many paths, but no metrics/tracing/alert pipeline is present.

## 15. API Contract Review

| Contract mismatch | Frontend expectation / call | Backend behavior | Impact |
|---|---|---|---|
| Project list pagination | `listBuilderProjects()` returns an array and chooser renders it | backend defaults to 20 and returns pagination metadata | projects after first page are invisible. |
| Preview base | route `/page-builder/projects/:projectId/preview/*` | runtime slices `/page-builder/preview` | incorrect page resolution/navigation in nested preview. |
| Public project identity | runtime consumes `project.published_schema` | public response omits project ID/version/timestamp | cache invalidation and support diagnostics are weak. |
| Private pages | runtime treats visibility as auth navigation | anonymous API returns entire schema | confidential content leaks before UI check. |
| Header/footer | builder persists show flags | runtime always renders chrome | published site differs from builder intent. |
| Site members | endpoints scoped under project and roles validated from project | durable membership is tenant-wide | project switching can invalidate role meaning. |
| Public form version | submission wants a schema version | public project query selects published version but code can reference draft revision | inaccurate/null submission provenance. |
| Builder client contract | current client sends `cloud-draft-v1` on core project writes | enforcement defaults false and not all adjacent mutations use it | obsolete clients may mutate during rollout. |
| Website settings | canonical tenant route plus hidden user-scoped compatibility routes | both remain active | duplicated contract and maintenance surface. |

No frontend API call without a corresponding backend route was confirmed in the core builder/auth/data paths reviewed. Compatibility routes should be removed only after telemetry confirms no clients depend on them.

## 16. File Storage and Privacy

Builder assets enforce size/type/magic checks, reject SVG, use randomized managed names, and are served only when the path matches the managed convention. Private data files are scoped by tenant/user and path containment is checked. Generated charts are served through authenticated ownership checks with download/security headers.

Missing production controls:

- no durable asset registry linking files to tenant/project/block;
- no quota, retention, reference counting, or cleanup on replace/archive/delete;
- public builder files can remain reachable indefinitely after project lifecycle changes;
- private generated charts are not mounted as a persistent Compose volume and can disappear on backend recreation;
- private uploads/public assets are local single-host mounts, limiting horizontal scaling and disaster recovery;
- predictable aggregate storage growth can exhaust disk even though individual file sizes are capped.

## 17. Billing and Entitlements

Billing is not production payment processing. Checkout records `pending_manual_activation` and returns `billing_not_configured`. The production webhook path rejects requests unless a real signed provider integration exists; current processing is documented in code as manual/development and defaults to provider `madar_manual`. Transactional idempotency, event-hash reuse checks, stale event ordering, and entitlement lookup are thoughtfully tested.

`ENFORCE_PUBLISH_ENTITLEMENT` defaults false. That is acceptable for beta compatibility but incompatible with a paid production promise. Before monetization: integrate a provider checkout, signature verification, replay-safe webhook adapter, reconciliation jobs, refund/cancel/chargeback semantics, customer self-service, and fail-safe entitlement enforcement.

## 18. Email and Notifications

Supabase handles verification/reset delivery. Admin-account-access email uses configured SMTP synchronously. In-app notifications and web push have implementation and tests. Reservation confirmation/status events enqueue durable outbox rows with deduplication and claim/finish RPCs.

However, `047_create_notification_outbox.sql` explicitly states that it does not schedule a worker, and no worker/cron service appears in Compose. `claim_notifications()` is used by tests but no production consumer was found. Features can therefore report successful queueing while email delivery never occurs. Add a separately deployed worker with retry/backoff, dead-letter visibility, metrics, and redacted error storage.

## 19. Data Analysis and AI

Data endpoints enforce user/tenant/dataset ownership, private chart access, request limits, export formula sanitation, and daily AI quotas. Remote dataset URLs are disabled by default, HTTPS is required unless explicitly overridden, private IPs and redirects are validated, and response bytes are capped.

Incomplete/hardening areas:

- file parsing remains in the web process; source has a TODO for a no-network resource-limited worker;
- generated code can run in-process when `AI_ALLOW_LOCAL_EXEC` is enabled. AST/builtin restrictions help, but there is no hard OS isolation or execution timeout;
- OpenAI and DeepSeek are advertised supported settings but planner branches explicitly raise “not implemented yet”; Gemini and mock are the real provider paths;
- remote URL validation resolves DNS before the HTTP client resolves again, leaving a DNS-rebinding window if the feature is enabled;
- dataset/chart retention, quotas, and cleanup are absent;
- no evidence of production prompt/output observability or privacy retention controls beyond application logs and caps.

## 20. Operations and Deployment

Positive controls: production ports bind explicitly, development Redis is isolated, uploads/migrations are mounted, Redis readiness can fail closed, production admin MFA/rate-limit settings are readiness-checked, and frontend/backend Docker builds pass.

Gaps:

- no Compose healthchecks, CPU/memory limits, worker/scheduler, log rotation policy, or metrics/alert stack;
- Dockerfiles run mutable base tags and backend runs as root;
- frontend uses `npm install`, not `npm ci`, reducing reproducibility;
- Python requirements mix exact and range/unpinned dependencies;
- no present backup/restore/rollback runbook or restore-test evidence; README references missing docs;
- generated charts lack persistent volume;
- single-host local file storage is a recovery and scaling dependency;
- Nginx config lacks application-level CSP, HSTS, frame, referrer, and permissions-policy headers;
- readiness is useful but cannot prove backups, worker delivery, external email/payment, or RLS correctness.

## 21. Dependency and Supply Chain

`pip check` in the built backend image passed. `npm ls --depth=0` failed because the current installed `node_modules` lacks `dotenv@^17.4.2` even though both `package.json` and lockfile require it. Tests and build still pass because their current paths do not load it; this demonstrates local install drift.

The frontend lockfile exists, but the Docker build uses `npm install`. Python requirements include both pinned and unpinned/ranged packages, and the base images are tag-based rather than digest-pinned. No online CVE audit was performed. A production supply-chain gate should use `npm ci`, exact Python lock/constraints with hashes where practical, image digest policy, SBOM generation, and separately approved vulnerability scanning.

## 22. Testing and Quality Gates

Current results:

- Frontend: 48 test files, 287 tests passed; duration 89.01 seconds with one worker.
- ESLint: 0 errors, 3 `react-hooks/exhaustive-deps` warnings in `TenantSiteRuntime.jsx` at lines 851, 869, and 903.
- Frontend theme audit: passed.
- Frontend production build: passed; chunk-size warning retained.
- Backend Docker build: passed.
- Backend: 545 unittests passed in 13.907 seconds.
- Backend dependency check: no broken requirements.
- Migration checker: failed, 49 database and 49 Supabase files, 2 duplicate-prefix errors, 2 historical duplicate-content warnings.
- `git diff --check`: passed before report creation.

Test strengths are security-focused backend route matrices and high-value Page Builder unit/mounted lifecycle coverage. Gaps:

- RLS tests mostly inspect migration text or mocks; no staging test proves effective grants/policies and direct-client denial.
- the RLS verifier does not encode the most important unsafe grants.
- only one Playwright file (two visual geometry tests) was found; it uses a shared published fixture and does not cover authentication, autosave concurrency, cross-device rebase, tenant isolation, recovery, or publish privacy.
- mocked Supabase clients can validate query intent but not PostgreSQL policy/function behavior.
- no backup/restore drill, migration-on-copy, rollback, or disaster-recovery test.
- no load/capacity tests for large builder schemas, uploads, parsing, public forms, reservations, or Redis.
- no accessibility automation or broad keyboard/screen-reader test evidence.

## 23. Detailed Findings

### P0

No P0 was confirmed without live-state verification. SEC-001 could become P0 if live testing confirms public authenticated data-API reachability and the migration state matches source; it is classified P1 because that deployment precondition was not tested.

### P1

#### SEC-001 — Authenticated users can potentially self-promote to system admin

- Severity: P1
- Subsystem: Authentication / database authorization
- Evidence: `database/migrations/004_enable_rls_policies.sql` grants authenticated `UPDATE` on `public.users`; `users_update_own` checks only `auth_id=auth.uid()`. `023` adds mutable `user_type`; `045` protects the last admin but does not prohibit promotion. `backend/services/auth_service.py::require_system_admin()` trusts `user_type == "admin"`.
- Affected: migrations 004/023/045; `require_system_admin` and every admin route.
- Impact: a normal authenticated user able to call PostgREST directly can update its own `user_type`, enroll MFA, and reach system-admin operations.
- Exploit/precondition: Supabase REST endpoint and public anon client credential are reachable/known; live grants/policies match source.
- Confidence: high static confidence; live exploitability requires read-only environment verification.
- Recommended repair: revoke authenticated insert/update on `users`; expose narrow self-profile RPC or column-specific grants excluding privilege/lifecycle/tenant fields; make admin promotion service-role RPC-only; add a defensive trigger rejecting non-service-role privileged-column changes.
- Migration required: yes.
- Owner: database + backend security.
- Validation: real authenticated client must fail direct privilege/tenant/status writes; app profile update must still work; admin AAL2 suite must pass.

#### DB-001 — Duplicate migration prefix blocks deterministic deployment

- Severity: P1
- Subsystem: Migrations
- Evidence: both trees contain `047_create_notification_outbox.sql` and `047_expand_tenant_site_member_roles.sql`; checker exits 1 with two errors.
- Impact: migration runners/order documentation can diverge or skip/ambiguously order one change.
- Precondition: any deployment consuming numeric ordering.
- Confidence: certain.
- Repair: renumber the unapplied/later migration consistently in both trees after checking production migration history; do not rewrite an applied identifier without a compatibility plan.
- Migration required: migration-history decision, not a new schema feature.
- Owner: database/operations.
- Validation: checker zero errors, staging migration from production snapshot, applied-history reconciliation.

#### PB-SEC-001 — “Private” published pages are anonymously disclosed

- Severity: P1
- Subsystem: Public runtime
- Evidence: `/sites/{subdomain}` returns full `published_schema`; `TenantSiteRuntime.runtimePageRequiresAuthentication()` enforces visibility only after JSON download.
- Impact: confidential member/private page text, links, block configuration, and metadata are readable without login.
- Precondition: know the public subdomain and inspect API response.
- Confidence: certain.
- Repair: return only public pages anonymously; add an authenticated content endpoint that verifies tenant-site membership and role for protected pages; never rely on client routing as authorization.
- Migration required: no, unless storing explicit access policy/version.
- Owner: backend + frontend.
- Validation: anonymous contract tests must prove protected content bytes absent; role matrix browser/API tests.

#### PB-INT-001 — Subdomain is implicitly bound to the latest published project

- Severity: P1
- Subsystem: Publishing / public site
- Evidence: `get_latest_published_project_for_tenant()` orders tenant projects by `last_published_at desc limit 1`; website settings contain no durable selected project binding.
- Impact: publishing an unrelated project silently replaces the tenant site and changes form/reservation resolution.
- Precondition: tenant has multiple published projects.
- Confidence: certain.
- Repair: add explicit `website_settings.published_project_id` (or hosting binding table), tenant FK/check, transactional switch during intended publish, and consistent form/reservation lookup.
- Migration required: yes.
- Owner: database + backend + frontend.
- Validation: multi-project publish tests, archive/delete behavior, cross-tenant FK rejection.

#### PB-INT-002 — Direct authenticated builder writes bypass concurrency and publish safeguards

- Severity: P1
- Subsystem: Page Builder / RLS
- Evidence: migration 024 grants authenticated CRUD; update RLS permits every active member and has no column/invariant restrictions.
- Impact: a direct client can set draft revision/schema, published schema/version/status, bypass client contract, entitlement, validation, optimistic concurrency, and audit.
- Precondition: direct authenticated Supabase API access.
- Confidence: high static confidence.
- Repair: revoke authenticated mutations; retain backend service-role access; if direct reads are desired, grant SELECT only; perform all mutations through backend/RPCs with explicit authorization.
- Migration required: yes.
- Owner: database + backend.
- Validation: direct mutation denial and normal backend save/publish/RLS tests.

#### PB-AUTH-001 — Tenant-site roles are project-defined but tenant-wide and not enforced as permissions

- Severity: P1
- Subsystem: Tenant-site accounts
- Evidence: site-member endpoints are nested under project and validate project role IDs, while membership uniqueness/storage is tenant-wide; public access checks membership existence, not project permission rules.
- Impact: publishing/switching projects can reinterpret roles; UI can imply authorization that the server does not enforce.
- Precondition: multiple projects or protected features differentiated by role.
- Confidence: high.
- Repair: decide tenant-wide versus project-scoped roles; model explicit permission claims; enforce them on content/data routes; migrate memberships consistently.
- Migration required: likely.
- Owner: product + database + backend + frontend.
- Validation: role permission matrix across two projects and disabled members.

#### OPS-001 — No verifiable backup, restore, or rollback capability

- Severity: P1
- Subsystem: Operations
- Evidence: README links to missing backup/launch documents; no restore scripts/tests or recovery objective evidence found; uploads are local volumes.
- Impact: database or host loss can become unrecoverable or exceed acceptable downtime; migrations cannot be safely rolled back under pressure.
- Precondition: operational incident.
- Confidence: high for repository evidence; external infrastructure may exist and must be documented.
- Repair: document automated encrypted backups for DB and files, retention/RPO/RTO, restore ownership, quarterly restore drills, and deploy rollback/migration compatibility.
- Migration required: no.
- Owner: operations.
- Validation: restore a production-like backup into isolated staging and run readiness/data integrity checks.

#### NOTIF-001 — Durable notification outbox has no delivery worker

- Severity: P1
- Subsystem: Notifications/email
- Evidence: migration 047 says it does not schedule a worker; service has claim/finish methods; Compose contains no worker/cron consumer.
- Impact: reservation/status emails can remain pending indefinitely while requests report successful queueing.
- Precondition: any outbox-backed notification.
- Confidence: certain from repository; external worker requires verification.
- Repair: deploy idempotent worker with retry/backoff/dead-letter metrics and readiness/alerts.
- Migration required: no, current schema is suitable.
- Owner: backend + operations.
- Validation: local isolated worker test, failure/retry test, production canary delivery and queue-depth alert.

#### BILL-001 — Billing is manual and entitlement enforcement defaults off

- Severity: P1
- Subsystem: Billing/business integrity
- Evidence: checkout returns `billing_not_configured` and `pending_manual_activation`; production webhook rejects; provider defaults manual; `ENFORCE_PUBLISH_ENTITLEMENT` defaults false.
- Impact: no secure automated revenue lifecycle; users may publish without paid entitlement; UI can overstate billing completeness.
- Precondition: launch as paid SaaS.
- Confidence: certain.
- Repair: label beta/manual clearly or implement provider checkout, signed webhooks, reconciliation, cancellation/refunds, and enforced entitlements.
- Migration required: possibly provider/customer fields, not necessarily.
- Owner: product + backend + operations.
- Validation: provider sandbox E2E, replay/stale/refund tests, fail-safe entitlement tests.

#### AI-001 — Heavy parsing and optional generated-code execution lack process isolation

- Severity: P1
- Subsystem: Data analysis/AI
- Evidence: source TODO calls for a no-network resource-limited parser; sandbox notes local exec should be disabled and moved to an isolated worker; both run in backend process when enabled.
- Impact: crafted/large data or generated computation can exhaust or compromise web worker availability; Python-level restrictions are not an OS sandbox.
- Precondition: local exec enabled or adversarial expensive input within accepted limits.
- Confidence: high architectural confidence.
- Repair: keep local exec disabled in production; move parsing/execution to isolated, no-network, timeout/memory/CPU-limited jobs.
- Migration required: no.
- Owner: backend + operations.
- Validation: resource-exhaustion tests, timeout/kill tests, network-denial tests.

### P2

#### DB-002 — Website settings can bypass backend validation and audit

- Severity: P2
- Subsystem: Database authorization
- Evidence: authenticated grants and member insert/update RLS remain in migrations 003/025/034 while backend PUT adds URL validation and audit.
- Impact: tenant members can write values outside backend contract and evade audit.
- Confidence: high static; live exposure requires verification.
- Repair: revoke direct writes and keep backend service-role mutation; add denial tests.
- Migration required: yes. Owner: database/backend. Validation: direct-client denial plus settings route suite.

#### DB-003 — RLS verification script gives false confidence on critical grants

- Severity: P2
- Subsystem: Security tooling
- Evidence: `UNSAFE_DIRECT_GRANTS` omits `users` and `builder_projects`; expected policy checks validate tenant tokens but not privileged columns/business invariants.
- Impact: CI/readiness can report safe RLS while escalation/integrity bypass remains.
- Confidence: certain.
- Repair: encode allowed grant matrix per role/table, privileged-column checks, function execute grants, and explicit builder/users denial.
- Migration required: no. Owner: backend/security tooling. Validation: fixture tests that intentionally unsafe grants fail.

#### PB-001A — Publish validates a normalized copy but RPC publishes raw draft

- Severity: P2
- Subsystem: Publishing
- Evidence: route validation prepares normalized schema while atomic RPC copies stored draft; normalized return is not the RPC input.
- Impact: published bytes can differ from the object that passed validation for legacy/noncanonical drafts.
- Confidence: medium-high; exact divergence needs a crafted fixture.
- Repair: atomically validate/canonicalize the stored draft or reject noncanonical drafts before publishing; return schema hash/version.
- Migration required: possibly RPC update. Owner: backend/database. Validation: malformed legacy draft and normalized-output equality tests.

#### PB-002A — Preview path parsing omits explicit project segment

- Severity: P2
- Subsystem: Builder preview
- Evidence: router uses `/page-builder/projects/:projectId/preview/*`; runtime uses `/page-builder/preview` for slicing/base.
- Impact: nested page preview navigation can resolve the wrong slug/path.
- Confidence: certain static mismatch.
- Repair: derive base from route params/matched pathname. Migration: no. Owner: frontend. Validation: mounted multi-page preview route test.

#### PB-003A — Public runtime ignores header/footer visibility

- Severity: P2
- Subsystem: Runtime parity
- Evidence: builder edits `siteChrome.showHeader/showFooter`; runtime always invokes render functions for public/draft site.
- Impact: published output contradicts configured design.
- Confidence: certain.
- Repair: use shared chrome renderer or honor flags. Migration: no. Owner: frontend. Validation: preview/public parity tests.

#### PB-004A — Project chooser silently truncates at 20 projects

- Severity: P2
- Subsystem: Routing/project selection
- Evidence: backend paginates with default 20; API discards pagination; chooser makes one request.
- Impact: users cannot open older projects through UI.
- Confidence: certain.
- Repair: return pagination object and implement load-more/cursor behavior. Migration: no. Owner: frontend/backend contract. Validation: 21+ project test.

#### PB-005A — Stable-ID validation is incomplete across nested entities

- Severity: P2
- Subsystem: Schema integrity/merge
- Evidence: current duplicate repair/validation concentrates on pages/forms/blocks; all section/row/column/field/workflow/role ID namespaces are not globally guaranteed.
- Impact: merge, selection, drag/drop, form references, and role assignment can target the wrong entity.
- Confidence: medium-high.
- Repair: define ID namespaces, deterministic legacy repair, publish validation, and conflict tests for every entity type.
- Migration required: explicit schema-version repair may be needed. Owner: frontend/backend. Validation: duplicate-ID corpus and cross-device merge tests.

#### PB-006A — Cross-tab advisory broadcasts full schemas

- Severity: P2
- Subsystem: Browser lifecycle/privacy/performance
- Evidence: BroadcastChannel messages contain canonical serialized full schema and local counters; receiver is advisory.
- Impact: large clone/serialization cost and unnecessary exposure to same-origin contexts; version semantics remain duplicated.
- Confidence: high.
- Repair: broadcast project ID, acknowledged revision, hash, and dirty indicator only; fetch backend on demand.
- Migration required: no. Owner: frontend. Validation: cross-tab advisory/no-write tests.

#### PB-007A — Website settings and siteChrome duplicate site identity

- Severity: P2
- Subsystem: Content contract
- Evidence: runtime merges website profile fields with project `siteChrome`; builder persists overlapping brand/contact/logo/footer values.
- Impact: editor, public site, and settings can show different values depending on merge precedence.
- Confidence: certain.
- Repair: define tenant-global versus project-local fields and one-way derivation; avoid bidirectional implicit sync.
- Migration required: possibly data consolidation. Owner: product/frontend/backend.
- Validation: settings change/publish/reload cross-device tests.

#### PB-008A — Public publish/version/cache contract is incomplete

- Severity: P2
- Subsystem: Public API
- Evidence: public site response exposes only schema; published project query has version/timestamp but response drops them; standalone form provenance can use absent draft revision.
- Impact: stale-content diagnosis, cache invalidation, and submission provenance are unreliable.
- Confidence: high.
- Repair: return safe project ID, published revision/version, timestamp and schema hash/ETag; use published version in submissions.
- Migration required: no. Owner: backend/frontend. Validation: publish/cache/form provenance tests.

#### PB-009A — Builder assets lack registry and lifecycle management

- Severity: P2
- Subsystem: Assets/storage
- Evidence: files are managed by filename convention and path; no DB record links asset to project/block or tracks references/deletion.
- Impact: orphaned public data, unbounded disk, inability to revoke or audit ownership.
- Confidence: certain.
- Repair: asset registry, tenant/project FK, quota, reference tracking, soft-delete/GC policy.
- Migration required: yes. Owner: database/backend/operations. Validation: cross-tenant access, replace/archive/delete GC tests.

#### PB-010A — Full-schema operations have no measured scale boundary

- Severity: P2
- Subsystem: Performance
- Evidence: persistence, semantic identity, recovery, BroadcastChannel, and merge repeatedly serialize/deep-clone whole schemas; PageBuilder is large and rerender-heavy.
- Impact: typing/drag latency, long saves, memory pressure, and request-size failures on large sites.
- Confidence: high architectural, unmeasured severity.
- Repair: publish supported schema limits, instrument sizes/timings, memoize by editor change generation, reduce broadcast payload, consider structural sharing.
- Migration required: no. Owner: frontend/backend. Validation: 95th-percentile large-schema benchmarks and body-limit UX tests.

#### STOR-001 — Generated charts are not durable across backend recreation

- Severity: P2
- Subsystem: Private storage
- Evidence: private generated-chart path has no Compose volume while other upload directories do.
- Impact: user-generated reports/charts can disappear after image/container replacement.
- Confidence: high.
- Repair: durable tenant-scoped object storage or mounted volume plus backup/retention. Migration: no. Owner: operations/backend. Validation: recreate-container persistence test in isolated stack.

#### STOR-002 — Storage quotas, retention, and cleanup are absent

- Severity: P2
- Subsystem: Storage/privacy
- Evidence: per-file limits exist, but no aggregate tenant/user quota or scheduled cleanup was found for uploads/charts/assets.
- Impact: disk exhaustion, privacy over-retention, cost growth.
- Confidence: high.
- Repair: quotas, retention policy, usage accounting, deletion jobs, alerts. Migration: likely usage/asset metadata. Owner: backend/database/operations.

#### FORM-001 — Public form submissions lack idempotency

- Severity: P2
- Subsystem: Forms
- Evidence: reservation flow has explicit idempotency keys; form submission flow does not expose equivalent protection.
- Impact: browser/network retries create duplicate business records.
- Confidence: high.
- Repair: client-generated idempotency key, tenant/project/form uniqueness, response replay. Migration: yes. Owner: backend/database/frontend. Validation: concurrent duplicate submission tests.

#### AUTH-001 — Admin-created site members use admin-known passwords

- Severity: P2
- Subsystem: Tenant-site users
- Evidence: member creation accepts a password and creates/confirms the auth user rather than using a one-time invite/reset flow.
- Impact: administrators know reusable customer credentials; no forced first-login change.
- Confidence: high.
- Repair: invite token/email, user-set password, expiry, optional MFA/rotation policy. Migration: no. Owner: backend/frontend/product. Validation: invite replay/expiry/account-enumeration tests.

#### AI-002 — Optional remote dataset fetch is vulnerable to DNS rebinding between validation and connect

- Severity: P2
- Subsystem: SSRF
- Evidence: resolver validates host IPs, then HTTP client resolves hostname independently; redirects are revalidated and feature defaults off.
- Impact: when enabled, attacker-controlled DNS can change to private address after validation.
- Confidence: medium-high.
- Repair: connect to validated IP with TLS hostname verification or use an egress proxy that enforces destination policy; keep feature disabled until then.
- Migration required: no. Owner: backend/operations. Validation: DNS-rebind and redirect tests in isolated network.

#### OPS-002 — Containers and web edge lack production hardening

- Severity: P2
- Subsystem: Deployment
- Evidence: mutable base tags, root processes, no resource limits/healthchecks/log policy; Nginx lacks CSP/HSTS/frame/referrer/permissions headers.
- Impact: wider blast radius, nondeterministic builds, weaker browser defense, poor failure isolation.
- Confidence: high.
- Repair: non-root images, pinned/digested bases, healthchecks/resources, read-only FS where possible, security headers at trusted proxy, log rotation.
- Migration required: no. Owner: operations. Validation: image policy scan, header tests, failure/restart drills.

### P3

#### FE-001 — Three runtime hook dependency warnings remain

- Severity: P3
- Subsystem: Frontend correctness
- Evidence: ESLint warnings at `TenantSiteRuntime.jsx` 851/869/903.
- Impact: stale closures may cause navigation/auth edge cases.
- Confidence: certain warning, behavior impact unproven.
- Repair: stabilize callbacks/derive values and add behavior tests; do not suppress. Migration: no. Owner: frontend.

#### FE-002 — Bundle and CSS size undermine route splitting

- Severity: P3
- Subsystem: Frontend performance
- Evidence: build sizes listed in section 13; broad global/builder CSS imports.
- Impact: slow first load, parse/style cost, difficult CSS ownership.
- Confidence: certain size, user impact needs field metrics.
- Repair: route-scoped CSS, remove dead styles, split Three.js-dependent features, establish budgets. Migration: no. Owner: frontend.

#### FE-003 — No route-level React error boundary

- Severity: P3
- Subsystem: Frontend resilience
- Evidence: no ErrorBoundary implementation found.
- Impact: an uncaught render error can blank the application with weak recovery guidance.
- Confidence: high.
- Repair: route-group boundaries with redacted logging and retry/navigation. Migration: no. Owner: frontend.

#### DEP-001 — Installed frontend dependencies do not match the lockfile

- Severity: P3
- Subsystem: Developer environment
- Evidence: `npm ls --depth=0` reports missing `dotenv@^17.4.2`; package and lockfile contain it.
- Impact: E2E or environment-loading scripts may fail depending on workstation state.
- Confidence: certain locally.
- Repair: use clean `npm ci` in CI/development bootstrap; do not patch around missing module. Migration: no. Owner: frontend/operations.

#### DEP-002 — Dependency builds are not fully reproducible

- Severity: P3
- Subsystem: Supply chain
- Evidence: frontend Docker uses `npm install`; Python requirements mix exact/ranged/unpinned; base tags mutable.
- Impact: different builds can resolve different code and vulnerabilities.
- Confidence: high.
- Repair: `npm ci`, Python lock/constraints, digest policy, SBOM/CVE gates. Migration: no. Owner: operations.

#### DOC-001 — Operational documentation is stale or missing

- Severity: P3
- Subsystem: Documentation
- Evidence: README claims no dedicated frontend runner despite Vitest suite and links to missing backup/launch docs; only four current docs were found.
- Impact: operators follow incorrect validation/recovery procedures.
- Confidence: certain.
- Repair: update README and add owned, tested runbooks. Migration: no. Owner: engineering/operations.

#### LEG-001 — Legacy V4 persistence and compatibility APIs remain

- Severity: P3
- Subsystem: Legacy code
- Evidence: V4 storage paths remain in Settings/UserDashboard/Archive and hidden user-scoped website/builder compatibility routes remain.
- Impact: duplicate state/contracts and accidental future reuse.
- Confidence: high.
- Repair: instrument usage, set removal date, retain export-only recovery as needed, delete in a focused release. Migration: no. Owner: frontend/backend/product.

#### TEST-001 — Browser, RLS, recovery, and operations tests remain too synthetic

- Severity: P3
- Subsystem: Quality engineering
- Evidence: one shared-fixture Playwright file; RLS largely text/mocked; no backup/restore or cross-device browser suite; backend emits repeated TestClient cookie deprecation warnings.
- Impact: real browser/database/operations regressions can pass unit suites.
- Confidence: certain.
- Repair: ephemeral isolated Supabase/browser environment, effective-policy tests, two-context concurrency suite, restore drill, update deprecated TestClient cookie setup. Migration: no. Owner: quality/backend/frontend/operations.

## 24. Partially Completed Work

- Billing: safe manual primitives, no real provider lifecycle.
- Notifications: outbox schema/service, no consumer.
- AI: Gemini/mock operational paths; OpenAI/DeepSeek settings are placeholders; no isolated execution worker.
- Tenant-site roles: CRUD/display exists, authorization model incomplete.
- Public private pages: UX gate exists, server secrecy absent.
- Asset management: safe file acceptance/serving exists, lifecycle registry absent.
- Project hosting: publishing works, durable subdomain-to-project binding absent.
- Legacy cleanup: core builder is server-first, older V4 dashboard/settings/archive paths remain.
- Operational readiness: component health checks exist, backup/restore, worker, observability, and rollback evidence do not.

## 25. Deprecated and Legacy Components

- V4 local-storage project data in noncanonical dashboard/settings/archive paths.
- Hidden `/users/{user_id}/...` compatibility variants alongside canonical tenant/session routes.
- Historical duplicate migrations 013/014.
- duplicate current prefix 047 (not merely legacy; deployment blocker).
- old Page Builder CSS layers/files that are not clearly imported; usage must be confirmed with build analysis before deletion.
- README statements and links predating the current frontend test/build architecture.

No files should be removed without usage telemetry and focused regression tests.

## 26. Missing Production Capabilities

- effective live RLS/grant verification and backend-only privileged mutation boundary;
- explicit site/project hosting binding;
- server-side protected page/content delivery;
- production billing provider and enforced entitlements;
- notification/email worker and queue monitoring;
- tested database/file backup and restore;
- durable/scalable object storage with registry, quotas, retention, cleanup;
- isolated parsing/AI execution workers;
- production observability: metrics, tracing, alerts, queue/disk/business health;
- ephemeral full-stack browser/RLS test environment;
- documented deployment rollback and migration compatibility process;
- dependency CVE/SBOM/image policy gate.

## 27. Recommended Repair Roadmap

### Immediate: before next production deployment

1. Fix SEC-001: revoke authenticated privileged user writes and add DB regression tests.
2. Fix PB-INT-002 and DB-002: make builder/settings mutations backend-only.
3. Extend `verify_rls_grants.py`; run read-only effective-policy verification in isolated staging.
4. Resolve duplicate migration prefix 047 against applied production history.
5. Prevent anonymous private-page schema disclosure.
6. Introduce explicit site-to-project binding or restrict tenants to one publishable project until implemented.
7. Document and execute a backup/restore drill.
8. Disable claims of automated billing/email delivery until provider/worker are operational.

### Near term: next 1–2 development cycles

1. Align tenant-site role scope and enforce permissions server-side.
2. Make publish validation and copied schema identical and return published identity metadata.
3. Add notification worker, retries, dead-letter handling, and alerts.
4. Fix preview/header/footer/public form-version contracts.
5. Add form submission idempotency.
6. Add project pagination and compound query indexes.
7. Add asset registry/quota/cleanup and persistent chart storage.
8. Build an isolated Supabase + Playwright security/concurrency suite.

### Medium term

1. Move data parsing/generated execution to resource-limited workers.
2. Implement real billing provider/reconciliation or formally retain manual beta scope.
3. Consolidate website settings/siteChrome ownership.
4. Complete stable-ID validation/versioned repair.
5. Decompose PageBuilder/public runtime by bounded state owners while preserving tested contracts.
6. Add production metrics, tracing, disk/queue/Redis alerts, and log retention.

### Later optimization

1. Reduce full-schema serialization and measure builder size/latency budgets.
2. Replace full-schema cross-tab messages with revision/hash signals.
3. Route-scope CSS, split Three.js, remove verified-dead legacy CSS/code.
4. Add error boundaries and broader accessibility automation.
5. Tighten reproducible dependency/image supply chain and continuous CVE policy.

## 28. Frontend Task List

- Correct runtime protected-content contract with backend.
- Fix preview base, header/footer flags, project pagination, public version handling.
- Align tenant-site roles/permissions UX with server model.
- Add idempotency key to public forms.
- Replace cross-tab full schema with hash/revision advisory.
- Resolve the three hook warnings with tests.
- Add route error boundaries.
- Reduce global CSS/bundle sizes with measured budgets.
- Retire V4 storage/compatibility UI after telemetry.
- Add isolated Playwright flows: auth, autosave/rebase, recovery, publish, multi-project hosting, roles.

## 29. Backend Task List

- Stop trusting directly mutable `users.user_type`; enforce privileged DB writes.
- Make protected public content server-authorized and filtered.
- Add explicit project binding lookup and versioned public response.
- Ensure publish copies exactly what passed validation.
- Implement form idempotency and correct submission version provenance.
- Deploy notification worker and operational metrics.
- Replace admin-known site-member passwords with invitations.
- Isolate parsing/generated code; keep local exec/remote URLs disabled until hardened.
- Remove compatibility routes after monitored deprecation.
- Split high-risk routers into authorization/service/transaction boundaries.

## 30. Database/Migration Task List

- Revoke authenticated writes to `users`, `builder_projects`, and `website_settings` as appropriate.
- Add narrow RPCs/column protection for permitted self-service operations.
- Resolve duplicate 047 based on applied history.
- Add explicit website/project binding FK and lifecycle constraints.
- Decide project-scoped versus tenant-scoped site roles and migrate.
- Add form idempotency uniqueness.
- Add asset registry/ownership/reference/retention tables.
- Add compound indexes matching builder/public lookup queries.
- Extend effective RLS/grant verification, including function execute grants and `search_path`.

## 31. Operations Task List

- Produce and test backup/restore/rollback runbooks.
- Deploy outbox worker and queue-depth/dead-letter alerts.
- Persist generated charts or migrate files to object storage.
- Add disk/quota monitoring and cleanup schedules.
- Add Compose/orchestrator healthchecks, resource limits, non-root/read-only controls.
- Establish CSP/HSTS/frame/referrer/permissions policies at the actual trusted edge.
- Use `npm ci`, Python constraints/lock, image/SBOM/CVE gates.
- Create isolated staging for RLS and browser E2E.
- Document Cloudflare/proxy/origin trust and failure modes.

## 32. Validation Results

| Validation | Result |
|---|---|
| `npm run lint` | Passed: 0 errors, 3 known hook warnings |
| `npm test -- --maxWorkers=1` | Passed: 48 files, 287 tests |
| `npm run build -- --outDir /tmp/madar-audit-dist` | Passed; theme audit passed; chunk-size warning |
| `npm ls --depth=0` | Failed: locally missing declared `dotenv@^17.4.2` |
| backend Docker build | Passed |
| backend unittest discovery | Passed: 545 tests |
| backend `python -m pip check` | Passed: no broken requirements |
| `python3 scripts/check_migrations.py` | Failed: 49/49, duplicate prefix 047 in both trees, 2 errors; historical 013/014 warnings |
| `git diff --check` before report | Passed |
| Playwright E2E | Not run: defaults to a shared published fixture and lacks isolated accounts/data |
| Live RLS verification | Not run: requires real database connectivity; no mutation allowed |
| Dependency CVE audit | Not run: internet-backed databases were outside audit constraints |
| Runtime readiness | Not rechecked: no container lifecycle changes were permitted; static readiness and tests reviewed |

The backend suite emitted Starlette `TestClient` per-request cookie deprecation warnings. They did not fail tests but should be cleaned before the dependency removes behavior.

## 33. Open Questions and Product Decisions

1. Is the Supabase REST endpoint publicly reachable, and where is the anon credential distributed? Treat it as public by design regardless.
2. Which migrations are applied in production, especially the two `047` files?
3. Is there external backup/restore infrastructure not represented in this repository?
4. Is an outbox worker deployed externally? If so, document image/version/health/alerts.
5. Is billing intentionally manual beta, or is paid self-service a launch requirement?
6. Should one tenant host one project or multiple named domains/subdomains?
7. Are page visibility modes intended to protect confidential content or only navigation?
8. Are site roles tenant-global or project-specific, and what permissions should they grant?
9. Which fields belong to tenant-global website settings versus project-local site chrome?
10. What are supported maximum builder schema, project count, upload storage, and dataset sizes?
11. What retention/deletion guarantees are promised for submissions, reservations, assets, datasets, charts, and audit logs?
12. Which AI providers are product-supported now versus future configuration placeholders?

## 34. Final Readiness Verdict

Madar is a strong late-beta engineering system with unusually good backend unit/security coverage and a substantially repaired Page Builder persistence model. It is not yet a secure, reliable general-production SaaS because database grants can bypass application authorization/integrity, protected public content is not server-protected, project hosting identity is implicit, migrations currently fail validation, and core operational capabilities—restore, notification delivery, real billing, durable asset lifecycle, and full-stack policy tests—are incomplete.

Verdict: **do not perform the next production deployment until SEC-001, DB-001, PB-SEC-001, PB-INT-001/PB-INT-002, and backup verification are resolved or explicitly constrained and verified in staging.** After those blockers, the existing application and test foundation is suitable for an incremental hardening roadmap rather than a rewrite.
