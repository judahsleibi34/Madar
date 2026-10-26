# Madar C5 Step 1 — Generalized Business Intelligence Frontend

Date: 2026-10-24
Status: **PASS — LOCALLY IMPLEMENTED AND OFFLINE VERIFIED**
Deployment status: **Not staging-tested and not production-ready**

## 1. Executive summary

C5 Step 1 adds a project-scoped Business Intelligence workspace for authorized, immutable project datasets. Users can select an available dataset, inspect the latest committed immutable version, review technical structure and a bounded server-provided preview, run compatible generic deterministic aggregations, inspect exact-version provenance, and render grouped results as an accessible bar chart and data table.

The implementation is domain-independent. It does not infer revenue, profit, currency, units, accounting meaning, row grain, or cross-dataset relationships. It does not call Qwen or any other model. Missing backend contracts are presented as explicit limitations rather than simulated with browser-local persistence or fabricated values.

The existing Data Sources feature remains responsible for ingestion and synchronization. The independent Data Logs flow remains `Source → Review → Prepare → Charts → Report` and is neither replaced nor redirected.

No backend code, migration, release manifest, active schema selection, worker, infrastructure, deployment, Qwen code, prompt, or model process was changed for this milestone.

## 2. Existing APIs and components reused

Repository inspection confirmed these authorized contracts:

- `GET /users/{user_id}/data/projects/{project_id}/datasets?limit=100`
  - Returns tenant/user/project-authorized active datasets and each dataset's latest immutable version.
  - Returns `available: false` on older schemas that lack the persistent dataset capability.
- `GET /users/{user_id}/data/projects/{project_id}/datasets/{dataset_id}`
  - Reopens the authorized latest version and supplies its bounded preview, columns, row count, dataset/version identifiers, and internal processing path.
- `POST /users/{user_id}/cleaning/statistics`
- `POST /users/{user_id}/cleaning/missing-report`
- `POST /users/{user_id}/cleaning/column-types`
  - Reused for technical profiling only; the UI does not convert technical types into business semantics.
- `POST /users/{user_id}/analysis/projects/{project_id}/datasets/{dataset_id}/versions/{version_id}/assist`
  - Resolves the exact authorized immutable version and performs deterministic existing analysis.
  - Returns project, dataset, version, version kind/number, and content-hash provenance.

Existing frontend infrastructure reused includes the dashboard shell/sidebar, project chooser and remembered data-project selection, route suspense/error surfaces, API client with authenticated cookies, theme tokens, localization direction handling, and the Data Sources/Data Logs project namespace helpers.

The existing backend assistant supports more internal operations, but the frontend exposes only the narrow operations verified as safe and compatible for this milestone. It does not duplicate calculations in JavaScript.

## 3. Navigation and frontend architecture

The new route is:

`/business-intelligence/projects/{project_id}/data`

Business Intelligence is a separate Workspace navigation item after Data Sources. It uses the same data-project chooser policy and session-scoped remembered project identity as Data Sources. A project URL is not opened unless it was explicitly confirmed or matches the remembered authorized selection. The backend remains authoritative for tenant/project/dataset authorization.

The workspace is lazy-loaded and has dedicated preload, loading, error-surface, route-classification, and compact-sidebar handling. Data Sources, Business Intelligence, and Data Logs retain separate routes and active-navigation states.

The principal component owns:

- authorized dataset registry state;
- immutable latest-version identity;
- technical profile and bounded-preview state;
- generic metric controls;
- exact-version result and provenance state;
- stale-request guards for dataset/profile and metric requests;
- Overview, Explore, Metrics, Visualizations, and Dashboard presentation.

## 4. Implemented workspace sections

### Overview

- Authorized project dataset selector.
- Latest committed immutable version selector and version kind/number.
- Row count, column count, technical missing-value count, update timestamp, and content hash when available.
- Explicit unavailable text for source linkage and last-successful-sync fields that the dataset contract does not expose.
- Explicit semantic metadata status: business meaning, units/currency, row grain, relationship validity, confidence, approval, and AI interpretation are not declared.
- Loading, empty, older-schema unavailable, and API error states.

### Explore

- Technical column types.
- Filled, missing, missing-percentage, and distinct information where returned by existing profile endpoints.
- Authorized server-provided preview, capped at 20 rows by the UI.
- Preview-only filter and sort controls.
- An explicit notice that filtering/sorting applies only to the bounded preview, not the full dataset.
- Partial-profile warning when one or more profiling calls fail.

### Metrics

- Record count.
- Sum of selected numeric column.
- Average of selected numeric column.
- Minimum and maximum of selected numeric column.
- Optional grouping by an existing column.
- Numeric column options are constrained by the returned technical profile/type.
- Every calculation is sent to the existing exact-version backend endpoint.
- Result labels remain generic and are bound to the executed metric snapshot, not guessed business meaning or later control changes.
- Unknown unit/currency remains visible.

Distinct count and time aggregation are not exposed because an adequate verified frontend API contract was not available. Ratio/difference operations exist internally but were deliberately excluded because the available technical schema does not establish compatible units or consequential semantic meaning.

### Visualizations

- Existing backend-generated grouped metric rows/chart metadata are rendered as a responsive accessible bar chart.
- The same values are supplied in an HTML data table.
- No chart appears until a real grouped calculation succeeds.
- The UI explicitly states that time trends require a validated backend date-aggregation contract.

### Dashboard

- Provides a session-only composition preview of the current genuine result.
- Clearly states that server-side persistence, sharing, layout, and refresh contracts do not yet exist.
- Does not claim browser-local data is a saved dashboard.

## 5. Dataset/version identity and provenance

Analysis requests include the current project ID, dataset ID, and immutable version ID in the authorized URL. Result provenance shows:

- `project_id`;
- `dataset_id`;
- `dataset_version_id`;
- `content_hash` when available;
- executed operation.

Dataset selection invalidates the previous result and increments request identities. Abort controllers cancel obsolete dataset/profile requests. Independent monotonically increasing request identities prevent a slow earlier dataset or metric response from replacing the current selection.

The current registry API returns only each dataset's latest version. The version control therefore shows the authoritative immutable latest version but is disabled, with an explicit historical-version-contract limitation. The UI does not invent a historical list.

## 6. Deterministic analysis behavior

All displayed metric values come from the authorized exact-version backend operation. The browser does not download an unbounded dataset or reproduce aggregation logic. Only type-compatible numeric columns are offered for numeric operations. Missing values are left to the existing backend operation semantics and are not silently changed to zero in the frontend.

The workspace does not provide:

- currency conversion or cross-currency addition;
- inferred financial statements or business KPIs;
- rate averaging, ratios, or differences without declared compatible semantics;
- arbitrary SQL or Python;
- cross-dataset joins;
- invented date parsing or time bucketing;
- model-generated calculations.

## 7. Data quality and freshness semantics

Technical statistics, missingness, column types, bounded records, content hash, and immutable version identity are displayed when supplied by existing authorized APIs. These indicators describe technical structure only.

The dataset registry/reopen response does not currently provide source identity, last successful source synchronization, checkpoint-ready timestamp, validated date coverage, duplicate counts, units, or currencies. The UI reports those gaps honestly. It does not confuse webhook receipt time, source event time, dataset commit time, or checkpoint readiness.

## 8. Responsive, accessibility, and RTL results

- English LTR and Arabic RTL copy and layout are supported.
- Native labeled controls and buttons are keyboard focusable.
- Tabs expose navigation, tablist, tab, `aria-selected`, `aria-controls`, and tabpanel relationships.
- Charts have accessible names and an equivalent data table.
- Loading/status/error surfaces use appropriate status/alert semantics.
- Responsive layouts cover desktop, tablet, and 390 px mobile; the live browser rehearsal found no horizontal document overflow at 390 × 844.
- Reduced-motion behavior is respected.
- The dedicated BI contrast run passed all 12 combinations of 3 viewports × 2 themes × 2 directions: 612 text, 228 control, and 190 icon checks, with 0 failures.
- The complete existing contrast audit passed 684 route combinations: 29,024 text, 324 placeholder, 8,366 control, and 10,310 icon checks, with 0 failed route checks. Coverage increased by 12 route combinations for the real populated BI workspace and was not reduced elsewhere.

## 9. Test and verification results

Final results:

| Gate | Result |
|---|---:|
| Focused BI/routing/sidebar/project integration | 7 files, 114/114 passed |
| Full frontend Vitest suite | 240 files, 1,778 passed, 0 failed, 1 skipped (1,779 total) |
| Frontend ESLint | PASS, 0 errors/warnings |
| Production build | PASS, 2,840 modules transformed |
| API-origin audit | PASS (non-production skip behavior preserved) |
| Theme contract audit | PASS |
| Bundle-origin audit | PASS (non-production skip behavior preserved) |
| Tenant public-bundle audit | PASS |
| Dedicated BI contrast audit | 12/12 route checks passed |
| Full contrast audit | 684/684 route checks passed |
| `git diff --check` | PASS |
| JSON locale parse | PASS |
| E2E older-schema fallback | 1/1 passed |
| E2E live API ingestion + BI | 1/1 passed |
| E2E Google Sheets offline regression | 1/1 passed |
| E2E signed webhook/recovery regression | 1/1 passed |

The final disposable E2E run used tmpfs PostgreSQL, PostgREST, Vault, loopback-only FastAPI/provider/object fixtures, real ingestion/checkpoint workers, Vite, and Playwright. It verified:

- schema-141 capability fallback;
- authorized project selection and tenant isolation;
- encrypted credential storage, incremental revisions, checkpoint readiness, and immutable dataset reuse;
- the populated BI Overview/Explore/Metrics/Visualizations workflow;
- a real exact-version grouped sum and returned rows (`B=25`, `C=35`, `E=50`);
- result provenance disclosure and accessible chart;
- BI mobile layout;
- Google Sheets offline regression;
- signed webhook ordering, durable history, recovery/retry, checkpoint, secret rotation/revocation, reconstruction, and browser status;
- unchanged Data Logs steps: Source, Review, Prepare, Charts, Report.

Artifacts from the final run are in the ephemeral local directory:

`/tmp/madar-data-sources-c3-step5-browser-6997-629607`

This is offline disposable verification, not persistent staging verification.

## 10. Files changed for C5 Step 1

New:

- `web/frontend/src/components/BusinessIntelligence/BusinessIntelligenceWorkspace.jsx`
- `web/frontend/src/components/BusinessIntelligence/BusinessIntelligenceWorkspace.test.jsx`
- `web/frontend/src/styles/admin/business-intelligence.css`
- `MADAR_C5_BUSINESS_INTELLIGENCE_FRONTEND.md`

Updated for route/navigation/integration coverage:

- `web/frontend/src/config/routes.js`
- `web/frontend/src/routes/UserWorkspaceRoutes.jsx`
- `web/frontend/src/routes/UserWorkspaceRoutes.test.jsx`
- `web/frontend/src/routes/routePreload.js`
- `web/frontend/src/routes/routePreload.test.js`
- `web/frontend/src/routes/routeUtils.js`
- `web/frontend/src/routes/routeUtils.test.js`
- `web/frontend/src/routes/routeErrorSurface.js`
- `web/frontend/src/routes/shared.jsx`
- `web/frontend/src/components/DashboardBuilder/DashboardSidebar.jsx`
- `web/frontend/src/components/DashboardBuilder/DashboardSidebar.test.jsx`
- `web/frontend/src/components/PageBuilder/core/PageBuilder.workspaceRouting.js`
- `web/frontend/src/components/PageBuilder/core/PageBuilder.workspaceRouting.test.js`
- `web/frontend/src/components/PageBuilder/workspace/BuilderProjectChooser.jsx`
- `web/frontend/src/components/PageBuilder/workspace/BuilderProjectChooser.test.jsx`
- `web/frontend/src/i18n/locales/en/dashboard.json`
- `web/frontend/src/i18n/locales/ar/dashboard.json`
- `web/frontend/scripts/check-color-contrast.mjs`
- `web/frontend/e2e/data-sources-live.spec.mjs`

The worktree already contained extensive C3/C4/Google Sheets/webhook/backend/release-policy changes before C5 began. They were preserved and are not claimed as C5 implementation work.

## 11. Backend contract gaps for future work

1. Historical immutable-version enumeration and exact-version reopen/preview.
2. Source-to-dataset linkage plus last successful synchronization, commit, and checkpoint-ready timestamps in the dataset read contract.
3. Server-side preview pagination, filters, sorting, and bounded query metadata.
4. Explicit distinct-count support through the exact-version metric contract.
5. Validated date fields, calendar/timezone policy, periods, and exact-version time aggregation.
6. Declared unit, currency, additive/non-additive behavior, and compatible-period metadata.
7. Row-grain and validated dataset-relationship metadata for multi-source analysis.
8. Server-side dashboard definitions, ownership, layout, sharing, refresh, and version-bound widget persistence.
9. A stable source/checkpoint freshness projection that does not conflate receipt, commit, and readiness.

## 12. Future AI integration points (not activated)

The frontend has explicit space for future validated metadata: business meaning, unit/currency, row grain, relationship validity, metric definition, approval status, provenance, confidence limitations, and model interpretation status.

Any future Qwen integration must remain a separately evaluated semantic-proposal task whose outputs are validated by trusted deterministic code and approved contracts. This milestone made no Qwen call, exposed no raw data to a model, changed no prompt, and did not treat the model as production-ready.

## 13. Remaining limitations

- Only the latest immutable version can be selected because historical enumeration is absent.
- Preview filtering/sorting is limited to the server-provided bounded preview.
- Dataset source and synchronization freshness are unavailable in the current read response.
- No validated time trends, distinct count, distributions, or correlations are offered in this first UI despite some internal analysis capabilities.
- Dashboard composition is session-only and explicitly not persisted.
- No semantic, unit, currency, row-grain, or relationship declaration exists yet.
- Active release schema remains 146. Persistent environments without the project-dataset contract receive the safe unavailable state.
- No persistent staging environment was tested. No deployment, migration selection, commit, push, or merge occurred.

## 14. Recommendation

**PASS — LOCALLY IMPLEMENTED AND OFFLINE VERIFIED.**

The acceptance objective is met for the capabilities the current authorized API genuinely exposes: users can enter a project-scoped BI workspace, explore an authorized bounded dataset view, select the authoritative latest immutable version, run compatible exact-version deterministic calculations, inspect trustworthy provenance, view functional charts/tables, and see explicit capability limits. Accessibility, RTL, responsive behavior, Data Sources, Google Sheets, webhook management, authorization, and Data Logs regressions passed locally.

This result is not staging-tested and not production-ready. Owner review is required before any next milestone or release action.

## 15. Proposed C5 Step 2 scope

Do not begin automatically. Recommended next scope, subject to separate authorization:

1. Define and implement an authorized historical dataset-version list and exact-version reopen contract.
2. Add source/checkpoint freshness projection with unambiguous receipt, commit, and ready timestamps.
3. Add server-side bounded preview paging/filter/sort.
4. Add explicit, validated distinct-count and date/time aggregation contracts.
5. Define persistent dashboard/widget ownership, layout, sharing, refresh, and version provenance.
6. Introduce trusted semantic-contract storage for units, currency, grain, metric definitions, and relationship approval—without integrating Qwen until its independent acceptance succeeds.
7. Repeat disposable verification, then plan separately authorized persistent staging validation.
