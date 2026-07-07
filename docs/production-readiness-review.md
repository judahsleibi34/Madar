# Madar Production Readiness Review

Review date: 2026-07-07  
Scope inspected: `frontend`, `backend`, `database/migrations`, `supabase/migrations`, `docker-compose.yml`, Dockerfiles, tests, and setup docs.  
Important working-tree note: this review includes current uncommitted code changes shown by `git status`, including AI restrictions, rate-limit overrides, and migrations `036`/`037`.

## 1. System Architecture

### High-Level Shape

Madar is a React/Vite single-page SaaS frontend backed by a FastAPI backend. The backend uses Supabase for authentication and Postgres data storage, Redis for rate-limit storage when available, local filesystem folders for generated charts and uploaded assets/files, and SMTP for one admin permission-code email flow.

- Frontend: React 19 + Vite, route groups in `frontend/src/routes/*`, API wrapper in `frontend/src/utils/apiClient.js`.
- Backend: FastAPI app in `backend/app.py`, routes in `backend/routes/*` and `backend/data_analysis/routes/*`.
- Database/Auth: Supabase client setup in `backend/database.py`; Supabase Auth used by `backend/routes/auth_routes.py` and `backend/services/auth_service.py`.
- Storage: managed local file routes in `backend/app.py` and data-analysis routes:
  - `/uploads/tenant_{id}/builder_assets/{filename}` serves intentionally public builder image assets from `PUBLIC_UPLOADS_DIR`.
  - `/users/{user_id}/visualization/charts/{chart_id}` serves private dataset-derived chart files and explorer HTML from `PRIVATE_CHARTS_DIR` after authentication and tenant/user scope checks.
  - Supabase Storage `avatars` bucket created by migration `022_create_avatars_storage_bucket.sql`.
- Deployment: Docker Compose in `docker-compose.yml`, backend Dockerfile in `backend/Dockerfile`, frontend Dockerfile/Nginx in `frontend/Dockerfile` and `frontend/nginx.conf`, Vercel SPA rewrite in `frontend/vercel.json`.

### Frontend Entry Points

Public routes in `frontend/src/routes/PublicRoutes.jsx`:

| Route | Component / purpose |
|---|---|
| `/` | Home |
| `/product-tour` | Product tour |
| `/demo` | demo `PageBuilder` |
| `/pricing`, `/pricing/base-plans` | pricing |
| `/pricing/custom-plan` | redirects to `/pricing` |
| `/team` | team |
| `/about` | about |
| `/contact` | contact form page |
| `/login` | login |
| `/signup` | signup |
| `/forgot-password` | forgot password |
| `/reset-password` | reset password |

Tenant public runtime in `frontend/src/routes/TenantSiteRoutes.jsx`:

| Route | Component / purpose |
|---|---|
| `/site/:subdomain/*` | published tenant site runtime |

Regular authenticated workspace in `frontend/src/routes/UserWorkspaceRoutes.jsx`:

| Route | Component / purpose |
|---|---|
| `/dashboard/*` | user dashboard |
| `/page-builder/form-preview/:formId` | form preview |
| `/page-builder/preview` | draft tenant site preview |
| `/page-builder/*` | page builder |
| `/builder-responses/*` | form responses |
| `/builder-data/*` | data analysis workspace |
| `/archive/*` | archive |
| `/my-plan/*` | plan/billing UI |
| `/notifications/*` | notifications UI |
| `/settings/change-password/*` | password change |
| `/settings/*` | settings/profile |
| `/admin/users/*` | restricted placeholder for regular users |

Admin frontend routes in `frontend/src/routes/AdminRoutes.jsx`:

| Route | Component / purpose |
|---|---|
| `/dashboard/*` | admin dashboard |
| `/admin/users/*` | user management |
| `/admin/account-access/*` | temporary admin account access |
| `/notifications/*` | notifications UI |
| `/settings/*` | admin account settings |
| `/page-builder/*`, `/builder-responses/*`, `/builder-data/*`, `/archive/*`, `/my-plan/*` | restricted placeholders for admins |

### Backend Entry Points

Core FastAPI setup is in `backend/app.py`. Middleware:

- `GZipMiddleware`, minimum size 1000.
- `RequestBodyLimitMiddleware` from `backend/services/request_body_limits.py`.
- CORS with `FRONTEND_URLS`.
- CSRF origin/token middleware using `backend/services/request_security.py`.

Backend endpoints found:

| Area | Endpoint(s) | File |
|---|---|---|
| status | `GET /` | `backend/app.py`, also `backend/routes/server_status_routes.py` defines another `GET /` |
| health | `GET /health/live`, `GET /health/ready` | `backend/routes/health_routes.py` |
| auth | `POST /auth/signup`, `POST /auth/login`, `GET /auth/user_status`, `POST /auth/refresh`, `PUT /auth/password/change`, `POST /auth/log_out` | `backend/routes/auth_routes.py` |
| password reset | `POST /auth/forgot-password`, `POST /auth/password-reset` | `backend/routes/password_routes.py` |
| MFA | `GET /auth/mfa/status`, `POST /auth/mfa/enroll`, `POST /auth/mfa/enroll/verify`, `GET /auth/mfa/factors`, `DELETE /auth/mfa/factors/{factor_id}`, `POST /auth/mfa/login/challenge`, `POST /auth/mfa/login/verify` | `backend/routes/mfa_routes.py` |
| user profile | `POST /users/{user_id}/info`, `PUT /users/{user_id}/profile`, `POST /users/{user_id}/avatar` | `backend/routes/user_routes.py` |
| admin profile | `POST /admin/profile/info`, `PUT /admin/profile/profile`, `POST /admin/profile/avatar` | `backend/routes/admin_profile_routes.py` |
| website settings | `GET/PUT /website/settings`, `GET/PUT /users/{user_id}/website/settings` | `backend/routes/website_routes.py` |
| builder asset upload | `POST /builder/assets/upload` | `backend/routes/builder_routes.py` |
| builder projects | `GET/POST /builder/projects`, `GET/PUT/DELETE /builder/projects/{project_id}`, plus legacy `/users/{user_id}/builder/...` aliases | `backend/routes/builder_routes.py` |
| builder form submissions | `GET /builder/projects/{project_id}/form-submissions`, `GET/PUT /builder/projects/{project_id}/form-submissions/{submission_id}` | `backend/routes/builder_routes.py` |
| builder publish | `POST /builder/projects/{project_id}/publish` | `backend/routes/builder_routes.py` |
| public contact | `POST /public/contact` | `backend/routes/public_contact_routes.py` |
| public site | `GET /public/sites/{subdomain}` | `backend/routes/public_site_routes.py` |
| public form submission | `POST /public/sites/{subdomain}/forms/{form_id}/submissions` | `backend/routes/public_site_routes.py` |
| billing checkout | `POST /billing/checkout`, `POST /users/{user_id}/billing/checkout` | `backend/routes/billing_routes.py` |
| billing webhook | `POST /billing/webhook` | `backend/routes/billing_routes.py` |
| admin billing | `POST /admin/billing/features` | `backend/routes/admin_billing_routes.py` |
| admin users | `GET /admin/users`, `PATCH /admin/users/{user_id}/user-type`, `DELETE /admin/users/{user_id}` | `backend/routes/admin_user_routes.py` |
| admin account access | `POST /admin/account-access/generate`, `POST /admin/account-access/verify`, `POST /admin/account-access/end` | `backend/routes/admin_account_access_routes.py` |
| data upload/read/export | `POST /users/{user_id}/data/upload`, `/data/read`, `/data/export` | `backend/data_analysis/routes/data_routes.py` |
| data cleaning | `/users/{user_id}/cleaning/inspect`, `/prepare-report`, `/statistics`, `/missing-report`, `/quality-report`, `/column-types`, `/apply`, `/export` | `backend/data_analysis/routes/cleaning_routes.py` |
| analysis | `GET /users/{user_id}/analysis/catalog`, `POST /analysis/run`, `POST /analysis/assist` | `backend/data_analysis/routes/analysis_routes.py` |
| visualization | `POST /users/{user_id}/visualization/columns/profile`, `/visualization/create` | `backend/data_analysis/routes/visualization_routes.py` |

No queue worker, cron runner, scheduler, Celery/RQ job, or background job entry point was found. `backend/ARCHITECTURE_NOTES.md` mentions Redis/RQ as future work, not implemented.

### Authentication and Authorization

Auth flow:

1. Signup `POST /auth/signup` creates a Supabase Auth user, tenant, local `users` row, and `tenant_memberships` row in `backend/routes/auth_routes.py`.
2. Login `POST /auth/login` calls Supabase Auth, stores `madar_access_token` and `madar_refresh_token` HttpOnly cookies through `set_auth_cookies` in `backend/services/auth_service.py`.
3. CSRF token is generated in `backend/services/request_security.py`, returned in `X-CSRF-Token`, and stored as readable `madar_csrf_token`.
4. Frontend `apiFetch` in `frontend/src/utils/apiClient.js` sends credentials and injects `X-CSRF-Token` on unsafe methods.
5. Session refresh is handled by `POST /auth/refresh` and automatic frontend retry on 401.

Authorization roles and boundaries:

- System role `user_type` from `users.user_type`, normalized in `backend/services/auth_service.py`.
- System admins are required by `require_system_admin`; admins cannot access normal user workspace routes via `require_regular_user`.
- Tenant roles come from `tenant_memberships.role` in `backend/services/tenant_service.py`.
  - `owner`, `admin`, `member` can write builder projects/assets.
  - `owner`, `admin` can archive builder projects.
  - active membership required for builder reads, billing checkout, and tenant context.
- Admin account access can temporarily resolve an admin session to a target user via `backend/services/admin_account_access_service.py`.

### Data Flows

Signup/login:

1. React auth pages call `/auth/signup` or `/auth/login`.
2. Backend validates Pydantic request models from `backend/classes.py`.
3. Supabase Auth creates/verifies the identity.
4. Backend writes local `users`, `tenants`, `tenant_memberships`.
5. Auth cookies and CSRF token are returned.

Builder:

1. Frontend `PageBuilder.api.js` calls `/builder/projects`.
2. Backend resolves active tenant membership through `tenant_service.py`.
3. Builder project JSON is validated by `assert_json_object` and `validate_builder_schema_urls`.
4. Data persists to `builder_projects`.
5. Publishing copies `draft_schema` to `published_schema`.
6. Public runtime fetches `/public/sites/{subdomain}` and receives published schema only.

Public forms:

1. Tenant runtime submits to `/public/sites/{subdomain}/forms/{form_id}/submissions`.
2. Backend validates subdomain, published project, field IDs, required fields, answer count, answer string length, and JSON byte size in `public_site_routes.py`.
3. Inserts into `builder_form_submissions` with submitter IP and user agent.

Data analysis:

1. User uploads CSV/XLS/XLSX to `/users/{user_id}/data/upload`.
2. Backend stores file under `DATA_UPLOAD_DIR`, default `uploads`, scoped by tenant/user in `backend/data_analysis/services.py`.
3. Data readers enforce scoped file resolution in `backend/data_analysis/io/data_reading.py`.
4. Cleaning/analysis/visualization routes operate on uploaded path.
5. AI analysis service is under `backend/data_analysis/ai/*`; current strictness blocks raw file reads, full dumps, sensitive values, prompt-bypass attempts, and chart/plot requests before provider calls.

Billing:

1. `/billing/checkout` validates tenant membership and stores a pending `features` row.
2. It returns `requires_payment: true` and message: "Payment provider integration is not configured yet."
3. `/billing/webhook` accepts internal `X-Madar-Webhook-Secret`, validates it against `BILLING_WEBHOOK_SECRET`, and applies a verified billing update.
4. No Stripe/PayPal SDK or signed provider-specific webhook validation was found.

Email:

- Supabase Auth email verification/password emails depend on Supabase configuration.
- `backend/services/email_service.py` sends admin account-access permission codes via SMTP. In non-production it can log the permission code if SMTP is absent.

### External Integrations and Dependencies

Backend:

- Supabase Auth/PostgREST/Storage: `supabase==2.30.0`, configured in `backend/database.py`.
- Redis: used by `backend/services/rate_limit_service.py` via `REDIS_URL`, falls back to in-memory if `RATE_LIMIT_FAIL_OPEN=true`.
- SMTP: `backend/services/email_service.py`.
- Google Gemini: `google-genai`, used by `backend/data_analysis/ai/planner.py`.
- Optional OpenAI/DeepSeek provider names exist in `backend/data_analysis/ai/settings.py`, but provider calls are not implemented in `planner.py`.
- Pandas/Numpy/SciPy/scikit-learn/statsmodels/openpyxl for data analysis.

Frontend:

- React, React Router, i18next, Framer Motion, Lucide, Three.js, Lottie.

No payment provider SDK, monitoring SDK, background worker, or centralized logging integration was found.

## 2. Production-Readiness Checklist

| Area | Status | Evidence / finding |
|---|---|---|
| Auth cookies | Partially ready | HttpOnly auth cookies, secure/samesite enforcement in production in `auth_service.py`. |
| CSRF | Good baseline | Origin and token middleware in `request_security.py`; tests in `test_security_foundation.py`. |
| CORS | Needs production config | `FRONTEND_URLS` defaults include localhost in `app.py`; production must override. |
| Authorization | Good baseline | User/admin split in `auth_service.py`, tenant membership in `tenant_service.py`, tests exist. |
| Public dataset privacy | Blocker | `app.py` mounts `UPLOADS_DIR` publicly; data uploads default `DATA_UPLOAD_DIR=uploads` in `data_analysis/services.py`. Uploaded datasets may be publicly reachable if paths are known. |
| Public asset storage | Acceptable with review | Builder image assets are intentionally public under `/uploads/tenant_*/builder_assets/*`; validation exists. |
| Private generated artifacts | Good baseline | Dataset-derived charts and explorer HTML are stored under `PRIVATE_CHARTS_DIR`, served through authenticated tenant/user-scoped routes, and HTML responses are attachment-first with CSP/nosniff/referrer/frame protections. |
| Billing | Blocker for paid launch | Checkout explicitly says payment provider is not configured in `billing_routes.py`; webhook uses shared secret, not provider signature. |
| AI usage limits | Partially ready | Free plan defaults to 5/day in `ai/settings.py`; `/analysis/ai` reserves daily usage and also uses short-window analysis abuse limits. |
| Visualization abuse limits | Good baseline | Visualization generation uses short-window per-user and per-tenant burst limits. It is not treated as an AI/product-tier daily quota. |
| AI safety | Improving | Strict pre-provider blocks in `ai/service.py`, code validation in `ai/code_validator.py`, tests in `test_ai_analysis_strictness.py`. |
| Input validation | Strong in many areas | Pydantic models, request body middleware, upload validation, URL validation. |
| Error handling | Mixed | Many routes catch and return generic errors; some broad `except Exception` hide failure details. |
| Logging/audit | Partial | `audit_logs` table and audit helpers; no central log aggregation/metrics/tracing found. |
| Rate limiting | Good baseline, operational risk | Redis-backed with in-memory fallback; `RATE_LIMIT_FAIL_OPEN=true` by default in compose. Production high-risk routes should fail closed or use Redis health checks. |
| Data privacy | Needs tightening | Public contact/form submissions stored with IP and user-agent; no retention/deletion policy found. Dataset upload privacy blocker above. |
| Secrets/env | Needs production process | `.env` exists locally with Supabase key names; docs list envs. No secret manager integration found. |
| Database migrations | Active but needs cleanup | Both `database/migrations` and `supabase/migrations`; many historical hardening migrations. Need authoritative migration process and staging restore rehearsal. |
| Backup/restore | Missing | No backup/restore scripts, PITR docs, or restore tests found. |
| Performance | Mixed | Pagination exists in builder/admin; data analysis is synchronous and local-file/pandas based. No worker queue. |
| Scalability | Risk | Local filesystem uploads/charts do not scale horizontally; Redis is only stateful service in compose. |
| Deployment | Partial | Docker Compose and frontend Dockerfile exist. No production reverse proxy/TLS/healthcheck/deploy docs found beyond setup docs. |
| Tests | Good backend unit/route coverage, missing E2E | Many backend tests; frontend tests are sparse; no Playwright/Cypress E2E found. |
| Documentation | Partial | `docs/setup.md`, `docs/backend-architecture-report.md`, roadmap docs exist; need updated production runbook. |

## 3. Testing Strategy

### Global Testing Requirements

Every backend entry point should have:

- Happy path with exact response shape.
- 401 unauthenticated case where protected.
- 403 role/tenant/user mismatch case where protected.
- Invalid input/schema case.
- Database side-effect assertions using fake Supabase clients.
- Audit side-effect assertions for security-sensitive writes.
- Rate-limit behavior where public or expensive.
- CSRF/origin behavior for cookie-authenticated unsafe methods.
- Failure mode when Supabase/Redis/storage/provider is unavailable.

Frontend should add:

- Route guard tests for public vs user vs admin paths.
- API client CSRF/401 retry tests already started in `frontend/src/utils/apiClient.test.js`, but expand to form-data and failed refresh.
- Component tests for auth flows, signup verification modal, public form submission, builder publish, and data upload errors.
- E2E smoke tests for signup/login, builder publish/public site/form submission, billing selection, data upload/analysis, admin user actions.

### Test Inventory

| Area | Entry point | Type of test needed | What should be tested | Priority | Existing test coverage found | Missing tests | Suggested test file location |
|---|---|---|---|---|---|---|---|
| App middleware | `backend/app.py` middleware | Unit/integration | CORS, CSRF, body limits, gzip, static mounts | Critical | `test_security_foundation.py`, `test_request_body_limits.py`, `test_app_middleware.py` | Production CORS allowlist with real domains; no public dataset mount regression test | `backend/tests/test_app_production_config.py` |
| Health | `/health/live`, `/health/ready` | Route | Config readiness true/false | High | `test_health_routes.py` | Redis/Supabase dependency readiness if added | `backend/tests/test_health_routes.py` |
| Signup | `POST /auth/signup` | Route/integration | Tenant/user/membership creation, rollback, email verification response | Critical | `test_onboarding_routes.py` | Duplicate email, Supabase partial failure rollback, password strength policy | `backend/tests/test_auth_signup.py` |
| Login/session | `/auth/login`, `/auth/user_status`, `/auth/refresh`, `/auth/log_out` | Route/security | Cookie flags, CSRF token, refresh replay, invalid session | Critical | `test_security_foundation.py`, `test_security_audit_events.py`, `test_admin_mfa_login_enforcement.py` | Browser E2E, concurrent refresh from frontend | `backend/tests/test_auth_session.py`, frontend E2E |
| Password reset/change | `/auth/forgot-password`, `/auth/password-reset`, `/auth/password/change` | Route/security | Generic forgot response, token validation, audit, password min length | Critical | `test_security_audit_events.py` | Expired token, weak password variants, Supabase failure mapping | `backend/tests/test_password_routes.py` |
| MFA | `/auth/mfa/*` | Route/security | Enrollment, challenge, verify, remove factors, AAL2 requirements | Critical | `test_mfa_routes.py`, `test_admin_mfa_login_enforcement.py` | Rate limiting login challenge/verify, recovery codes if planned | `backend/tests/test_mfa_routes.py` |
| User profile | `/users/{user_id}/info`, `/profile`, `/avatar` | Route/security | Own-user only, URL validation, avatar MIME/magic/size | High | `test_user_profile_url_validation.py` | Full avatar upload path, storage rollback, delete old avatar | `backend/tests/test_user_routes.py` |
| Admin profile | `/admin/profile/*` | Route/security | Admin only, avatar upload, profile update | High | Some admin auth boundary tests | Detailed admin profile route tests | `backend/tests/test_admin_profile_routes.py` |
| Website settings | `/website/settings` and user alias | Route/integration | Tenant-scoped CRUD, subdomain uniqueness/validation, URL safety, audit | Critical | `test_website_routes.py` | Concurrent subdomain conflicts, public cache behavior | `backend/tests/test_website_routes.py` |
| Public site | `GET /public/sites/{subdomain}` | Public route | Valid published site, hidden draft schema, missing/archived site, rate limit | Critical | `test_website_routes.py`, `test_builder_archived_projects.py` | Large schema performance, cache headers | `backend/tests/test_public_site_routes.py` |
| Public form submission | `POST /public/sites/{subdomain}/forms/{form_id}/submissions` | Public route/security | Required fields, unknown fields, answer size, rate limit, IP capture | Critical | `test_builder_form_submissions.py`, `test_request_body_limits.py` | Spam controls/CAPTCHA if required, duplicate submission behavior | `backend/tests/test_builder_form_submissions.py` |
| Public contact | `POST /public/contact` | Public route | Valid/invalid payload, no auth, rate limit | High | `test_public_contact_routes.py` | Email/notification dispatch if added | `backend/tests/test_public_contact_routes.py` |
| Builder assets | `POST /builder/assets/upload` | Route/security | Auth, role, MIME/magic/size, traversal, audit, rate limit | Critical | `test_builder_asset_upload.py` | Virus scanning if required, CDN storage integration | `backend/tests/test_builder_asset_upload.py` |
| Builder projects | `/builder/projects*` | Route/integration | CRUD, tenant isolation, slug conflicts, archive, publish | Critical | `test_builder_backend_hardening.py`, `test_builder_archived_projects.py` | Frontend E2E publish round-trip | `backend/tests/test_builder_routes.py`, E2E |
| Builder submissions admin | `/builder/projects/{id}/form-submissions*` | Route/security | Tenant isolation, pagination, status changes, audit | High | `test_builder_form_submissions.py` | Permission distinction for member vs owner/admin if desired | `backend/tests/test_builder_form_submissions.py` |
| Billing checkout | `/billing/checkout` | Route/integration | Tenant membership, plan validation, pending feature row, audit | Critical | `test_billing_routes.py` | Real provider checkout session when implemented | `backend/tests/test_billing_provider.py` |
| Billing webhook | `/billing/webhook` | Route/security | Secret/signature, invalid provider event, idempotency | Critical | Limited in `test_billing_routes.py` | Provider signature verification, replay/idempotency table | `backend/tests/test_billing_webhook.py` |
| Admin billing | `/admin/billing/features` | Route/security | Admin only, valid plans/status, audit | High | `test_billing_routes.py` | Bulk/invalid tenant behavior | `backend/tests/test_billing_routes.py` |
| Admin users | `/admin/users*` | Route/security | List pagination/search, role updates, delete, audit, self-delete prevention | Critical | `test_admin_user_pagination.py` | Delete Supabase Auth failure rollback, search fuzzing | `backend/tests/test_admin_user_routes.py` |
| Admin account access | `/admin/account-access/*` | Route/security | Code generation, SMTP failure, verify, cookie, expiry, end session | Critical | Not enough visible route tests from inventory | Rate limiting, replay, wrong-code lockout, audit, target-user consent UX | `backend/tests/test_admin_account_access_routes.py` |
| Data upload | `/users/{user_id}/data/upload` | Route/security | Auth, user mismatch, type/size, private storage, no public serving | Critical | `test_data_workspace_rate_limits.py`, `test_data_reading_cache.py` | Public exposure regression for `DATA_UPLOAD_DIR`; malware scanning if needed | `backend/tests/test_data_upload_routes.py` |
| Data read/export | `/data/read`, `/data/export` | Route/security | Scoped paths, remote URL disabled, SSRF guards, response shape, spreadsheet formula injection protection for CSV/XLSX-compatible output | Critical | `test_data_reading_cache.py`, `test_spreadsheet_security.py` | Export privacy and size limits | `backend/tests/test_data_routes.py` |
| Cleaning | `/cleaning/*` | Route/data | Each cleaning action, bad input path, malformed actions, large files | High | `test_data_cleaning_preparation.py`, rate limit tests | Route-level DB/file side effects | `backend/tests/test_cleaning_routes.py` |
| Analysis | `/analysis/catalog`, `/analysis/run`, `/analysis/assist` | Route/data | Catalog localization, domain dispatch, invalid columns, auth/rate limits | High | `test_analysis_engine.py`, `test_assisted_analysis.py`, rate limit tests | Route-level failure shapes | `backend/tests/test_analysis_routes.py` |
| AI chatbot | `data_analysis/ai/service.py` caller | Unit/integration | 5/day, token cap, blocked prompts, no plots/files/raw rows, provider failure | Critical | `test_ai_analysis_strictness.py` | Route wiring to `ai_usage_daily`, persistence increment tests, provider contract tests | `backend/tests/test_ai_usage_routes.py` |
| Visualization | `/visualization/*` | Route/data | Profile/create, invalid chart config, generated file path safety, short-window per-user/per-tenant burst limits | Medium | Rate limit tests and visualization module implied | Route-level visualization output tests | `backend/tests/test_visualization_routes.py` |
| RLS/migrations | `database/migrations`, `supabase/migrations` | Static/integration | Direct anon/auth grants, tenant policies, migration order, rollback | Critical | `test_security_foundation.py` static checks | Run migrations on blank DB in CI, restore rehearsal | `backend/tests/test_migrations.py`, CI job |
| Frontend public pages | React public routes | Component/E2E | Navigation, language/RTL, contact submit, auth redirects | High | Sparse i18n tests | Public route smoke tests | `frontend/src/routes/PublicRoutes.test.jsx`, E2E |
| Frontend workspace | User routes | Component/E2E | Route guards, builder publish, data upload, settings | Critical | A few PageBuilder tests | Full user journey E2E | `frontend/e2e/user-workspace.spec.ts` |
| Frontend admin | Admin routes | Component/E2E | Admin-only pages, user management, account access | Critical | Minimal | Admin E2E | `frontend/e2e/admin.spec.ts` |
| API client | `apiClient.js` | Unit | CSRF injection, 401 refresh, retry once, error parsing | Critical | `frontend/src/utils/apiClient.test.js` | multipart/form-data, failed refresh redirect behavior | `frontend/src/utils/apiClient.test.js` |

## 4. Production Blockers

### Critical Blockers

1. Public dataset exposure risk.
   - Evidence: `backend/app.py` mounts `UPLOADS_DIR` at `/uploads`; `backend/data_analysis/services.py` defaults `DATA_UPLOAD_DIR` to `uploads`.
   - Impact: uploaded CSV/XLS/XLSX datasets can be placed under a publicly served static path.
   - Required fix: separate public builder assets from private data uploads. Set `DATA_UPLOAD_DIR` to a non-mounted private directory and add a regression test.

2. Billing is not a real payment integration.
   - Evidence: `backend/routes/billing_routes.py` returns "Payment provider integration is not configured yet."
   - Impact: users can create pending feature selections but cannot complete real payment through the app.
   - Required fix: integrate real provider checkout and signed webhooks, or explicitly launch without paid self-serve billing.

3. AI daily usage enforcement is not wired to an entry route.
   - Evidence: `run_ai_analysis_on_dataframe` requires counters; `ai_usage_daily` migration/helper exists, but no route was found calling `get_daily_ai_usage`/`increment_daily_ai_usage`.
   - Impact: 5/day is configured at service boundary but not proven enforced in live chatbot flow.
   - Required fix: wire daily usage fetch/increment atomically around provider calls and test it.

4. No backup/restore readiness found.
   - Evidence: no backup scripts/runbook/restore tests found.
   - Impact: production data recovery is undefined.
   - Required fix: Supabase PITR/backup policy, restore rehearsal, and documented RPO/RTO.

### High-Risk Issues

1. Local filesystem storage is not horizontally scalable.
   - Evidence: Docker compose binds `./backend/uploads` and `./backend/avatar_uploads`; charts/assets are local static files.
   - Risk: multiple backend containers will not share files; deployments can lose files without persistent volumes.

2. Rate limiter defaults to fail open.
   - Evidence: `RATE_LIMIT_FAIL_OPEN=true` in `docker-compose.yml`.
   - Risk: Redis outage disables protection on public/auth/upload routes.

3. Payment webhook security is generic.
   - Evidence: `X-Madar-Webhook-Secret` shared secret in `billing_routes.py`.
   - Risk: not equivalent to Stripe/PayPal signed event verification and idempotency.

4. Frontend has no full E2E coverage.
   - Evidence: only Vitest unit/component tests found; no Playwright/Cypress config found.

5. Monitoring/alerting is missing.
   - Evidence: Python logging and audit rows exist, but no metrics, trace IDs, alerting, Sentry/OpenTelemetry, or structured log shipping found.

### Medium-Risk Improvements

1. Broad route-level `except Exception` patterns return generic errors; good for users, but need correlation IDs and structured logs.
2. Public form spam controls are limited to rate limits; no CAPTCHA/honeypot/provider spam scoring found.
3. Migrations exist in two folders; production needs one authoritative process and a drift check.
4. Data analysis and visualization run synchronously; large files can tie up API workers.
5. `.env` exists locally with Supabase key names; production needs secret manager and key rotation policy.

### Nice-to-Have Improvements

1. Add OpenAPI schema review and generated API client tests.
2. Add cache headers for public site runtime.
3. Add lifecycle cleanup for old generated charts/uploads.
4. Add dependency/security scanning in CI.
5. Add performance tests for public site fetch and form submission.

## 5. Prioritized Next Actions

1. Fix private data upload storage.
   - Change `DATA_UPLOAD_DIR` default to a private non-mounted directory, e.g. `private_uploads`.
   - Keep builder assets in a separate public directory.
   - Add tests proving `/uploads/...` cannot serve uploaded datasets.

2. Decide billing launch mode.
   - If paid launch: implement provider checkout sessions, signed webhook verification, idempotency, and provider event table.
   - If not: hide/label paid checkout as waitlist/manual billing.

3. Wire AI usage enforcement.
   - Add route-level usage fetch before provider call.
   - Increment `ai_usage_daily` only when a question is accepted for processing.
   - Add tests for free user questions 1-5 allowed, 6th blocked, reset by date, and no increment for blocked unsafe prompt.

4. Production environment hardening.
   - Set `FRONTEND_URLS` to production origins only.
   - Set `RATE_LIMIT_FAIL_OPEN=false` or add route-specific fail-closed for auth/public writes.
   - Set `COOKIE_SECURE=true`, `COOKIE_SAMESITE=none` only if cross-site deployment requires it.
   - Set `CSRF_SECRET`, `SESSION_ACTIVITY_SECRET`, `BILLING_WEBHOOK_SECRET`, SMTP vars, AI provider keys.

5. Add backup/restore runbook.
   - Define Supabase backup/PITR settings.
   - Perform staging restore test.
   - Document RPO/RTO and owner.

6. Add E2E smoke suite.
   - Signup/login/logout.
   - Builder create/publish/public fetch/form submit.
   - Data upload/read/analysis.
   - Admin user list/update/delete.
   - Billing checkout or manual-billing placeholder.

7. Add production observability.
   - Request IDs, structured JSON logs, error aggregation, metrics, alerts.
   - Track 4xx/5xx by route, auth failures, rate-limit events, webhook failures, data upload failures.

8. Run full CI gates before launch.
   - Backend pytest.
   - Frontend lint/test/build.
   - Migration apply on blank DB.
   - Dependency vulnerability scan.
   - Container build smoke test.
