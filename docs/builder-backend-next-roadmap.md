# Builder Backend Next Roadmap

## 1. Current Confirmed State

This document reflects the current codebase state after the Builder submissions flow milestone. It is based on the current backend routes, migrations, tests, Docker configuration, and Page Builder frontend API/runtime files.

### Project storage and publishing

- `builder_projects` exists in migrations `023_create_builder_projects.sql` under both `database/migrations/` and `supabase/migrations/`.
- A Builder project belongs to a `tenant_id` and can optionally reference `owner_user_id`.
- The full current Builder JSON is stored in `draft_schema`.
- Publish copies the current `draft_schema` into `published_schema`, increments `published_version`, sets `last_published_at`, and sets `status = 'published'`.
- `published_schema` is overwrite-in-place, not immutable publish history.
- Project statuses are `draft`, `published`, and `archived`.
- Project list excludes archived projects.
- Project delete is implemented as soft archive.
- The backend enforces a max Builder schema size through `MAX_BUILDER_SCHEMA_BYTES`, defaulting to 2 MiB.

### Authenticated Builder project routes

Current Builder API uses canonical authenticated routes:

- `GET /builder/projects`
- `POST /builder/projects`
- `GET /builder/projects/{project_id}`
- `PUT /builder/projects/{project_id}`
- `DELETE /builder/projects/{project_id}`
- `POST /builder/projects/{project_id}/publish`
- `GET /builder/projects/{project_id}/form-submissions`
- `GET /builder/projects/{project_id}/form-submissions/{submission_id}`
- `PUT /builder/projects/{project_id}/form-submissions/{submission_id}`

Temporary compatibility aliases still exist under `/users/{user_id}/builder/...`. Those aliases validate the path `user_id` against the authenticated session and should be removed after frontend and external clients have migrated.

`assert_context_user()` verifies that the path `user_id` matches the authenticated session user id.

### Public site resolution

- Public site routes are mounted under `/public`.
- `GET /public/sites/{subdomain}` resolves `website_settings.subdomain` first.
- The route then resolves `tenant_id` from `website_settings.tenant_id`.
- A `user_id` fallback still exists for demo/backward compatibility when `tenant_id` is missing.
- The public site route loads the latest published project for that tenant.
- Public site response includes `published_schema` only.
- Public site response does not return `draft_schema`.
- Public URLs are tenant/site-subdomain based, not builder project slug based.

### Form submissions

- `builder_form_submissions` exists in migration `025_create_builder_form_submissions.sql`.
- Status values are updated by migration `026_update_builder_form_submission_statuses.sql`.
- Submissions are tied to `tenant_id`, `project_id`, and `form_id`.
- Forms are still defined inside `published_schema.forms`; there is no normalized `builder_forms` table yet.
- Public submit route: `POST /public/sites/{subdomain}/forms/{form_id}/submissions`.
- The public submit route resolves the tenant through public subdomain, loads the latest published project, confirms the form exists in `published_schema.forms`, and confirms a published page contains a connected `formBlock`.
- Required fields are validated using the published form schema.
- Unknown submitted field IDs are rejected.
- Answers are stored as JSON keyed by stable field ids.
- A `field_snapshot` is stored with the submission.
- Best-effort `submitter_ip` and `user_agent` are stored.
- Public submissions return a frontend-friendly response and do not expose live submission lists publicly.

### Responses page

- Authenticated submissions list route returns backend rows newest first with `limit` and `offset`.
- The frontend `BuilderResponsesPage.jsx` loads backend submissions through `fetchBuilderFormSubmissionsPage()`.
- The Responses page supports refresh without reloading the whole Builder project.
- The Responses page supports simple previous/next pagination with a page size of 50.
- Existing copy/export behavior uses the displayed in-memory rows.
- Preview/demo embedded `form.responses` fallback remains for non-backend/demo flows.

### Submission status updates

- Authenticated status update route exists: `PUT /builder/projects/{project_id}/form-submissions/{submission_id}`. Temporary compatibility alias: `PUT /users/{user_id}/builder/projects/{project_id}/form-submissions/{submission_id}`.
- Accepted user-facing statuses are `New`, `Contacted`, `Closed`, `Spam`, and `Archived`, case-insensitive.
- Database stores normalized lowercase values: `new`, `contacted`, `closed`, `spam`, `archived`.
- Backend list/read/update responses map database values back to frontend labels.
- Migration `026_update_builder_form_submission_statuses.sql` drops the old status constraint, converts `reviewed` to `contacted`, normalizes capitalized values, and adds the new status constraint.

### Redis and rate limiting

- Docker Compose includes a `redis:7-alpine` service named `madar-redis`.
- `backend/services/rate_limit_service.py` uses Redis by default at `REDIS_URL`, default `redis://redis:6379/0`.
- If Redis is unavailable and `RATE_LIMIT_FAIL_OPEN=true`, the service logs a warning and falls back to an in-memory store.
- Rate limiting is configurable through environment variables.
- Current rate limit scopes include auth, password reset/change flows, public site lookup, public form submissions, and public contact submissions.

### Origin/Referer protection

- `backend/services/request_security.py` implements strict Origin/Referer checks for cookie-authenticated writes.
- Safe methods `GET`, `HEAD`, and `OPTIONS` are not blocked.
- If a request has `madar_access_token` or `madar_refresh_token` cookies, state-changing requests must come from configured frontend origins unless disabled through env.
- Allowed origins come from `FRONTEND_URLS` and `CSRF_TRUSTED_ORIGINS`.
- This is not a full CSRF token flow yet.

### RLS state

- RLS exists for several core tables through migrations.
- `builder_projects` has select/insert/update/delete policies using `tenant_memberships` and `auth.uid()`.
- `builder_form_submissions` has an authenticated tenant-member select policy only; direct public inserts are not allowed by RLS.
- `website_settings` has hardened select/insert/update policies using `tenant_memberships` and a `user_id` fallback.
- `tenant_memberships` select policy currently uses `auth_id = auth.uid()`, so direct Supabase access only returns the caller's membership rows, not all same-tenant members.
- `users` RLS allows users to select/insert/update their own row via `auth_id = auth.uid()`.
- `contacts` RLS is enabled in early migrations, but no current policy was found in the inspected migration excerpt. Needs verification.
- `features` grants authenticated select but no RLS policy was found in the inspected migrations. Needs verification.
- Backend uses the Supabase service role client for privileged operations, so route-level tenant checks are the primary protection in production.

### Supabase and self-hosted Postgres portability

- Backend database access is tightly coupled to the Supabase Python SDK and PostgREST-style `.table().select().eq().execute()` calls.
- Auth depends on Supabase Auth sessions/tokens and local HttpOnly cookies storing Supabase access/refresh tokens.
- RLS policies use Supabase `auth.uid()`.
- Migrations reference `auth.users` in `tenant_memberships`, and migration `022_create_avatars_storage_bucket.sql` references Supabase Storage. Needs verification for self-hosted Postgres compatibility.
- `database.py` refuses to start without a distinct `SUPABASE_SERVICE_KEY`, which prevents privileged operations from silently using the anon key.
- Migration to self-hosted Postgres is currently moderate-to-risky without an adapter layer and auth/session redesign.

## 2. Current Architecture Map

### Authenticated Builder route map

Canonical authenticated Builder routes:

| Method | Route | Purpose | Access |
| --- | --- | --- | --- |
| GET | `/builder/projects` | List non-archived tenant projects | active tenant member |
| POST | `/builder/projects` | Create tenant project | owner/admin/member |
| GET | `/builder/projects/{project_id}` | Load tenant project | active tenant member |
| PUT | `/builder/projects/{project_id}` | Update name/slug/status/draft_schema | owner/admin/member |
| DELETE | `/builder/projects/{project_id}` | Soft archive project | owner/admin |
| POST | `/builder/projects/{project_id}/publish` | Copy draft_schema to published_schema | owner/admin/member plus configured subdomain |
| GET | `/builder/projects/{project_id}/form-submissions` | List project submissions | active tenant member |
| GET | `/builder/projects/{project_id}/form-submissions/{submission_id}` | Read one submission | active tenant member |
| PUT | `/builder/projects/{project_id}/form-submissions/{submission_id}` | Update submission status only | active tenant member |

Temporary compatibility aliases mirror the same routes at `/users/{user_id}/builder/...`; they should stay undocumented for new clients and be removed in a later cleanup after usage is verified.

### Public route map

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/public/sites/{subdomain}` | Resolve tenant site by `website_settings.subdomain` and return public metadata plus `published_schema` |
| POST | `/public/sites/{subdomain}/forms/{form_id}/submissions` | Submit a public form response for a form in the latest published project |

### Website settings route map

Current website routes are also user-scoped:

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/users/{user_id}/website/settings` | Ensure and return tenant website settings |
| PUT | `/users/{user_id}/website/settings` | Update tenant website settings |

### Database table map

| Table | Current role |
| --- | --- |
| `tenants` | Tenant root record. |
| `users` | Local profile row tied to Supabase Auth via `auth_id`; includes current `tenant_id`. |
| `tenant_memberships` | Tenant membership and role source for Builder access checks. |
| `website_settings` | Tenant public site settings, including `subdomain`; still has `user_id` compatibility. |
| `builder_projects` | Full Builder project JSON in `draft_schema`; published JSON in `published_schema`. |
| `builder_form_submissions` | Public form submissions tied to tenant/project/form ids. |
| `contacts` | Legacy/public contact storage. Needs RLS review. |
| `features` | Subscription/features table. Needs RLS review. |

### Tenant ownership model

- Backend tenant context comes from `require_regular_user()` and then `tenant_memberships`.
- `users.tenant_id` is treated as the user's primary/current tenant.
- `tenant_memberships` is treated as the authoritative role/access row for Builder routes.
- Backend requires active membership for reads and status updates.
- Backend allows Builder write access for `owner`, `admin`, and `member`.
- Backend restricts archive/delete to `owner` and `admin`.

### Auth/session model

- Supabase Auth is used for signup/login/session validation.
- Backend stores Supabase access and refresh tokens in HttpOnly cookies named `madar_access_token` and `madar_refresh_token`.
- `/auth/user_status` is used by the frontend to resolve the current backend user.
- `PageBuilder.api.js` resolves current user id and builds `/users/{user_id}/...` URLs.

### Service-role vs RLS reality

- Most backend routes use `service_supabase`, which bypasses RLS.
- RLS is secondary protection for any direct Supabase client/table access.
- Because service role bypasses RLS, every backend route must enforce tenant and project ownership itself.
- Public routes also use service role and must enforce public visibility and tenant resolution explicitly.

### Frontend API expectations

- `PageBuilder.api.js` defaults to `VITE_API_URL || '/api'`.
- Authenticated Builder API calls use `getUserScopedPath(userId, path)`.
- The frontend expects `credentials: 'include'` for authenticated Builder calls.
- Public site fetch calls `/public/sites/{subdomain}` without credentials.
- Public form submit calls `/public/sites/{subdomain}/forms/{formId}/submissions` without credentials.
- Builder load/save/publish uses backend first, with localStorage retained as fallback/cache.
- Public runtime loads `published_schema`; it should not see `draft_schema`.

## 3. Known Technical Debt / Risks

- User-scoped route design adds route consistency risk. The path `user_id` is redundant with the session and must always be checked with `assert_context_user()`.
- Route consistency is still mixed across the app: Builder is canonical at `/builder/...` with temporary user-scoped aliases, website settings remains user-scoped, and public routes are not user-scoped.
- Supabase SDK/PostgREST coupling is strong. Moving to self-hosted Postgres requires replacing table-builder calls, Supabase Auth token validation, `auth.uid()` RLS assumptions, and storage assumptions.
- Backend service role bypasses RLS. RLS must be treated as secondary protection only.
- `users.tenant_id` and `tenant_memberships` can diverge. Current tenant context depends on both `users.tenant_id` and an active membership row for that same tenant.
- Public route safety depends on `website_settings.subdomain` uniqueness and tenant-first resolution. Needs verification that database uniqueness is enforced for tenant/public subdomain semantics.
- The public route still has `user_id` fallback in `resolve_tenant_id()` for demo compatibility. This should be revisited before multi-tenant production launch.
- CSRF protection is Origin/Referer only. It is better than no protection but not a full token flow.
- Public form submissions accept JSON answers and store snapshots, but there is no request body size limit specific to public submit.
- Builder forms/pages remain embedded in `draft_schema`/`published_schema`; there are no normalized `builder_pages` or `builder_forms` tables.
- localStorage fallback/cache remains in PageBuilder and TenantSiteRuntime. This is useful for resilience but can confuse source-of-truth behavior if not carefully contained.
- Public runtime still renders response table elements from embedded schema/sample `form.responses`; live backend submissions are not exposed publicly, which is correct, but the distinction should remain explicit in UI/product design.
- Status naming differs between UI labels and DB values, intentionally. Keep `New/Contacted/Closed/Spam/Archived` in UI and lowercase normalized DB values.
- Environment/tunnel URLs are local and volatile. `.env` is ignored, but runtime behavior can change when Cloudflare tunnel URLs change.
- Migration numbering contains duplicate numbers in existing history, such as `023_*` and `024_*` pairs. Fresh install ordering should be verified.
- Needs verification: whether every migration can run cleanly in lexical order on a fresh database.
- Needs verification: whether all backend tests run as a full suite, not only Builder/security-focused suites.

## 4. Security Roadmap

### Stage 1: Confirm current protections

- Run and keep green the current Builder/security test suites:
  - `tests.test_builder_form_submissions`
  - `tests.test_builder_backend_hardening`
  - `tests.test_security_foundation`
  - `tests.test_authorization_boundaries`
- Add focused tests for every authenticated Builder route proving wrong `user_id` path values are rejected.
- Add tests proving service-role routes reject cross-tenant project and submission ids.
- Add public route tests proving `draft_schema` is never included.

### Stage 2: RLS review and hardening

- Inventory all tables and policies from the live database, not just migration files.
- Verify `builder_projects` direct authenticated policies match backend expectations.
- Add update policy review for `builder_form_submissions` if direct authenticated status updates will ever be allowed; otherwise keep direct writes disabled.
- Review `website_settings` `user_id` fallback policies and decide when to remove or narrow them.
- Review `contacts`, `features`, and `users` policies for tenant isolation.
- Add tests or SQL checks for direct anon/authenticated table access if Supabase client-side access remains possible anywhere.

### Stage 3: CSRF hardening

- Keep current Origin/Referer protection as baseline.
- Add a CSRF token flow for cookie-authenticated writes:
  - token issuing route or double-submit cookie design
  - per-session or rotating tokens
  - frontend header inclusion
  - clear behavior for expired/missing tokens
- Keep Origin/Referer validation as defense in depth.

### Stage 4: Request and abuse limits

- Add request body size limits for public routes and Builder save/publish.
- Add field count and answer size limits for form submissions.
- Add duplicate submission throttles per IP/subdomain/form/email fingerprint.
- Add structured abuse logging for 400/403/429 public submission failures.

### Stage 5: Audit and admin logging

- Add audit logging for project publish, project archive, status changes, settings changes, and future role changes.
- Track actor user id, tenant id, action, target id, IP, user-agent, and timestamp.
- Keep logs secure and avoid storing raw secrets or excessive PII.

### Stage 6: File/upload security readiness

- Before adding assets, define allowed MIME types, max file sizes, image validation, virus/malware scanning plan, safe public serving, tenant ownership checks, and signed/private URL behavior.

## 5. Redis Roadmap

### Current Redis usage

- Redis is used for rate limit counters through `RedisRateLimitStore`.
- Keys are shaped as `rl:{scope}:{client_ip}:{identity}`.
- Docker Compose provides `madar-redis` with `redis:7-alpine`.
- Default backend `REDIS_URL` is `redis://redis:6379/0`.

### Fail-open vs fail-closed

- Current default is `RATE_LIMIT_FAIL_OPEN=true`.
- If Redis is unavailable, backend falls back to in-memory counters.
- This avoids breaking local/dev testing but is weaker in production.
- Production recommendation: set `RATE_LIMIT_FAIL_OPEN=false` for high-risk public routes, or add route-specific fail behavior.

### Production configuration

- Configure Redis with authentication where supported.
- Set memory limits and eviction policy intentionally.
- Add health checks and alerts for Redis availability.
- Decide whether rate limit counters need persistence; generally they do not, but job queues and webhook queues will.
- Separate Redis databases or key prefixes for rate limits, queues, caches, and idempotency.

### Future usage

- Job queue for webhook delivery.
- Retry queue and dead-letter queue for failed webhooks.
- Cache for public site lookups if performance becomes an issue.
- Idempotency key cache for public submissions and webhook dispatch.
- Optional abuse fingerprint/Bloom filter storage if abuse volume justifies it.

## 6. Rate Limiting Roadmap

### Currently protected routes/scopes

- Auth signup uses `enforce_auth_rate_limit(request, 'signup', email)`.
- Auth login uses `enforce_auth_rate_limit(request, 'login', email)`.
- Forgot password uses `enforce_password_rate_limit(request, 'forgot_password', email)`.
- Password reset uses `enforce_password_rate_limit(request, 'password_reset')`.
- Public site lookup uses `enforce_public_rate_limit(request, 'site_lookup', subdomain)`.
- Public form submit uses `enforce_public_form_submission_rate_limit(request, 'create', '{subdomain}:{form_id}')`.
- Public contact routes use public contact rate limiting. Details should be reviewed in `public_contact_routes.py` before extending.

### Improvements

- Add per-IP plus per-subdomain/per-form limits for public form submissions.
- Add optional per-email or per-normalized-answer fingerprint throttles for forms that collect email.
- Add per-user limits for authenticated destructive actions.
- Add tighter limits for password reset by email and IP together.
- Add admin-configurable limits later, stored per tenant/site/form.
- Return clear `429` messages without leaking whether an email/user exists.

### Testing

- Unit-test the rate limit helper with Redis mocked and in-memory fallback.
- Integration-test one public route and one auth route.
- Keep env overrides for local testing, for example low limits in tests and higher defaults in dev.
- Avoid breaking local testing by documenting `RATE_LIMIT_ENABLED=false` and small-window test settings.

## 7. RLS Roadmap

### Current known policies

- `users`: select/insert/update own row by `auth_id = auth.uid()`.
- `tenants`: select if an active `tenant_memberships` row exists for `auth.uid()`.
- `tenant_memberships`: current select policy appears to expose only the caller's own membership rows by `auth_id = auth.uid()`.
- `builder_projects`: select for active tenant members; insert/update for active owner/admin/member; delete for owner/admin.
- `builder_form_submissions`: select for active tenant members; no direct authenticated insert/update policy in migration `025`.
- `website_settings`: select/insert/update using active tenant memberships and compatibility `user_id` ownership logic.
- `features`: authenticated select grant exists; policy needs verification.
- `contacts`: RLS is enabled in early migration, but policy state needs verification.

### Required work

- Dump live policies from Supabase/Postgres and compare against migrations.
- Decide whether tenant members should directly read all same-tenant memberships or only their own row.
- Ensure direct Supabase access cannot insert public form submissions.
- Ensure direct Supabase access cannot update submission statuses unless explicitly intended.
- Confirm `website_settings.subdomain` uniqueness and ownership constraints.
- Add future RLS before creating `builder_assets`, `builder_pages`, `builder_forms`, webhook tables, reservation tables, and tenant role tables.
- Keep backend service-role tenant checks even if RLS is perfect.

## 8. Webhooks Roadmap

Do not implement webhooks until the event model and retry model are designed.

### Proposed tables

- `webhook_endpoints`
  - tenant id, URL, status, subscribed event types, secret hash/encrypted secret, created_by, created_at, updated_at
- `webhook_events`
  - immutable event id, tenant id, event type, resource type/id, payload JSON, created_at, idempotency key
- `webhook_deliveries`
  - endpoint id, event id, attempt count, status, response code/body summary, next_attempt_at, last_attempt_at, error summary

### Events

- `form.submitted`
- `submission.status_changed`
- `project.published`
- `contact.created`
- `reservation.submitted` later

### Delivery strategy

- Sign payloads with HMAC SHA-256 using per-endpoint secrets.
- Include timestamp, event id, and signature headers.
- Use Redis/job queue for async delivery.
- Retry with exponential backoff and jitter.
- Add dead-letter behavior after max attempts.
- Add idempotency keys for event creation and delivery.
- Avoid sending drafts or private schemas in webhook payloads.

### Admin UI needs

- Endpoint CRUD.
- Secret rotation.
- Event subscription selection.
- Delivery logs.
- Retry failed delivery.
- Disable endpoint after repeated failures.

### Testing

- Unit-test signing and verification examples.
- Test retry scheduling and dead-letter behavior.
- Test idempotent event creation.
- Test tenant isolation for endpoint/event access.

## 9. Bloom Filter / Abuse Protection Roadmap

### Possible use cases

- Disposable or banned email pre-checks.
- Repeated spam payload fingerprints.
- Blocked IP/user-agent fingerprints.
- Duplicate submission detection.
- Webhook idempotency pre-checks before DB lookup.

### Risks and tradeoffs

- Bloom filters can have false positives.
- False positives are dangerous if they silently block legitimate submissions.
- Bloom filters do not replace durable DB indexes, rate limits, or audit logs.
- Privacy matters: payload fingerprints should be salted/hashed and avoid storing raw PII.

### RedisBloom vs app-level Bloom filter

- RedisBloom is operationally convenient but requires Redis module support, which `redis:7-alpine` does not provide by default.
- App-level Bloom filters require persistence/rebuild strategy and careful deployment handling.
- Normal DB indexes and Redis counters are enough for MVP abuse controls.

### MVP recommendation

Defer Bloom filters. Use rate limits, DB indexes, normalized fingerprints, and audit logs first. Revisit Bloom filters only when abuse volume creates measurable DB or Redis pressure, or when RedisBloom is explicitly available in production.

## 10. Builder Features Still Needed

- Backend asset uploads.
- `builder_assets` table.
- Image validation and transformation.
- Public asset serving.
- Normalized `builder_pages` table.
- Normalized `builder_forms` table.
- Immutable publish snapshots/version history.
- Rollback to previous publish.
- Response notes.
- Response filters and status-filter UI.
- Backend export endpoint.
- Analytics and summary stats.
- Workflows.
- Webhooks.
- Reservations.
- Collections/CMS.
- Tenant roles and finer permissions.
- Members/invitations.
- Site-member auth/private pages.
- More complete form validation types beyond required/unknown field id checks.
- Anti-spam tools and moderation workflows.

## 11. Recommended Implementation Order

### Immediate next small tasks

1. Stabilize current submissions/status flow.
   - Ensure migration `026` is applied in Supabase.
   - Manually smoke test status updates for `Contacted` and `Closed`.
   - Confirm no 500/CORS-like symptom remains on status updates.
2. Finish the Builder route migration.
   - Treat `/builder/...` as canonical.
   - Monitor usage of `/users/{user_id}/builder/...` aliases, then remove them in a later cleanup.
   - If permanent, document it as the API contract.
   - If not permanent, plan a separate migration/compatibility period.
3. Add response filters/status UX polish.
   - Filter displayed rows by status client-side first.
   - Consider backend query param later if volume requires it.

### Next backend hardening tasks

4. Strengthen RLS and tenant isolation tests.
   - Add SQL/policy inspection checklist.
   - Add route-level cross-tenant tests for all Builder endpoints.
5. Add CSRF token flow.
   - Keep Origin/Referer validation as defense in depth.
6. Add request size and payload field limits.
   - Especially for public form submissions and Builder saves.

### Next frontend integration tasks

7. Improve Responses UI.
   - Status filters.
   - Better empty/loading/error states if needed.
   - Optional row detail view after backend read endpoint is proven useful.
8. Keep public runtime from exposing live submissions.
   - Public response table elements should remain schema/sample only unless product explicitly changes this.

### Deferred advanced tasks

9. Add asset upload only after security limits are ready.
10. Add webhooks after event model and queue are designed.
11. Normalize pages/forms after current JSON source-of-truth is stable.
12. Defer Bloom filter unless abuse becomes real or RedisBloom is available.

## 12. Validation Checklist

### Automated checks

- Run Builder submission tests:
  - `docker exec madar-backend python -m unittest tests.test_builder_form_submissions -v`
- Run hardening/security/boundary tests:
  - `docker exec madar-backend python -m unittest tests.test_builder_backend_hardening tests.test_security_foundation tests.test_authorization_boundaries -v`
- Run frontend build after frontend changes:
  - `docker compose up -d --build frontend`
- Add future fresh migration test for both `database/migrations/` and `supabase/migrations/`.

### Manual checks

- Auth/session:
  - login
  - `/auth/user_status`
  - logout/login again
- Project CRUD:
  - create project
  - list projects
  - load project
  - update draft schema
  - archive project and confirm it disappears from list
- Publish/go live:
  - publish project
  - confirm Go Live uses `website_settings.subdomain`
  - confirm public URL opens `/site/{subdomain}`
- Public site:
  - `GET /public/sites/{subdomain}` returns 200
  - public response includes `published_schema`
  - public response does not include `draft_schema`
- Public form submit:
  - valid submit succeeds
  - missing required field fails
  - unknown field id fails
  - rate limit can return 429 under configured limits
- Response listing:
  - submitted row appears in Builder Responses
  - refresh reloads current page
  - previous/next pagination works
- Status updates:
  - `New` -> `Contacted` persists
  - `Contacted` -> `Closed` persists
  - `Spam` and `Archived` persist
  - refresh shows frontend-friendly labels
- RLS/cross-tenant:
  - wrong tenant project id rejected
  - wrong tenant submission id rejected
  - path `user_id` mismatch rejected
- CSRF/origin checks:
  - valid frontend origin accepted for authenticated writes
  - invalid origin rejected
  - safe GETs not blocked
- Redis availability/fallback:
  - Redis running in Docker
  - rate limit counters work
  - fail-open/fail-closed behavior matches env
- Migration application:
  - Supabase migration `026` applied before browser testing status updates
  - fresh install ordering needs verification because duplicate migration numbers exist

## Open Decisions Before More Backend Work

- When should temporary `/users/{user_id}/builder/...` Builder compatibility aliases be removed?
- When can the `website_settings.user_id` fallback be removed?
- Should direct Supabase authenticated users ever update submissions, or should all writes remain FastAPI-only?
- Should `tenant_memberships` direct select expose all same-tenant members or only the current user's own membership?
- What is the first normalized Builder table to introduce: assets, pages, or forms?
- What production posture should Redis use: fail-open for all routes, fail-closed for public write routes, or route-specific behavior?
