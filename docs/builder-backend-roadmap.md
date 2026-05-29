# Builder Backend Roadmap

Inspection date: 2026-05-29

Scope: architecture and planning only. This document records the current Page Builder state and a staged backend implementation plan. No production routes, migrations, models, or application logic are changed by this document.

## Inspection Findings

- The current Page Builder is a rich frontend implementation with project, page, form, response, workflow, user, theme, and publish concepts already modeled in React state.
- Builder persistence and publishing are still primarily localStorage-based through `STORAGE_KEY = "madar_app_builder_frontend_v4"`.
- The public tenant runtime currently reads the published site from localStorage, so it is not a real backend-backed public publishing flow yet.
- The active backend has working secure cookie auth, user profile/avatar routes, website settings routes, feature/subscription routes, and protected data/cleaning/analysis/visualization routes.
- The live database already has core SaaS tables: `tenants`, `users`, `tenant_memberships`, `website_settings`, `features`, and `contacts`.
- There are no backend builder tables yet for projects, pages, forms, submissions, assets, publish snapshots, roles, or site members.
- There are no active backend routes yet under `/builder/*` or `/public/sites/*`.
- The builder frontend already calls backend data-analysis endpoints from `BuilderAnalysisPage.jsx`, but project save/load/publish and site rendering remain frontend-only.
- `PageBuilder.api.js` uses `VITE_API_BASE_URL || "/api"` while the rest of the app uses `VITE_API_URL`; this should be normalized during integration.
- The tenant model now supports `tenant_memberships`, which should become the durable foundation for one tenant with many users.

# Current State Assessment

## Existing Frontend Builder Capabilities

### What Already Exists

- `frontend/src/components/PageBuilder/PageBuilder.jsx` contains the main authenticated builder UI.
- `PageBuilder.constants.js` defines builder tabs, block types, field types, workflow types, permissions, themes, storage key, and empty-state copy.
- `PageBuilder.factories.js` defines project, page, section, form, field, collection, workflow, role, user, and theme factory helpers.
- `BuilderResponsesPage.jsx` provides a responses-focused view for locally captured form/reservation submissions.
- `BuilderAnalysisPage.jsx` integrates uploaded data files with the existing backend data/cleaning/analysis endpoints.
- `TenantSiteRuntime.jsx` renders a public-style site experience from a published project.
- The builder supports pages, forms, response tables, roles/users, theme settings, website chrome, login/register blocks, reservation blocks, collection-like structures, and workflow-like configuration.

### What Can Be Reused

- The existing project JSON shape from `createProject()` can be used as the draft schema stored in backend JSON columns or normalized across tables.
- Existing UI flows for editing pages/forms/theme can be retained while swapping persistence from localStorage to APIs.
- `BuilderAnalysisPage.jsx` can reuse the existing protected data-analysis backend endpoints.
- `TenantSiteRuntime.jsx` can be reused as the public renderer once it loads published snapshots from backend routes.
- Existing authenticated app user state and secure HttpOnly cookie auth can be reused for owner/admin builder APIs.

### What Must Be Rebuilt

- Project save/load/publish must move from localStorage to backend APIs.
- Published site rendering must load immutable published snapshots from public backend routes.
- Forms and submissions need backend persistence.
- Builder assets/media need backend storage, validation, and tenant ownership.
- Builder roles/users/permissions need a real tenant membership and role model.
- Workflows, collections, and site-member features should remain out of MVP unless explicitly needed.

### Risks

- The current builder stores large nested objects in localStorage. Moving directly to normalized tables could create many integration points at once.
- Some files appear experimental or parallel implementations, including `PageBuilder.subdomain.jsx`, `PageBuilder.factories.subdomain.js`, and `LoginPage.updated.jsx`.
- Existing local project data may not map cleanly to future backend records unless a compatibility layer is planned.
- The API base variable mismatch can cause calls to hit the wrong origin if not fixed carefully.

## Existing Backend Capabilities

### What Already Exists

- `backend/app.py` configures FastAPI, CORS with credentials, secure cookie auth routes, user routes, website routes, feature routes, contact routes, and data-analysis routes.
- Active auth routes include `/auth/signup`, `/auth/login`, `/auth/user_status`, and `/auth/log_out`.
- Active user routes include `/user/info`, `/user/profile`, and `/user/avatar`.
- Active website settings routes include `/website/settings` GET and PUT.
- Protected data routes exist under `/data`, `/cleaning`, `/analysis`, and `/visualization`.
- `backend/services/auth_service.py` centralizes cookie names, cookie settings, session lookup, token refresh, and authenticated user lookup.
- `backend/routes/auth_routes.py` creates a tenant, user, and owner membership during signup.
- `backend/routes/features_routes.py` stores subscription/features by tenant.

### What Can Be Reused

- `require_authenticated_user` should be reused for owner/admin builder APIs.
- `get_current_user_payload` and `get_authenticated_user_row` can provide user and tenant context.
- Existing tenant-aware user payloads can seed builder ownership checks.
- Existing upload validation patterns from avatar upload and data upload can guide builder asset validation.
- Existing `service_supabase` usage should be reused for trusted server-side table operations.

### What Must Be Rebuilt

- Add dedicated builder route module, likely `backend/routes/builder_routes.py`.
- Add request/response models in `backend/classes.py` or a new model module if the file becomes too large.
- Add public runtime route module for published site reads and form submissions.
- Add shared tenant authorization helpers for owner/member checks.
- Add rate limiting middleware or route-level throttling for auth and public form submissions.

### Risks

- Website settings currently use tenant-aware records but should be reviewed for consistent use of server-side Supabase and RLS.
- Builder APIs must not trust tenant IDs from request bodies.
- Publishing must create immutable snapshots rather than exposing mutable drafts.

## Existing Database Tables

### What Already Exists

- `tenants`: tenant identity and basic owner/brand metadata.
- `users`: app users with `auth_id`, email, profile fields, avatar, subscription fields, and `tenant_id`.
- `tenant_memberships`: tenant/user/auth membership rows with role and status.
- `website_settings`: tenant/user website settings, including subdomain and brand fields.
- `features`: tenant subscription and builder feature selection.
- `contacts`: contact form records.

### What Can Be Reused

- `tenants.tenant_id` should be the primary tenant boundary for builder data.
- `users.tenant_id` can remain the default/current tenant for the current single-tenant-per-user UX.
- `tenant_memberships` should become the source of truth for multi-user tenant access.
- `website_settings.subdomain` can be reused for public site subdomain routing if uniqueness is enforced.

### What Must Be Rebuilt

- Add builder project/page/form/submission/asset tables.
- Add tenant role tables if the current text role on memberships is not enough for builder permissions.
- Add publish metadata or published snapshot columns/tables.
- Add RLS policies for builder tables.

### Risks

- If `users.tenant_id` and `tenant_memberships` disagree, authorization behavior can become ambiguous.
- Subdomain uniqueness and ownership need database-level constraints.
- RLS must match the server-side access pattern. Service role operations bypass RLS, so app-level checks are still required.

## Existing Tenant Model

### What Already Exists

- Signup creates a tenant row.
- Signup creates the first user with `tenant_id`.
- Signup creates a `tenant_memberships` row with owner role and active status.
- Existing user payloads include `tenant_id`.

### What Can Be Reused

- Owner membership can authorize builder project creation.
- Active membership can authorize member access later.
- `tenant_id` can be attached to every builder table.

### What Must Be Rebuilt

- Define member roles and permissions for builder access.
- Decide whether `users.tenant_id` is only the default tenant or a hard one-user-one-tenant constraint.
- Add tenant role records if custom roles are needed.

### Risks

- A future multi-tenant switcher will need APIs to select active tenant.
- Builder APIs should query membership for authorization, not only the user row's `tenant_id`.

## Existing Authentication Model

### What Already Exists

- Secure HttpOnly cookies are used for access and refresh tokens.
- Cookies support `Secure` and `SameSite=None` for cross-origin Cloudflare tunnels.
- CORS allows credentials and explicit frontend origins.
- `/auth/user_status` verifies session state.
- `/user/info` returns the current user profile and tenant context.

### What Can Be Reused

- Existing cookie auth can protect all builder owner/admin APIs.
- Existing user info loading can hydrate frontend builder ownership state.
- Existing logout flow can clear builder state and draft cache.

### What Must Be Rebuilt

- Add CSRF protection for state-changing cookie-authenticated APIs.
- Add rate limits for login, signup, and public submission endpoints.
- Add tenant authorization dependencies beyond simple authentication.

### Risks

- `SameSite=None` cookies are required for tunnels but increase CSRF exposure without CSRF tokens or origin checks.
- Public routes must not reuse authenticated dependencies accidentally.

## Existing Publishing Flow

### What Already Exists

- `PageBuilder.jsx` has a local `publishProject` flow that writes publish metadata into localStorage.
- `TenantSiteRuntime.jsx` reads the published project from localStorage.
- The frontend can preview a site-like runtime experience.

### What Can Be Reused

- The current published project JSON shape can become the snapshot payload.
- The preview/runtime UI can render backend snapshots with limited changes.
- Existing subdomain settings can contribute to route resolution.

### What Must Be Rebuilt

- Persist draft project state to backend.
- Create a backend publish endpoint.
- Store immutable published snapshots.
- Serve published snapshots through public read-only routes.
- Add subdomain lookup and uniqueness validation.

### Risks

- If public routes read draft rows, unpublished changes could leak.
- If published rows are mutable, version integrity and rollback become harder.

## Existing Submission Flow

### What Already Exists

- Runtime forms and reservation blocks can submit into local project state.
- `BuilderResponsesPage.jsx` can display locally stored submissions.
- Response fields and statuses exist in frontend structures.

### What Can Be Reused

- Existing submission objects can guide backend form submission schema.
- Existing responses UI can be wired to backend submission read routes.
- Existing field definitions can drive backend validation.

### What Must Be Rebuilt

- Public form submission endpoint.
- Reservation submission endpoint.
- Submission validation against published form schema.
- Owner/admin submission read APIs.
- Spam protection, rate limiting, and optional captcha/honeypot.

### Risks

- Trusting frontend field definitions without checking published schema can allow arbitrary data injection.
- Public submission endpoints can become spam targets.
- File fields need separate asset rules and stricter validation.

## Existing Storage / Upload Flow

### What Already Exists

- Avatar upload stores validated images under `backend/avatar_uploads/` and serves them from `/avatar_uploads`.
- Data upload stores CSV/XLS/XLSX files under backend upload storage and restricts reads to uploaded files.
- Chart generation writes only to `generated_charts`.

### What Can Be Reused

- Existing content-type and size validation patterns can guide builder asset uploads.
- Existing static serving approach can be used for local development assets.
- Existing path confinement logic should be mirrored for builder assets.

### What Must Be Rebuilt

- Builder asset table and upload endpoint.
- Tenant-owned asset storage path.
- Public asset serving strategy for published sites.
- Asset deletion and garbage collection rules.

### Risks

- Serving tenant files from a shared static directory without ownership checks can leak assets.
- Public assets and private draft assets need different access models.
- Large media files may exceed local disk expectations on the home server.

## Existing Security Model

### What Already Exists

- Authenticated backend routes use secure cookies and CORS credentials.
- Data, cleaning, analysis, and visualization endpoints are protected by auth.
- File reads are confined to upload directories.
- SSRF/private URL blocking exists in data reading.
- Chart output is restricted to generated chart storage.
- Generic public errors are used in sensitive auth flows.

### What Can Be Reused

- Auth route dependency patterns.
- Tenant ID in authenticated user payload.
- Service role Supabase access for trusted backend operations.
- Existing upload validation and path safety patterns.

### What Must Be Rebuilt

- RLS policies for builder tables.
- Tenant authorization helpers.
- CSRF protection.
- Public form rate limiting.
- Asset validation and scanning rules.
- Auditable publish snapshots.

### Risks

- Service role operations must be paired with explicit tenant filters.
- Public routes require careful distinction between published and draft data.
- Cookie-based APIs need CSRF defenses before broadening write surface area.

## Existing Technical Debt And Blockers

### What Already Exists

- LocalStorage persistence is deeply embedded in builder save/load/publish flows.
- Builder API config uses a different env var name than the rest of the frontend.
- Several Page Builder files appear to be alternate or older paths.
- Backend has no builder-specific models, routes, migrations, or RLS.

### What Can Be Reused

- Current frontend state shape.
- Current builder UI controls and flows.
- Current tenant signup foundation.
- Current profile/session infrastructure.

### What Must Be Rebuilt

- Durable backend persistence.
- Public runtime backend integration.
- Ownership and permission model.
- Submission persistence and analysis integration.

### Risks

- Implementing every builder concept at once would be high-risk.
- Workflows, collections, automation, site members, and advanced permissions should be deferred until MVP persistence and publishing are stable.

# Phase 1: Database / Migration Foundation

Risk: High

## Files Likely Involved

- `database/migrations/*`
- `supabase/migrations/*`

## Proposed Tables

### `builder_projects`

Required columns:

- `id uuid primary key default gen_random_uuid()`
- `tenant_id uuid not null references tenants(tenant_id) on delete cascade`
- `owner_user_id uuid references users(id) on delete set null`
- `name text not null`
- `slug text not null`
- `status text not null default 'draft'`
- `draft_schema jsonb not null default '{}'::jsonb`
- `published_schema jsonb`
- `published_version integer not null default 0`
- `last_published_at timestamptz`
- `created_at timestamptz not null default now()`
- `updated_at timestamptz not null default now()`

Relationships:

- One tenant has many builder projects.
- One project has many pages, forms, assets, and submissions.

Constraints:

- Unique `(tenant_id, slug)`.
- Check `status in ('draft', 'published', 'archived')`.

Ownership model:

- Tenant owner/admin can create projects.
- Project owner can be tracked by `owner_user_id`, but access should still be tenant membership based.

Tenant isolation model:

- Every query must filter by `tenant_id`.
- RLS should allow rows only for active tenant members.

### `builder_pages`

Required columns:

- `id uuid primary key default gen_random_uuid()`
- `tenant_id uuid not null references tenants(tenant_id) on delete cascade`
- `project_id uuid not null references builder_projects(id) on delete cascade`
- `title text not null`
- `slug text not null`
- `page_type text not null default 'page'`
- `sort_order integer not null default 0`
- `draft_content jsonb not null default '{}'::jsonb`
- `published_content jsonb`
- `is_home boolean not null default false`
- `created_at timestamptz not null default now()`
- `updated_at timestamptz not null default now()`

Constraints:

- Unique `(project_id, slug)`.
- At most one home page per project should be enforced with a partial unique index.

### `builder_forms`

Required columns:

- `id uuid primary key default gen_random_uuid()`
- `tenant_id uuid not null references tenants(tenant_id) on delete cascade`
- `project_id uuid not null references builder_projects(id) on delete cascade`
- `page_id uuid references builder_pages(id) on delete set null`
- `name text not null`
- `slug text not null`
- `schema jsonb not null default '{}'::jsonb`
- `published_schema jsonb`
- `is_active boolean not null default true`
- `created_at timestamptz not null default now()`
- `updated_at timestamptz not null default now()`

Constraints:

- Unique `(project_id, slug)`.

### `builder_form_submissions`

Required columns:

- `id uuid primary key default gen_random_uuid()`
- `tenant_id uuid not null references tenants(tenant_id) on delete cascade`
- `project_id uuid not null references builder_projects(id) on delete cascade`
- `form_id uuid not null references builder_forms(id) on delete cascade`
- `page_id uuid references builder_pages(id) on delete set null`
- `submission_type text not null default 'form'`
- `payload jsonb not null`
- `status text not null default 'new'`
- `source_ip_hash text`
- `user_agent text`
- `created_at timestamptz not null default now()`
- `updated_at timestamptz not null default now()`

Constraints:

- Check `submission_type in ('form', 'reservation')`.
- Check `status in ('new', 'reviewed', 'archived', 'spam')`.

Public write model:

- Public users can insert submissions only through backend service routes, not directly through client Supabase.
- Backend validates payload against published form schema.

### `builder_assets`

Required columns:

- `id uuid primary key default gen_random_uuid()`
- `tenant_id uuid not null references tenants(tenant_id) on delete cascade`
- `project_id uuid references builder_projects(id) on delete cascade`
- `uploaded_by_user_id uuid references users(id) on delete set null`
- `filename text not null`
- `storage_path text not null`
- `public_url text`
- `mime_type text not null`
- `size_bytes bigint not null`
- `asset_kind text not null default 'image'`
- `visibility text not null default 'draft'`
- `created_at timestamptz not null default now()`

Constraints:

- Unique `storage_path`.
- Check `visibility in ('draft', 'published', 'private')`.

### `tenant_memberships`

Current table already exists and should be retained.

Recommended required columns:

- `id uuid primary key`
- `tenant_id uuid not null references tenants(tenant_id) on delete cascade`
- `user_id uuid references users(id) on delete cascade`
- `auth_id uuid`
- `role text not null`
- `status text not null default 'active'`
- `created_at timestamptz`
- `updated_at timestamptz`

Recommended constraints:

- Unique `(tenant_id, user_id)` where `user_id is not null`.
- Unique `(tenant_id, auth_id)` where `auth_id is not null`.
- Check role and status values.

### `tenant_roles`

Required columns:

- `id uuid primary key default gen_random_uuid()`
- `tenant_id uuid not null references tenants(tenant_id) on delete cascade`
- `name text not null`
- `slug text not null`
- `permissions jsonb not null default '{}'::jsonb`
- `is_system boolean not null default false`
- `created_at timestamptz not null default now()`
- `updated_at timestamptz not null default now()`

Constraints:

- Unique `(tenant_id, slug)`.

MVP note:

- This can be deferred if `tenant_memberships.role` with fixed values is enough for first release.

## Optional Future Tables

### `builder_collections`

- Use later for CMS-like structured content.
- Defer until project/page/form persistence is stable.

### `builder_workflows`

- Use later for automation rules triggered by form submissions.
- Defer because it introduces background job semantics, notifications, and failure handling.

### `site_members`

- Use later for private pages or customer accounts inside published tenant sites.
- Defer because it creates a second authentication domain separate from SaaS owner/admin auth.

## RLS Strategy

- Enable RLS on all builder tables.
- Authenticated direct Supabase access should be allowed only if JWT claims can safely map to `auth.uid()` and active memberships.
- Backend service-role access must still enforce tenant filters in code because service role bypasses RLS.
- Public routes should not expose Supabase credentials. They should read published data through backend service routes.
- Submissions should be inserted by backend routes after validation and rate limiting.

## Validation Checklist

- Migrations apply cleanly on a fresh database.
- Migrations apply cleanly on the current database.
- Existing users continue working.
- Signup creates a tenant, user, and owner membership.
- Login and `/user/info` still return the expected tenant context.
- RLS prevents cross-tenant reads.
- RLS prevents cross-tenant writes.
- Subdomain uniqueness works.
- Existing website settings remain readable and editable.

# Phase 2: Backend Route Design

Risk: High

## Files Likely Involved

- `backend/routes/builder_routes.py`
- `backend/classes.py`
- `backend/app.py`
- `backend/services/auth_service.py`
- Optional: `backend/services/tenant_service.py`
- Optional: `backend/services/builder_service.py`

## Shared Backend Requirements

Authentication:

- All `/builder/*` owner/admin routes require secure cookie auth with `require_authenticated_user`.
- Public `/public/*` routes do not require auth, but must only expose published data.

Authorization:

- Resolve the current user's active tenant from authenticated user row and/or `tenant_memberships`.
- Do not accept `tenant_id` from clients as authority.
- Check active tenant membership for every project/page/form/asset/submission read or write.
- Owner/admin required for project deletion, publishing, members, and role changes.

Validation:

- Validate UUID path params.
- Validate slugs.
- Validate JSON schema size.
- Validate page and form ownership through project and tenant.
- Validate uploaded asset MIME type, extension, and size.
- Return generic public errors where details may leak tenant data.

## Projects

### `GET /builder/projects`

Request:

- Optional query params: `status`, `limit`, `offset`.

Response:

- List of projects for the current tenant with summary metadata.

Auth:

- Authenticated tenant member.

Ownership checks:

- Filter by current tenant membership.

### `POST /builder/projects`

Request model:

- `name`
- `slug`
- Optional `draft_schema`
- Optional initial `site_chrome`
- Optional initial `theme`

Response:

- Created project.

Auth:

- Tenant owner/admin or member with builder create permission.

Validation:

- Slug unique inside tenant.
- Project schema must fit size limits.

### `GET /builder/projects/{id}`

Response:

- Full project draft with pages/forms/assets summaries.

Auth:

- Authenticated tenant member.

Ownership checks:

- Project must belong to current tenant.

### `PUT /builder/projects/{id}`

Request model:

- `name`
- `slug`
- `status`
- `draft_schema`
- Optional partial update fields.

Response:

- Updated project.

Auth:

- Tenant owner/admin or member with edit permission.

Validation:

- Prevent changing `tenant_id`.
- Enforce schema size and supported keys.

### `DELETE /builder/projects/{id}`

Response:

- Success marker.

Auth:

- Tenant owner/admin.

Behavior:

- Prefer soft archive first; hard delete only if explicitly required.

## Publishing

### `POST /builder/projects/{id}/publish`

Request model:

- Optional `message`
- Optional `target_subdomain`
- Optional `include_assets`

Response:

- `published_version`
- `published_at`
- Public site URL data.

Auth:

- Tenant owner/admin or publish permission.

Behavior:

- Validate project completeness.
- Validate subdomain ownership.
- Copy current draft schema/pages/forms into immutable published snapshot fields or snapshot table.
- Mark referenced assets as published where appropriate.

Validation:

- Published versions are immutable snapshots.
- Draft rows remain editable after publish without changing public output.

## Pages

Recommended routes:

- `GET /builder/projects/{project_id}/pages`
- `POST /builder/projects/{project_id}/pages`
- `GET /builder/projects/{project_id}/pages/{page_id}`
- `PUT /builder/projects/{project_id}/pages/{page_id}`
- `DELETE /builder/projects/{project_id}/pages/{page_id}`

Request model:

- `title`
- `slug`
- `page_type`
- `sort_order`
- `draft_content`
- `is_home`

Response model:

- Page record with draft content and metadata.

Auth:

- Authenticated tenant member for read.
- Owner/admin/editor for write.

Ownership:

- Project and page must both belong to current tenant.

## Forms

Recommended routes:

- `GET /builder/projects/{project_id}/forms`
- `POST /builder/projects/{project_id}/forms`
- `GET /builder/projects/{project_id}/forms/{form_id}`
- `PUT /builder/projects/{project_id}/forms/{form_id}`
- `DELETE /builder/projects/{project_id}/forms/{form_id}`

Request model:

- `name`
- `slug`
- `page_id`
- `schema`
- `is_active`

Response model:

- Form record with schema and metadata.

Auth:

- Authenticated tenant member for read.
- Owner/admin/editor for write.

Validation:

- Field types must be from supported frontend list.
- Required fields must have stable IDs.

## Assets

Recommended routes:

- `GET /builder/projects/{project_id}/assets`
- `POST /builder/projects/{project_id}/assets`
- `GET /builder/projects/{project_id}/assets/{asset_id}`
- `PUT /builder/projects/{project_id}/assets/{asset_id}`
- `DELETE /builder/projects/{project_id}/assets/{asset_id}`

Request model:

- Multipart file upload for create.
- Metadata update for rename/alt text/visibility if supported.

Response model:

- Asset ID, URL, MIME type, size, visibility.

Auth:

- Authenticated tenant member with edit permission.

Validation:

- Allow image formats initially: PNG, JPEG, WebP, SVG only if sanitized.
- Enforce max file size.
- Store under tenant/project scoped path.

## Members

Recommended routes:

- `GET /builder/members`
- `POST /builder/members/invite`
- `PUT /builder/members/{membership_id}`
- `DELETE /builder/members/{membership_id}`
- `GET /builder/roles`
- `POST /builder/roles`
- `PUT /builder/roles/{role_id}`
- `DELETE /builder/roles/{role_id}`

MVP:

- Use existing `tenant_memberships.role` with fixed values: `owner`, `admin`, `editor`, `viewer`.
- Defer custom `tenant_roles` UI until needed.

Auth:

- Owner/admin only.

Validation:

- Prevent removing last owner.
- Prevent privilege escalation by non-owner users.

## Submissions

Recommended owner/admin read routes:

- `GET /builder/projects/{project_id}/submissions`
- `GET /builder/projects/{project_id}/forms/{form_id}/submissions`
- `GET /builder/projects/{project_id}/submissions/{submission_id}`
- `PUT /builder/projects/{project_id}/submissions/{submission_id}`

Request model:

- Filters: `form_id`, `status`, `created_from`, `created_to`, `limit`, `offset`.
- Update: `status`, optional owner notes if added.

Response model:

- Submission records with payload and form metadata.

Auth:

- Authenticated tenant member with response view permission.

Validation:

- Tenant/project/form ownership checks.
- Avoid returning hidden/system fields unless authorized.

## Validation Checklist

- Tenant owner can create, read, update, delete own project.
- Tenant editor can edit only when role permits it.
- Cross-tenant access returns 403 or 404 consistently.
- Project publish creates immutable snapshot.
- Draft edits after publish do not alter public output.
- Asset upload validates file type and size.
- Submission read filters work and stay tenant-scoped.

# Phase 3: Frontend Integration Plan

Risk: Medium-High

## Files Likely Involved

- `frontend/src/components/PageBuilder/PageBuilder.jsx`
- `frontend/src/components/PageBuilder/BuilderResponsesPage.jsx`
- `frontend/src/components/PageBuilder/BuilderAnalysisPage.jsx`
- `frontend/src/components/PageBuilder/PageBuilder.api.js`
- `frontend/src/pages/SettingsPage.jsx`
- Optional: `frontend/src/components/PageBuilder/TenantSiteRuntime.jsx`

## Replace LocalStorage Save

Current behavior:

- `PageBuilder.jsx` writes the full project object to localStorage under `STORAGE_KEY`.

Target behavior:

- Save drafts through `PUT /builder/projects/{id}`.
- Save pages through page CRUD routes once normalized.
- Save forms through form CRUD routes once normalized.
- Keep localStorage as a draft cache only for temporary offline recovery.

Implementation approach:

- Introduce a small builder API client in `PageBuilder.api.js`.
- Normalize API base URL to `VITE_API_URL`.
- Add `credentials: "include"` to all authenticated builder requests.
- Initially store the full project JSON in `builder_projects.draft_schema` to reduce frontend churn.
- Later split pages/forms/assets into normalized tables as the UI stabilizes.

## Replace LocalStorage Publish

Current behavior:

- `publishProject` updates local project publish metadata and stores it in localStorage.

Target behavior:

- `POST /builder/projects/{id}/publish` creates immutable published snapshot.
- Frontend receives public URL metadata and published version.
- Local project state updates only with returned publish metadata.

## Replace LocalStorage Load

Current behavior:

- `loadInitialProject` reads localStorage.

Target behavior:

- On builder mount, call `GET /builder/projects` and select recent/default project.
- Load selected project with `GET /builder/projects/{id}`.
- If backend load fails and localStorage has a draft cache, offer a recovery path instead of silently replacing backend data.

## Add Backend Synchronization

Recommended sequence:

1. Add API client methods.
2. Load project list on builder entry.
3. Save current draft to backend manually with the existing Save button.
4. Add debounced autosave only after manual save is reliable.
5. Add conflict handling with `updated_at` or version numbers.

## Keep LocalStorage As Draft Cache/Fallback

Allowed uses:

- Unsaved local draft cache.
- Temporary recovery after network failure.
- Migration helper for old local projects.

Disallowed uses:

- Source of truth for published sites.
- Source of truth for owner response lists.
- Source of truth for tenant roles or members.

## Responses Page Integration

Current behavior:

- `BuilderResponsesPage.jsx` reads local project submission structures.

Target behavior:

- Load submissions from `GET /builder/projects/{project_id}/submissions`.
- Support filters by form/status/date.
- Keep analysis import by passing selected submissions or exported CSV to analysis flows.

## Builder Analysis Page Integration

Current behavior:

- `BuilderAnalysisPage.jsx` already calls protected backend data endpoints.

Target behavior:

- Keep those calls.
- Optionally add direct import from backend form submissions.
- Maintain `credentials: "include"`.

## Settings Page Integration

Current behavior:

- `SettingsPage.jsx` saves website settings through `/website/settings` and also touches builder localStorage for some site chrome fields.

Target behavior:

- Website settings remain the tenant-level source for brand/subdomain.
- Builder projects should reference or copy tenant website settings intentionally.
- Avoid silent localStorage updates that drift from backend settings.

## Validation Checklist

- Save project.
- Refresh browser.
- Logout and login.
- Project persists.
- Publish project.
- Draft changes after publish remain private.
- Responses page loads backend data.
- Analysis page still uploads and analyzes CSV.
- Refresh `/page-builder` does not lose project.

# Phase 4: Public Tenant Runtime

Risk: High

## Files Likely Involved

- `frontend/src/components/PageBuilder/TenantSiteRuntime.jsx`
- New public backend route module, likely `backend/routes/public_site_routes.py`
- `backend/app.py`
- Public route models in `backend/classes.py` or a route-local schema module

## Public Route Design

### `GET /public/sites/{subdomain}`

Purpose:

- Resolve a public site by subdomain.

Response:

- Site metadata.
- Published project ID/version.
- Home page slug.
- Navigation summary.
- Theme and site chrome.

Access:

- Public.

Rules:

- Return only published snapshots.
- Do not reveal draft project IDs or private owner data.
- Return 404 for unknown, inactive, or unpublished sites.

### `GET /public/sites/{subdomain}/pages/{slug}`

Purpose:

- Load one published page by slug.

Response:

- Published page content.
- Published forms referenced by the page.
- Public asset URLs.

Access:

- Public.

Rules:

- Read only published page content.
- Draft-only pages return 404.
- Private pages require future site-member auth and should be out of MVP.

### `POST /public/sites/{subdomain}/forms/{form_id}/submissions`

Purpose:

- Accept public form submissions.

Request:

- JSON payload keyed by published field IDs.
- Optional anti-spam token or honeypot fields.

Response:

- Generic success marker.

Access:

- Public, rate limited.

Rules:

- Validate against published form schema.
- Ignore or reject fields not in schema.
- Store submission with tenant, project, form, and page context.

### Reservation Submission Route

Recommended route:

- `POST /public/sites/{subdomain}/reservations/{form_id}/submissions`

Alternative:

- Use the same form submission route with `submission_type = 'reservation'`.

MVP recommendation:

- Use the same endpoint and distinguish reservation forms by schema/type. This avoids duplicate validation paths.

## Public Access Rules

- Public users can read only published site metadata, pages, forms, and published assets.
- Public users can create submissions only through validated public endpoints.
- Public users cannot list submissions.
- Public users cannot access draft project JSON.
- Unknown or unpublished subdomains return 404.

## Published Vs Draft Behavior

- Draft tables/columns are owner/admin only.
- Published snapshots are copied during publish.
- Public routes read published snapshots only.
- Publish creates a version number and timestamp.
- Later rollback can repoint current published version to an older immutable snapshot.

## Subdomain Resolution

- Use `website_settings.subdomain` as the canonical subdomain owner.
- Enforce uniqueness at database level.
- Normalize subdomains to lowercase.
- Validate allowed characters and reserved names.
- Public route resolves subdomain to tenant and active published project.

## Caching Strategy

- Public site metadata and pages can be cached briefly with ETags or version-based cache keys.
- Published version should be included in responses.
- Asset URLs should include stable content paths or cache-busting version markers.
- Form submission endpoints must not be cached.

## Security Considerations

- No draft data on public routes.
- No owner email/phone unless explicitly part of public website settings.
- Rate limit public reads if abuse appears, but prioritize form submission rate limits.
- Validate form payload size.
- Validate file uploads separately if public file fields are added.
- Store source IP as hash or metadata carefully to minimize privacy risk.

## Validation Checklist

- Public site works without auth.
- Unknown subdomain returns 404.
- Unpublished site returns 404.
- Published home page loads.
- Published page by slug loads.
- Draft changes remain private.
- Public form submission succeeds for valid payload.
- Public form submission rejects invalid fields.
- Public form submission is rate limited.

# Phase 5: Security, RLS, And Rate Limiting

Risk: High

## Files Likely Involved

- Migrations in `database/migrations/*` and/or `supabase/migrations/*`
- `backend/services/auth_service.py`
- Route dependencies in new builder/public route modules
- Middleware in `backend/app.py` or a dedicated middleware module
- Optional service modules for tenant and rate-limit helpers

## Tenant Isolation Helpers

Required helpers:

- `get_current_tenant_context(user)` returns tenant ID, user ID, auth ID, role, and membership status.
- `require_tenant_member` checks active membership.
- `require_tenant_role(["owner", "admin"])` checks role.
- `assert_project_access(project_id, tenant_id)` checks project ownership.
- `assert_page_access(page_id, project_id, tenant_id)` checks page ownership.
- `assert_form_access(form_id, project_id, tenant_id)` checks form ownership.

Rules:

- Never trust client-supplied `tenant_id`.
- Always join or filter by tenant ID.
- Prefer 404 for cross-tenant object lookup if object existence should not be revealed.

## RLS Policies

Recommended policies:

- Tenant members can select builder projects for their tenant.
- Tenant editors/admins can insert/update builder projects for their tenant.
- Tenant owners/admins can delete/archive builder projects.
- Public users cannot directly select draft builder tables through Supabase client.
- Public published views should be exposed through backend routes, not direct table access.
- Form submissions should not be publicly selectable.

Important:

- Service role bypasses RLS. Backend code must still enforce tenant checks.

## Cookie Authentication Requirements

- Continue using HttpOnly cookies.
- Continue using `Secure` and `SameSite=None` where cross-origin tunnel deployment requires it.
- Continue using CORS exact frontend origins with `allow_credentials=True`.
- All frontend builder API calls must include `credentials: "include"`.
- Keep `/auth/user_status` and `/user/info` as refresh-time session sources.

## CSRF Protection Requirements

Because cookies are sent automatically:

- Add CSRF token protection for state-changing authenticated routes.
- At minimum, enforce strict `Origin` and `Referer` checks against configured frontend origins.
- Prefer a double-submit CSRF token or server-issued CSRF token endpoint for authenticated writes.
- Apply to POST, PUT, PATCH, DELETE under `/builder`, `/website`, `/user/profile`, `/user/avatar`, and other state-changing routes.

## Upload Limits

Recommended initial limits:

- Builder image asset max: 5 MB.
- Builder document asset max: defer until needed.
- Public form JSON payload max: small fixed size, such as 256 KB.
- Public file fields: defer or require stricter 5 MB limit and virus scanning if added.

Allowed MIME types:

- Images: `image/png`, `image/jpeg`, `image/webp`.
- SVG only if sanitized or disallowed for MVP.

Storage:

- Tenant/project scoped paths.
- No user-controlled path components.
- Randomized filenames.

## Asset Validation

- Validate content type and extension.
- Optionally inspect magic bytes for images.
- Strip metadata if privacy requirements demand it.
- Return backend-origin URLs for assets.
- Keep draft assets private until publish if feasible.

## Submission Spam Protection

- Rate limit by IP and subdomain/form.
- Add honeypot field support.
- Add minimum form render-to-submit delay if needed.
- Optionally add CAPTCHA later.
- Store rejected submission metadata only if useful and privacy-safe.

## Login / Signup Rate Limits

- Apply per-IP and per-email throttles.
- Keep public error messages generic.
- Log enough server-side metadata to investigate abuse without leaking to clients.

## Form Submission Rate Limits

- Apply per-IP, per-subdomain, and per-form limits.
- Use stricter limits for unauthenticated public endpoints.
- Return generic 429 response.
- Do not reveal whether a form ID exists across tenants.

## Validation Checklist

- Cross-tenant project access fails.
- Cross-tenant page access fails.
- Cross-tenant form access fails.
- Cross-tenant submission access fails.
- Public draft data is inaccessible.
- Public submissions are rate limited.
- Invalid upload types are rejected.
- Oversized uploads are rejected.
- Cookie auth continues working.
- CSRF protection does not break legitimate frontend calls.

# Phase 6: End-To-End Testing Checklist

## Authentication

- Signup creates user, tenant, and owner membership.
- Login sets secure HttpOnly cookies.
- `/auth/user_status` returns authenticated state.
- `/user/info` returns user and tenant context.
- Logout clears session cookies.
- Session persists after refresh on `/settings`, `/dashboard`, and `/page-builder`.

## Tenant Creation

- New tenant row is created during signup.
- First user is assigned owner role.
- Membership row is created.
- Existing users still load correctly.
- Future invited members can belong to same tenant.

## Builder

- Create project.
- List projects.
- Load project.
- Update project.
- Archive/delete project.
- Create page.
- Update page.
- Delete page.
- Create form.
- Update form.
- Delete form.
- Upload asset.
- Load asset list.
- Reject invalid asset type.
- Reject oversized asset.

## Publishing

- Publish project.
- Confirm published version increments.
- Confirm public site uses published snapshot.
- Update draft after publish.
- Confirm public site does not change until republished.
- Publish updates.
- Confirm previous version integrity.

## Public Runtime

- Load site by subdomain.
- Load home page.
- Load page by slug.
- Unknown page returns 404.
- Unknown subdomain returns 404.
- Submit form.
- Submit reservation.
- Invalid submission is rejected.
- Rate-limited submission returns 429.

## Responses

- Owner can review submissions.
- Editor/viewer access follows role permissions.
- Filter by form.
- Filter by status.
- Filter by date.
- Update submission status.
- Import/export response data for analysis.

## Regression Tests

- Refresh `/settings`.
- Refresh `/dashboard`.
- Refresh `/page-builder`.
- Avatar upload still works.
- Profile updates still work.
- Website settings updates still work.
- Data upload still works.
- Analysis still works.
- Chart generation still works if called by existing workflows.
- CORS credentials still work from the frontend tunnel.

# Final Section

## Recommended Implementation Order

1. Database foundation for builder projects, pages, forms, submissions, and assets.
2. Tenant authorization helpers and fixed role checks.
3. Authenticated project CRUD using full draft JSON storage first.
4. Frontend project save/load integration.
5. Publish endpoint with immutable published snapshot.
6. Public site read routes.
7. Public form submission route and owner submission read routes.
8. Asset upload support.
9. Normalize pages/forms into dedicated tables if not done in the first pass.
10. Add advanced roles, workflows, collections, automation, and site members later.

## Estimated Complexity Per Phase

- Phase 1 database/migrations: High.
- Phase 2 backend route design and implementation: High.
- Phase 3 frontend integration: Medium-High.
- Phase 4 public tenant runtime: High.
- Phase 5 security/RLS/rate limiting: High.
- Phase 6 end-to-end testing: Medium-High.

## Estimated Development Effort

- MVP database and backend project CRUD: 2 to 4 development days.
- Frontend save/load integration: 2 to 4 development days.
- Publish snapshots and public runtime: 3 to 5 development days.
- Forms/submissions and responses integration: 2 to 4 development days.
- Assets and upload hardening: 1 to 3 development days.
- Security/RLS/rate limiting hardening: 2 to 5 development days.
- End-to-end testing and fixes: 2 to 4 development days.

Total MVP estimate: 2 to 4 focused weeks, depending on how much schema normalization is included up front.

## Biggest Architectural Risks

- Trying to normalize every builder concept before the backend-backed MVP works.
- Letting public runtime read draft data.
- Relying only on frontend tenant IDs for authorization.
- Expanding cookie-authenticated write routes without CSRF protection.
- Mixing `users.tenant_id` and `tenant_memberships` without a clear active-tenant rule.
- Treating workflows, collections, site members, and automation as MVP requirements.
- Letting localStorage remain the source of truth after backend persistence exists.

## Recommended MVP Scope

Include:

- Tenant-owned builder projects.
- Draft project save/load.
- Page and form persistence, either embedded in project JSON at first or normalized if time allows.
- Publish endpoint that creates immutable published snapshots.
- Public site read routes by subdomain and page slug.
- Public form/reservation submission endpoint.
- Owner responses view backed by database.
- Basic builder asset upload.
- Tenant isolation and role checks.
- Rate limiting for public submissions.

Defer:

- Workflows.
- Collections.
- Automation.
- Custom tenant roles UI.
- Site-member/private-page login.
- Advanced collaboration.
- Version rollback UI.
- Public file upload fields.
- Complex CMS features.

Recommended MVP principle:

- Make one tenant create one project, publish it, load it publicly, and receive form submissions safely before adding advanced builder features.
