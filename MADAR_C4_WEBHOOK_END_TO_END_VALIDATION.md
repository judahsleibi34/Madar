# Madar C4 Step 2 — Webhook End-to-End Validation

Date: 2026-10-24
Scope: local, disposable verification only
Repository revision inspected: `cf444303e55a2c6a214ab53f683442cf2fac15fe` with pre-existing uncommitted C1–C4 and Google Sheets work preserved

## 1. Executive summary and verdict

**Final verdict: FAIL / BLOCKED — the webhook E2E workflow is offline-functional, but the mandatory repository-wide contrast gate is not green.**

The complete webhook path succeeded with real local application components:

`signed HTTP request → FastAPI → Vault secret resolution → PostgreSQL/PostgREST durable inbox → database deduplication → real bounded worker process → existing incremental ingestion → immutable private history → dataset revision → checkpoint worker → React browser state`

The disposable browser run also proved worker crash recovery, retry, stale-lease fencing, concurrent duplicate delivery, two-worker exclusion, ordering, credential rotation while leased, revocation while leased, terminal dead-lettering, historical reconstruction, checkpoint readiness, and tenant/project authorization.

All C4-focused tests, the exact locked backend suite, the full frontend suite, migration checks, lint, build, dependency checks, syntax checks, and `git diff --check` passed. The complete Data Sources browser regression—including older-schema fallback, API synchronization, Google Sheets, and webhook—passed.

The repository-wide contrast audit completed 672 route checks but failed 444 route checks. Every one of its 888 findings is one of two unrelated notification-permission controls at contrast ratio 1.42 where 3.0 is required. The `/data-sources` route had zero failed combinations. These controls were pre-existing/user-owned and outside the authorized narrow C4 correction, so they were not changed. The task's acceptance criteria require the accessibility/contrast gate to pass; therefore this report does not declare `C4 PASS — OFFLINE VERIFIED`.

No staging or production readiness is claimed.

## 2. Safety preflight and isolation

- The worktree was dirty before this task. Existing changes were preserved; no reset, checkout, deletion, commit, push, merge, or PR operation was performed.
- The checked-in active release remains `web/deployment/releases/release.json`, target schema **146**.
- Migrations 161 and 162 remain unselected candidate migrations. Neither was applied to persistent infrastructure.
- The repository production `.env` target was identified and was not used.
- The harness generated unique container/network names, random local secrets, loopback-only ports, a temporary directory, and a PostgreSQL `tmpfs` data directory.
- `APP_ENV=test` was used. Webhook and synthetic-provider gates were enabled only in the disposable test processes.
- PostgreSQL, PostgREST, Vault, FastAPI, the fixture services, Vite, and browser automation were local. No real Google or webhook provider endpoint was contacted.
- The locked backend suite ran with its outbound-network guard and reported `EXTERNAL_ATTEMPTS []` and `EXTERNAL_SITES []`.
- Teardown was verified after the runs. No C4 containers remained; only the pre-existing `madar-dev-backend` and `madar-dev-redis` containers were present.
- Qwen was not accessed or modified.

The mandatory release documents were reviewed before making release-sensitive frontend/harness changes:

- `docs/MADAR_AUTO_DEPLOY_MERGE_CONTRACT.md`
- `docs/production-release-policy.md`
- `docs/automated-database-migration-architecture.md`
- `docs/control-plane-upgrade-architecture.md`

No deployment gate, migration orchestration, compatibility metadata, release selector, or production runtime behavior was changed, so no policy-document update was required.

## 3. Disposable architecture

| Component | What ran | Classification |
| --- | --- | --- |
| PostgreSQL | Pinned local PostgreSQL 17 container with database storage on `tmpfs` | Real disposable database |
| PostgREST | Pinned local PostgREST container against the disposable database | Real service |
| Vault | Pinned local Vault dev container, loopback-only, disposable token and Transit key | Real disposable Vault |
| FastAPI | Repository backend image with Uvicorn and schema compatibility changed only inside the disposable DB | Real application |
| Webhook worker | `run_webhook_ingestion_worker.py` invoked as bounded child processes | Real worker process |
| Sync worker | `run_automatic_source_sync.py` invoked as a bounded child process | Real worker process |
| Checkpoint worker | `run_dataset_checkpoint_worker.py` invoked as bounded child processes | Real worker process |
| Immutable storage | Private loopback HTTP object-store fixture holding synthetic objects in process memory | Allowed disposable storage fixture |
| External webhook producer | Playwright HTTP client generating synthetic HMAC requests | Synthetic external producer |
| External API/Google | Loopback HTTP provider fixture | Synthetic external provider only |
| Frontend | Local Vite process | Real React application |
| Browser | Playwright-controlled Chromium | Real browser automation |
| Identity/data | Seeded synthetic tenant, projects, users, JWT, records, and credentials | Synthetic test data |

Core FastAPI, PostgreSQL/PostgREST, Vault, ingestion, history, and checkpoint behavior was not mocked in the passing C4 E2E run.

## 4. Corrections made during integration

1. Added the real webhook browser workflow and disposable worker controls. The previous harness stopped at C3/Google and could not drive schema 162, webhook workers, recovery, or evidence collection.
2. Sent Playwright request bodies as `Buffer` values. Passing strings allowed Playwright serialization to change the bytes, which correctly caused raw-byte HMAC verification to reject the request.
3. Changed the read-only evidence helper to use `GET`; it had initially issued `POST` and received 404.
4. Added the missing browser webhook revoke action, expected-fence submission, one-time-secret clearing, English/Arabic text, and component coverage.
5. Added a test-only crash worker boundary: a real child process claims one event and exits without processing it. The harness then uses the real lease reconciliation RPC and real worker for recovery.
6. Moved existing automatic-sync and checkpoint execution out of `ThreadingHTTPServer` request threads and into the repository's real child worker scripts. The combined harness twice reproduced a native Pandas/Arrow segmentation fault in `pandas.core.arrays.string_arrow._from_sequence`; the process boundary eliminated the crash and better matches runtime execution.
7. Made schema-162-only evidence columns conditional. The combined older-schema/C3 phase correctly lacks the reconciliation columns added by migration 162.
8. Added a focused `MADAR_E2E_WEBHOOK_ONLY=YES` harness mode for bounded iteration. The default still runs the complete older-schema, API, Google Sheets, and webhook sequence.

No security assertion was weakened, no production provider was registered, and no second ingestion pipeline was introduced.

## 5. Migration validation

The disposable migration-162 rehearsal passed:

- exact 161 predecessor requirement;
- transactional forced-rollback probe (the displayed `division by zero` is intentional evidence that DDL/state rolled back);
- migration locking and concurrency;
- table/RPC constraints and RLS;
- service-role-only privileged behavior;
- durable unique event identity and duplicate disposition;
- two-worker single-claim behavior.

Mirror hashes:

- migration 162 database and Supabase copies: `f9f532a12940d0b57e5d64992168822af62fd6f51f452e92d3ddc4cb4ca8bf04`
- migration 161 database and Supabase copies: `04308e96e6659f194f564cba1dddfa99643ea78a3fde63f913af5969050e7031`

The candidate-chain validator reported active schema 146 unchanged, target 162, and transitions 146→147 through 161→162. Migration-tree validation reported 162 database migrations, 162 Supabase migrations, zero errors, and the two known warnings for identical historical migrations 013/014. Forward-release, dependency-lock, transition, secret-hygiene, mirror, and checksum checks passed.

## 6. FastAPI ingress and signature evidence

The browser test sent requests to the actual FastAPI ingress using HMAC-SHA256 over `timestamp + "." + exact raw body bytes`.

Verified outcomes:

- valid signed event: HTTP 202 only after durable database acceptance;
- duplicate event ID with identical content: HTTP 200 with `disposition=duplicate`;
- invalid secret/signature: HTTP 401;
- signed body followed by body tampering: HTTP 401;
- timestamp older than the allowed window: HTTP 401;
- unknown opaque endpoint UUID: HTTP 404;
- disabled endpoint: HTTP 404;
- old secret after rotation: HTTP 401;
- revoked endpoint/credential: HTTP 404;
- wrong resource identity: HTTP 422;
- malformed JSON: HTTP 422;
- malformed authoritative record: HTTP 422;
- oversized payload: HTTP 413;
- unsupported deletion: HTTP 422;
- notification-only event: HTTP 202 and durable scheduling, not row mutation.

External payload fields never selected tenant/project/source authority; scope came from the opaque endpoint row. The synthetic adapter deliberately supports upsert and notification events only, so there is no supported authoritative deletion case to execute. Unsupported deletion was explicitly verified fail-closed.

## 7. Durable inbox, workers, retry, lease, and crash recovery

The accepted event was observable in `data_source_webhook_events` before processing. Database uniqueness on `(endpoint_id, provider_event_id)` reduced six concurrent deliveries of one provider event to one durable event and one logical mutation.

Recovery proof:

1. A signed event for record C was durably accepted.
2. A real child process called the claim RPC, obtained lease fence 1, and exited without commit.
3. The database still held the acknowledged event as `leased`.
4. The harness advanced only that disposable lease expiry.
5. The real reconciliation RPC moved it to `retry` with `attempts=1` and `error_category=worker_lease_expired`.
6. A later real worker claimed it and committed revision 4 with `attempts=2`.
7. Completion using the original token/fence returned false; the stale worker could not overwrite state.

Two bounded workers were also invoked concurrently for three queued events. Their combined claim count was exactly three, with no duplicate logical processing.

Rotation/revocation fencing proof:

- An event was claimed and left leased, then the UI rotated the secret/fence. Stale completion returned false; expiry reconciliation moved the event to `dead_letter` with `webhook_endpoint_fenced`. The old secret failed and the new secret worked only after explicit enablement.
- Another event was claimed and left leased, then the UI revoked the endpoint. Stale completion again returned false; expiry reconciliation terminally dead-lettered it. No record or dataset revision was created.

Previously committed records and checkpoints remained intact throughout failed/fenced processing. No checkpoint was marked ready for either dead-letter event.

## 8. Authoritative event-to-dataset proof

The synthetic authoritative sequence produced this deterministic state:

- A version 1 → dataset revision 1, amount 10.
- A version 2 → later revision, amount 25.
- A version 0 replay after version 2 → processed as a true no-op; A remained at `source_order=2` and amount 25.
- Six concurrent deliveries for B version 1 → one event and one revision, amount 40.
- Crash-recovered C → revision 4, amount 60.
- Rotation-fenced D event → dead letter and no revision.
- New-secret D version 2 → revision 5, amount 80.
- Revocation-fenced E event → dead letter; E absent from current records.

Final state had five immutable dataset versions, committed revision 5, stable source record IDs A/B/C/D, and no E. Older source order never overwrote newer state. Receipt time was not used as record ordering authority.

## 9. Notification-only reconciliation

Two signed `resource.changed` notifications were durably accepted and processed as `reconciliation_scheduled`. They coalesced through the resource's single `reconciliation_requested_at`/`reconciliation_reason=webhook_notification` state and did not change the dataset revision or current records.

The synthetic webhook provider intentionally has no approved outbound reader. Therefore this run honestly demonstrates durable pending reconciliation, not a fabricated provider refetch. Existing automatic synchronization and Google Sheets readers were separately exercised by the same complete browser harness, including stable datasets, no-op behavior, conservative deletion, and provider revocation. No Google Drive notification scope or behavior was added.

## 10. Immutable history and checkpoints

- Every successful authoritative mutation wrote through the existing shared immutable storage path.
- Explicit reconstruction of revision 1 returned one record/one change.
- Explicit reconstruction of revision 3 returned two records, read immutable bytes, and had a different deterministic state hash from revision 1.
- Checkpoint workers materialized ready checkpoints through the existing reconstruction code.
- The UI displayed `Ready for the latest revision` after checkpoint completion and showed accurate freshness/last-received/last-processed state.
- No-op/older events created no unnecessary dataset version.
- Dead-lettered rotation/revocation events created neither versions nor checkpoints.

## 11. React browser and tenant-isolation evidence

An authenticated browser user:

1. selected the synthetic data project;
2. opened Data Sources;
3. created an approved provider-neutral webhook source;
4. provisioned a one-time Vault-backed secret;
5. enabled/disabled the endpoint;
6. triggered signed deliveries;
7. observed receipt, retry, processing, freshness, revision, and checkpoint states;
8. rotated the secret;
9. revoked the endpoint;
10. observed accurate enabled/revoked states.

The test also verified HTTP 403 for a different user in the same project path and HTTP 404 for the source under another project. The older physical schema 141 browser test showed the safe unavailable capability state.

Synthetic screenshots from the passing final run are in `/tmp/madar-c4-full-browser-final`, including:

- `webhook-01-enabled.png`
- `webhook-02-processed.png`
- `webhook-03-retry-visible.png`
- `webhook-04-revoked.png`

These `/tmp` artifacts are disposable and are not repository deliverables.

## 12. Secret hygiene and authorization

- Plaintext webhook secrets were returned only by provision/rotation responses and displayed only as one-time UI values.
- Revocation clears the one-time UI value.
- PostgreSQL endpoint/event evidence contains only credential identity/version/fence metadata, hashes, normalized bounded payload, and redacted error categories—not plaintext secrets or authorization headers.
- Vault Transit was used by the real credential service.
- Invalid signatures could not enqueue work.
- Endpoint, credential, source, lease-token, and lease-fence checks prevented stale commits.
- RLS and privileged-RPC checks passed in migration rehearsal.
- Event/dataset/checkpoint identities remained bound to the synthetic tenant and project.
- Tracked secret hygiene passed, and the locked backend runner observed no external network attempts.

## 13. Exact commands and results

### Passing commands

```text
env MADAR_E2E_WEBHOOK_ONLY=YES MADAR_E2E_ARTIFACT_DIR=/tmp/madar-c4-webhook-recovery bash web/scripts/rehearse_data_sources_browser_e2e.sh
  1 webhook browser test passed (1.6m)

env MADAR_E2E_ARTIFACT_DIR=/tmp/madar-c4-full-browser-final bash web/scripts/rehearse_data_sources_browser_e2e.sh
  older-schema browser: 1 passed
  API sync browser: 1 passed
  Google Sheets browser: 1 passed
  webhook browser: 1 passed

bash web/scripts/rehearse_migration_162.sh
  passed disposable 161→162 rollback, lock, isolation, deduplication, and worker-claim concurrency

docker run ... madar-backend-test python scripts/run_tests_no_external_network.py
  3,715 tests run; 3,032 passed; 683 skipped; 0 failed; 0 errors
  EXTERNAL_ATTEMPTS []; EXTERNAL_SITES []

docker run --rm --network none ... python -m unittest tests.test_webhook_candidate tests.test_webhook_registry tests.test_webhook_routes
  17 passed; 0 failed; 0 skipped; 0 errors

npx vitest run --environment jsdom src/components/PageBuilder/DataAnalysisWorkspace/components/ApiSourceManagementPanel.test.jsx
  16 passed; 0 failed; 0 skipped

npm test -- --run src/components/PageBuilder/DataAnalysisWorkspace/components/ApiSourceManagementPanel.test.jsx
  script's existing `src` argument selected the full suite:
  239 files passed; 1,763 tests passed; 1 skipped; 0 failed

python3 web/scripts/webhook_candidate.py --help
python3 web/scripts/check_data_sources_staging_chain.py --help
python3 web/scripts/check_migrations.py --help
python3 web/scripts/check_forward_release.py --help
python3 web/scripts/check_dependency_locks.py --help
python3 web/scripts/check_secret_hygiene.py --help
  these repository scripts execute validation directly; aggregate exit 0
  active schema 146 unchanged; candidate chain to 162 valid
  162+162 migration mirrors; 0 errors; 2 known historical warnings

docker run --rm --network none madar-backend-test python -m pip check
  No broken requirements found

npm run lint
  passed

npm run build
  passed; existing >500 kB chunk advisory only

python3 -m py_compile [C4 fixture/routes/services/worker/tests]
node --check web/frontend/e2e/data-sources-webhook-live.spec.mjs
bash -n web/scripts/rehearse_data_sources_browser_e2e.sh
git diff --check
  all passed
```

For the locked backend line, `...` above abbreviates only the mount list for readability. The executed command was the complete `Run backend tests` `docker run` block in `.github/workflows/backend-check.yml`, with each `$PWD` resolved to `/home/judah/Madar Projects/Madar`; no environment entry or mount was omitted. It included `APP_ENV=test`, loopback placeholder Supabase values, isolated `/tmp/madar-ci` storage, `PYGWALKER_TELEMETRY_ENABLED=false`, `MADAR_TEST_REPOSITORY_ROOT=/test-repository`, a 1 GiB `/tmp` tmpfs, all workflow-specified read-only repository mounts, `--network none`, and `python scripts/run_tests_no_external_network.py`.

The full browser harness required two diagnostic attempts before its final pass. The first reproduced the Pandas/Arrow native crash; the second exposed an older-schema query for schema-162-only evidence columns. Both causes were fixed in the disposable harness as documented above.

An earlier non-authoritative backend diagnostic used:

```text
docker run --rm --network none -e MPLCONFIGDIR=/tmp/matplotlib \
  -v '/home/judah/Madar Projects/Madar:/workspace/Madar:ro' \
  -w /workspace/Madar/web/backend madar-backend-test \
  python -m unittest discover -s tests
```

It ran 3,627 tests with 2,917 passed, 683 skipped, 15 failures, and 12 errors. Those failures came from running outside the repository's required locked environment: missing CI fixture mounts/`REDIS_URL` and inherited commercial configuration. The exact checked-in hermetic command above subsequently ran 3,715 tests cleanly and is the authoritative result.

### Non-passing mandatory command

```text
npm run contrast:audit
  routeChecks: 672
  textChecks: 29,996
  placeholderChecks: 324
  controlChecks: 8,232
  iconChecks: 11,199
  failedRouteChecks: 444
```

The report `/tmp/madar-contrast-audit/report.json` contains 888 findings total:

- 444 occurrences: `button.notification-permission-secondary`, ratio 1.42, required 3.0;
- 444 occurrences: `button.notification-permission-close` (English/Arabic labels), ratio 1.42, required 3.0.

There were no `/data-sources` failures and no other unique failed selectors. The first audit invocation was sandbox-blocked; the reported result above is from the completed approved headless-Chrome run against a temporary loopback Vite server.

## 14. Files changed for C4 Step 2

- `web/frontend/e2e/data-sources-webhook-live.spec.mjs` — new real signed-webhook browser E2E, recovery, ordering, rotation, revocation, reconstruction, and tenant isolation coverage.
- `web/backend/tests/data_sources_browser_e2e_fixture.py` — schema-162 evidence, bounded real worker processes, crash/recovery controls, historical reconstruction, and schema-aware evidence.
- `web/scripts/rehearse_data_sources_browser_e2e.sh` — candidate-162 disposable phase, webhook-only iteration mode, and test-only webhook gates.
- `web/frontend/src/components/PageBuilder/DataAnalysisWorkspace/components/ApiSourceManagementPanel.jsx` — missing fenced webhook revoke action and one-time-secret clearing.
- `web/frontend/src/components/PageBuilder/DataAnalysisWorkspace/components/ApiSourceManagementPanel.test.jsx` — revoke request/fence/UI coverage.
- `web/frontend/src/components/PageBuilder/DataAnalysisWorkspace/constants/uiText.js` — English/Arabic revoke status and error text.
- `MADAR_C4_WEBHOOK_END_TO_END_VALIDATION.md` — this evidence report.

The worktree contains extensive pre-existing changes and untracked C1–C4/Google/Qwen files. They were preserved and are not claimed as Step 2 changes. No Qwen file was edited.

## 15. Remaining blockers, risks, and recommendation

### Blocking acceptance item

Obtain owner authorization to correct the pre-existing notification-permission control contrast, then rerun `npm run contrast:audit`. If it returns zero failed route checks and the narrow correction does not regress the already-green suites, the collected evidence supports changing the verdict to **C4 PASS — OFFLINE VERIFIED**.

### Non-blocking limitations

- Only the test-only HMAC adapter is registered. No production webhook provider exists or was tested.
- The synthetic webhook provider has no outbound reader, so notification events remain honestly scheduled/pending; no fake reconciliation success is claimed.
- Deletion is unsupported by this adapter; the rejection path is verified, but no supported deletion semantics are claimed.
- Local Vault ran in disposable dev mode. This is not staging Vault evidence.
- Browser screenshots and object-store contents are disposable `/tmp` artifacts.
- Real staging authorization, public callback routing, provider verification, persistent migration, and production deployment remain untested and unauthorized.

## 16. Environment-change statement

No staging or production system was contacted or changed. No persistent database migration was applied. No release selection changed. No public webhook endpoint or persistent worker was enabled. No customer data was used. No commit, push, merge, deployment, or server activation occurred.

**Recommendation:** keep C4 classified as **FAIL / BLOCKED pending the single repository-wide contrast correction and clean rerun**. The webhook infrastructure itself is implemented and passes the complete offline functional/security E2E path. Do not begin staging activation from this report.

## Final-status addendum — C4 Step 2A (2026-10-24)

The FAIL / BLOCKED verdict above is preserved as the historical Step 2 result. The authorized Step 2A correction subsequently replaced the two notification-permission controls' 1.42:1 decorative borders with the existing semantic control-border token, restored an opaque semantic focus indicator, and made the offline contrast fixture render the prompt deterministically.

Fresh verification passed: 672/672 contrast route checks with zero failures and the prompt visibly present in all 444 expected authenticated checks; 1,765 frontend tests passed with 1 skipped; lint and build passed; notification/PWA interaction tests passed 39/39; focused webhook UI tests remained 16/16; and the complete disposable Data Sources browser suite passed 4/4, including the signed-webhook workflow. No backend/webhook behavior changed, so the earlier 3,715-test hermetic backend and 17-test focused webhook backend evidence remains applicable.

The complete final evidence and limitations are recorded in `MADAR_C4_FINAL_ACCESSIBILITY_GATE.md`.

**Superseding current status: C4 — PASS, OFFLINE VERIFIED.** This is not staging-tested, production-ready, deployed, or real-provider verified.
