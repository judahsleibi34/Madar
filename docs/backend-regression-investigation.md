# Backend regression investigation — 2026-10-11

The complete backend suite passes in the repository's intended CI environment:
**2,917 tests, zero failures, zero errors, 526 skips**. All 12 previously reported
failures and 12 errors were reproduced in the native virtual environment, then
resolved by using the existing isolated CI invocation, without modifying runtime
code, fixtures or assertions. Classification for all 24 entries is **D: test
fixture/environment issue**. No entry requires an architecture-driven assertion
update, schema change or entitlement relaxation.

## Reproduction and first root cause

The investigation first reproduced the reported invocation:

```bash
cd web/backend
madar_env/bin/python scripts/run_tests_no_external_network.py
```

Result: 2,817 tests in 40.592 seconds; 12 failures, 12 errors, 526 skips. This matches
the previous learner-pass run's exact failure/error inventory. The network guard
blocked external attempts; no external request was permitted by that runner.

The first shared cause occurs during discovery/import, before an individual test
assertion: `database.load_backend_environment()` defaults to `web/.env`. With no
explicit environment isolation, its development fallback enables dotenv override;
the file then selects production settings. The first reported import error is
`test_app_middleware`, through `app.py:101` →
`runtime_config.validate_runtime_configuration()` → missing production `REDIS_URL`.

The workflow `.github/workflows/backend-check.yml` is authoritative for the full
suite. Its Docker test target excludes `.env*`, installs locked dependencies,
runs as UID 65534, supplies synthetic credentials and `APP_ENV=test`, provides
writable temporary storage, and mounts the expected source layout read-only.
The investigation built that image and executed the workflow's **Run backend
tests** command verbatim. Result: 2,917 tests in 37.032 seconds, 526 skips,
`EXTERNAL_ATTEMPTS []`, `EXTERNAL_SITES []`.

The 100-test count difference comes from seven failed module imports: native
discovery counted seven `_FailedTest` placeholders; CI loaded their 107 actual
tests. Those errors were not 12 individually executed test-case failures.

## Root-cause groups

| Group | Entries | Evidence | Correction |
| --- | --- | --- | --- |
| D1: production startup configuration loaded during discovery | Seven import errors | All terminate at the same missing `REDIS_URL` production validation. Those seven complete modules pass in CI. | Existing isolated CI image/environment. No production validator bypass or Redis configuration change. |
| D2: operator commercial override imported into entitlement fixtures | Nine failures | Runtime warned that commercial enforcement was disabled; `test_inactive_subscription_grants_nothing` returned `operator_configuration_override` instead of `canonical_inactive`. Other fixtures saw all capabilities, override storage and 10,000 seats. | Exclude app dotenv from tests; canonical enforcement retains its default in CI. |
| D3: production cookie policy imported into MFA fixture | One failure | Cookie had `SameSite=none`; fixture expects the test default `SameSite=lax`. | Isolated test environment; production cookie policy unchanged. |
| D4: production operational readiness obligations inherited by fixtures | Two failures | Diagnostic below identifies unmocked worker/parser/backup checks failing despite mocked database/auth/schema checks. | Isolated test environment; readiness still fails closed in production. |
| D5: CI source/migration mount layout absent in native run | Five errors | Four tests cannot find `web/.github/workflows/backend-check.yml`; quiz test cannot find `/workspace/database/migrations/082_create_public_quiz_attempts.sql`. All pass with workflow mounts. | Use the complete existing read-only mounts and `MADAR_TEST_REPOSITORY_ROOT`. |

The two readiness tests were rerun with a diagnostic wrapper that printed only
component states. Both had `calendar_sync_worker=misconfigured`,
`calendar_sync_queue=unavailable`, `parser_isolation=in_process`,
`notification_worker=unavailable`, `notification_queue=unavailable`, and
`backup_freshness=missing`. Their database/auth/storage/schema checks were mocked
`ok`. These are production obligations leaking into test fixtures, **not a failing
schema141 query**. No shared `setUpClass` or database fixture failure caused the
24-entry inventory; seven modules failed at import, five entries failed reading
source files, and twelve reached assertions under the wrong configuration.

`database.py`, `entitlement_service.py`, `auth_service.py`, `runtime_config.py`,
`readiness_service.py` and the backend workflow have no working-tree diff against
HEAD. The same current application/test source passes both complete CI runs.
This supports D for every entry. It does not justify calling a real regression
pre-existing merely to dismiss it.

## All 12 failing tests

Each row is category D. All passed unchanged in the focused rerun and both complete
CI runs. Names below are fully qualified unittest IDs.

| # | Test | Root cause and observed evidence |
| --- | --- | --- |
| 1 | `test_commercial_entitlements.EntitlementMatrixTests.test_base_plan_capability_matrix` | D2: Forms fixture unexpectedly includes `page_builder`. |
| 2 | `test_commercial_entitlements.EntitlementMatrixTests.test_branded_subdomain_requires_addon_or_reviewed_grandfathering` | D2: override grants `branded_madar_subdomain` without canonical add-on. |
| 3 | `test_commercial_entitlements.EntitlementMatrixTests.test_cancelled_expired_past_due_and_malformed_states_grant_nothing` | D2: 26 capabilities returned instead of none. |
| 4 | `test_commercial_entitlements.EntitlementMatrixTests.test_duplicate_entitled_subscription_is_rejected` | D2: canonical duplicate-subscription exception not raised under override. |
| 5 | `test_commercial_entitlements.EntitlementMatrixTests.test_inactive_subscription_grants_nothing` | D2: `operator_configuration_override` instead of `canonical_inactive`. |
| 6 | `test_commercial_entitlements.EntitlementMatrixTests.test_missing_subscription_fails_closed` | D2: override grants capabilities despite absent subscription. |
| 7 | `test_commercial_entitlements.EntitlementMatrixTests.test_storage_addons_aggregate_exact_bytes` | D2: override 10 GiB instead of canonical 12 GiB. |
| 8 | `test_commercial_entitlements.EntitlementMatrixTests.test_unknown_active_plan_and_dependency_failure_fail_closed` | D2: override grants capabilities instead of none. |
| 9 | `test_commercial_entitlements.EntitlementMatrixTests.test_workspace_seat_addons_aggregate` | D2: override 10,000 seats instead of canonical eight. |
| 10 | `test_mfa_login_cookie_handoff.MfaCookieHandoffTests.test_real_response_preserves_cookie_and_jar_reaches_prefixed_challenge` | D3: actual `SameSite=none`, expected test default `lax`. |
| 11 | `test_readiness_service.ReadinessServiceTests.test_all_required_components_ready` | D4: production worker/parser/backup checks make `ready=False`. |
| 12 | `test_readiness_service.ReadinessServiceTests.test_explicit_optional_redis_outage_is_ready` | D4: Redis correctly optional; other inherited production checks still fail. |

## All 12 erroring entries

Each row is category D. The seven `_FailedTest` IDs identify discovery/import
errors, not an individual test method. The focused rerun loads those full modules.

| # | Test/error ID | Root cause and observed evidence |
| --- | --- | --- |
| 1 | `unittest.loader._FailedTest.test_app_middleware` | D1: app import rejects missing production `REDIS_URL`. |
| 2 | `test_backend_ci_environment.BackendCiEnvironmentTests.test_application_import_uses_writable_ci_storage_as_non_root` | D5: expected workflow source file absent at native fallback root. |
| 3 | `test_backend_ci_environment.BackendCiEnvironmentTests.test_backend_ci_mounts_frontend_vite_config_read_only` | D5: same missing workflow path. |
| 4 | `test_backend_ci_environment.BackendCiEnvironmentTests.test_backend_ci_uses_safe_complete_hermetic_environment` | D5: same missing workflow path. |
| 5 | `test_backend_ci_environment.BackendCiEnvironmentTests.test_ci_uses_git_capable_test_target_without_expanding_runtime_image` | D5: same missing workflow path. |
| 6 | `unittest.loader._FailedTest.test_business_write_authority` | D1: same app import configuration rejection. |
| 7 | `unittest.loader._FailedTest.test_provider_recovery` | D1: same app import configuration rejection. |
| 8 | `test_public_quiz_security.PublicQuizSecurityTests.test_attempt_migration_serializes_limits_and_finalize_with_row_lock` | D5: migration082 unavailable at native `/workspace/database` fallback. |
| 9 | `unittest.loader._FailedTest.test_public_site_runtime` | D1: same app import configuration rejection. |
| 10 | `unittest.loader._FailedTest.test_public_upload_routes` | D1: same app import configuration rejection. |
| 11 | `unittest.loader._FailedTest.test_publication_isolation` | D1: same app import configuration rejection. |
| 12 | `unittest.loader._FailedTest.test_storage_delivery` | D1: same app import configuration rejection. |

Complete reproduced stack traces are retained in
[backend-regression-investigation-traces.txt](backend-regression-investigation-traces.txt).
Repository paths are normalized; the synthetic MFA cookie value is redacted.
No application credentials or dotenv contents are included.

Category totals: **A 0, B 0, C 0, D 24, E 0, F 0**. No reported failure was caused
by recent learner work or earlier E-Learning changes. None remains to be excused as
pre-existing/unrelated. No expected assertion needed updating.

## Schema141 contract

Read-only verification of the configured **loopback** application database found
`public.application_schema_state(contract_key='core').schema_version=141`, plus
all four independent tables: `elearning_forms`, `elearning_form_versions`,
`elearning_form_responses`, `elearning_form_files`.

`run_local.configure_local_environment(local_database=True,
schema_contract='schema-114-141-bridge.json')` selects compatible range 114–141;
that descriptor targets141. E-Learning Forms additionally require
`settings_available(141)` and fail closed below it. Older player/referral/programme
minimum schema gates represent their own introduction versions, not a global
expectation that the current database must be139/140.

The active **production** `web/deployment/releases/release.json` deliberately
remains target115, compatible range115–115, migration class/policy `none`, without
a migration manifest. Local141 selection does not change production release
authority. Neither descriptor nor any release metadata was edited in this pass.

The existing `rehearse_migration_141.py` applied the retained immutable001–141
chain to its separately marked disposable database, reached the production115
checkpoint, verified populated138→139,139→140,140→141 preservation and rollback,
then ran 292 database tests successfully. These cover programmes, referrals,
CEFR, tenant isolation, owner tools, integration and independent Forms. It removed
the marked rehearsal database; application data was untouched.

Assertions referring to138/139/140 in the rehearsal intentionally verify the
pre-upgrade state after rollback. Local setup tests also deliberately exercise
older retained contracts (including118 and136); the release-contract suite checks
all retained candidates through141. No reported test assumes139/140 must be the
current global schema. No stale schema assertion required correction.

Both migration trees contain exactly141 migrations, with matching bytes. No142
exists. Before/after SHA-256 inventory verifies every migration and release JSON
is unchanged. The migration validator's two warnings are the already-recognized
identical013/014 historical files, one warning per tree; zero errors.

## Learner API contract audit

| Area | Existing backend contract checked | Finding |
| --- | --- | --- |
| Dashboard / resume | `elearningPlayer.fetchMyLearning`, `elearning_player_service.my_learning`, existing125/128 RPC projections | Course/progress/resume IDs already exist; no new endpoint or fabricated progress. Dashboard uses up to four resumable rows from the existing first page. |
| Referrals | `/elearning/my-learning/referrals`, `academy_referral_service.account` | `available`, `enabled`, eligible code, balances/history are existing server projections; disabled accounts have no share action. |
| Rewards / wallet | Same referral projection and `academy_programme_service.account` | Existing balances, simulated flag and actual wallet fields are used; UI does not credit money or change financial authority. |
| Withdrawals | Existing `/elearning/programmes/account` and `/withdrawals` | Configured methods/minimum, capability, debt, amount, ownership confirmation and idempotency payload match existing guards. No payment provider or accounting changes. |
| Programme details | Existing account/application projection and guarded private-document endpoints | UI displays submitted answers/payment information; staff review notes and workflow history are excluded from learner display. Backend remains authoritative for eligibility. |
| Form login / return | Academy form GET returns401 for required login; Academy login uses `academyReturnPath` | UI preserves the contextual path/query through existing return validation; Forms definitions/responses remain in independent tenant storage. |
| Notification deep links | `notification_action_service.validate_notification_action_path` and frontend `notificationActions` | Recent backend edit only expanded the existing allowlist to actual guarded learner routes. Tenant-bound action handling and external/query/fragment rejection remain covered by tests. |
| Capability visibility | `/elearning/programmes/capabilities` returns capabilities and `programme_flags`; account settings/referral response supply optional navigation | UI uses existing server flags and capabilities. Showing a link never grants permission. No invented grant or new backend assumption found. |

Recent learner work's backend runtime scope is the notification route allowance;
the full suite and related notification tests pass unchanged. `CoursePlayer` and
its canonical content, assessment, progress and credential authority were not
changed in this investigation. No frontend contract correction was necessary.

## Exchange direction

**New Exchange applications should use E-Learning Forms.** The current specialised
`AcademyProgrammesPage` still submits `kind=exchange` to the existing programme
application endpoint, and `AcademyExchangeSelector` uses the existing guarded
`/elearning/owner/exchange/available/for-me` projection. This is the retained legacy
flow, not the desired new Forms architecture.

None of the 24 reported failures concerns Exchange. The database rehearsal checks
legacy application/opportunity compatibility and preservation; it does not make
Forms depend on specialised application tables or Builder submissions. No legacy
record was deleted, no specialised backend was expanded, and no Exchange refactor
was performed. Routing new applications through independent Forms belongs to the
subsequent explicitly scoped architecture work.

## Corrections and verification layers

The smallest correction was to run the already-defined CI environment and repair
the local testing documentation. `web/README.md` previously referenced a missing
`docker-compose.test.yml`; it now points to the real backend workflow, explains
dotenv contamination and distinguishes disposable database verification from the
application database. No test-only production behavior was introduced.

Files changed **in this pass only**:

- `web/README.md`: intended backend testing instructions.
- `docs/backend-regression-investigation.md`: inventory, classifications and evidence.
- `docs/backend-regression-investigation-traces.txt`: sanitized reproduced traces.
- `docs/elearning-learner-surroundings-audit.md`: link to the resolved backend gate.

Existing uncommitted E-Learning changes predate this pass and were retained.
Backend/API behavior changed: **none**. Schema changed: **no**. Payments, EduHope
configuration, Forms/Builder storage boundaries and the course player were retained.

| Layer | Result |
| --- | --- |
| Native reproduction | 2,817 tests; exact12 failures/12 errors/526 skips. Expected diagnostic failure. |
| Intended complete CI reproduction | 2,917 tests; zero failures/errors,526 skips;37.032s; no external attempts. |
| Previously failing cases and blocked modules | 124 tests passed;4.898s; no external attempts. |
| Related backend modules | 184 tests passed;5.972s; no external attempts. Entitlements, MFA, readiness, CI layout, quiz, referrals/programmes, owner tools, capabilities, Forms, player, credentials, notification actions and local contracts. |
| Final complete backend suite | **2,917 tests; zero failures/errors;526 skips;35.828s; no external attempts.** |
| Schema141 disposable database rehearsal | **292 tests passed**;15.465s; immutable chain, populated preservation and rollback checks also passed. |
| Dependency locks / migration trees / transitions / secret hygiene / forward-release source | All five checks passed. |
| Locked backend test image / installed dependencies | Build passed; `python -m pip check`: no broken requirements. |
| Migration/release immutability and whitespace | Before/after checksums match; no142; `git diff --check` passed. |
| Frontend suite / lint / build | Not rerun: no frontend or shared contract changed in this pass. Previous learner pass retained1,502 frontend passes and lint/build passes. |

The full CI suite has 526 explicit skips, principally opt-in database/native
integration requirements; its 2,917 discovered tests represent2,391 executed
passing cases. The separate schema141 rehearsal executes the292 database checks
above. It does not claim every optional platform/database integration skip was
executed, nor production rollout acceptance.

There are **no remaining backend failures** under the intended suite invocation.
The backend regression gate is clear to continue E-Learning architecture work.
This is not a PR, deployment or production-readiness approval. Production/staging
image acceptance, governed backup/restore, upgrade and external-provider gates
were outside this local investigation and were not executed.

## Copyable complete backend invocation

From the repository root, build as described in `web/README.md`, then run the
workflow command below. The workflow remains the source of truth if it changes.

```bash
docker run --rm \
  --env APP_ENV=test \
  --env SUPABASE_URL=http://127.0.0.1:54321 \
  --env SUPABASE_ANON_KEY=madar-ci-placeholder-anon-not-a-secret \
  --env SUPABASE_SERVICE_KEY=madar-ci-placeholder-service-not-a-secret \
  --env PUBLIC_UPLOADS_DIR=/tmp/madar-ci/public/uploads \
  --env DATA_UPLOAD_DIR=/tmp/madar-ci/private/uploads \
  --env PRIVATE_CHARTS_DIR=/tmp/madar-ci/private/generated-artifacts \
  --env MADAR_UPLOAD_WORKSPACE_DIR=/tmp/madar-ci/parser \
  --env MPLCONFIGDIR=/tmp/madar-ci/cache/matplotlib \
  --env XDG_CACHE_HOME=/tmp/madar-ci/cache/xdg \
  --env PYGWALKER_TELEMETRY_ENABLED=false \
  --env MADAR_TEST_REPOSITORY_ROOT=/test-repository \
  --tmpfs /tmp:rw,exec,nosuid,nodev,size=1g,mode=1777 \
  --volume "$PWD/web/scripts:/scripts:ro" \
  --volume "$PWD/web/demo-data:/demo-data:ro" \
  --volume "$PWD/web/frontend/public:/frontend/public:ro" \
  --volume "$PWD/web/database:/app/database:ro" \
  --volume "$PWD/web/supabase:/app/supabase:ro" \
  --volume "$PWD/web/scripts:/test-repository/scripts:ro" \
  --volume "$PWD/web/deployment:/test-repository/deployment:ro" \
  --volume "$PWD/web/precutover:/test-repository/precutover:ro" \
  --volume "$PWD/web/database:/workspace/database:ro" \
  --volume "$PWD/web/supabase:/workspace/supabase:ro" \
  --volume "$PWD/web/database:/database:ro" \
  --volume "$PWD/web/supabase:/supabase:ro" \
  --volume "$PWD/.github/workflows/backend-check.yml:/test-repository/.github/workflows/backend-check.yml:ro" \
  --volume "$PWD/web/backend/Dockerfile:/test-repository/backend/Dockerfile:ro" \
  --volume "$PWD/web/frontend/Dockerfile:/test-repository/frontend/Dockerfile:ro" \
  --volume "$PWD/web/frontend/security_headers.conf.template:/test-repository/frontend/security_headers.conf.template:ro" \
  --volume "$PWD/web/frontend/storefront_frame_headers.conf.template:/test-repository/frontend/storefront_frame_headers.conf.template:ro" \
  --volume "$PWD/web/frontend/admin_preview_frame_headers.conf.template:/test-repository/frontend/admin_preview_frame_headers.conf.template:ro" \
  --volume "$PWD/web/frontend/nginx.conf.template:/test-repository/frontend/nginx.conf.template:ro" \
  --volume "$PWD/web/frontend/vite.config.js:/test-repository/frontend/vite.config.js:ro" \
  --volume "$PWD/web/docker-compose.yml:/test-repository/docker-compose.yml:ro" \
  --volume "$PWD/web/docker-compose.dev.yml:/test-repository/docker-compose.dev.yml:ro" \
  madar-backend-test python scripts/run_tests_no_external_network.py
```
