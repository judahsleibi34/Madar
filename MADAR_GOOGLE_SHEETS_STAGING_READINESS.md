# Madar Google Sheets staging readiness

Status: **READY for a separately authorized, controlled staging activation after
the prerequisites below are satisfied. NOT READY for production activation.**

This document is preparation and verification evidence. It does not select a
release, apply a migration, enable a worker, configure Google Cloud, authorize a
Google account, or permit production changes.

## 1. Actual selected release and the schema-136 discrepancy

The authoritative checked-in descriptor is
`web/deployment/releases/release.json`. It selects target schema **146**, with
compatibility 144..146, rollback compatibility at 144, deployment profile
`completed-normal-commercial144-146`, and manifest
`migrations-145-146-commercial.json`.

Git history shows that commit
`b0fdfe049510724c06a04706390cd174ea57a1d1` (`Bind manual commercial release to
verified schema144-146 maintenance transition`) changed the descriptor from
target 136 to target 146 on 2026-10-15 09:54:55 +03:00. The commit also added the
144→146 manifest and bridge and updated the release policy, control-plane code,
and tests. It is contained by local and remote `main`. The working tree does not
modify `release.json`.

The earlier C3 prompts and reports that called schema 136 active were stale
relative to that commit. In this document, “selected” means selected by the
checked-in source descriptor. No persistent environment was queried, so this
review does not claim that a database is actually at schema 146.

Repository evidence establishes that the source selection was deliberate and
guarded as a manual release. It does **not** contain an independently verifiable
human approval receipt for a past persistent-environment execution. The policy
in the same commit still requires explicit operation authorization. Therefore
Git can establish the selected source contract, but cannot by itself prove that
an actual migration/deployment was authorized or executed.

The complete consecutive Data Sources candidate path is:

`146 → 147 → 148 → 149 → 150 → 151 → 152 → 153 → 154 → 155 → 156 → 161`

All manifests remain candidates outside `release.json`. Validation confirms the
chain begins at the selected schema 146, every transition has the exact expected
predecessor, migration mirrors match, and the schema-156→161 bridge is expand-only
and application-compatible at schemas 156 and 161. It does not authorize skipping
147–156.

## 2. Release-policy review

The uncommitted C3 Step 5 additions to
`MADAR_AUTO_DEPLOY_MERGE_CONTRACT.md`, `production-release-policy.md`, and
`automated-database-migration-architecture.md` add only an unselected schema-161
boundary and its validation requirements. They do not change `release.json`,
enable automatic deployment, authorize migration execution, weaken backup or
forward-repair rules, widen production mutation authority, or enable Google
traffic. They explicitly require separate release approval and a real staging
OAuth test.

No accidental deployment-approval expansion was found. Existing 144→146 manual
release and privileged control-plane boundaries remain intact.

## 3. Accessibility correction

The global contrast audit reproduced 12 failures for
`button.ecommerce-add-variant-button` on `/ecommerce/products/new`: light/dark,
LTR/RTL, and compact/intermediate/wide. Text and icon contrast passed; the
transparent control used `--theme-border-strong`, producing only 1.6:1 against
the page surface where 3:1 is required.

The only visual change replaces that border with the existing semantic
`--color-border-control` token. Button dimensions, copy, behavior, layout,
background, hover state, and e-commerce functionality are unchanged. The full
contrast audit must report zero failed routes before staging activation.

## 4. OAuth, credential, and data-security assessment

Verified controls:

- OAuth uses the server-side authorization-code flow, PKCE S256, a 256-bit
  nonce, an HMAC-authenticated state value, a stored SHA-256 state digest,
  ten-minute expiry, and atomic single-use consumption.
- State is bound to the authenticated user, tenant, project, source, provider,
  and exact configured redirect URI. The callback revalidates the active session,
  tenant membership, project/source ownership, provider, and source status before
  token exchange.
- Only `https://www.googleapis.com/auth/spreadsheets.readonly` is requested and
  accepted. No Drive browsing or Sheets write method exists.
- The client secret is server configuration only. Refresh tokens and PKCE
  verifiers use the existing schema-155 source-scoped Vault Transit envelope.
  Access tokens remain in memory and are not returned to the browser.
- Credential versions and the source credential revision are revalidated before
  persistence. Database completion repeats the exact credential fence, so a
  concurrent revoke cannot advance a dataset revision or a no-op cursor.
- Refreshes do not persist access tokens. Existing scheduler leases prevent two
  workers from owning the same scheduled resource; reusable refresh-token calls
  may overlap with interactive inspection without weakening the final credential
  fence.
- Server requests are limited to fixed Google token and Sheets endpoints. DNS is
  validated and pinned, TLS hostname verification remains enabled, redirects are
  refused, user URLs are never fetched, and endpoint overrides work only for exact
  test-loopback configuration.
- Transport audit metadata excludes request targets, response bodies, headers,
  codes, and tokens. `SecretValue` cannot be rendered or serialized.
- Mapping and reads are tenant/project/source scoped. The schema-161 tables are
  RLS-enabled, denied to public/anon/authenticated roles, and available only to
  the service role through scoped functions.
- A complete unchanged scan uses the credential-fenced no-op RPC and updates only
  the diagnostic snapshot cursor. It creates no revision, history chunk, or
  checkpoint.
- Google rows missing from a later scan are intentionally retained. Authorization
  errors, header drift, timeouts, truncated responses, and partial scans cannot
  generate tombstones or mass deletion.

Small corrections made during this readiness review:

1. Every adapter metadata/header/page request now inherits the generic 15-second
   ingestion deadline instead of creating a fresh per-request 20-second deadline.
2. The process-local Sheets cadence is one request per second, matching Google's
   documented 60-read/minute/user/project quota more conservatively.
3. The security design now accurately states that the database stores the digest
   of the complete signed state, not merely the nonce.

## 5. Google API integration risks and limits

- The read-only Sheets scope can read every spreadsheet accessible to the
  authorizing Google account. Madar narrows actual requests to one configured
  spreadsheet and numeric sheet ID, but Google does not issue a per-sheet scope.
- External OAuth apps in Testing accept only registered test users, and grants
  using this scope normally expire after seven days. Staging must explicitly test
  the resulting reconnect behavior.
- Google documents 300 reads/minute/project and 60 reads/minute/user/project and
  recommends truncated exponential backoff for 429 responses. Madar retries
  bounded GET failures, but its rate limiter is process-local, not distributed.
  Keep staging worker/provider concurrency low and monitor actual Cloud quotas.
- The connector supports at most 10,000 rows, 128 selected columns, ten pages,
  1,000 rows/page, a 4 MiB Sheets response, and a 15-second complete ingestion
  budget. These are safety limits, not a large-sheet scalability claim.
- Sheets does not provide an atomic transactional snapshot across these bounded
  reads. Concurrent edits can change the fingerprint or fail validation. This is
  why deletion inference remains disabled.
- OAuth revocation and Workspace administrator policy can invalidate refresh
  tokens outside Madar. Such failures require reconnect and must never be treated
  as an empty spreadsheet.

Authoritative references:

- <https://developers.google.com/identity/protocols/oauth2/web-server>
- <https://developers.google.com/identity/protocols/oauth2/resources/best-practices>
- <https://developers.google.com/identity/protocols/oauth2/production-readiness/policy-compliance>
- <https://developers.google.com/workspace/sheets/api/limits>
- <https://developers.google.com/workspace/sheets/api/troubleshoot-api-errors>

## 6. Migration 161 activation prerequisites

Before an authorized staging migration:

1. Record the actual staging schema using the authoritative `core` schema-state
   row. Do not infer it from `release.json`.
2. Obtain a fresh, explicit staging release/migration approval identifying exact
   source revision, target 161, environment, backup, operator, and rollback plan.
3. Verify a known-good, restorable staging backup before any SQL.
4. Run dependency locks, migration-tree/mirror validation, transition validation,
   forward-release validation, candidate checksum validation, secret hygiene, and
   the full 146→161 disposable rehearsal against the exact proposed source.
5. If staging is below 146, stop and use its separately governed predecessor path.
   Never skip or rewrite migrations.
6. Apply checksum-pinned candidates 147 through 161 consecutively. Migration 161
   itself requires and locks exact schema 156 before DDL.
7. Verify schema state 161, RLS/grants, Vault availability, immutable storage,
   quota/accounting controls, scheduler fences, and application compatibility
   before enabling the provider.
8. Keep schedules and workers disabled until manual authorization and ingestion
   have passed. Do not change the production `release.json` as part of staging
   preparation.

Migration-161 SQL checksum:
`04308e96e6659f194f564cba1dddfa99643ea78a3fde63f913af5969050e7031`.

Candidate manifest checksum:
`52ef79e36ee55cd57a21e9cdc7132f0819682a78c906b45b3c3dc2f94a4ea2d5`.

## 7. Exact staging operator checklist

### A. Google Cloud staging project

- [ ] Create or select a Google Cloud project dedicated only to staging. Do not
      reuse a production project/client.
- [ ] Enable **Google Sheets API** for that project. Google Drive API is not
      required for this connector.
- [ ] Configure the OAuth consent/brand information with accurate application,
      support, contact, privacy, and authorized-domain data.
- [ ] Choose the correct audience. For an External staging app, keep publishing
      status **Testing** and add only the named synthetic staging account under
      **Test users**.
- [ ] Add only
      `https://www.googleapis.com/auth/spreadsheets.readonly` under data access.
- [ ] Create an OAuth client of type **Web application**.
- [ ] Register exactly one staging callback, including scheme, host, path, port
      if non-default, and trailing-slash choice:
      `https://<staging-api-host>/data/oauth/google-sheets/callback`.
- [ ] Do not register wildcards, localhost, development callbacks, or production
      callbacks on the staging client.

### B. Secure Madar configuration

- [ ] Deliver the client ID and secret through the approved staging secret
      manager; never Git, `.env` source files, Compose files, tickets, or chat.
- [ ] Generate an independent random state key of at least 32 bytes, encode it as
      base64url, and store it in the staging secret manager.
- [ ] Set server-side on both callback/backend and synchronization workers:
      `GOOGLE_SHEETS_CLIENT_ID`, `GOOGLE_SHEETS_CLIENT_SECRET`,
      `GOOGLE_SHEETS_REDIRECT_URI`, and `GOOGLE_SHEETS_STATE_KEY`.
- [ ] Confirm `GOOGLE_SHEETS_REDIRECT_URI` exactly equals the registered HTTPS
      callback. Confirm no test endpoint override variable is present.
- [ ] Restrict server egress to the required Google token and Sheets API hosts;
      browser navigation to Google's authorization host remains user-side.
- [ ] Keep `GOOGLE_SHEETS_PROVIDER_ENABLED` false until migration and dependency
      prerequisites are complete.
- [ ] Verify Vault Transit is initialized through its existing governed process,
      healthy, and accessible without exposing root tokens or unseal material.

### C. Controlled schema and provider activation

- [ ] Confirm the real staging database schema and backup evidence.
- [ ] Obtain the separate staging migration authorization.
- [ ] Apply the exact candidate chain through 161 using the governed migration
      process and verify every checksum/postcondition.
- [ ] Start the application with provider disabled and verify ordinary Data
      Sources, Data Logs, uploads, authentication, and project isolation.
- [ ] Set `GOOGLE_SHEETS_PROVIDER_ENABLED=true`, restart only through the normal
      staging procedure, and verify Google appears in source capabilities.
- [ ] Keep automatic schedules disabled during initial testing.

### D. Synthetic workbook acceptance

- [ ] Use a staging-only Google account and a dedicated non-sensitive workbook.
- [ ] Create at least two tabs and a sheet with columns such as `record_id`,
      `name`, `amount`, and `active`. Use unique, nonblank stable record IDs.
- [ ] Authorize from the intended tenant/project/source and confirm the consent
      screen requests only read-only Sheets access.
- [ ] Confirm tampered/replayed/expired state, wrong session, wrong tenant/project,
      denial, and redirect mismatch fail safely.
- [ ] Enter the canonical Sheets URL, discover tabs, select one numeric sheet ID,
      preview headers, select columns, choose `record_id`, and register the source.
- [ ] Run the initial import. Record source/resource/dataset IDs, committed
      revision, checkpoint, and UI freshness.
- [ ] Run again unchanged and confirm no new revision, history chunk, or checkpoint.
- [ ] Change a value, add a record, reorder rows, and rename the tab. Confirm the
      same dataset/resource is updated through stable record and numeric sheet IDs.
- [ ] Remove a row and confirm Madar retains the prior record and reports the
      conservative `retain_missing_records` behavior.
- [ ] Test duplicate/blank IDs, header change, permission loss, missing sheet,
      429 behavior, and timeout without cursor/revision corruption.
- [ ] Enable one conservative schedule, execute it through the existing worker,
      and verify lease/fence, next-run, revision, checkpoint, and health state.
- [ ] Allow or force an access-token refresh and confirm the refresh token remains
      encrypted and absent from UI, logs, lineage, storage paths, and audits.
- [ ] Revoke the local Madar credential during a controlled synchronization and
      confirm final commit fencing. Then revoke Google access and confirm the
      source enters reconnect-required state without data loss.
- [ ] Repeat tenant/project/source denial tests and inspect logs for secrets.

### E. Disable and rollback posture

- [ ] Disable schedules, stop the governed synchronization worker, and set
      `GOOGLE_SHEETS_PROVIDER_ENABLED=false`.
- [ ] Revoke affected Madar credentials and the Google grant; rotate client/state
      secrets if exposure is suspected.
- [ ] Preserve datasets and immutable history under normal retention policy.
      Disconnect does not delete imported data.
- [ ] Do not attempt a down-migration. After schema advancement, use forward
      repair with the compatible application. Restore the verified pre-migration
      backup only through a separately authorized recovery operation.
- [ ] Capture secret-free staging evidence and require a new review before any
      production proposal.

## 8. Verification record

Completed offline on 2026-10-23:

- Focused Google Sheets/OAuth/scheduler backend tests: **35 passed, 0 failed**.
- Locked backend suite: **3,715 collected; 3,032 passed; 683 skipped; 0
  failed**. Its network guard reported `EXTERNAL_ATTEMPTS []` and
  `EXTERNAL_SITES []`.
- Backend installed dependency check: **passed**, no broken requirements.
- Full frontend suite: **239 files passed; 1,761 tests passed; 1 skipped; 0
  failed**.
- Frontend ESLint, theme contract, API-origin checks, production build,
  production-bundle origin audit, and tenant-bundle audit: **passed**.
- Production npm dependency audit: **0 vulnerabilities**.
- Global contrast audit: **672 route checks**, 25,814 text checks, 324
  placeholder checks, 5,942 control checks, and 8,288 icon checks; **0 failed
  route checks**. This includes all light/dark, LTR/RTL, and
  compact/intermediate/wide variants.
- Complete disposable browser fixture: **3 passed, 0 failed** — schema-141 safe
  fallback, existing HTTP-provider onboarding/sync/revocation, and Google Sheets
  OAuth/mapping/stable-dataset sync/conservative deletion/revocation. Artifacts:
  `/tmp/madar-data-sources-c3-step5-browser-20817-1003885`.
- Migration mirrors and prefix checks: **161/161 matched; 0 errors**.
- Migration transition, forward-release, Google candidate checksum,
  Data Sources staging-chain, dependency-lock, secret-hygiene, and
  `git diff --check` gates: **passed**.
- Disposable full schema-136→161 rehearsal: **passed**, including forced
  transactional rollback, migration locking, dispatcher concurrency, and Google
  connector boundaries. The deliberate `division by zero` lines are injected
  rollback tests, not migration failures.

Warnings and skips:

- Migration validation retains two known warnings because historical migrations
  013 and 014 have identical content in each mirror tree. No new duplicate was
  introduced.
- The locked backend suite skipped 683 tests that require explicitly marked
  external/disposable environment facilities; the frontend suite skipped one
  existing test.
- The backend emitted the existing Starlette `httpx` deprecation warning and
  Pygwalker offline informational message. The frontend build emitted the
  existing bundle-size warning for a chunk above 500 kB. Playwright reported
  that `NO_COLOR` was ignored because `FORCE_COLOR` was set.
- The first Google-only browser invocation exited with status 2 and no diagnostic
  output while the contrast-audit development server was still active. After
  stopping that local server, both a clean Google-only run and the complete
  three-test browser suite passed. This is classified as local harness/resource
  interference, not a reproduced connector defect.

No real Google authorization or API request was performed. It must not be
described as passed until the separately approved staging exercise.

## 9. Recommendation

**READY, conditionally, for a separately authorized staging-only activation**
once every unchecked prerequisite above is satisfied and the final offline gates
are green. This recommendation does not attest the actual schema of any persistent
environment, historical operation authorization, or real Google behavior.

**NOT READY for production.** Production requires successful real-Google staging
evidence, OAuth lifetime/revocation observations, quota and alert validation,
egress verification, an explicit production release proposal, and separate
authorization.
