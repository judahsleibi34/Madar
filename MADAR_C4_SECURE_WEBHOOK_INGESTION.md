# Madar C4 Step 1 — Secure Webhook Ingestion Verification

Date: 2026-10-24
Scope: local/disposable implementation only; no deployment, release selection, persistent migration, real provider registration, or production access was performed.

## Recommendation

**FAIL / NOT READY for persistent staging activation.**

The provider-neutral foundation, schema 162 candidate, management UI, release governance, security controls, and isolated migration/concurrency checks are implemented. The success criterion requires a single synthetic event to traverse real FastAPI ingress, PostgreSQL inbox, Vault, background processing, immutable dataset revision/history, and checkpoint creation, plus a real browser-to-backend flow. That complete integrated disposable topology was not available in this checkout and was not fabricated with mocks. Schema 161 and 162 also remain unselected and unapplied. C4 must therefore remain disabled pending C4 Step 2 verification.

## 1. Architecture and adapter contract

The implementation adds one bounded ingress path and reuses the existing Data Sources ingestion pipeline:

1. An authenticated management request provisions an endpoint and a Vault-backed source credential.
2. An unauthenticated external `POST /data/webhooks/{opaque_endpoint_id}` is resolved server-side. No tenant, project, source, or claimed provider value from the payload establishes authorization.
3. The registered adapter verifies the exact raw request bytes and normalizes the event.
4. PostgreSQL durably accepts/deduplicates the normalized bounded payload before the receiver returns success.
5. A separately invoked bounded worker claims events with a database lease and fence.
6. Authoritative events enter the existing incremental Data Source ingestion, immutable storage, revision/history, and checkpoint paths. Notification-only events mark the resource for reconciliation instead of treating the notification as row data.

`WebhookAdapter` describes approved provider identity, supported resources/events, verification, normalized delivery kind, stable provider event ID, occurrence time, ordering value, and payload. The production registry is intentionally empty and immutable. A synthetic HMAC adapter is available only when both `APP_ENV=test` and `MADAR_TEST_WEBHOOK_ADAPTER_ENABLED=true`; arbitrary imports, scripts, and user-defined verification code are not supported.

The runtime additionally requires `MADAR_WEBHOOK_INGRESS_ENABLED=true`, `APP_ENV` equal to `test` or `development`, and database schema 162 or newer. `production` and `staging` remain hard-disabled even if the environment flag is set.

## 2. Signature and credential lifecycle

The synthetic adapter uses `v1=<hex HMAC-SHA256>` over `timestamp + "." + exact_raw_body`, checked with constant-time comparison. It requires a stable event ID, a timestamp no more than 300 seconds old, `application/json`, a body no larger than 64 KiB, headers totaling no more than 16 KiB, strict JSON without duplicate keys, and bounded nesting/collection/scalar sizes.

Secrets are generated server-side with `secrets.token_urlsafe(48)`, encrypted through the existing Data Source credential/Vault service, and never stored in plaintext in PostgreSQL. The plaintext is returned only by the successful provisioning/rotation response and is omitted from status and ingress responses. Endpoint rows bind credential ID, credential version, source credential revision, and endpoint fence. Rotation and revocation invalidate stale unleased work; already leased work is prevented from committing by credential and endpoint fences.

Management operations preserve the existing authenticated tenant/project/source authorization and rate limits:

- `GET /data/projects/{project_id}/sources/{source_id}/webhook`
- `POST /data/projects/{project_id}/sources/{source_id}/webhook`
- `PUT /data/projects/{project_id}/sources/{source_id}/webhook`
- `POST /data/projects/{project_id}/sources/{source_id}/webhook/revoke`
- `POST /data/projects/{project_id}/sources/{source_id}/webhook/events/{event_id}/retry`

The external receiver is deliberately separate from browser-authenticated routes. Its CSRF exemption is restricted to the exact UUID-shaped ingress route; verification and durable acceptance replace session authentication.

## 3. Durable inbox, deduplication, and replay

Candidate migration 162 adds:

- `data_source_webhook_endpoints`, scoped to tenant/project/source/resource/actor/provider/credential and protected by RLS plus service-role-only RPCs.
- `data_source_webhook_events`, containing the bounded normalized payload, SHA-256 payload hash, receipt/occurrence times, state, attempt/retry metadata, lease owner/token/expiry/fence, ingestion run, result revision, and redacted diagnostics.
- Resource reconciliation request/status fields on `data_source_resources`.

The database uniqueness constraint on `(endpoint_id, provider_event_id)` makes duplicate receipt durable across processes and restarts. Concurrent duplicates resolve to the existing event rather than creating parallel work. Success is returned only after `accept_data_source_webhook_event158` commits. Raw authorization headers and plaintext secrets are not persisted.

The inbox has a 30-day default retention target. Cleanup is explicit, bounded, service-role-only, and excludes active work.

## 4. Ordering and recovery semantics

This is durable at-least-once receipt with idempotent processing; it does not claim exactly-once delivery across the provider boundary.

- Claims use `FOR UPDATE SKIP LOCKED`, expiring leases, random lease tokens, and monotonically increasing lease fences.
- Heartbeats extend only the current fenced lease.
- A worker crash leaves the acknowledged event durable; reconciliation returns expired work to retry or terminal state.
- Each authoritative event reserves ingestion with `webhook:{internal_event_id}` as its idempotency key.
- Existing record `source_order` prevents older deliveries from overwriting newer state.
- The same ordering value with different content is a terminal revision conflict.
- A stale identical event completes as a no-op and does not create a new immutable dataset version.
- Metadata/storage ambiguity uses the existing ingestion recovery callbacks before the event is failed.
- Retry is bounded with database-controlled eligibility/backoff; terminal events require an authorized explicit retry.
- Revocation/rotation prevents stale credentials from completing current work.

Deletion is intentionally unsupported by the synthetic adapter. Missing rows are never interpreted as deletes.

## 5. Event-to-dataset behavior

`record.upsert` is the only synthetic authoritative operation. It requires a stable record ID, positive integer version, object data, and exact source/resource binding. It is converted to the existing provider-neutral `ProviderRecord`, bounded CSV artifact, staged incremental change, immutable storage object, committed dataset revision/history, and checkpoint request.

`resource.changed` contains no row data. It calls `request_webhook_reconciliation158`, coalesces repeated notifications on the source resource, and leaves the approved existing API/synchronization reader responsible for a later bounded re-fetch.

Scheduled synchronization and Google Sheets snapshot behavior are unchanged. No Drive watch scope or callback was added. Data Logs was not modified.

## 6. Candidate migration 162

Files:

- `web/database/migrations/162_add_secure_webhook_ingestion.sql`
- `web/supabase/migrations/162_add_secure_webhook_ingestion.sql`

The files are byte-identical with SHA-256:

`f9f532a12940d0b57e5d64992168822af62fd6f51f452e92d3ddc4cb4ca8bf04`

Release metadata:

- `web/deployment/releases/migrations-161-162-webhooks.json` — SHA-256 `e19fae6ef784d78e8e0e6c1a636db284e97b2796d610f00d4a61229b6b4dea91`
- `web/deployment/releases/schema-161-162-webhooks-bridge.json` — SHA-256 `94841d7a116b05768cbb0eb564eb4f504aecf6b0ac79ace5f274872f6093338e`

The migration starts a transaction, locks the `core` schema-state row, requires exact predecessor 161 before DDL, is additive, enables RLS, revokes public/anon/authenticated access to privileged functions, grants only the service role, advances 161 to 162 only after DDL, performs its post-transition assertion, and commits. Migration 161 and all older migrations were left unchanged.

The checked-in active release remains schema **146**. Candidate 162 was not selected or applied to any persistent database.

## 7. Data Sources UI

`ApiSourceManagementPanel` now renders webhook controls only when the provider catalogue reports an approved webhook capability. It shows endpoint readiness, enabled state, credential state, last receipt, last successful processing, pending/failed counts, reconciliation status, and dataset/checkpoint freshness. Provision/rotate displays the new secret once. Enable/disable and revoke operations carry the expected endpoint fence.

When schema 162 is unavailable or the production registry is empty, the UI reports the capability as unavailable. It does not fabricate a connection or event. Existing spreadsheet, API, and Google Sheets sections are preserved.

## 8. Exact C4 files changed

New files:

- `web/backend/routes/webhook_routes.py`
- `web/backend/scripts/run_webhook_ingestion_worker.py`
- `web/backend/services/webhook_ingestion_service.py`
- `web/backend/services/webhook_registry.py`
- `web/backend/tests/test_webhook_candidate.py`
- `web/backend/tests/test_webhook_registry.py`
- `web/backend/tests/test_webhook_routes.py`
- `web/database/migrations/162_add_secure_webhook_ingestion.sql`
- `web/supabase/migrations/162_add_secure_webhook_ingestion.sql`
- `web/deployment/releases/migrations-161-162-webhooks.json`
- `web/deployment/releases/schema-161-162-webhooks-bridge.json`
- `web/scripts/rehearse_migration_162.sh`
- `web/scripts/webhook_candidate.py`
- `MADAR_C4_SECURE_WEBHOOK_INGESTION.md`

Modified for C4:

- `web/backend/app.py`
- `web/backend/data_analysis/routes/data_routes.py`
- `web/backend/services/project_data_source_service.py`
- `web/backend/services/provider_registry.py`
- `web/backend/services/request_security.py`
- `web/frontend/src/components/PageBuilder/DataAnalysisWorkspace/components/ApiSourceManagementPanel.jsx`
- `web/frontend/src/components/PageBuilder/DataAnalysisWorkspace/components/ApiSourceManagementPanel.test.jsx`
- `web/frontend/src/components/PageBuilder/DataAnalysisWorkspace/constants/uiText.js`
- `web/frontend/src/styles/admin/PageBuilder/data-analysis/07-source.css`
- `web/scripts/check_data_sources_staging_chain.py`
- `web/scripts/check_forward_release.py`
- `web/scripts/check_migrations.py`
- `docs/MADAR_AUTO_DEPLOY_MERGE_CONTRACT.md`
- `docs/automated-database-migration-architecture.md`
- `docs/production-release-policy.md`

The worktree already contained extensive uncommitted C1–C3/Google Sheets work. Those files and changes were preserved. Files such as migration 161, Google Sheets services/tests/docs, automatic synchronization, transport, browser fixtures, e-commerce contrast styling, and README changes are pre-existing work and are not claimed as C4 changes.

## 9. Verification results

### Passed

- Focused backend webhook/validator suite: **17 passed, 0 failed, 0 skipped, 0 errors** in the repository's network-isolated local test container.
- Focused Data Sources component suite: **16 passed, 0 failed, 0 skipped** (includes two webhook UI tests).
- Full frontend suite: **1,763 passed, 1 skipped, 0 failed** across **239 passed test files**.
- Python compilation: all new webhook services, routes, worker, validators, and tests compiled successfully.
- Disposable PostgreSQL migration 162 rehearsal: passed schema 161→162 upgrade, forced transactional rollback, exact predecessor enforcement, two-session migration locking (only one contender advanced), RLS/service-role checks, durable duplicate acceptance, and two-worker single-claim behavior.
- Webhook candidate validator: passed corrected transition, whitespace tolerance, missing lock, wrong predecessor, wrong core contract, unrelated lock, comment spoofing, duplicate transition, mirror mismatch, checksum, and bridge checks.
- Data Sources candidate chain: passed 146→162; active release unchanged at 146; migration 142 remains the documented excluded historical candidate.
- Migration trees: **162 database + 162 Supabase migrations**, mirrors match, **0 errors**, **2 known warnings** for the unchanged historical duplicate content in migrations 013/014.
- Forward-release source contract: passed.
- Secret hygiene: passed.
- Dependency locks: passed.
- Frontend lint: passed.
- Frontend build and theme contract: passed. Build emitted only the existing large-chunk advisory.
- Global mocked contrast audit: **672 route checks**, **24,782 text**, **327 placeholder**, **5,602 control**, and **7,255 icon** checks; **0 failed route checks** across compact/intermediate/wide, light/dark, and LTR/RTL.
- `git diff --check`: passed.
- External network attempts during the focused network-isolated backend run: none.

### Full backend suite

The completed full-suite attempt collected **3,627 tests**: **2,915 passed, 683 skipped, 17 failed, and 12 errors**. One failure was the new mirror-mismatch negative fixture; it was corrected and its focused suite then passed. The remaining observed failures/errors were pre-existing environment or unrelated release-test conditions, including absent Redis configuration, repository mount paths expected by release tests, commercial-entitlement operator configuration, cookie assertions, and existing control-plane/readiness expectations.

A final full-suite rerun was attempted after the fixture correction but was **blocked by the local environment**: the repository runner expects Docker image `madar-current-reconciliation-test`, which was no longer present, and the isolated environment could not pull it. Therefore no adjusted full-suite result is claimed. The current focused C4 result is the authoritative post-fix result.

### Not run / blocked

- Complete real FastAPI → PostgreSQL/PostgREST → Vault → worker → immutable storage → dataset history → checkpoint integration: blocked because the disposable combined topology/harness is not present.
- Real React browser → authenticated backend management → signed ingress E2E: blocked for the same reason. The checkout's development proxy points to production, so ordinary browser E2E was intentionally not run. The contrast browser run used the built app on loopback with all API traffic mocked.
- Schema 146→162 full database chain with PostgREST, Vault, storage, FastAPI, and worker together: not demonstrated; only the schema 161→162 migration-specific disposable rehearsal was completed.
- Persistent staging, real provider, and production checks: intentionally prohibited.

## 10. Security and isolation evidence

- Tenant/project/source/user checks are inherited from `get_project_data_source` for management and encoded into all service-role RPC predicates.
- External ingress resolves scope from an opaque endpoint ID and ignores payload scope claims.
- Both new tables have RLS enabled; direct public, anon, and authenticated table/function privileges are denied.
- Secrets live in the existing Vault-backed credential service; status, diagnostics, and logs carry only identifiers/versions and redacted categories.
- Exact-body signature, freshness, duplicate JSON-key, body/header limit, unknown endpoint/type, unsupported deletion, production-disable, and response-redaction tests passed.
- Database uniqueness and claims provide cross-process deduplication and worker exclusion.
- Credential revision plus endpoint and lease fences prevent stale rotation/revocation work from committing.

These are code-level and migration-level findings. They are not a claim that tenant isolation has been exercised through a deployed schema 162 stack.

## 11. Supported and intentionally unsupported capabilities

Verified offline:

- Provider-neutral adapter registry and normalized authoritative/notification contracts.
- Test-only signed HMAC fixture.
- Durable schema/RPC design, duplicate protection, worker claims, leases, fences, retry/reconciliation state, retention, and UI fallback.
- Existing incremental ingestion integration at unit/service-contract level.

Intentionally unsupported:

- Any production webhook provider (production registry is empty).
- User-authored verification code or arbitrary callback handlers.
- Deletion events.
- Google Drive watch channels or expanded Google scopes.
- Public listener activation, persistent workers, migration selection, or deployment.
- Claims of external exactly-once delivery or globally ordered provider events.

## 12. Remaining limitations and C4 Step 2

1. Build a hermetic disposable integration harness that starts PostgreSQL through schema 162, PostgREST, synthetic Vault Transit, private object storage, FastAPI, ingestion/checkpoint workers, and Vite without any persistent or external endpoint.
2. Execute all 25 requested failure/race cases through that real topology, including worker crashes before/after commit, concurrent delivery, retry, ordering conflict, notification coalescing, authorization, and older-schema fallback.
3. Add browser E2E for authenticated provision/one-time secret/enable/status/retry/revoke against the disposable backend.
4. Confirm immutable revision reconstruction and checkpoint readiness from database/storage artifacts, not service mocks.
5. Resolve the current credential-model limitation before a provider needs outbound API credentials and inbound webhook verification on the same source: a Data Source currently has one active credential reference. Dedicated webhook sources work, but multiple simultaneous credential purposes require reviewed credential slots or a separate endpoint-owned Vault reference.
6. Restore/build the locked backend test image and obtain a clean complete backend regression result.
7. Only after those checks pass, request separate approval to activate migrations 147–162 in a verified staging environment and register a specific production provider.

Until then, keep `MADAR_WEBHOOK_INGRESS_ENABLED` unset, keep the production adapter allowlist empty, do not schedule the worker, and do not select schema 162.
