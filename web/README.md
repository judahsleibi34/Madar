# Madar web application

This document applies to the web application root (`web/`). Git commands belong
at the repository root; unless a command shows an absolute path, run the Docker,
backend, frontend, migration, and script commands below from `web/`. The sibling
`mobile/` application is built separately and is not part of this Compose stack.

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
- tenant websites use canonical `https://<subdomain>.madarportal.com/` URLs;
  `/site/<subdomain>/` remains redirect-only compatibility state
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
- `PUBLIC_SITE_DOMAIN` (the trusted tenant-host suffix, for example
  `madarportal.com`)

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

- `WEB_PUSH_ENABLED` (explicit operator switch; defaults to disabled)
- `WEB_PUSH_VAPID_PUBLIC_KEY`
- `WEB_PUSH_VAPID_PRIVATE_KEY`
- `WEB_PUSH_VAPID_SUBJECT` (a contact URI such as `mailto:ops@example.com`)
- All three canonical VAPID values are required when `WEB_PUSH_ENABLED=true`.
  The deprecated `VAPID_PRIVATE_KEY` name is ignored by runtime health and
  delivery decisions.
- Run the notification worker (`docker compose --profile workers up`) so queued
  notifications and calendar reminders are delivered while the Madar page is
  closed.
- Each user must click **Enable system notifications** on the Notifications
  page once per browser/device and grant the browser permission prompt.

### Isolated local database for development

If `web/.env` points to a database shared with production, use a separate local
Supabase stack instead of applying development migrations to that database.
Install Docker Engine and ensure your user can access its local Unix socket,
then run from the repository root:

```bash
python3 web/scripts/start_local_database.py
cd web/backend
python run_local.py --local-db
```

Activate the backend virtual environment before starting the API. The setup
helper uses Supabase CLI 2.119.0 through `npx`, validates the migration trees,
starts the Docker stack defined by `web/supabase/config.toml`, and applies pending
migrations with an explicit `--local`. It preserves existing local data and does
not link, push, or reset a hosted project. Initial startup downloads the local
Supabase images. Docker volumes retain the local database between starts.

The helper verifies the declared schema target and both E-Learning tables through
the local API before creating `web/.env.database.local` with permissions 0600.
This ignored file contains local credentials only; `web/.env` is preserved.
The `--local-db` launcher refuses missing configuration and hosted database URLs.
It loads the schema compatibility range from `deployment/releases/release.json`
so health readiness checks use the current release contract after local migrations.
For an existing isolated database at schema 136, explicitly select the retained
development candidate contract with
`python run_local.py --local-db --local-schema-contract schema-114-136-bridge.json`.
This option requires loopback database URLs, preserves schema compatibility
checks, and runs no migrations. It does not change the production release contract.
Restart any existing API process before using this launcher. The frontend's
normal development proxy already targets `127.0.0.1:8000`.

Create a separate account using the app's sign-up flow. Production accounts,
tenants and courses are not copied. Supabase Studio is available at
`http://127.0.0.1:54323`; local email is captured by Supabase's mail testing service.
For an existing local test account, add `MADAR_TEST_EMAIL`, `MADAR_TEST_PASSWORD`
and `MADAR_TEST_AUTO_LOGIN="true"` to the ignored `web/.env.database.local` file,
then restart the API with `run_local.py --local-db`. The local launcher signs in
through the normal password flow when the app checks its session. Credentials
stay on the backend; this feature requires development mode, a local database,
and localhost requests. Set `MADAR_TEST_AUTO_LOGIN="false"` to test sign-out or
other accounts. The database setup helper preserves these settings on reruns.
Stop the stack without removing its data with:

```bash
cd web
npx --yes supabase@2.119.0 stop
```


Rate limiting and request-size controls:

For native local development without Docker or Redis, activate your backend
virtual environment and run `python run_local.py` from `web/backend` instead of
`uvicorn app:app --reload`. Stop the existing API process first. This launcher
loads `web/.env`, keeps rate limiting enabled, and explicitly permits the
in-memory fallback when Redis is unavailable. It serves the API on
`127.0.0.1:8000` and refuses production configuration. Counters are local to the
process and reset on restart; use the normal Redis-backed runtime for production.


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
- frontend: `127.0.0.1:3000 -> 8080`

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

Run the complete backend suite in the isolated environment defined by
[`Backend Check`](../.github/workflows/backend-check.yml). From the repository
root, build its locked, non-root test image:

```bash
docker build --target test -t madar-backend-test web/backend
```

Then execute the workflow's complete **Run backend tests** command, including all
environment variables and read-only mounts. The copyable command and the regression
investigation results are in
[`docs/backend-regression-investigation.md`](../docs/backend-regression-investigation.md).
Finish the backend CI checks with:

```bash
docker run --rm madar-backend-test python -m pip check
```

Running the backend test runner directly in the development virtual environment
can load `web/.env`, including production cookie, entitlement and worker settings.
Setting `APP_ENV=test` alone does not isolate that dotenv file. The CI image excludes
environment files and uses synthetic credentials, writable temporary storage and
the source paths required by the tests. The suite also blocks external network
attempts. Use this environment for the full backend gate; preserve the local app's
configuration separately.

Database integration tests require a separate marked disposable database. The
existing `web/scripts/rehearse_migration_141.py` verifies the immutable 001–141
chain and runs the E-Learning database tests against that disposable database.
It requires the loopback local database configuration and does not upgrade the
application database.

For full image validation, still run:

```bash
docker compose -f web/docker-compose.yml build backend frontend
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
- confirm public-site routing uses `https://<subdomain>.madarportal.com/` and
  legacy `/site/<subdomain>/` requests redirect permanently
- confirm billing expectations match the current feature-state implementation
- confirm auth, CSRF, tenant isolation, and audit logging are working
- confirm `security.txt` and the privacy policy page are reachable

## Known Limitations

- real payment processing is not integrated yet
- migration history exists in two parallel directories and still needs a future source-of-truth decision
- browser E2E coverage remains smaller than the unit/component coverage
- wildcard DNS, TLS, and Cloudflare Tunnel routing remain operator-managed
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

## Reusable E-Learning programmes and owner tools (unselected schema140 candidate)

The implementation inventory and verification record are in
[`docs/eduhope-implementation.md`](../docs/eduhope-implementation.md).
Production `release.json` remains the exact schema115/non-migrating profile.
The retained schema140 manifest does not authorize production migration or deploy.

For a local Supabase database already migrated to schema140:

```bash
cd web/backend
./madar_env/bin/python run_local.py --local-db --local-schema-contract schema-114-140-bridge.json
```

In a separate terminal, start Madar's existing notification consumer:

```bash
cd web/backend
./madar_env/bin/python run_local_notifications.py --local-schema-contract schema-114-140-bridge.json
```

The worker launcher refuses non-loopback configuration, enables internal delivery,
and disables external SMTP/push for this development process. Its health endpoint
is `http://127.0.0.1:8090/health`. These launchers do not apply migrations. The local
schema contract choice does not modify the active production release contract.
The API's optional production worker-readiness gate remains disabled locally;
check the separate worker health endpoint for actual development worker status.

Owner **E-Learning → Settings** controls tenant programme configuration according
to existing commercial module access: Commerce for referral/affiliate/finance,
Website for support/exchange, Forms exports for advanced reports. Backend checks
remain authoritative. Names, terms, reward values, support eligibility/threshold
and withdrawal minimum/methods are tenant data. New thresholds/minima/methods are
unset until explicitly configured; no EduHope prices or reward presets are applied.
Prices remain in existing Learning Plans/commerce offerings. Migration139 preserves
historical opt-in settings while replacing the brand gate with `programmes_enabled`.

Online payments use the registered Stripe Checkout adapter
(`services/stripe_payment_provider.py`) for one-time plans. Payments stay
`payment_provider_unavailable` until the backend env file sets all of:

```text
MADAR_PAYMENT_PROVIDER=stripe
STRIPE_SECRET_KEY=sk_test_...        # test mode; sk_live_ also needs MADAR_STRIPE_LIVE_MODE=true
STRIPE_WEBHOOK_SECRET=whsec_...
```

The Stripe webhook endpoint is `https://api.madarportal.com/elearning/payments/webhook`
with events `checkout.session.completed`, `checkout.session.async_payment_succeeded`
and `checkout.session.async_payment_failed`. Access is granted only from a signed
webhook or the buyer's server-side reconciliation of Stripe's PaymentIntent; both
derive the same event identity, so the atomic SQL deduplicates them. Learners return
to My Plans, which confirms the payment and opens the purchased course. In test mode,
card `4242 4242 4242 4242` with any future expiry and CVC succeeds without a charge.
Monthly/yearly plans are refused online until subscription billing is implemented.
The explicit local commerce simulator creates no payable academy rewards or
qualifying Tuition Support sales.

A destructive-data-free SQL rehearsal creates and removes a marked disposable
localhost database, validates fresh history and transactional rollback, and runs
learning-commerce/referral/CEFR/programme regressions:

```bash
cd web
./backend/madar_env/bin/python scripts/rehearse_migration_140.py
```

Actual curriculum, five CEFR section mappings and existing offering prices remain
unconfigured at the user's request. Configure CEFR on a course's existing
Certificates screen after its required final exams have been published with 70%
passing scores and retakes enabled. Credentials use the existing PDF, verification
and revocation endpoints.

Owner tools extend the existing Academy hub with metrics, the shared Settings
with institution verification and application switches, existing tuition
applications with private attachments, and exchange opportunity management.
Contact administration extends platform contacts; the Academy Builder profile
adds contact, programme information and open exchange components while retaining
shared pages, chrome and publishing. The architecture audit and acceptance
report are linked in the implementation document. Live provider credentials,
real course content and institution domains remain unconfigured.


## Independent E-Learning Forms (local schema141)

[The Forms report](../docs/elearning-forms-implementation.md) documents the
Builder methodology reuse, independent tenant definitions/responses, private
files, notifications, endpoint/security contracts and verification. Start from
**E-Learning → Settings → Forms** with an entitled tenant academy owner. A nested
Forms menu appears when an active/archived form or historical responses exist.
The existing platform test account retains its platform permissions.

For a local database already upgraded to141, use these explicit contracts in
separate terminals from `web/backend`:

```bash
./madar_env/bin/python run_local.py --local-db --local-schema-contract schema-114-141-bridge.json
./madar_env/bin/python run_local_notifications.py --local-schema-contract schema-114-141-bridge.json
```

These commands select runtime compatibility; they do not apply migrations.
To validate fresh history, populated upgrades, rollback and domain tests on a
marked disposable local database, run from the repository root:

```bash
./web/backend/madar_env/bin/python web/scripts/rehearse_migration_141.py
```

Migration141 and its descriptors are an unselected candidate. Production
`release.json` remains the unchanged schema115 non-migrating contract. Local
validation or a runtime schema choice does not authorize production deployment.
