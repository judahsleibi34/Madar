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

The backend loads configuration from `.env` and Docker Compose. Do not commit secrets.

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
- `SESSION_INACTIVITY_TIMEOUT_SECONDS`
- `ADMIN_MFA_LOGIN_ENFORCEMENT`
- `TRUSTED_PROXY_IPS`

Rate limiting and request-size controls:

- `REDIS_URL`
- `RATE_LIMIT_ENABLED`
- `RATE_LIMIT_FAIL_OPEN`
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
- `MAX_JSON_BODY_BYTES`
- `MAX_SMALL_JSON_BODY_BYTES`
- `MAX_DATA_JSON_BODY_BYTES`

Builder and public-site settings:

- `UPLOADS_DIR`
- `AVATAR_UPLOAD_DIR`
- `BUILDER_ASSET_MAX_BYTES`
- `MAX_BUILDER_SCHEMA_BYTES`
- `ALLOW_INSECURE_HTTP_URLS`

Billing and deployment helpers:

- `BILLING_WEBHOOK_SECRET`
- `APP_ENV` / `ENV` / `FASTAPI_ENV`

Data-analysis and remote dataset controls:

- `CHART_OUTPUT_DIR`
- `DATA_UPLOAD_DIR`
- `MAX_UPLOAD_BYTES`
- `ALLOW_REMOTE_DATASET_URLS`
- `ALLOW_INSECURE_REMOTE_DATASET_HTTP`
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

Billing is currently limited to internal feature-state handling and pending checkout records.

There is no real payment provider integration yet, so this branch should be treated as billing-preparation work rather than a production payment system.

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
