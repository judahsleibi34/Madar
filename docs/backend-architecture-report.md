# Madar Backend Architecture Report

Last updated: 2026-06-07

## 1. Executive Summary

The Madar backend is a FastAPI service backed by Supabase for authentication, relational data storage, privileged service-role operations, file storage, and published site data. It supports three broad product areas:

- Public website APIs, including signup, login, password reset, contact/public site access, and public builder form submissions.
- Authenticated user workspace APIs, including profile, website settings, page builder projects, form submission review, billing checkout intent, and data-analysis tools.
- System admin APIs, including user management, user type changes, account deletion, and billing feature updates.

The backend is intentionally split by account type:

- Admin APIs live under `/admin/...` and require `user_type = admin`.
- User-owned APIs live under `/users/{user_id}/...` and require a regular non-admin user whose authenticated database `users.id` matches the path `user_id`.
- Public APIs live under `/auth/...`, `/public/...`, and the root health/status route.

This separation prevents admins from accidentally entering user workspace APIs and prevents users from reading or mutating another user workspace by changing ids in the URL. Tenant-scoped records are also filtered by `tenant_id`, and uploaded data files are stored under tenant/user-specific directories.

## 2. Runtime Stack

The backend stack is:

- Python FastAPI application in `backend/app.py`.
- Supabase Python client in `backend/database.py`.
- Supabase Auth for identity and session tokens.
- Supabase Postgres for users, tenants, memberships, features, builder projects, website settings, contacts, and form submissions.
- Supabase Storage for profile avatars.
- Pandas-based local data processing for CSV, Excel, Google Sheets, JSON, cleaning, analysis, and visualization.
- Optional Redis-backed rate limiting with in-memory fallback.

Important environment variables:

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_KEY`
- `FRONTEND_URLS`
- `FRONTEND_URL`
- `COOKIE_SECURE`
- `COOKIE_SAMESITE`
- `APP_ENV` / `ENV` / `FASTAPI_ENV`
- `CSRF_ORIGIN_CHECK_ENABLED`
- `CSRF_ALLOW_MISSING_ORIGIN`
- `CSRF_TRUSTED_ORIGINS`
- `RATE_LIMIT_ENABLED`
- `RATE_LIMIT_FAIL_OPEN`
- `REDIS_URL`
- `DATA_UPLOAD_DIR`
- `MAX_UPLOAD_BYTES`
- `MAX_REMOTE_DATA_BYTES`
- `DATAFRAME_MAX_ROWS`
- `DATAFRAME_MAX_COLUMNS`
- `BILLING_WEBHOOK_SECRET`

`backend/database.py` refuses to start without a valid `SUPABASE_SERVICE_KEY`, and it also rejects using the anon key as the service key. This is important because the backend uses privileged service-role operations for admin tasks, signup provisioning, billing updates, and some data access.

## 3. Application Composition

`backend/app.py` creates the FastAPI app, configures CORS, installs CSRF origin checking middleware, and includes routers.

Registered routers:

- `routes.auth_routes`
- `routes.user_routes`
- `routes.website_routes`
- `routes.password_routes`
- `routes.server_status_routes`
- `routes.contact_routes`
- `routes.billing_routes`
- `routes.admin_billing_routes`
- `routes.admin_user_routes`
- `routes.builder_routes`
- `routes.public_site_routes`
- Data-analysis routers:
  - `data_analysis.routes.data_routes`
  - `data_analysis.routes.cleaning_routes`
  - `data_analysis.routes.analysis_routes`
  - `data_analysis.routes.visualization_routes`

The app also defines dependency wrappers:

- `require_authenticated_user`
- `require_normal_user`

The data-analysis routers are included with `Depends(require_normal_user)`, and the routes themselves additionally include `/users/{user_id}` path validation.

## 4. Authentication Architecture

Authentication logic is centralized in `backend/services/auth_service.py`.

### Cookie Sessions

The backend stores Supabase session tokens as HTTP-only cookies:

- `madar_access_token`
- `madar_refresh_token`

Cookie behavior:

- `httponly=True`
- `secure=True` in production by default
- SameSite controlled by `COOKIE_SAMESITE`
- 15-minute max age for access and refresh cookies
- Path `/`

### Session Refresh

`get_authenticated_user_row(request, response)` reads the cookies and tries to validate or refresh the Supabase session:

1. If both access and refresh tokens exist, it calls `supabase.auth.set_session`.
2. If that fails, it refreshes with `supabase.auth.refresh_session`.
3. If only refresh token exists, it refreshes.
4. If only access token exists, it calls `supabase.auth.get_user`.
5. If a new session is returned, cookies are refreshed on the response.
6. It loads the local `users` row by `auth_id`.

This means Supabase Auth is the identity authority, while the local `users` row is the application profile and authorization source.

### User Payload

`build_user_payload(user_data)` returns a normalized frontend-safe user object:

- `id`
- `auth_id`
- `tenant_id`
- `first_name`
- `last_name`
- `name`
- `email`
- `phone`
- `avatar`
- `subscription_type`
- `payment_status`
- `user_type`
- `created_at`
- `updated_at`

Billing routes and auth status enrich this with plan/features data from `features`.

### Account Type Gates

There are three important authorization helpers:

- `require_system_admin(request, response)`  
  Allows only `user_type = admin`.

- `require_regular_user(request, response)`  
  Allows only non-admin users.

- `require_regular_user_id(user_id, request, response)`  
  Allows only non-admin users whose local `users.id` equals the route `user_id`.

The third helper is the primary protection for `/users/{user_id}/...` routes.

## 5. Login, Signup, and Password Flows

### Signup

Endpoint: `POST /auth/signup`

Flow:

1. Normalize email.
2. Enforce signup rate limit.
3. Validate first name, last name, and password length.
4. Check email uniqueness in local `users`.
5. Create a Supabase Auth user using service-role admin API.
6. Create a tenant row.
7. Create a local `users` row linked to the Supabase `auth_id`.
8. Create an active `tenant_memberships` row with role `owner`.
9. If any step fails, cleanup attempts remove membership, user, tenant, and Supabase Auth user.

Signup currently returns the created auth/local/tenant identifiers but does not automatically set login cookies.

### Login

Endpoint: `POST /auth/login`

Flow:

1. Normalize email.
2. Enforce login rate limit.
3. Authenticate with Supabase Auth using the anon client.
4. Load the local `users` row by `auth_id`.
5. Sync local email if Supabase email changed and no conflict exists.
6. Set auth cookies.
7. Return `build_user_payload(local_user)`.

The returned payload includes the local backend `id`, which the frontend uses to call `/users/{id}/...`.

### Auth Status

Endpoint: `GET /auth/user_status`

This endpoint checks the cookie session, refreshes cookies when needed, and returns:

```json
{
  "logged_in": true,
  "user": {}
}
```

On failure, it returns:

```json
{
  "logged_in": false,
  "user": null
}
```

The frontend can use this endpoint on page refresh to recover the user id and account type.

### Password Change

Endpoint: `PUT /auth/password/change`

Authenticated users can change their password by providing current and new password. The backend verifies the current password with Supabase Auth, updates the user password through the service-role admin API, and tries to establish a fresh session with the new password.

### Forgot/Reset Password

Endpoints:

- `POST /auth/forgot-password`
- `POST /auth/password-reset`

The forgot-password route hides whether the email exists and returns a generic message. Reset validates the access token with Supabase and updates the password using an admin client.

## 6. Route Architecture

### Public Routes

Public routes do not require a logged-in workspace user.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/` | Basic health/status response |
| `POST` | `/auth/signup` | Create Supabase auth user, tenant, local user, membership |
| `POST` | `/auth/login` | Authenticate and set cookies |
| `GET` | `/auth/user_status` | Check/refresh session |
| `PUT` | `/auth/password/change` | Authenticated password change |
| `POST` | `/auth/log_out` | Clear auth cookies |
| `POST` | `/auth/forgot-password` | Start reset flow |
| `POST` | `/auth/password-reset` | Reset password with token |
| `GET` | `/public/sites/{subdomain}` | Load latest published site |
| `POST` | `/public/sites/{subdomain}/forms/{form_id}/submissions` | Submit public builder form |
| `POST` | `/billing/webhook` | Billing provider webhook with shared secret |

### User-Owned Routes

All user-owned routes require:

- valid cookie session,
- non-admin `user_type`,
- route `user_id` matching local authenticated `users.id`.

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/users/{user_id}/info` | Current user profile + billing summary |
| `PUT` | `/users/{user_id}/profile` | Update profile fields |
| `POST` | `/users/{user_id}/avatar` | Upload avatar to Supabase Storage |
| `GET` | `/users/{user_id}/website/settings` | Fetch/ensure tenant website settings |
| `PUT` | `/users/{user_id}/website/settings` | Update website settings |
| `POST` | `/users/{user_id}/billing/checkout` | Validate checkout request and return checkout intent placeholder |
| `GET` | `/users/{user_id}/builder/projects` | List tenant builder projects |
| `POST` | `/users/{user_id}/builder/projects` | Create builder project |
| `GET` | `/users/{user_id}/builder/projects/{project_id}` | Load builder project |
| `PUT` | `/users/{user_id}/builder/projects/{project_id}` | Update builder project |
| `DELETE` | `/users/{user_id}/builder/projects/{project_id}` | Archive project; requires tenant owner/admin membership |
| `POST` | `/users/{user_id}/builder/projects/{project_id}/publish` | Publish draft schema |
| `GET` | `/users/{user_id}/builder/projects/{project_id}/form-submissions` | List form submissions |
| `GET` | `/users/{user_id}/builder/projects/{project_id}/form-submissions/{submission_id}` | Read one form submission |
| `POST` | `/users/{user_id}/data/upload` | Upload CSV/XLS/XLSX into tenant/user scoped storage |
| `POST` | `/users/{user_id}/data/read` | Read uploaded file or public data URL |
| `POST` | `/users/{user_id}/cleaning/inspect` | Inspect dataset |
| `POST` | `/users/{user_id}/cleaning/prepare-report` | Preparation/profile report |
| `POST` | `/users/{user_id}/cleaning/statistics` | Statistical report |
| `POST` | `/users/{user_id}/cleaning/missing-report` | Missing value report |
| `POST` | `/users/{user_id}/cleaning/quality-report` | Data quality report |
| `POST` | `/users/{user_id}/cleaning/column-types` | Column type inference |
| `POST` | `/users/{user_id}/cleaning/apply` | Apply cleaning pipeline |
| `GET` | `/users/{user_id}/analysis/catalog` | Localized analysis catalog |
| `POST` | `/users/{user_id}/analysis/run` | Run configured analysis reports |
| `POST` | `/users/{user_id}/analysis/assist` | Run assisted question/metric analysis |
| `POST` | `/users/{user_id}/visualization/create` | Create chart visualization |

### Admin Routes

All admin routes require `user_type = admin`.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/admin/users` | Paginated user list with tenant features |
| `PATCH` | `/admin/users/{user_id}/user-type` | Change local user type to `admin` or `user` |
| `DELETE` | `/admin/users/{user_id}` | Delete user account and possibly tenant |
| `POST` | `/admin/billing/features` | Apply billing/feature update for tenant |

## 7. Tenant and Workspace Model

Tenant membership logic lives in `backend/services/tenant_service.py`.

`TenantContext` contains:

- `tenant_id`
- `user_id`
- `auth_id`
- `role`
- `membership_status`
- `user`
- `membership`

Tenant context lookup:

1. Requires a regular user.
2. Reads local `tenant_id`, `id`, and `auth_id`.
3. Validates the user has an active `tenant_memberships` row matching `tenant_id`, `user_id`, `auth_id`.
4. Returns role and membership metadata.

Builder permissions:

- `require_active_tenant_member`: any active member.
- `require_builder_write_access`: role in `owner`, `admin`, `member`.
- `require_builder_admin_access`: role in `owner`, `admin`.

This creates two layers of protection:

- User id path match prevents cross-user calls.
- Tenant membership prevents cross-tenant data access.

## 8. Database Architecture

The database is Supabase Postgres with migrations in both `database/migrations` and `supabase/migrations`.

Core tables:

- `users`
- `tenants`
- `tenant_memberships`
- `contacts`
- `website_settings`
- `features`
- `builder_projects`
- `builder_form_submissions`

### users

Purpose: local application profile mapped to Supabase Auth.

Important columns:

- `id`
- `auth_id`
- `tenant_id`
- `first_name`
- `last_name`
- `email`
- `phone`
- `avatar`
- `user_type`
- subscription/payment fields from older migrations
- timestamps

The backend treats `users.id` as the path id for `/users/{user_id}/...`.

### tenants

Purpose: tenant/workspace boundary.

Signup creates one tenant per initial account. Membership rows connect users to tenants.

### tenant_memberships

Purpose: tenant authorization.

Fields include tenant id, local user id, Supabase auth id, role, and status.

Builder access checks use this table.

### website_settings

Purpose: tenant public-site settings.

Stores:

- subdomain
- brand
- footer store name
- logo URL
- contact email
- phone
- description
- tenant/user ownership

The service can migrate older user-owned settings into tenant-owned settings when `tenant_id` is missing.

### features

Purpose: billing/subscription/feature state by tenant.

Stores:

- `tenant_id`
- `subscription_type`
- `plan`
- `builder_type`
- `payment_status`

Admin and billing webhook routes update this table through `apply_verified_billing_update`.

### builder_projects

Purpose: durable Page Builder project storage.

Important columns:

- `id`
- `tenant_id`
- `owner_user_id`
- `name`
- `slug`
- `status`: `draft`, `published`, `archived`
- `draft_schema`
- `published_schema`
- `published_version`
- `last_published_at`

The full page-builder state is stored as JSON in `draft_schema`. Publishing copies the draft JSON into `published_schema`, increments `published_version`, and sets `status = published`.

### builder_form_submissions

Purpose: store public submissions for forms embedded in published projects.

Important columns:

- `id`
- `tenant_id`
- `project_id`
- `form_id`
- `form_title`
- `form_version`
- `status`
- `answers`
- `quiz_result`
- `field_snapshot`
- `submitted_at`
- `submitter_ip`
- `user_agent`

Submissions are inserted by public routes using the service-role client and read by authenticated tenant members.

## 9. Supabase Client Strategy

Two clients are created:

- `supabase`: anon key client
- `service_supabase`: service role client

Anon client use cases:

- login with password,
- validate/refresh user sessions,
- password reset token validation.

Service-role client use cases:

- admin user provisioning,
- local user/tenant/membership creation,
- privileged table reads/writes,
- admin user deletion,
- billing updates,
- public form submission insert,
- avatar storage operations.

Because service-role bypasses RLS, the backend must enforce authorization before service-role queries. The recent `/users/{user_id}` guard is part of that application-level authorization layer.

## 10. Security Architecture

### CORS

CORS origins are loaded from `FRONTEND_URLS`, defaulting to localhost development origins. Credentials are allowed because auth is cookie-based.

### CSRF Origin Checking

`services/request_security.py` blocks cookie-authenticated unsafe methods unless the request `Origin` or `Referer` is trusted.

Protected methods:

- `POST`
- `PUT`
- `PATCH`
- `DELETE`

Safe methods are ignored:

- `GET`
- `HEAD`
- `OPTIONS`

The middleware only applies when auth cookies are present.

### Rate Limiting

`services/rate_limit_service.py` provides:

- Redis-backed counters when Redis is available.
- In-memory fallback if Redis fails and `RATE_LIMIT_FAIL_OPEN=true`.
- Scoped helper functions for auth, password, public site, and public form submissions.

Rate-limited areas:

- signup,
- login,
- forgot password,
- password reset,
- public site lookup,
- public form submission.

### User/Admin Separation

Separation is enforced by helpers:

- Admin-only routes call `require_system_admin`.
- User workspace routes call `require_regular_user_id`.
- Tenant builder routes call regular-user tenant membership checks.

This means:

- Admins can manage accounts through `/admin/...`.
- Admins cannot access regular user workspace routes.
- Users cannot access `/admin/...`.
- Users cannot access another user id path.
- Users cannot cross tenant boundaries unless they have an active membership.

### File and URL Safety

Data upload/read hardening includes:

- allowed extensions: `.csv`, `.xls`, `.xlsx`,
- max upload size,
- content-type allowlist,
- generated file names,
- tenant/user upload directories,
- path traversal protection,
- local-file reads restricted to scoped upload roots,
- public URL reads only for HTTP/HTTPS,
- DNS/IP validation to block private, loopback, link-local, multicast, reserved, and unspecified IPs,
- remote byte limits,
- redirect limit.

## 11. User Profile and Avatar Flow

Profile routes live under `/users/{user_id}`.

### Profile Info

`POST /users/{user_id}/info` returns:

- user payload,
- billing summary for the tenant.

### Profile Update

`PUT /users/{user_id}/profile` supports:

- first name,
- last name,
- email,
- phone,
- avatar URL.

Email updates check for duplicates by local `users.email` and `auth_id`.

### Avatar Upload

`POST /users/{user_id}/avatar`:

1. Requires matching regular user id.
2. Reads uploaded file bytes.
3. Enforces 5 MB max.
4. Detects image type by magic bytes.
5. Allows PNG, JPEG, WebP.
6. Stores file at `avatars/users/{auth_id}/{uuid}.{ext}`.
7. Updates local user `avatar`.
8. Attempts cleanup of old avatar if it belonged to the same user storage path.

## 12. Website and Public Site Architecture

Authenticated users configure website settings through:

- `GET /users/{user_id}/website/settings`
- `PUT /users/{user_id}/website/settings`

Validation includes:

- subdomain pattern,
- brand length,
- footer name length,
- image URL/data URL validation,
- contact email validation,
- phone length,
- description length.

Published public sites are loaded through:

- `GET /public/sites/{subdomain}`

Public site loading:

1. Validate subdomain.
2. Rate limit site lookup.
3. Resolve `website_settings` by subdomain.
4. Resolve tenant id.
5. Load latest published `builder_projects` row for tenant.
6. Return site settings and `published_schema`.

Public form submission:

1. Validate subdomain and form id.
2. Rate limit by subdomain + form id.
3. Resolve site and tenant.
4. Load latest published project.
5. Find form in `published_schema`.
6. Confirm a published page contains a connected form block for that form.
7. Validate answers against published form fields.
8. Insert submission with field snapshot, IP, and user agent.

## 13. Page Builder Architecture

Builder routes live under `/users/{user_id}/builder`.

Project lifecycle:

1. Create project with `name`, `slug`, and `draft_schema`.
2. Store project under current tenant and owner user id.
3. List/load/update only within current tenant.
4. Archive instead of hard delete.
5. Publish copies `draft_schema` to `published_schema`, increments version, and requires configured public subdomain.

Project access:

- Listing/loading: active tenant member.
- Creating/updating/publishing: tenant member with write access.
- Archiving: tenant owner/admin membership.

Every builder route also validates the URL `user_id` against the authenticated user context.

Form submissions:

- Public users create submissions through `/public/...`.
- Authenticated tenant users read submissions through `/users/{user_id}/builder/projects/{project_id}/form-submissions`.
- Reads filter by `tenant_id`, `project_id`, and optional `form_id`.

## 14. Billing Architecture

Billing validation and persistence live in `services/billing_service.py`.

Supported subscription modes:

- `full_platform`
  - plans: `starter`, `pro`, `business`
  - `builder_type` must be null

- `individual_builder`
  - plans: `basic`, `premium`
  - `builder_type` required
  - builder types: `website`, `forms`, `quiz`, `reservation`, `reports`, `data`

Payment statuses:

- `pending`
- `active`
- `past_due`
- `canceled`

### User Checkout

`POST /users/{user_id}/billing/checkout` currently validates the desired plan and returns a placeholder checkout response. It is prepared for external checkout integration but does not yet call a provider.

### Webhook

`POST /billing/webhook` requires `BILLING_WEBHOOK_SECRET` and compares the incoming `x-madar-webhook-secret` using constant-time comparison. Valid webhook updates write to `features`.

### Admin Billing Update

`POST /admin/billing/features` allows admins to directly apply billing feature state for a tenant.

## 15. Admin User Management

Admin user services live in `services/admin_user_service.py`.

Capabilities:

- List users with pagination and email search.
- Join tenant features into the list response.
- Change user type between `admin` and `user`.
- Delete user account.

Deletion behavior:

1. Admin cannot delete their own account.
2. Load target user.
3. Check whether the target tenant has any remaining members.
4. Delete Supabase Auth user using admin API.
5. If the target user was the last tenant member, delete tenant.
6. Return deleted user summary.

Because this is service-role backed, the route must always remain admin-gated.

## 16. Data Analysis Architecture

Data-analysis routes live under `/users/{user_id}/...` and require regular-user identity.

### Upload and Read

`data_routes.py` handles:

- file upload,
- external data URL read,
- Google Sheets conversion,
- dataset preview response.

Uploaded files are stored at:

```text
uploads/tenant_{tenant_id}/user_{user_id}/{uuid}.{ext}
```

`DataReadingNormal` supports:

- CSV with multiple encodings,
- Excel,
- JSON public URLs,
- Google Sheets URLs,
- caching by file metadata or URL TTL,
- row and column limits,
- JSON-safe normalization.

### Cleaning

`DataCleaning` extends `DataReadingNormal`.

Capabilities:

- preparation report,
- inspection,
- statistical inspection,
- missing-value report,
- quality report,
- column type detection,
- rename columns/values,
- drop missing rows,
- drop duplicates,
- fill missing values,
- convert types,
- clean text,
- normalize multi-select fields,
- remove outliers,
- correlation and group summaries,
- pipeline execution.

The preparation pipeline normalizes headers, standardizes missing values, infers numeric/date/boolean/text/category/multi-select types, and returns warnings for suspicious mixed data.

### Analysis Routing

`data_analysis/router.py` maps analysis domains to analyzer classes:

- finance,
- meal,
- ngo_meal,
- forms,
- assisted.

The analysis router validates that requested methods exist in `ANALYSIS_CATALOG`, creates one analyzer per domain, and runs requested methods with provided params.

### Visualization

Visualization routes read and optionally clean a dataset, then pass the resulting dataframe to `DataVisualization`.

## 17. Frontend API Contract

The frontend receives `user.id` from:

- `POST /auth/login`, immediately after login.
- `GET /auth/user_status`, after reload/bootstrap.

The frontend then calls user-owned APIs with:

```text
/users/{user.id}/...
```

Key frontend API helper:

- `frontend/src/components/PageBuilder/PageBuilder.api.js`

It resolves the current backend user from `/auth/user_status` if a user id was not passed directly.

Profile/settings/data-analysis views now build URLs using the current authenticated user id.

## 18. Important Request Flows

### Login to Workspace API

1. User submits credentials to `/auth/login`.
2. Supabase validates credentials.
3. Backend sets HTTP-only cookies.
4. Backend returns local `user.id`.
5. Frontend stores user in app state.
6. Frontend calls `/users/{user.id}/...`.
7. Backend validates cookie session and path id match.

### Page Builder Publish

1. Frontend saves current project draft through `/users/{id}/builder/projects`.
2. Backend validates regular user and tenant membership.
3. Backend stores `draft_schema`.
4. Frontend calls `/users/{id}/builder/projects/{project_id}/publish`.
5. Backend requires configured subdomain.
6. Backend copies draft to published schema and increments version.
7. Public site route can now serve the published schema.

### Public Form Submission

1. Public visitor submits to `/public/sites/{subdomain}/forms/{form_id}/submissions`.
2. Backend resolves tenant and latest published project.
3. Backend validates the form exists and is embedded in published pages.
4. Backend validates required/unknown fields.
5. Backend inserts into `builder_form_submissions`.
6. Authenticated tenant user reads it through the user-scoped builder submissions route.

### Data Upload and Analysis

1. User uploads file to `/users/{id}/data/upload`.
2. Backend validates file and stores it under tenant/user directory.
3. Backend previews the dataframe.
4. User runs cleaning/analysis requests with returned `file_path`.
5. Backend resolves the same authenticated tenant/user scope before reading the path.
6. Local file reader rejects paths outside the tenant/user upload root.

## 19. Current Strengths

- Clear FastAPI router organization.
- Supabase session refresh is centralized.
- Service-role key validation prevents accidental insecure startup.
- Cookie security behavior is environment-aware.
- CSRF origin checking protects cookie-authenticated write requests.
- User/admin separation is explicit in route paths and authorization helpers.
- Tenant membership checks protect builder project access.
- Public form submissions validate against published schema rather than draft state.
- Upload and external URL reading include meaningful safety controls.
- Data-analysis pipeline has scoped storage, caching, and bounded dataset sizes.
- Billing logic validates plan/subscription combinations before persistence.

## 20. Known Risks and Follow-Ups

### Service-Role Authorization Discipline

Many routes use `service_supabase`, which bypasses RLS. This is acceptable only if route-level authorization is consistently applied. New routes should never query tenant/user records with service role before checking identity and scope.

Recommended rule: any new user-owned route should be under `/users/{user_id}` and call `require_regular_user_id` or derive tenant context from `tenant_service`.

### Duplicate Legacy Auth Routes

There is a `routes/contact_routes.py` file that appears to define auth-like endpoints under `/auth` as well. Because `auth_routes.py` is the current main auth implementation, this should be reviewed for duplication or dead code.

### Test Harness Drift

Full unittest discovery currently has older import paths such as:

- `data_analysis.data_reading`
- `data_analysis.data_cleaning`
- `data_analysis.analysis_catalog`
- `data_analysis.assisted_analysis`

The current implementation uses nested paths like:

- `data_analysis.io.data_reading`
- `data_analysis.cleaning.data_cleaning`
- `data_analysis.core.analysis_catalog`
- `data_analysis.assisted.assisted_analysis`

Tests should be updated or compatibility modules should be added.

### Billing Checkout Provider

`/users/{user_id}/billing/checkout` validates checkout input but returns a placeholder message. Payment provider integration is still incomplete.

### Admin Visibility Policy

Admins currently can manage users and billing but are intentionally blocked from user workspace endpoints. If support impersonation is ever needed, it should be implemented as a separate audited admin-only impersonation system, not by weakening `/users/{user_id}` checks.

### Public Form Abuse Controls

Public form submissions have rate limiting, schema validation, and IP/user-agent capture. Future hardening could include spam scoring, CAPTCHA, and status workflows.

### Data URL SSRF Protection

The current public URL reader checks DNS results and blocks private/local IP ranges before each redirect. This is a good baseline. If deployed behind complex DNS/network infrastructure, consider adding outbound network egress policies at the container or cloud level as defense in depth.

## 21. Suggested Next Improvements

1. Add route tests for `require_regular_user_id` mismatch behavior.
2. Add tests proving admins receive 403 from `/users/{user_id}/...`.
3. Remove or archive duplicate legacy auth/contact routes after confirming they are unused.
4. Fix data-analysis test imports or add compatibility modules.
5. Introduce typed service-layer response objects for builder and website settings.
6. Add audit logging for admin user deletion, user type changes, and billing feature updates.
7. Implement real checkout provider integration behind the existing billing validation layer.
8. Add OpenAPI route grouping notes or docs for public, user, and admin APIs.
9. Add database-level RLS policy reviews for all tenant-owned tables even though backend uses service role.
10. Add structured logging instead of `print(...)` for production diagnostics.

## 22. File Map

Core app:

- `backend/app.py`
- `backend/database.py`
- `backend/classes.py`

Routes:

- `backend/routes/auth_routes.py`
- `backend/routes/password_routes.py`
- `backend/routes/user_routes.py`
- `backend/routes/website_routes.py`
- `backend/routes/billing_routes.py`
- `backend/routes/admin_billing_routes.py`
- `backend/routes/admin_user_routes.py`
- `backend/routes/builder_routes.py`
- `backend/routes/public_site_routes.py`
- `backend/routes/server_status_routes.py`
- `backend/routes/contact_routes.py`

Services:

- `backend/services/auth_service.py`
- `backend/services/tenant_service.py`
- `backend/services/billing_service.py`
- `backend/services/admin_user_service.py`
- `backend/services/website_settings_service.py`
- `backend/services/request_security.py`
- `backend/services/rate_limit_service.py`

Data analysis:

- `backend/data_analysis/routes/data_routes.py`
- `backend/data_analysis/routes/cleaning_routes.py`
- `backend/data_analysis/routes/analysis_routes.py`
- `backend/data_analysis/routes/visualization_routes.py`
- `backend/data_analysis/io/data_reading.py`
- `backend/data_analysis/cleaning/data_cleaning.py`
- `backend/data_analysis/router.py`
- `backend/data_analysis/domains/*`
- `backend/data_analysis/core/*`
- `backend/data_analysis/assisted/*`
- `backend/data_analysis/visualization/*`

Database migrations:

- `database/migrations/*`
- `supabase/migrations/*`

Tests:

- `backend/tests/*`

## 23. Final Architecture Assessment

The backend architecture is a pragmatic FastAPI/Supabase service with clear route separation, strong cookie-session handling, useful tenant membership checks, and a growing data-analysis subsystem. The most important recent architectural improvement is the explicit split between admin routes and user-owned routes:

- Admins operate through `/admin/...`.
- Regular users operate through `/users/{user_id}/...`.
- Public visitors operate through `/public/...` and `/auth/...`.

This gives the application a clean authorization shape that is easy to reason about and easy to test. The remaining architecture work should focus on removing legacy duplicate routes, tightening tests around the new authorization contract, and documenting service-role query requirements for future backend development.
