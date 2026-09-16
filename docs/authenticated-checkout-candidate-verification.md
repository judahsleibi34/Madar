# Authenticated checkout candidate verification

Baseline: `1dc9482c66a406396fd376c6d9c821ceab2fd968` in
`D:/Madar-release-099`, verified clean before work on 2026-09-16.

## Root cause and contract audit

`services/auth_service.py:get_authenticated_user_row` has no return annotation.
Every successful return is a plain two-element tuple:
`(auth_user, user_data)` (or `(auth_user, target_user)` for permitted admin
account access). The first member is the provider user object; the second is
its `public.users` profile dictionary, selected by `auth_id`. The local profile
has the integer customer identity used by commerce. Authentication failures
raise exceptions. This contract remains unchanged.

Checkout and `/public/sites/{subdomain}/loyalty/me` assigned the whole tuple to
`customer`, then evaluated `customer["id"]`, raising
`TypeError: tuple indices must be integers or slices, not str` before the RPC.
Both callers now unpack the profile. Both retain their existing admin-account
access restrictions and guest/session behavior.

All production calls were inspected:

| Module | Caller | Result handling |
| --- | --- | --- |
| `app.py` | `require_authenticated_user` | Forwards the tuple unchanged; no production uses found |
| `app.py` | `_asset_visibility` | Unpacks the profile |
| `services/auth_service.py` | `require_system_admin`, `require_regular_user` | Unpack both members |
| `routes/auth_routes.py` | `user_status`, `refresh_session`, `change_password`, `log_out` | Unpack the tuple |
| `routes/mfa_routes.py` | `authenticated_mfa_context` | Unpacks both members |
| `routes/public_site_routes.py` | `require_tenant_visitor` | Unpacks the profile |
| `routes/public_site_routes.py` | `create_public_store_order`, `get_public_store_loyalty` | Corrected to unpack the profile |

`routes/user_routes.py` imports the helper but does not call it. No other
production caller treats the tuple as a dictionary.

## Regression coverage

The baseline Linux test image reproduced three HTTP assertion failures:
checkout with access cookies, checkout with refresh cookies, and loyalty read
all returned HTTP 500. Guest checkout, guest loyalty denial, and rejected-session
checkout behavior passed.

`tests/test_authenticated_checkout.py` covers HTTP 201 authenticated COD
checkout, local profile ID versus provider ID, distinct customer/store tenants,
untrusted typed contact information, guest checkout, rejected sessions,
authenticated loyalty lookup, and guest loyalty HTTP 401.

Its opt-in PostgreSQL 17 test applies the existing migration tree only to a fresh
disposable container. It drives the HTTP checkout handler through a psycopg
adapter executing the real atomic order RPC, checks stored customer identity,
stock 20 to 18, and one inventory movement. Collection plus delivery earns 10
points; checkout, collection, and delivery replays preserve one earning entry,
the same balance, and the same stock. Guest delivery earns no loyalty.
Authentication itself is mocked with its actual tuple contract; these tests do
not claim staging/provider qualification.

To run the database test, use a fresh disposable PostgreSQL 17 container with
no production connections. Run the locked backend test image with the CI
placeholder/storage environment and migration mounts from
`.github/workflows/backend-check.yml`, add
`--network container:<disposable-postgres-container>` and
`--env MADAR_CHECKOUT_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1/postgres`,
and execute `python -m unittest -v tests.test_authenticated_checkout`.
The integration class refuses non-loopback database hosts. It is skipped in
the ordinary offline suite and was executed separately during this verification.

## Release scope

No migration, manifest, compatibility metadata, deployment gate, or migration
or control-plane orchestration changed. The production release policy does not
require a behavior update for this caller correction. The schema range remains
81 through 99, target 99. The legacy RPC fallback remains unchanged.

Pinned database and Supabase copies match their unchanged manifest SHA-256:

| Migration | SHA-256 |
| --- | --- |
| 097 | `d4068175a555f610e590a94313ed600fcfac2f54b3fe902da1f6539fe227870e` |
| 098 | `8366d2dc74458888d0f470faf2b8e3318aacb57bc4cc421a93382ccffe25511f` |
| 099 | `8fe9d429149d397a90e5a1420d9133d0fcd731f59159d811fe81336d1f59b7a0` |

The intended production and isolated-E2E environment files are absent from this
checkout. `check_production_config.py` with absent local inputs reports required
values MISSING and exits 1. This mandatory configuration gate remains unresolved;
no substitute fixture is presented as intended-environment validation.
Production access, deployment, and `supabase db push` were not performed.

## Completed local checks

- Focused HTTP and PostgreSQL regression: 6 tests passed.
- Existing targeted commerce/checkout/loyalty suite: 60 tests passed.
- Full official Linux suite: 1,329 discovered, 1,328 passed, 1 integration opt-in
  skipped; zero external attempts. Finalized tests baked into a fresh locked
  Docker `test` target. Workflow placeholder environment, tmpfs, and all
  read-only repository mounts were retained. Command:
  `python scripts/run_tests_no_external_network.py`.
- `check_dependency_locks.py`: passed.
- `check_migrations.py`: passed, only the two documented historical 013/014
  duplicate-content warnings.
- `check_migration_transitions.py`: passed.
- `check_secret_hygiene.py`: passed.
- `python -m pip check`: passed.
- Locked backend test and runtime image builds: passed.
- Pinned production frontend image build: passed, with
  `VITE_API_URL=https://api.madarportal.com` and
  `MADAR_REQUIRE_PRODUCTION_API_URL=true`; API-origin, theme, and bundle-origin
  audits passed during the build. No runtime was deployed.
- Linux Node 22 `npm ci` (Docker build) and `npm run lint`: passed.
- `npm audit --omit=dev --audit-level=high`: passed, zero vulnerabilities.
- Complete frontend suite: 154 files passed, 941 tests passed, 1 skipped under
  Linux Node 22 using `npm test -- --maxWorkers=2`, with unchanged test timeouts.
  A corrected default-worker run timed out in the existing product-editor
  matrix test at 5 seconds while local suites overlapped; the same test passed
  with two workers. Earlier harness attempts inherited production API settings
  and/or lacked the Compose-file mount; those failures are not counted as
  successful validation. The successful run cleared build-only API settings and
  mounted the repository Compose file read-only at `/docker-compose.yml`.
- `docker compose ... config --quiet`: passed with the local example env file,
  CI placeholders, and schema 81..99. This verifies local syntax only, not
  intended-environment configuration or production topology readiness.
- All six database/Supabase migration files were also compared byte for byte
  against the pinned baseline Git objects and are unchanged.
- `git diff --check`: passed.

## Candidate disposition

NEW CANDIDATE BLOCKED: the application defect is corrected and the available
local tests/builds pass, but the release-policy checklist's mandatory
intended-environment configuration check cannot pass without the intended
production and isolated-E2E environment files. No release gate was bypassed.
This change creates a new child candidate commit; the baseline is not amended.
