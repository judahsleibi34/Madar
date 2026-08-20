# Madar SaaS

Madar is a multi-tenant SaaS website builder and tenant workspace platform built with a FastAPI backend, a React/Vite frontend, and Supabase for authentication and data storage.

## Current Status

The current branch already supports the core product loop end to end:

- signup, login, session refresh, logout, and password reset/change
- tenant onboarding and tenant membership creation
- tenant-scoped dashboard pages and website settings
- Page Builder authoring, save/update, and publish/go-live
- public site rendering from published builder data
- public form submission capture
- admin user management and admin billing feature management
- audit logging for auth, password, admin, and MFA events
- MFA settings, enrollment, factor removal, and admin-login enforcement behind a disabled-by-default flag
- English and Arabic frontend localization
- privacy policy page and `/.well-known/security.txt`

What is still partial or intentionally limited:

- billing stores internal feature-state and pending checkout state, but no real payment provider is integrated yet
- the canonical live-site URL is still path-based: `/site/<subdomain>/`
- the repository still contains duplicate migration trees that should eventually be consolidated
- the frontend has build/lint validation, but no dedicated frontend unit test runner is configured yet

## Architecture Overview

Madar is split into three main layers:

- `backend/`: FastAPI application, auth/session handling, tenant authorization, builder APIs, public site APIs, audit logging, and tests
- `frontend/`: React/Vite application with auth pages, dashboard, page builder, public site runtime, settings pages, and i18n
- `database/` and `supabase/`: SQL migrations for the application schema, RLS, grants, and backfills

The backend is the trust boundary. It owns cookie/session validation, CSRF checks, tenant isolation, service-role access, and audit writes.

## Repository Structure

- `backend/routes/`: HTTP routes for auth, tenants, website settings, billing, builder, public site, MFA, admin actions, and health checks
- `backend/services/`: shared backend logic for auth, tenant context, MFA, security, audit logging, rate limiting, request validation, and storage helpers
- `backend/tests/`: backend unit tests and route coverage
- `backend/data_analysis/`: the data-analysis workspace and supporting backend logic
- `frontend/src/components/AuthPages/`: signup, login, forgot-password, and reset-password screens
- `frontend/src/components/DashboardBuilder/`: dashboard, settings, security/MFA, and tenant workspace UI
- `frontend/src/components/PageBuilder/`: builder canvas, publish flow, preview/runtime helpers, and public site runtime
- `frontend/src/i18n/`: English and Arabic translations
- `frontend/public/.well-known/security.txt`: security contact metadata served by the frontend build
- `database/migrations/`: SQL migration history used by the repo
- `supabase/migrations/`: mirrored SQL migration history currently kept in parallel
- `docs/`: supporting notes and archived references

## Required Environment Variables

The backend loads configuration from the repository-root `.env` and Docker
Compose. Local development explicitly reloads that file with override enabled,
so stale variables inherited from an old terminal cannot silently point the API
at a different Supabase project. Production keeps deployment-provided
environment variables authoritative.

Use `MADAR_ENV_FILE` to select another env file. Use
`MADAR_ENV_OVERRIDE=false` only when you intentionally want shell variables to
win during local development. Do not commit secrets.

Core required values:

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_KEY`
- `FRONTEND_URL` or `FRONTEND_URLS`

Common security and session settings:

- `COOKIE_SECURE`
- `COOKIE_SAMESITE`
- `CSRF_SECRET`
- `CSRF_ORIGIN_CHECK_ENABLED`
- `CSRF_ALLOW_MISSING_ORIGIN`
- `CSRF_TRUSTED_ORIGINS`
- `SESSION_ACTIVITY_SECRET`
- `SESSION_INACTIVITY_TIMEOUT_SECONDS` (optional; defaults to `0`, which keeps
  the session active for the lifetime of the browser session; set a positive
  number to enforce an inactivity timeout)
- `ADMIN_MFA_LOGIN_ENFORCEMENT`
- `TRUSTED_PROXY_IPS`

Calendar integrations and workers:

- `CALENDAR_CREDENTIALS_SECRET` (a dedicated high-entropy secret used to encrypt provider tokens)
- `PUBLIC_API_URL` and `FRONTEND_PRIMARY_URL` (must match the registered OAuth redirect hosts)
- `GOOGLE_CALENDAR_CLIENT_ID` and `GOOGLE_CALENDAR_CLIENT_SECRET`
- `MICROSOFT_CALENDAR_CLIENT_ID` and `MICROSOFT_CALENDAR_CLIENT_SECRET`
- `CALENDAR_SYNC_WORKER_ENABLED`
- `CALENDAR_SYNC_INTERVAL_SECONDS`
- `NOTIFICATION_WORKER_ENABLED` (also dispatches scheduled calendar reminders)

Native browser/operating-system notifications:

- `WEB_PUSH_VAPID_PUBLIC_KEY`
- `WEB_PUSH_VAPID_PRIVATE_KEY`
- `WEB_PUSH_VAPID_SUBJECT` (a contact URI such as `mailto:ops@example.com`)
- Run the notification worker (`docker compose --profile workers up`) so queued
  notifications and calendar reminders are delivered while the Madar page is
  closed.
- Each user must click **Enable system notifications** on the Notifications
  page once per browser/device and grant the browser permission prompt.

Rate limiting and request-size controls:

- `REDIS_URL`
- `RATE_LIMIT_ENABLED`
- `RATE_LIMIT_FAIL_OPEN`
  - Production should use `false` so Redis/rate-limiter failures do not silently allow abusive traffic. Local development may override this to `true` if Redis is intentionally unavailable.
- `AUTH_RATE_LIMIT_LIMIT`
- `AUTH_RATE_LIMIT_WINDOW_SECONDS`
- `PASSWORD_RATE_LIMIT_LIMIT`
- `PASSWORD_RATE_LIMIT_WINDOW_SECONDS`
- `PUBLIC_RATE_LIMIT_LIMIT`
- `PUBLIC_RATE_LIMIT_WINDOW_SECONDS`
- `DATA_WORKSPACE_RATE_LIMIT_LIMIT`
- `DATA_WORKSPACE_RATE_LIMIT_WINDOW_SECONDS`
- `DATA_UPLOAD_RATE_LIMIT_LIMIT`
- `DATA_UPLOAD_RATE_LIMIT_WINDOW_SECONDS`
- `DATA_ANALYSIS_RATE_LIMIT_LIMIT`
- `DATA_ANALYSIS_RATE_LIMIT_WINDOW_SECONDS`
- `DATA_VISUALIZATION_RATE_LIMIT_LIMIT`
- `DATA_VISUALIZATION_RATE_LIMIT_WINDOW_SECONDS`
- `BUILDER_ASSET_UPLOAD_RATE_LIMIT_LIMIT`
- `BUILDER_ASSET_UPLOAD_RATE_LIMIT_WINDOW_SECONDS`
- `MAX_REQUEST_BODY_BYTES`
- `MAX_BUILDER_ASSET_REQUEST_BODY_BYTES`
- `MAX_JSON_BODY_BYTES`
- `MAX_SMALL_JSON_BODY_BYTES`
- `MAX_DATA_JSON_BODY_BYTES`

Builder and public-site settings:

- `PUBLIC_UPLOADS_DIR`
- `AVATAR_UPLOAD_DIR`
- `BUILDER_ASSET_MAX_BYTES`
- `BUILDER_VIDEO_MAX_BYTES`
- `BUILDER_DOCUMENT_MAX_BYTES`
- `MAX_BUILDER_SCHEMA_BYTES`
- `ALLOW_INSECURE_HTTP_URLS`

Billing and deployment helpers:

- `BILLING_WEBHOOK_SECRET`
- `APP_ENV` / `ENV` / `FASTAPI_ENV`

Data-analysis and remote dataset controls:

- `DATA_UPLOAD_DIR`
- `PRIVATE_CHARTS_DIR` / `GENERATED_CHARTS_DIR`
- `AI_FREE_DAILY_MESSAGES`
- `AI_PRO_DAILY_MESSAGES`
- `AI_ENTERPRISE_DAILY_MESSAGES`
- `MAX_UPLOAD_BYTES`
- `MAX_DATASET_UPLOAD_BYTES`
- `LARGE_DATASET_THRESHOLD_BYTES`
- `MAX_FULL_DATAFRAME_BYTES`
- `CSV_CHUNK_SIZE_ROWS`
- `MAX_PREVIEW_ROWS`
- `CSV_DUPLICATE_TRACK_ROWS`
- `MAX_EXCEL_UPLOAD_BYTES`
- `ALLOW_REMOTE_DATASET_URLS`
- `REMOTE_INGESTION_WORKER_URL`
- `REMOTE_INGESTION_WORKER_HEALTH_URL`
- `REMOTE_INGESTION_BACKEND_TIMEOUT_SECONDS`
- `REMOTE_INGESTION_DEADLINE_SECONDS`
- `REMOTE_INGESTION_HARD_TIMEOUT_SECONDS`
- `DATAFRAME_CACHE_MAX_ITEMS`
- `DATAFRAME_URL_CACHE_SECONDS`
- `MAX_REMOTE_DATA_BYTES`
- `DATAFRAME_MAX_ROWS`
- `DATAFRAME_MAX_COLUMNS`
- `MAX_EXCEL_FILE_BYTES`
- `MAX_EXCEL_UNCOMPRESSED_BYTES`
- `MAX_EXCEL_ZIP_ENTRIES`
- `MAX_EXCEL_SHEETS`
- `MAX_EXCEL_ROWS`
- `MAX_EXCEL_COLUMNS`
- `MAX_EXCEL_CELL_CHARS`
- `PARSER_ISOLATED_WORKER_ENABLED`
- `PARSER_WORKER_URL`
- `PARSER_WORKER_HEALTH_URL`
- `PARSER_WORKER_TIMEOUT_SECONDS`
- `PARSER_JOB_TIMEOUT_SECONDS`

Remote ingestion is HTTPS/443-only and has no backend direct-fetch fallback.
When enabled, the backend sends a bounded GET-only request contract to the
isolated `remote-ingestion-worker`; that worker validates every DNS answer,
connects to the selected numeric address while retaining TLS SNI and hostname
verification, manually revalidates redirects, rejects content encoding, and
streams at most 10 MiB. The fetched bytes are parsed by the separate no-network
parser worker. An enabled feature without the correctly identified live egress
worker fails readiness.

Upload storage is intentionally split by trust level:

- `PUBLIC_UPLOADS_DIR` backs managed public `/uploads/tenant_{id}/builder_assets/...` routes. It is for intentionally public files such as builder image assets.
- `DATA_UPLOAD_DIR` backs private CSV/XLS/XLSX data-analysis uploads and exported/user dataset files. It defaults to `private_uploads` and must never be mounted as static files in production.
- `PRIVATE_CHARTS_DIR` backs private dataset-derived generated charts. It defaults to `private_generated_charts` and is served only through authenticated `/users/{user_id}/visualization/charts/{chart_id}` routes.

The backend fails startup if `DATA_UPLOAD_DIR` or `PRIVATE_CHARTS_DIR` is configured inside the public upload tree, because filename secrecy is not a security boundary.

Large CSV uploads are streamed to private storage and summarized with chunked
metadata extraction instead of full in-memory DataFrames. Defaults are
`MAX_DATASET_UPLOAD_BYTES=209715200`, `LARGE_DATASET_THRESHOLD_BYTES=52428800`,
`MAX_FULL_DATAFRAME_BYTES=52428800`, `CSV_CHUNK_SIZE_ROWS=3000`, and
`MAX_PREVIEW_ROWS=120`. Duplicate tracking defaults to
`CSV_DUPLICATE_TRACK_ROWS=100000` row signatures. Excel files above
`MAX_EXCEL_UPLOAD_BYTES=52428800` are
rejected with guidance to convert to CSV because Excel parsing is not chunked.
When `PARSER_ISOLATED_WORKER_ENABLED=true`, bounded full-dataframe parsing is
delegated to the internal `parser-worker` service. The worker has read-only
access to private uploads, no outbound network, and container CPU, memory, PID,
capability, and filesystem restrictions. Readiness verifies the worker identity
and health endpoint; the flag alone is not sufficient.

AI provider usage is enforced at `POST /users/{user_id}/analysis/ai` in
`backend/data_analysis/routes/analysis_routes.py` before provider calls are
made. Free users default to `AI_FREE_DAILY_MESSAGES=5`; pro and enterprise
limits default to 100 and 1000. Unsafe prompts and unauthenticated or
tenant-mismatched requests are rejected before usage is incremented. Accepted
requests reserve one daily message before the planner provider call, so provider
failures after that point still count as attempted usage.

## Docker Setup

Build the application images with Docker Compose:

```bash
docker compose build backend frontend
```

Run the backend and frontend containers together:

```bash
docker compose up
```

The compose file currently maps:

- backend: `127.0.0.1:8001 -> 8000`
- frontend: `127.0.0.1:3000 -> 80`

Redis is included as a compose service for rate limiting.

## Supabase Migration Process

Madar currently keeps migrations in two trees:

- `database/migrations`
- `supabase/migrations`

They are currently mirrored and should be treated as parallel copies of the same schema history. Do not delete or restructure them as part of this cleanup.

Recommended process:

1. provision the Supabase project and required keys
2. apply the SQL migrations in the expected order
3. verify RLS policies and service-role-only paths
4. run backend tests against the target environment
5. confirm login, onboarding, builder publish, public site, and audit logging flows before release

## Public Site URL Policy

The current canonical public URL is path-based:

- `/site/<subdomain>/`

That is the live URL used by the current publish/go-live flow. Custom-domain support is not the canonical path for this branch.

## Tenant Onboarding Flow

The current onboarding flow is:

1. user signs up through the auth flow
2. backend creates the local profile and the tenant record
3. tenant membership is created for the signed-in user
4. website settings capture the tenant subdomain and brand details
5. the user enters the dashboard and starts building pages
6. publish/go-live makes the public site available at `/site/<subdomain>/`

## Page Builder and Publish Flow

The Page Builder supports:

- page creation and duplication
- component placement and editing
- forms and responses
- runtime preview
- starter templates
- publishing the current project state to the public site

Publish flow summary:

1. validate the current builder state
2. save/update the project
3. call the publish endpoint
4. resolve the public path-based live URL
5. show the live site link after successful publish

## Security Model

Madar uses a layered security model:

- auth cookies are HttpOnly
- CSRF protection is enabled for browser requests
- `TenantContext` is used to verify tenant membership and tenant-scoped access
- RLS is enabled on the sensitive Supabase-backed tables
- admin-only and regular-user-only route boundaries are enforced in the backend
- MFA exists for enrollment and verification, with admin-login enforcement behind `ADMIN_MFA_LOGIN_ENFORCEMENT=false` by default
- audit logging records auth, password, admin, and MFA events with sanitized metadata

## Billing Limitation

The server-authoritative commercial catalog is exposed at `GET /billing/catalog`.
Canonical base-plan, add-on, storage, hosted-address, workspace-seat, and AI
standard-token primitives are introduced by migration `071`. Customer plan and
add-on requests remain pending until an AAL2-authenticated administrator reviews
and activates them.

There is no payment-provider integration, automatic renewal, card storage, or
invoice generation. Migrations `071` and `072` were applied to the shared live
database on 2026-07-31. Legacy billing and branded-route review records must
still be reconciled before strict canonical entitlements are enabled in an
application rollout. See
`docs/madar-pricing-entitlements-implementation.md` for the compatibility and
deployment sequence.

## Testing Commands

Use Docker-based validation from the repository root. For backend unit tests, include the test override and `--no-deps` so the test container does not try to create the fixed-name Redis containers used by the running production/dev stacks:

```bash
docker compose -f docker-compose.yml -f docker-compose.test.yml run --rm --no-deps backend python -m unittest tests.test_security_foundation -v
```

For the broader backend stabilization suite:

```bash
docker compose -f docker-compose.yml -f docker-compose.test.yml run --rm --no-deps backend python -m unittest \
  tests.test_security_foundation \
  tests.test_website_routes \
  tests.test_builder_backend_hardening \
  tests.test_builder_form_submissions \
  tests.test_builder_archived_projects \
  tests.test_builder_asset_upload \
  -v
```

The test override uses a separate Compose project name, removes fixed `container_name` values for test services, avoids publishing backend/frontend ports, and keeps the read-only migration mounts available at `/app/database` and `/app/supabase`.

For full image validation, still run:

```bash
docker compose build backend frontend
docker compose build frontend
git diff --check
```

If you are working on a smaller change, run the most relevant backend test module(s) first and expand from there.

## Backend Smoke Tests

Run the backend smoke script after deploys or container rebuilds to verify safe read-only endpoints, expected unauthenticated failures, and CORS preflight behavior. The script does not use credentials and does not send mutating requests.

```bash
./scripts/backend_smoke.sh prod-local
./scripts/backend_smoke.sh dev-local
./scripts/backend_smoke.sh prod-public
```

Use `prod-local` for the production backend bound to `127.0.0.1:8001`, `dev-local` for the development backend bound to `127.0.0.1:8002`, and `prod-public` for `https://api.madarportal.com`.

## Deployment Checklist

Before merging or deploying:

- confirm the branch is clean enough for release
- complete the production launch checklist in `docs/production-launch-checklist.md`
- confirm backup/restore readiness using `docs/production-backup-restore.md`
- verify the Docker build succeeds for backend and frontend
- run the backend test modules relevant to the change
- confirm migrations are applied in the target environment
- confirm Supabase keys and backend env vars are present
- confirm public-site routing still uses `/site/<subdomain>/`
- confirm billing expectations match the current feature-state implementation
- confirm auth, CSRF, tenant isolation, and audit logging are working
- confirm `security.txt` and the privacy policy page are reachable

## Known Limitations

- real payment processing is not integrated yet
- migration history exists in two parallel directories and still needs a future source-of-truth decision
- frontend automated tests are limited compared with the backend coverage
- the current canonical live URL remains path-based
- some compatibility fallbacks remain in the backend for older data paths

## Current Roadmap Summary

Phase 0: documentation cleanup and validation
- keep the branch understandable and verifiable
- maintain accurate setup, migration, and deployment notes

Phase 1: MVP stabilization
- lock down auth, tenant isolation, builder publish, and public site regressions

Phase 2: first-run tenant experience
- improve onboarding, empty states, and first publish guidance

Phase 3: Page Builder MVP polish
- improve publish UX, preview fidelity, and public runtime reliability

Phase 4: billing/features/admin management
- turn the internal billing state into a real entitlement and payment workflow

Phase 5: production hardening
- add stronger observability, operational checks, and deployment safety

Phase 6: future SaaS expansion
- custom domains, collaboration, analytics, and integration depth
