# Madar C5 Step 3 — Automated Reporting and Refresh

Date: 2026-10-26
Verdict: **C5 Step 3 — PASS, LOCALLY IMPLEMENTED AND OFFLINE VERIFIED**

This verdict is limited to current repository source and isolated disposable local
infrastructure. It is not a staging result, a production-readiness declaration, or
authorization to select or deploy schema 164.

## 1. Executive summary

Madar now has an opt-in, database-backed reporting workflow for persistent Business
Intelligence dashboards. A bounded dispatcher detects due schedules and opted-in
dashboards whose `latest_committed` widgets have newer immutable dataset versions.
Durable report runs capture the dashboard revision, dashboard definition, and exact
per-widget dataset-version vector before calculation. A fenced worker reuses the
existing deterministic analysis executor, records completed or honest
`needs_attention` results, and publishes a bounded private CSV only before atomically
claiming durable completion.

The browser supports automatic-refresh opt-in, daily/weekly/monthly schedules,
enable/disable and edit/remove operations, manual generation, durable history,
retry, authorized CSV download, print-friendly output, and terminal report archival.
English/LTR and Arabic/RTL use the existing BI workspace design system.

The final disposable browser rehearsal covered the complete existing C3/C4/C5 chain,
including API source ingestion, checkpoints, Google Sheets offline behavior, signed
webhooks, historical BI dashboards, recurring reports, browser reload, private export,
and tenant isolation. A reporting-specific run additionally proved the pinned versus
latest-version automatic-refresh behavior after a second committed dataset version.

## 2. Reused dashboard, version, and worker contracts

The implementation does not introduce another metric engine, ingestion pipeline, or
authorization model. It reuses:

- `bi_dashboards` and `bi_dashboard_widgets`, dashboard revisions, optimistic
  concurrency, and `pinned`/`latest_committed` policies from candidate schema 163;
- project-scoped immutable `data_dataset_versions` and their content hashes;
- exact-version resolution and the existing deterministic Python analysis executor;
- source-resource committed revisions, reconciliation status, and dataset checkpoints;
- existing service-role database access, authenticated tenant/project scope checks,
  private artifact storage, and notification-event infrastructure;
- the existing CLI worker pattern and disposable PostgreSQL/PostgREST/Vault/browser
  harness.

Reports remain derived artifacts. They do not create or alter source dataset history.
Data Logs retains its independent Source → Review → Prepare → Charts → Report flow.

## 3. Automatic refresh architecture

Automatic refresh is disabled by default. Enabling it is an authorized, revision-checked
dashboard mutation through `configure_bi_dashboard_refresh160`.

The bounded scheduler pass scans only opted-in dashboards. For each dashboard it:

1. reloads the authorized saved definition;
2. ignores pinned widgets;
3. compares each `latest_committed` binding with the newest committed immutable
   dataset version;
4. creates a content-derived deduplication identity from trigger type, dashboard ID,
   dashboard revision, widget IDs, and changed version IDs;
5. enqueues a `data_refresh` report only when an eligible change exists.

The enqueue RPC resolves and freezes exact versions in the report run. It never mutates
the saved widget binding. The real browser rehearsal confirmed that the pinned widget
used the prior version, the latest widget used the newly checkpointed version, and both
saved widget bindings remained unchanged after the refresh report completed.

No listener, timer, scheduler, or worker starts at FastAPI import time. Operators must
explicitly run the bounded scheduler/worker commands.

## 4. Scheduler and timezone semantics

Schedules are durable database rows with daily, weekly, or monthly cadence; an IANA
timezone; whole-minute local time; enabled state; next due time; last attempt; last
success; failure code; and optimistic revision.

Timezone behavior is deterministic:

- nonexistent local times advance minute-by-minute to the first valid local instant;
- repeated local times select the earlier UTC instant;
- weekly weekdays use Monday `0` through Sunday `6`;
- monthly days are clamped to the final valid day of shorter months;
- schedule calculations produce UTC instants but do not change metric-engine UTC
  bucketing semantics.

The dispatcher uses the database as the source of due work, enqueues the occurrence,
and revision-checks advancement of `next_run_at`. A restart therefore loses neither the
schedule nor the idempotent occurrence identity.

## 5. Report-run state machine

Candidate schema 164 supports:

`queued → running → completed | needs_attention`

and, for execution failures:

`running → retry_pending → running → failed`.

The schema also admits `cancelled` and `skipped` terminal records for compatible future
operations. Claims are atomic and bounded. Running jobs carry lease owner, random lease
token, monotonic fence, expiry, heartbeat timestamp, attempt count, and maximum attempts.
Expired leases recover to `retry_pending` or terminal `failed`.

Completion requires a current token/fence and unexpired lease. A completed run must have
valid bounded artifact metadata. The worker writes and hashes the private CSV first, then
attempts the fenced completion transaction. If completion is stale, it removes the
newly written artifact rather than exposing duplicate output.

## 6. Deduplication and concurrency controls

The database enforces global uniqueness of the SHA-256 deduplication key. Scheduled
identity contains schedule ID, exact due slot, and schedule revision. Data-refresh
identity contains the dashboard revision and changed latest-version identities. Manual
runs receive a unique identity unless the caller supplies an idempotency key. Retry
identity is derived from the prior run ID and attempt state.

Claims use `FOR UPDATE SKIP LOCKED`, a maximum batch of 20, and at most two concurrently
running report jobs per tenant. Schedule count is limited to 20 per project/user scope.
The migration rehearsal proved duplicate enqueue collapse, concurrent claim exclusion,
expired-lease recovery, token rotation, increasing fences, and rejection of stale
completion.

## 7. Captured version vector and provenance

Each run freezes:

- tenant, project, creator, dashboard, dashboard revision, trigger, due slot, and run
  creation/execution timestamps;
- the complete saved widget definition and validated analysis specification;
- one immutable dataset version per resolvable widget, including dataset ID, version ID,
  version number/kind, content hash, committed timestamp, and version policy;
- per-widget execution status, deterministic operation, result, and exact provenance;
- per-dataset freshness/checkpoint notes;
- result snapshot, warnings, and CSV artifact identity/hash.

This version vector supports dashboards spanning independent datasets without claiming
transactional synchronization or inferred relationships. A report continues using its
captured definition and versions even if the dashboard or sources change later.

## 8. Checkpoint and freshness behavior

The worker reuses the C5 Step 2 freshness projection and keeps committed revision,
checkpoint revision/status, pending reconciliation, and readiness distinct. A schedule
may require ready checkpoints. In that mode a stale or pending checkpoint raises the
retryable `report_checkpoint_not_ready` state rather than computing from a falsely
declared current source.

When checkpoint readiness is not required, the report records the actual available
freshness evidence and still remains bound to a committed immutable version. Missing
versions, revoked/unavailable datasets, invalid specifications, or incompatible fields
produce explicit widget warnings and `needs_attention`; they are not replaced with
zeroes or stale guessed fields.

## 9. Supported output and export formats

The supported downloadable artifact is UTF-8 CSV containing widget, status, dataset and
version IDs, content hash, deterministic operation, label, and value. Cells beginning
with spreadsheet formula characters are prefixed safely. CSV content is capped at 500
rows and 1 MiB.

The workspace also renders an accessible print layout suitable for browser printing or
“Save as PDF.” There is no server-side PDF renderer and no external rendering service.
Reports are explicitly generic analytical reports; no audited-financial-statement claim
or inferred revenue/profit/currency/unit meaning is added.

## 10. Private artifact storage and authorization

CSV files live below the configured private generated-artifact root in a deterministic
tenant/run/content-hash path. The database stores only bounded private metadata; the UI
never receives the storage key. Retrieval requires the existing authenticated user,
tenant, project, creator, and report scope. The service resolves the path beneath the
private root, verifies file existence, byte size, and SHA-256 before returning a private,
`no-store`, `nosniff` download.

Terminal reports may be archived. Archival is scope-checked, excludes active work, hides
the run from ordinary history/detail/download access, and does not delete source dataset
history. Physical artifact retention remains conservative rather than deleting files
during an interactive request.

## 11. Reporting frontend

The Business Intelligence workspace now has a Reports tab with:

- honest schema-unavailable and empty states;
- dashboard automatic-refresh opt-in;
- daily/weekly/monthly schedule creation;
- dashboard selection, timezone, local time, weekday/month day, and enabled state;
- schedule edit, enable/disable, next-run display, and confirmed removal;
- manual generation;
- persistent report history with trigger, state, dashboard revision, and version summary;
- report open, retry, authorized CSV download, browser print, and confirmed archive;
- exact version vector, per-widget results, warnings, freshness disclosure, and unknown
  semantic/unit/currency disclosure.

The interface supports English/LTR, Arabic/RTL, keyboard-focusable controls, responsive
mobile layout, and existing Madar tokens/styles.

## 12. Notification behavior

After fenced durable completion, the worker attempts one existing tenant notification
event for ready or needs-attention state using the report ID as the durable source
identity. Notification failure cannot roll back or falsify report completion. No browser
push prompt, email, Slack, WhatsApp, Google, or other external delivery was added or
claimed.

## 13. Candidate migration 164

Migration 164 is additive and transactional from an exactly locked predecessor schema
163. It adds `bi_dashboards.auto_refresh_enabled`, `bi_report_schedules`, and
`bi_report_runs`; composite ownership constraints; RLS; revoked public/authenticated
table and RPC access; service-role-only command RPCs; bounded JSON/artifact checks;
deduplication; leases/fences; retries; schedule revisions; and archival.

The database and Supabase SQL mirrors are byte-identical. The manifest checksum,
compatibility bridge, candidate validator, staging-chain validator, migration validator,
forward-release validator, and release-policy documentation include 164. Concurrent
migration attempts serialize on `application_schema_state`; the wrong predecessor fails
before DDL, and a forced transaction error rolls back to 163.

The checked-in active release remains **schema 146**. Schemas 161–164 remain unselected,
undeployed candidates.

## 14. Security and tenant-isolation proof

The browser/API tests proved anonymous requests return 401, mismatched user paths return
403, and cross-tenant/cross-project report access returns 404. SQL rehearsal rejected a
cross-tenant enqueue and confirmed authenticated/anonymous roles cannot read report
tables or execute worker RPCs. Service methods reassert tenant, project, creator, and
resource identity; predictable UUID access does not bypass those predicates.

The full no-network backend suite passed authorization, private-storage, request-safety,
source, webhook, and dashboard regressions. CSV formula injection has a dedicated unit
test. Artifact paths are never returned in list/detail payloads. Worker error responses
contain safe codes/types; bounded diagnostic text is test-only. No credential or raw
source row is copied into report metadata or logs.

## 15. Recovery and failure-injection proof

Verified directly:

- forced migration rollback and concurrent migration lock;
- duplicate scheduled run collapse;
- two-worker claim exclusion;
- lease expiry, retry recovery, new token/fence, and stale-completion rejection;
- valid artifact durability before completion;
- stale completion artifact removal in the worker contract;
- bounded retry/backoff and terminal attempt limits;
- missing/stale required checkpoint deferral;
- empty/no-valid-widget and schema/access `needs_attention` paths in implementation;
- formula-injection neutralization, artifact bounds, path and digest checks;
- deleted source dashboard retry refusal;
- notification failure isolation;
- existing C3/C4 worker crash, recovery, checkpoint, webhook, and credential-revocation
  regressions in the complete browser/backend chain.

The reporting worker is a bounded one-shot process. It does not silently mark work
complete after storage or database failure, and restarting it reclaims only durable
queued/retry/expired work.

## 16. Full disposable browser E2E evidence

The final clean harness used fresh tmpfs PostgreSQL 17, PostgREST, local Vault, local
FastAPI, real ingestion/checkpoint/report workers, private temporary artifact storage,
Vite, Playwright, synthetic users/projects, and no external provider.

The full chain passed six independent real-browser specifications:

1. schema-141 honest Data Sources fallback;
2. authorized API-source onboarding, three revisions, immutable checkpoints, freshness,
   revocation, and tenant isolation;
3. Google Sheets offline OAuth/mapping/sync/deletion/revocation behavior;
4. signed webhook → durable inbox/history → worker → checkpoint → browser and recovery;
5. historical exact-version analytics and dashboard persistence across reload;
6. manual and scheduled reports through the real report worker, persistent history,
   exact version display, private CSV download, and report authorization.

The final reporting-only scenario additionally created two immutable versions and a
dashboard with pinned and latest widgets, enabled auto refresh, committed/checkpointed
new source data, dispatched one `data_refresh` run, executed it through the real worker,
proved old/new version selection by policy, proved saved bindings unchanged, and then
completed manual and scheduled reports. Artifact directories were under `/tmp` and the
harness removed its containers/network/database on exit.

## 17. Test and audit results

- Focused backend reporting/dashboard/candidate: **12 passed, 0 skipped, 0 failed, 0
  errors**.
- Focused BI frontend component: **10 passed, 0 skipped, 0 failed**.
- Supported locked no-network backend suite: **3,758 run; 3,075 passed; 683 intentionally
  skipped; 0 failed; 0 errors; 0 external attempts; 0 external sites**.
- Full frontend suite: **240 files passed; 1,781 tests passed; 1 intentionally skipped;
  0 failed**.
- Final complete disposable browser chain: **6/6 specifications passed**.
- Strengthened reporting-only disposable browser run: **1/1 passed**.
- Schema 163→164 rehearsal: **PASS** for rollback, lock, RLS/privileges, version vector,
  dedupe, concurrent claim, recovery, stale fencing, bounded artifact, scoped archive,
  and cross-tenant rejection.
- Contrast audit: **684 route checks, 25,866 text checks, 324 placeholder checks, 5,990
  control checks, 8,356 icon checks, 0 failed routes** across compact/intermediate/wide,
  light/dark, LTR/RTL, and admin/public/user surfaces.
- Frontend ESLint: **PASS**.
- Frontend production build and API-origin/theme/bundle/tenant-bundle audits: **PASS**.
- Migration trees: **164/164 mirrored, 0 errors**; only the documented historical 013/014
  duplicate-content warnings remain.
- Candidate staging chain: **146→164 PASS; active schema 146 unchanged**.
- Forward-release, migration-transition, dependency-lock, tracked-secret hygiene,
  installed Python dependency, and `git diff --check` gates: **PASS**.

Two preliminary backend invocations are not counted as product results: a simplified
mount/environment run produced known harness failures, and the first supported run found
two CI-path errors in the new candidate test. The path fixture was corrected and the
entire supported suite then passed. Likewise, two preliminary contrast invocations
failed before auditing because Chrome was sandbox-blocked and then because no Vite server
was running; the final exhaustive loopback audit above passed.

## 18. Exact files changed for C5 Step 3

Reporting implementation and routes:

- `web/backend/services/bi_reporting_service.py`
- `web/backend/services/bi_dashboard_service.py`
- `web/backend/data_analysis/routes/data_routes.py`
- `web/backend/scripts/run_bi_report_scheduler.py`
- `web/backend/scripts/run_bi_report_worker.py`

Database/release contract:

- `web/database/migrations/164_add_automated_reporting.sql`
- `web/supabase/migrations/164_add_automated_reporting.sql`
- `web/deployment/releases/migrations-163-164-automated-reporting.json`
- `web/deployment/releases/schema-163-164-automated-reporting-bridge.json`
- `web/scripts/automated_reporting_candidate.py`
- `web/scripts/check_data_sources_staging_chain.py`
- `web/scripts/check_migrations.py`
- `web/scripts/check_forward_release.py`
- `web/scripts/rehearse_migration_164.sh`
- `docs/MADAR_AUTO_DEPLOY_MERGE_CONTRACT.md`
- `docs/production-release-policy.md`
- `docs/automated-database-migration-architecture.md`

Frontend and browser verification:

- `web/frontend/src/components/BusinessIntelligence/BusinessIntelligenceWorkspace.jsx`
- `web/frontend/src/components/BusinessIntelligence/BusinessIntelligenceWorkspace.test.jsx`
- `web/frontend/src/styles/admin/business-intelligence.css`
- `web/frontend/e2e/business-reporting-live.spec.mjs`
- `web/backend/tests/data_sources_browser_e2e_fixture.py`
- `web/scripts/rehearse_data_sources_browser_e2e.sh`

Backend verification:

- `web/backend/tests/test_bi_reporting_service.py`
- `web/backend/tests/test_automated_reporting_candidate.py`

This report is `MADAR_C5_AUTOMATED_REPORTING_AND_REFRESH.md`. Shared route, BI, fixture,
harness, validator, and policy files also contain earlier accepted C3/C4/C5 work in the
current dirty worktree; those user-owned changes were preserved.

## 19. Remaining limitations

- This is offline local evidence only. No persistent staging environment or real
  production release was exercised.
- Schema 164 must exist before reporting is available; schema 163 and older receive an
  honest capability-unavailable response.
- Scheduler and worker activation remains an explicit operator task. No persistent
  service/timer deployment was added.
- CSV and browser print are supported. Native server PDF, email, chat, and other external
  delivery are not implemented.
- Business semantics, units, currencies, accounting periods, cross-dataset relationships,
  and financial classifications remain unknown until separately trusted contracts exist.
- The 120-second execution budget is cooperatively checked between widgets. Parsing and
  analysis continue to rely on the existing bounded analysis/runtime isolation; this
  milestone does not add a stronger per-widget OS CPU/memory sandbox.
- Report archival is durable and authorized, but automated physical artifact retention
  cleanup is not activated. This avoids deleting private evidence without a separately
  approved retention policy.
- Some destructive race/failure cases are proven at service/RPC/worker-contract level
  rather than each receiving a separate browser journey; the mandatory end-to-end stages
  themselves use the real local processes and durable services.

## 20. Operational no-deployment confirmation

The C5 Step 3 migration and browser verification used only disposable tmpfs databases;
it did not apply candidate migrations or reporting writes to production. Separately, the
owner's ordinary local API is intentionally connected to the production schema-146
Supabase services through an SSH tunnel. Read-only production health/schema checks are
part of that local connectivity workflow and must not be described as a local database.
No production data was modified, no staging or production deployment occurred, and no
active release selection changed. No persistent reporting scheduler, worker, system
service, or timer was enabled. No commit, push, merge, or PR was created. No real Google
provider operation or external delivery was enabled. Qwen was not accessed, modified,
invoked, restarted, or integrated.

The loopback-only Vite policy remains intact. A temporary loopback Vite process used by
the contrast audit was stopped after the audit. All disposable browser and migration
containers/networks/databases were removed by their harness cleanup traps.

## 21. Recommended next milestone

Stop here for owner review. The next separately authorized work should be a technical
dataset-profiling and trusted semantic-contract milestone before financial/operational KPI
claims. Production activation of schema 161–164, persistent scheduler deployment, real
provider verification, and Qwen integration each require their own later authorization
and evidence gates.
