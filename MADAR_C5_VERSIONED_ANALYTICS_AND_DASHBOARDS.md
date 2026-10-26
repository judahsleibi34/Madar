# Madar C5 Step 2 — Versioned Analytics and Persistent Business Dashboards

## 1. Executive summary

**Recommendation: PASS — LOCALLY IMPLEMENTED AND OFFLINE VERIFIED.**

C5 Step 2 now provides an authorized, project-bound Business Intelligence workspace over immutable dataset versions. Users can select historical versions, run bounded server-side exploration, calculate deterministic generic metrics, view source/checkpoint freshness, and persist version-aware dashboard definitions. Dashboard widgets retain their dataset, immutable version, and analysis specification across a real browser reload.

The full disposable proof exercised FastAPI, PostgreSQL/PostgREST, Vault, signed webhook receipt, the webhook worker, private immutable history, checkpointing, candidate migration 163, React/Vite, and Playwright. The final locked backend, frontend, migration, authorization, contrast, and browser gates passed.

This is not staging-tested or production-ready. The selected release remains schema 146; migrations 161, 162, and 163 remain unselected candidates. No persistent database, staging service, production service, release selection, external provider, Qwen process, commit, push, or merge was touched.

## 2. Actual reused API and data contracts

The implementation extends the existing system rather than introducing a parallel data path:

- Existing authentication, active membership, user/tenant resolution, and project authorization are enforced by the data routes before service execution.
- `project_datasets`, `project_dataset_versions`, private immutable object storage, exact-version reopening, content hashes, revision lineage, and checkpoint records remain authoritative.
- Existing source registry, source resources, ingestion runs, automatic synchronization, webhook inbox, reconciliation, and checkpoint data supply the freshness projection.
- The existing assisted-analysis executor remains the metric engine. Distinct count and date aggregation were added there; the browser does not reproduce metric calculations.
- Existing private-storage hydration and integrity verification are reused before analysis.
- Existing service-role/RPC database conventions and schema compatibility gates are reused for persistence.
- Existing Builder project identity and routing are reused by the separate `/business-intelligence/projects/{project_id}/data` workspace.
- Data Logs remains independent and unchanged: **Source → Review → Prepare → Charts → Report**.

The added HTTP contracts are:

- `GET .../datasets/{dataset_id}/versions`
- `GET .../datasets/{dataset_id}/versions/{version_id}`
- `POST .../datasets/{dataset_id}/versions/{version_id}/explore`
- `GET .../datasets/{dataset_id}/freshness`
- `GET|POST .../dashboards`
- `GET|PATCH|DELETE .../dashboards/{dashboard_id}`
- `POST .../dashboards/{dashboard_id}/widgets`
- `PATCH|DELETE .../dashboards/{dashboard_id}/widgets/{widget_id}`
- `POST .../dashboards/{dashboard_id}/widgets/{widget_id}/execute`

All routes remain under the existing authenticated user/project data router.

## 3. Historical dataset-version support

`list_project_dataset_versions` returns a tenant-, project-, dataset-, and uploader-scoped bounded list ordered newest first. Its safe projection includes immutable version ID, version number, version kind, commit/creation time, content hash, bounded file metadata, and revision lineage where present. Physical paths, object credentials, connector credentials, and internal network details are omitted.

An exact version is resolved and authorized before storage access. Reopening a historical version never aliases it to latest and never rewrites history. The frontend stores the selected dataset and exact selected version independently; changing either invalidates displayed analysis and cancels/ignores stale requests.

Older schemas return an explicit capability-unavailable response instead of querying tables that do not exist. Exact-version preview remains bounded by the existing reopen contract.

## 4. Version-bound exploration and analysis

`versioned_analytics_service.explore_dataset_version` provides server-side exploration with:

- maximum page size 100 and maximum offset 10,000;
- at most 64 selected columns, eight filters, and two stable sort keys;
- equality, compatible range, missing, and not-missing filters;
- actual-schema field allowlisting before any operation;
- technical-type coercion for numeric, Boolean, date/datetime, and text equality;
- stable mergesort and an exact total within the admitted dataset;
- a 10 MiB object limit, 100,000-row limit, 512 KiB response limit, and three-second cooperative deadline;
- exact dataset/version/content-hash provenance on every successful result.

Unknown fields, text range comparisons, unsupported operators, oversized objects, excessive rows, excessive result payloads, and expired deadlines fail explicitly. No user expression is evaluated, no field identifier is concatenated into SQL or executable Python, and no arbitrary code path exists.

CSV/XLS parsing is intentionally conservative: the authorized object is integrity-checked and read only after its declared/actual size is admitted. This is a bounded file-analysis path, not a claim of random-access warehouse execution.

## 5. Source freshness/checkpoint semantics

The read-only freshness projection distinguishes:

- last event received;
- last ingestion attempt;
- last successful ingestion;
- latest committed immutable dataset version;
- latest completed analytical checkpoint;
- resource revision and reconciliation state;
- automatic synchronization state;
- pending reconciliation or failed processing;
- disabled/revoked source state.

Webhook receipt is not presented as synchronization, a committed version is not presented as checkpoint completion, and failure/reconciliation states remain visible. A dataset without a supported source relationship returns an honest unavailable reason. The projection excludes credentials, webhook verification secrets, OAuth tokens, Vault material, physical storage paths, and internal provider locations.

## 6. Metric and date-aggregation behavior

The trusted Python analysis service supports record count, sum, mean, minimum, maximum, grouped counts/compatible aggregations, and distinct non-missing count. Missing values are excluded rather than silently converted to zero.

Validated date aggregation supports day, ISO-style week boundaries, and calendar month in UTC, with count/sum/mean/min/max where the value column is compatible. Pandas mixed-format parsing is used after technical validation. Invalid and missing dates are excluded and counted in warnings. Results include observed coverage and partial first/last period metadata. The output remains generically labeled—for example, “monthly sum of amount”—and does not infer revenue, profit, cash flow, growth, currency, unit, or business meaning.

Period-over-period interpretation is not enabled because semantic coverage and measure contracts are not yet sufficient. Ambiguous units/currencies remain explicitly unvalidated.

## 7. Persistent dashboard architecture

Candidate schema 163 adds private dashboard definitions and widgets:

- dashboard project/tenant/creator ownership, name, description, timestamps, and optimistic revision;
- widget identity/type, dataset ID, exact bound version ID, pinned/latest policy, validated analysis specification, layout, display options, and timestamps;
- composite foreign keys that keep tenant, project, creator, dataset, and version relationships aligned;
- service-role-only scoped RPCs for list/get/create/update/delete and widget mutations;
- one shared dashboard revision incremented transactionally for dashboard and widget writes.

The service validates strict operation, period, policy, layout, and display allowlists and bounds all strings/configuration. It stores definitions and immutable references, not cached or fabricated business numbers. Widget execution recomputes through the trusted exact-version analysis service and its row/byte/deadline guard.

The frontend provides dashboard list/create, title and description editing, configurable 12-column width/height, adding a successfully executed result, reopening after reload, explicit refresh, widget removal, and confirmed dashboard deletion. Empty, loading, unavailable, error, and needs-attention states are rendered.

Dashboards are currently private to their creator within the authorized project. No public links or unauthenticated sharing were added.

## 8. Candidate migration 163

Added mirrored files:

- `web/database/migrations/163_add_bi_dashboards.sql`
- `web/supabase/migrations/163_add_bi_dashboards.sql`

Both have SHA-256 `a8120fa80b6e9f78356cdd89a323ad661b08fd84d4043699c8e5748827b4993b`.

Added unselected release metadata:

- `migrations-162-163-bi-dashboards.json`: SHA-256 `4d3118246ab3f44047a1aa8e738a375bd93109fc1281d899314ee43d148c4708`
- `schema-162-163-bi-dashboards-bridge.json`: SHA-256 `462821607d74280e4f4afaa044abb4203afebbf4892112167bf800e6d991a67a`

The migration requires exact predecessor schema 162 while holding the schema-state row lock. The disposable rehearsal verified forced transaction rollback, concurrent migration serialization (exactly one winner), RLS/privileges, scoped CRUD, cross-tenant denial, and concurrent same-revision widget writes (exactly one winner). The deliberate `division by zero` shown in rehearsal output is the rollback probe and was followed by a passing clean application.

Migration-tree validation found 163 database and 163 Supabase migrations, zero errors, and only the two documented historical 013/014 duplicate-content warnings.

## 9. Authorization and RLS evidence

Authorization is enforced in layers:

1. FastAPI authenticates the user and resolves the active tenant/membership.
2. The route verifies the requested user and project under that tenant.
3. Dataset/version services repeat tenant/project/dataset/uploader scoping.
4. Dashboard RPCs require tenant, project, creator, dashboard, widget, dataset, and version identities.
5. Database composite foreign keys reject inconsistent ownership relationships.
6. RLS is enabled on both dashboard tables; direct access is revoked from `public`, `anon`, and `authenticated`; only service-role RPC execution is granted.
7. Optimistic revision checks reject stale writes with HTTP 409 rather than overwriting concurrent changes.

The real browser/API test confirmed anonymous dashboard denial (401), mismatched-user denial (403), and cross-tenant project non-disclosure (404). The migration rehearsal independently confirmed cross-tenant mutation denial.

## 10. Dataset-version and dashboard provenance

Every exploration or analysis result records the project dataset ID, exact immutable version ID/number/kind, content hash where available, and operation specification. Every widget stores the exact dataset/version binding and validated analysis definition. The UI exposes this provenance in each widget and continues to show the version actually used after reload or refresh.

No displayed widget is represented as current merely because a source event arrived. Latest committed dataset version, analysis version, and checkpoint status remain distinct.

## 11. Schema drift and refresh behavior

Version policies are explicit:

- `pinned` always recomputes from the stored immutable version until the user changes the definition.
- `latest_committed` checks the latest committed version only on explicit user refresh.

The latest policy advances its bound version only after the newer version resolves, the referenced fields/operation remain compatible, and execution succeeds. An incompatible schema returns `needs_attention` and retains the old binding; it does not silently reuse missing columns or claim a successful refresh. Pinned widgets never auto-advance.

## 12. Browser E2E evidence

The final disposable end-to-end run used a fresh PostgreSQL database, PostgREST, local Vault transit key/token, FastAPI, private HTTP object fixture, webhook worker path, Vite, and Playwright. External delivery was disabled and the database/storage were removed afterward.

- Signed webhook → durable inbox → worker → immutable history/checkpoint → browser status: **1 passed (1.6 minutes)**.
- Disposable upgrade from schema 162 to candidate 163.
- Dataset/history enumeration, oldest-version selection, server exploration, distinct count, dashboard/widget creation, full browser reload, exact-version provenance, pinned refresh, authorization denials, widget deletion, and dashboard deletion: **1 passed (10.5 seconds)**.
- Artifacts: `/tmp/madar-data-sources-c3-step5-browser-25205-1326847`, including created/reopened C5 dashboard screenshots and webhook-state screenshots.

Earlier regression slices in the same implementation verification passed the older-schema fallback (1/1), main Data Sources browser flow (1/1), and Google Sheets offline browser flow (1/1). No real Google authorization or staging service was contacted.

## 13. Accessibility and RTL results

The full unchanged route-coverage contrast audit passed:

- 684 route checks;
- 29,166 text checks;
- 324 placeholder checks;
- 8,370 control checks;
- 10,354 icon checks;
- 456 notification-prompt route checks;
- zero failed route checks.

It covered public, admin, and user routes—including Business Intelligence—at compact, intermediate, and wide viewports, in light/dark themes and English LTR/Arabic RTL. The workspace uses labeled native controls, keyboard-operable tabs/buttons/tables, responsive single-column fallback, RTL-safe layout, and accessible tabular alternatives for analytical output.

## 14. Full test counts

Final gates:

- Locked backend image: **3,750 passed, 683 skipped, 0 failures, 0 collection errors** in 69.964 seconds; `EXTERNAL_ATTEMPTS []`, `EXTERNAL_SITES []`.
- Backend dependency consistency: **no broken requirements**.
- Frontend: **240 files passed; 1,780 tests passed; 1 skipped; 0 failed**.
- Focused Business Intelligence frontend: **9/9 passed**.
- Focused backend implementation checkpoint: **48/48 passed**; the final full suite additionally covered the final bounded execution guard.
- Browser E2E safety guard: **1/1 passed**.
- Final webhook browser flow: **1/1 passed**.
- Final C5 browser persistence flow: **1/1 passed**.
- Migration 163 disposable rehearsal: **passed**.
- Candidate 163 validator, complete 146→163 candidate-chain validator, migration transition validator, forward-release validator, dependency-lock validator, tracked-secret hygiene, frontend lint, frontend build, and `git diff --check`: **passed**.
- Migration tree: **163/163 mirrored, 0 errors, 2 known historical warnings**.

Expected skips are database/environment-gated tests outside the hermetic unit suite; disposable database coverage was run separately. There were no final collection errors.

## 15. Exact C5 files changed

Core backend and tests:

- `web/backend/services/project_dataset_service.py`
- `web/backend/services/versioned_analytics_service.py`
- `web/backend/services/bi_dashboard_service.py`
- `web/backend/data_analysis/routes/data_routes.py`
- `web/backend/data_analysis/assisted/assisted_analysis.py`
- `web/backend/tests/test_project_datasets.py`
- `web/backend/tests/test_versioned_analytics.py`
- `web/backend/tests/test_bi_dashboard_service.py`
- `web/backend/tests/test_bi_dashboard_candidate.py`
- `web/backend/tests/test_assisted_analysis.py`
- `web/backend/tests/test_authorization_matrix.py`
- `web/backend/tests/test_webhook_candidate.py` (CI/local candidate-path compatibility only)

Database, release metadata, validation, and rehearsal:

- `web/database/migrations/163_add_bi_dashboards.sql`
- `web/supabase/migrations/163_add_bi_dashboards.sql`
- `web/deployment/releases/migrations-162-163-bi-dashboards.json`
- `web/deployment/releases/schema-162-163-bi-dashboards-bridge.json`
- `web/scripts/bi_dashboard_candidate.py`
- `web/scripts/rehearse_migration_163.sh`
- `web/scripts/check_data_sources_staging_chain.py`
- `web/scripts/check_forward_release.py`
- `web/scripts/check_migrations.py`
- `web/scripts/rehearse_data_sources_browser_e2e.sh`

Frontend, browser tests, and routing:

- `web/frontend/src/components/BusinessIntelligence/BusinessIntelligenceWorkspace.jsx`
- `web/frontend/src/components/BusinessIntelligence/BusinessIntelligenceWorkspace.test.jsx`
- `web/frontend/src/styles/admin/business-intelligence.css`
- `web/frontend/e2e/business-intelligence-live.spec.mjs`
- `web/frontend/e2e/data-sources-live.spec.mjs`
- `web/frontend/src/routes/UserWorkspaceRoutes.jsx`
- `web/frontend/src/routes/UserWorkspaceRoutes.test.jsx`
- `web/frontend/src/routes/routeErrorSurface.js`
- `web/frontend/src/routes/routePreload.js`
- `web/frontend/src/routes/routePreload.test.js`
- `web/frontend/src/routes/routeUtils.js`
- `web/frontend/src/routes/routeUtils.test.js`
- `web/frontend/src/routes/shared.jsx`
- `web/frontend/src/config/routes.js`
- `web/frontend/src/components/DashboardBuilder/DashboardSidebar.jsx`
- `web/frontend/src/components/DashboardBuilder/DashboardSidebar.test.jsx`
- `web/frontend/src/components/PageBuilder/core/PageBuilder.workspaceRouting.js`
- `web/frontend/src/components/PageBuilder/core/PageBuilder.workspaceRouting.test.js`
- `web/frontend/src/components/PageBuilder/workspace/BuilderProjectChooser.jsx`
- `web/frontend/src/components/PageBuilder/workspace/BuilderProjectChooser.test.jsx`
- `web/frontend/src/i18n/locales/en/dashboard.json`
- `web/frontend/src/i18n/locales/ar/dashboard.json`
- `web/frontend/scripts/check-color-contrast.mjs`

Policy/documentation:

- `docs/MADAR_AUTO_DEPLOY_MERGE_CONTRACT.md`
- `docs/production-release-policy.md`
- `docs/automated-database-migration-architecture.md`
- `web/README.md`
- `MADAR_C5_VERSIONED_ANALYTICS_AND_DASHBOARDS.md`

The worktree also contains owner changes and earlier C3/C4/C5 Step 1 candidate work. Those changes were preserved and are not reclassified as C5 Step 2 work by this list.

## 16. Known limitations

- CSV/XLS exact-version exploration reads the admitted authorized object into process memory; the hard 10 MiB/100,000-row limits make this safe for the current architecture, but it is not a random-access analytical warehouse.
- The three-second deadline is cooperative and cannot interrupt a synchronous parser mid-call; byte and row admission limits provide the hard bound.
- Date aggregation is UTC only. Arbitrary business timezones and fiscal calendars are deferred.
- Period-over-period comparisons are deferred until complete-period coverage and semantic measure contracts are trustworthy.
- Currency, unit, row grain, balance/rate behavior, semantic role, and approval status are not inferred. Generic deterministic results remain usable without them.
- Advanced project sharing and public dashboard links are deferred; dashboards are creator-private inside an authorized project.
- `latest_committed` refresh is user-initiated only; no background dashboard refresh worker was added.
- Candidate schema 163 is available only in disposable/offline verification. Older selected schemas show capability-unavailable states.
- No arbitrary large-result browsing, joins, multi-dataset relationship inference, or automatic semantic mapping is claimed.
- Qwen remains entirely separate and is not a dependency.

## 17. No-deployment confirmation

No staging or production deployment occurred. No persistent migration was applied. No release manifest selection was changed. `web/deployment/releases/release.json` still targets schema 146. No public webhook was activated, no real Google service was contacted, no persistent worker/server was started, and no commit, push, merge, or production mutation was performed.

Implementation state: **implemented and offline-tested**. Staging state: **not tested**. Production state: **not production-ready**.

## 18. Explicit recommendation

**PASS — OFFLINE VERIFIED.**

The acceptance criteria for C5 Step 2 are met in isolated local/disposable infrastructure: historical version selection and exact analysis, bounded authorized exploration, deterministic distinct/date operations, honest freshness, persistent dashboards across sessions, exact widget provenance, explicit compatible refresh, cross-tenant denial, migration/RLS/concurrency safety, full regression, and genuine browser-to-backend persistence all passed.

This recommendation does not authorize candidate migration selection, staging, production deployment, or Qwen integration.

## 19. Proposed next milestone

Stop for owner review. After acceptance, the recommended next milestone is a separately authorized C5 follow-up for trusted semantic contracts and technical dataset profiling: validated semantic roles, units/currency, row grain, aggregation behavior, relationship evidence, approval state, and compatibility metadata. It should remain deterministic and provider/model-neutral, avoid compulsory manual mapping, and establish the safety basis for later KPI work and separately evaluated AI semantic proposals.

Do not begin that milestone, staging work, migration selection, or Qwen integration without new authorization.
