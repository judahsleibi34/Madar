# Madar commercial migrations 071-072: live execution record

**Execution date:** 2026-07-31 UTC

**Database:** Madar's single shared live database

**Authorization:** Explicit owner authorization for backup, migration, validation, documentation, and a local development commit

## Outcome

Migrations 071 and 072 were backed up, dry-run, rehearsed, applied in order, and
validated. The live ledger is current through 072. No production application
checkout was edited, no application service was restarted or deployed, and no
remote Git operation was performed.

This database is shared by development and production and contains internal/test
tenants but no external customers. It was still handled as production: the
verified backup was a hard gate; SQL test mutations were rollback-only; content
was not dumped into this report; and failures were not repaired ad hoc.

## Repository state

| Item | Value |
|---|---|
| Checkout | `/home/madar/saas/Madar-dev` |
| Branch | `builder-backend` |
| Starting commit | `92b90bcceda9405441f50f68ae69bbab8331373a` |
| `origin/main` before work | `92b90bcceda9405441f50f68ae69bbab8331373a` |
| Initial relationship | 0 ahead / 0 behind |
| Initial implementation paths | 70 status entries: 48 tracked modifications and 22 untracked paths |
| Production checkout | Not modified |

All pre-existing commercial-entitlement and publication-isolation work was
preserved. Generated builds, caches, logs, backup data, environment files, and
database output are excluded from the commit.

## Pending-migration assessment

The live `supabase_migrations.schema_migrations` ledger contained exactly
001-070. The official Supabase CLI 2.111.0 dry run selected only these files:

| Migration | Purpose | Database SHA-256 | Supabase SHA-256 | Before | Compatibility and recovery |
|---|---|---|---|---|---|
| `071_create_commercial_entitlements.sql` | Canonical subscription/add-on state, standard hosted paths, legacy reviews, operational counters, AI token accounting/RPCs | `b76c139ca1bcf25e09527eee6ceb071d17c01da481e20c624c70d8fdbeff9704` | Same | Pending | Additive; old `features`, routes, storage usage, and publication bindings retained. Restore verified backup if a transaction-level/application compatibility failure required database recovery. |
| `072_harden_publication_isolation.sql` | Publication integrity reviews, fail-closed snapshot checks, atomic publish/bind RPC | `54b7e653a4d8e78290a79e906e9a5599b0f6427c4f8fe7ab98f067f35e702953` | Same | Pending | Additive and same publish RPC signature. Historical ambiguous rows are reviewed, not selected or rewritten. Application rollback may leave additive review/schema objects intact. |

Both migration trees contain 72 byte-mirrored migrations. The validator reports
only the known historical duplicate-content warnings for 013/014. No destructive
statement, migration-order mismatch, mirror drift, content deletion, or
immediate old-backend incompatibility was found.

Expected locking is limited to transactional DDL/catalog locks, deterministic
updates of six `website_settings` rows, advisory locks inside new RPCs, and the
brief locks used when scanning/backfilling publication integrity. There are no
large live commercial tables at this stage.

## Backup

| Item | Result |
|---|---|
| Successful backup | `/home/madar/backups/madar-20260731T120207Z` |
| Started | 2026-07-31T12:02:07Z |
| Completed | 2026-07-31T12:03:46Z |
| Database dump size | 837,143 bytes |
| Complete directory size | 26,151,726 bytes |
| Database dump SHA-256 | `18060ae3c7452dd9cf6efc8cc8dce28adee54b456abca97e59108edf96f3aab2` |
| Repository verifier | Passed |
| `pg_restore --list` | Passed |
| File stores | Builder/public assets, private uploads, generated artifacts, avatars included |

The first attempt, `/home/madar/backups/madar-20260731T120056Z`, was killed by
the command-execution timeout and contains a zero-byte dump without a manifest.
It is invalid, was never treated as a backup, and is retained only so the failed
gate is not hidden.

## Pre-migration facts

| Category | Verified value |
|---|---:|
| Tenants | 7 |
| Legacy feature rows | 3, IDs 1-3, all `canceled` |
| Active legacy feature rows | 0 |
| Website settings | 6 |
| Builder projects | 5 |
| Published-project bindings | 5 |
| Form submissions | 5 |
| Reservations | 0 |
| Storage accounts | 6 |
| Authoritative tenant scopes | 3 |
| Per-user safety scopes | 3 |
| Reserved storage bytes | 0 |

Subdomains were `ibtikar`, `madar`, `palcode`, `email`, `test-madar`, and
`madar-demo`; only tenant 5 / `email` lacked a published binding. There were no
case-normalized duplicates or invalid values.

Tenant and `user:<id>` storage rows intentionally reported the same physical
used bytes. They are hierarchical accounting views, not values to sum. Tenant
rows had 5 GiB quotas and user rows retained 1 GiB safety quotas. Tenant 4 was
actively receiving storage writes during preflight, so its used bytes and the
object/reservation history counts increased while the services remained live.
Both migrations leave `storage_accounts.used_bytes` and `reserved_bytes`
untouched; no migration-induced storage loss or reset was observed.

## Execution

The migration method was:

```text
npx --yes supabase@latest db push --db-url <redacted-live-url> --yes
```

Credentials were obtained from the running production backend environment
without printing their value.

| Event | UTC timestamp |
|---|---|
| Migration command started | 2026-07-31T12:06:57Z |
| 071 applied | Within the same ordered transaction sequence |
| 072 applied | Immediately after 071 |
| Migration command completed | 2026-07-31T12:07:35Z |

Both migrations contain `notify pgrst, 'reload schema'`; no service restart was
needed. A post-execution CLI dry run reported the remote database up to date
with no pending migrations.

## Schema and data validation

- The ledger contains migrations 001-072 exactly once.
- All expected commercial tables exist: `tenant_subscriptions`,
  `tenant_addons`, `billing_addon_requests`,
  `legacy_billing_migration_reviews`, `hosted_address_migration_reviews`,
  `commercial_usage_monthly`, `ai_token_model_multipliers`,
  `ai_token_allocations`, `ai_token_reservations`, and `ai_token_ledger`.
- `publication_integrity_reviews` and both publication RPC/check functions from
  072 exist.
- All 11 new tables inspected have RLS enabled.
- Public/anon/authenticated mutation paths are revoked in migration source;
  the inspected service-role table/function access and named sequence grants
  are present. New sequence grants are narrow, not schema-wide.
- `tenant_subscriptions_one_active_idx` and
  `tenant_addons_one_active_ai_package_idx` exist.
- `website_settings_standard_path_slug_check` is validated and its
  case-insensitive unique index exists.
- Six standard slugs are nonnull, valid, nonreserved, and duplicate-free.
- All legacy routes have `legacy_subdomain_routing_preserved=true` and
  `branded_subdomain_commercial_status='pending_review'`; none was silently
  granted a paid exception.
- Five published bindings remained published; tenant 5 / `email` remained
  unpublished. No binding changed unexpectedly.
- `publication_integrity_reviews` contains zero issues for current live rows.
  The 072 historical constraint intentionally remains `NOT VALID`; it enforces
  new/updated rows and should be validated only after the documented review
  process in a later migration.

## Legacy billing

Feature IDs 1, 2, and 3 remain canceled. There are zero active legacy features,
zero active canonical subscriptions, and zero active add-ons. Three legacy
review rows were produced, one for each tenant having historical feature data.
Each has no `active_legacy_feature_id`, no recommended plan, and
`review_required` with the reason that no active legacy billing row exists.
Therefore no canceled record granted an entitlement and no tenant was marked
mapped.

## Storage-scope validation

`backend/services/storage_quota_service.py` now selects only
`scope_key='tenant' and user_id is null` for commercial/My Plan usage. It uses
the exact base entitlement plus active `additional_storage_5gb` quantities,
updates only tenant `quota_bytes`, leaves all used/reserved fields intact, and
passes a fixed 1 GiB quota to per-user safety accounting. A regression fixture
with identical bytes in tenant/user scopes proves the bytes are reported once
and only the tenant quota changes. The focused storage/commercial suite passed
22/22.

## AI token validation

Migration 071 disposable rehearsal passed allocation, reservation, overrun,
deficit, expiry, idempotency, concurrency, one-package, RLS, and failed-
transaction scenarios. A rollback-only live-schema transaction on internal
tenant 7 additionally proved:

- actual use below and equal to reservation;
- 500 actual tokens consuming 200 reserved plus 300 additional tokens;
- 1,000 actual tokens consuming the remaining 800 and recording a 200-token
  deficit without a negative balance;
- Starter-to-Plus assignment leaving exactly one active recurring AI package;
- finalization after reservation expiry;
- duplicate late finalization returning the existing ledger result;
- zero persistent test add-ons and zero persistent test ledger rows after
  rollback.

No paid provider was called.

## Application and operational validation

| Check | Result |
|---|---|
| Disposable 001-071 rehearsal | Passed, including reapplication and failed-transaction atomicity |
| Disposable 001-072 rehearsal | Passed, including publication repair/review behavior |
| Migration mirror/checksum validation | Passed; 72 mirrored migrations, only known 013/014 warnings |
| Dependency lock consistency | Passed |
| Backend focused storage/commercial tests | 22/22 passed |
| Backend full suite | 799/800 passed; one pre-existing CORS middleware assertion error |
| Frontend tests | 476 passed, 1 skipped; 80/80 files passed |
| Frontend production build/theme audit | Passed; existing large-chunk warning only |
| Frontend lint | Passed; 0 errors, 0 warnings |
| Python compile | Passed using an isolated bytecode cache |
| Base production Compose config | Passed |
| Development overlay Compose config | Passed |
| `git diff --check` | Passed |
| Targeted secret scan | Passed |
| Final backend `pip check` rerun | Not completed: Docker approval/usage limit after earlier implementation run had passed |

The backend failure is
`test_app_middleware.AppMiddlewareTests.test_unhandled_exception_returns_sanitized_json_with_cors_and_request_id`.
Its synthetic error response lacks the expected localhost CORS header; this
work did not modify CORS/middleware code.

Production-reachable `npm audit --omit=dev` reports React Router advisories (one
moderate, one high through `react-router-dom`); 7.18.2 is available. Full
`npm audit` reports six findings: one low, one moderate, and four high across
`@babel/core`, `brace-expansion`, `postcss`, `react-router`/
`react-router-dom`, and `vite`. Available current releases observed were
`@babel/core` 7.29.7 (same major), `brace-expansion` 5.0.9, `postcss` 8.5.25,
`react-router-dom` 7.18.2, and Vite 8.2.0. No automatic fix or dependency change
was made.

## Existing production compatibility

No new code was deployed. The current production containers remained up and
healthy under their existing Docker health checks. Read-only checks returned:

- `GET /health/live`: 200;
- `GET /health/ready`: 503 degraded, with database, schema, auth, and Redis
  healthy but the pre-existing storage readiness component unavailable;
- `GET /public/sites/palcode`: 200 with the expected structural response keys;
- frontend `/site/palcode` and `/site/palcode/shop`: 200.

No authenticated credential was used for a synthetic login, so internal-user
authentication was validated through the health component and automated auth
suite rather than by creating a live session. Storage metadata remained
queryable directly. Existing public form/reservation schemas remained present;
no mutating public smoke request was sent.

## Remaining rollout steps

1. Review the six pending branded-route commercial statuses; preserve routing
   while deciding explicit grandfather/add-on/removal state.
2. Address or accept the production React Router audit findings.
3. Investigate the existing storage readiness degradation and CORS test error.
4. Deploy the new backend first in compatibility mode; do not enable stricter
   policy before reconciling tenants.
5. Verify catalog, My Plan, standard paths, branded compatibility, forms,
   reservations, storage reservations, AI mock accounting, and audit events.
6. Deploy the frontend, rerun smoke tests, and invalidate only relevant
   application/public-site caches.
7. Validate `builder_projects_publication_integrity_check` in a later migration
   after every historical publication review is resolved.

## Recovery

For an application regression, roll back backend/frontend binaries together
while retaining the additive 071/072 schema and review history; the old backend
continued operating after migration. For genuine database impairment, use the
verified `madar-20260731T120207Z` backup and the established restore runbook in a
controlled outage. Never selectively delete subscription, token ledger,
review, or publication history as an improvised rollback.

The final local commit hash is reported by `git rev-parse HEAD` and the terminal
completion report. A Git commit cannot embed its own final hash in its committed
content because changing the content changes that hash.

## Follow-up hardening and builder styling (2026-07-31)

This follow-up made no database call and did not alter or reapply migrations 071
or 072. Their committed checksums remain respectively
`b76c139ca1bcf25e09527eee6ceb071d17c01da481e20c624c70d8fdbeff9704`
and `54b7e653a4d8e78290a79e906e9a5599b0f6427c4f8fe7ab98f067f35e702953`.

### Baseline and stale-image diagnosis

The authoritative current-source baseline was 800 backend tests with 16
failures and one error. Earlier one-off Compose commands had used an older
`madar-dev-backend` image; rebuilding the development backend copied the current
checkout and restored the generated-code worker and CI-environment results.
That image drift was a test-execution error, not a database or production-image
change.

### CORS 500-response correction

Starlette orders newly registered user middleware outermost. CORS had been
registered before the function-based observability middleware, so the latter
caught an inner exception and returned its sanitized JSON response without that
response ever traversing CORS. The exception branch tried to compensate with a
separate header helper, which was not the same middleware boundary and made the
behavior dependent on a second origin set.

`CORSMiddleware` is now registered after the function middleware and routers,
making it outermost. The observability exception path only constructs the safe
500 JSON and request ID; exact-origin reflection, credentials, and exposed
headers come from the canonical CORS middleware. Allowed development and
production origins, disallowed/no-origin requests, credentials, sanitization,
request IDs, preflight, HTTP exceptions, CSRF responses, body limits, and GZip
are covered without wildcarding or arbitrary Origin reflection.

### Entitlement-aware route test isolation

The authorization and rate-limit test clients predated canonical commercial
tables. Their lightweight database doubles could not satisfy either canonical
or legacy lookup, so correct fail-closed enforcement returned 503 before the
authorization/rate-limit behavior under test.

`EntitlementTestState` now patches only the entitlement lookup boundary. Tests
explicitly activate `business` or grant the narrow `data_import`, `charts`, or
`response_management` capability to named fixture tenants. The real
`require_entitlement` route gate remains active; unconfigured tenants return
503, configured-but-denied capabilities return 402, cross-tenant authorization
still rejects access, and approved requests still reach rate limiting. No
global test bypass, fail-open lookup, legacy rollout flag, or all-tenant grant
was added.

### Durable storage ownership prevention

The readiness failure came from four bind-mounted host directories created or
left root-owned while the backend image correctly runs as UID/GID 65534. The
manual production ownership repair is operator-confirmed and readiness now
reports `storage="ok"`.

The repository now contains `scripts/prepare_production_storage.sh` and a
systemd drop-in under `deployment/systemd/`. The fixed, argument-free root hook
runs before the unprivileged deployment service starts Compose, creates only
the four trusted paths with `install -d`, sets directory mode 0755, and scopes
recursive ownership repair to UID/GID 65534 without deleting, truncating, or
world-writable chmod. The drop-in was not installed during this task; operations
must install it before the next production deployment because modifying the
running production host was explicitly out of scope.

### Button color model and accessibility

Buttons now support optional `backgroundColor`, `textColor`,
`hoverBackgroundColor`, `hoverTextColor`, and `borderColor` fields. Frontend
normalization and backend draft/publish validation accept only six-digit hex and
normalize to uppercase. Empty fields reset to existing theme/variant behavior.
Malformed hex, declarations, semicolons, URL/expression/JavaScript/HTML content,
CSS variables, arbitrary `style`, `buttonColors`, and nested new color fields
inside `styles` are rejected.

The inspector adds native color pickers, editable hex inputs, clear actions,
accessible labels/error association, live canvas updates, and non-blocking
normal/hover contrast warnings. A shared presentation helper drives editor and
public renderers. Hover overrides never apply to disabled buttons, link-shaped
disabled actions are noninteractive, and the existing focus-visible indicator
is not removed. Buttons with no new fields render exactly through their prior
theme defaults; draft save/reload and publish/republish preserve configured
values without mass-rewriting old blocks.

### Follow-up validation

| Check | Result |
|---|---|
| Focused backend follow-up suite | 42 tests passed |
| Ephemeral root storage-preparation exercise | Passed: four paths, 65534:65534, mode 0755, existing file retained, arbitrary argument rejected |
| Full backend suite in rebuilt current-source image | 813 tests passed, `OK` |
| Full frontend suite | 82 files passed; 489 passed, 1 skipped |
| Button/runtime/persistence focused frontend suite | 6 files, 62 tests passed |
| Frontend production build and theme audit | Passed; existing large-chunk warning retained |
| Frontend lint | Existing baseline retained: 9 errors, 4 warnings; no new finding |
| Production Compose validation | Passed |
| Development overlay Compose validation | Passed |
| Migration mirror validation | 72/72, zero errors; known 013/014 warnings retained |
| Dependency-lock validation | Passed |
| Python compile / `pip check` / installed constraints | Passed / no broken requirements / passed |
| `npm audit --omit=dev` | 2 findings: `react-router` high, `react-router-dom` moderate |
| Full `npm audit` | 6 findings: 1 low, 1 moderate, 4 high (`@babel/core`, `brace-expansion`, `postcss`, `react-router`, `react-router-dom`, `vite`) |
| `git diff --check` | Passed before documentation update; rerun at commit gate |
| Targeted secret/artifact scan | Passed before documentation update; rerun after staging |

No forced audit fix or unrelated dependency upgrade was made. The production
checkout, database, services, deployment installation, DNS, Cloudflare, and
remote Git state were untouched.
