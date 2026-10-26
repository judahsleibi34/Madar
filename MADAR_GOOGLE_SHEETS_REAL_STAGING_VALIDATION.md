# Madar Google Sheets real-staging validation

Date: 2026-10-23
Source revision inspected: `cf444303e55a2c6a214ab53f683442cf2fac15fe`
Branch inspected: `main`
Outcome: **BLOCKED — mandatory safety stop before any external mutation**

This report records the attempted C3 Step 7 staging activation. No deployment,
database connection, backup, migration, provider activation, OAuth request,
Google API request, worker start, commit, push, or production mutation was
performed.

## 1. Exact staging environment and source revision

The source revision is the commit shown above plus the preserved uncommitted C3
connector and release-candidate work listed by `git status`. The workspace does
not contain an identifiable persistent staging target. The only available
application environment file declares `APP_ENV=production`; no staging-specific
environment file or exported staging variables were found.

The repository's `web/staging` harness is documented as loopback-only,
disposable, and backed by tmpfs PostgreSQL. It is useful for local rehearsal but
does not satisfy the requested isolated, persistent, real-Google staging target.

Because the available runtime cannot be conclusively distinguished from
production, the milestone's mandatory stop rule applies.

## 2. Environment-separation evidence

Read-only evidence collected:

- `web/.env` declares `APP_ENV=production`.
- No staging environment variables are exported in the current shell.
- No `.env.staging*` or equivalently named persistent-staging configuration was
  found within the inspected repository depth.
- `web/staging/README.md` states that its harness is loopback-only, disposable,
  and never depends on production or customer endpoints.
- The current branch is `main` and the worktree contains substantial preserved
  uncommitted work, so this checkout is not itself proof of a deployed staging
  revision.

No destination URL, database identity, cloud project ID, service account, Vault
cluster, bucket, or worker host was contacted. Values of existing secrets were
not printed or copied.

## 3. Backup and restore evidence

**Not executed.** No approved staging database was identifiable, so a backup
could not be taken or restored without risking production access. There is no
new backup digest, restore transcript, or restored schema-state assertion.

Required before resumption: provide an independently identifiable staging
database and an approved backup destination, then create a fresh coordinated
backup and restore it into a disposable database. Verify the restored `core`
schema-state row before migration.

## 4. Pre-migration schema and migration path

The checked-in release descriptor still targets schema 146. The reviewed
candidate path is:

`146 → 147 → 148 → 149 → 150 → 151 → 152 → 153 → 154 → 155 → 156 → 161`

This is source-level evidence only. The actual staging schema was not queried.
Migration must stop if the staging `core` schema-state row is absent, is not the
expected predecessor, or disagrees with the approved path.

Migration 161 remains an unselected candidate. Its reviewed SQL SHA-256 is
`04308e96e6659f194f564cba1dddfa99643ea78a3fde63f913af5969050e7031` and the
candidate manifest digest is
`52ef79e36ee55cd57a21e9cdc7132f0819682a78c906b45b3c3dc2f94a4ea2d5`.

## 5. Migration execution and postconditions

**Not executed.** No SQL was applied. Schema 161 was not selected or activated.
RLS, grants, schema state, Vault functions, immutable storage, quotas, accounting,
and scheduler fences therefore have no new real-staging evidence from this run.

## 6. Google Cloud and OAuth configuration

**Not configured or contacted.** The required Google Sheets variables were not
exported and were absent from the inspected application environment file:

- `GOOGLE_SHEETS_PROVIDER_ENABLED`
- `GOOGLE_SHEETS_CLIENT_ID`
- `GOOGLE_SHEETS_CLIENT_SECRET`
- `GOOGLE_SHEETS_REDIRECT_URI`
- `GOOGLE_SHEETS_STATE_KEY`

No credentials should be pasted into chat or committed to the repository.

Operator action required:

1. Create or select a Google Cloud project dedicated exclusively to staging.
2. Enable Google Sheets API.
3. Configure an External OAuth app in Testing mode and add only the named
   staging test user.
4. Configure only the sensitive scope
   `https://www.googleapis.com/auth/spreadsheets.readonly`.
5. Create a Web application OAuth client.
6. Register exactly
   `https://<staging-api-host>/data/oauth/google-sheets/callback`; scheme, host,
   port, path, case, and trailing-slash choice must exactly match the runtime
   value.
7. Put client ID, client secret, and an independent random state key of at least
   32 bytes into the approved staging secret manager. Do not place them in Git,
   source `.env` files, tickets, logs, or chat.
8. Expose the secrets only to the staging backend/callback and sync worker.
9. Keep `GOOGLE_SHEETS_PROVIDER_ENABLED=false` until backup, migration, and
   dependency verification pass.
10. Provide the operator with the exact non-production hostname and a staging
    identity attestation before resuming this run.

Google requires an exact redirect URI match for web-server OAuth and recommends
secure server-side storage of the client secret. The Sheets read-only scope can
read spreadsheets available to the authorizing account, so the test account and
workbook must contain only synthetic data.

## 7. OAuth authorization and refresh results

**Not executed.** No authorization URL was generated, no browser consent was
started, no callback was received, and no access or refresh token was issued.
PKCE, state single-use behavior, callback binding, refresh, expiry, and token
redaction therefore retain offline-test evidence only.

## 8. Synthetic Google Sheet used

**Not created.** The operator must create a non-sensitive staging workbook with
at least two tabs and stable unique, nonblank record IDs, for example:

`record_id`, `name`, `amount`, `active`

Do not use customer data, production accounts, or a workbook shared with
production identities.

## 9. Manual and scheduled synchronization

**Not executed.** No source registration, manual read, schedule, worker claim,
or checkpoint ran against Google.

## 10. Revision, checkpoint, lineage, and version restoration

**Not executed.** There is no real-staging evidence for initial revision
creation, immutable checkpoint publication, lineage, current-version reopening,
or exact historical-version restoration.

## 11. Idempotency and safe no-op behavior

**Not executed against real Google.** Offline coverage remains the only evidence
that an unchanged complete snapshot does not create a new revision, history
chunk, or checkpoint.

## 12. Revocation, permission loss, and recovery behavior

**Not executed.** Local credential revocation, Google grant revocation, workbook
permission loss, reconnect-required behavior, and in-flight credential fencing
still require controlled staging validation.

## 13. Tenant and project isolation

**Not executed in persistent staging.** No cross-tenant, cross-project, or
cross-source request was sent. Existing offline tests are not a substitute for
the required staging checks.

## 14. Quota, retry, timeout, and incomplete-snapshot behavior

**Not executed against Google.** Staging must validate bounded retry for 429 and
transient 5xx responses, the end-to-end deadline, incomplete-snapshot rejection,
and unchanged cursor/revision state after failure. Google currently documents
300 read requests per minute per project and 60 per minute per user per project;
the run must measure actual staging behavior rather than assume those limits are
available exclusively to Madar.

## 15. Secret hygiene and log inspection

No new secret was received or generated, and no OAuth or Google request was
made. Repository inspection printed environment variable names and safe
environment classifications only, not values. A post-run persistent-staging log,
database, audit, lineage, object-key, and process-environment inspection remains
required after an authorized OAuth/sync run.

## 16. Performance and operational observations

No real-provider timing, quota, database, Vault, object-storage, queue, worker,
or checkpoint measurements were collected. Existing local measurements must not
be represented as persistent-staging capacity evidence.

## 17. Rollback and disablement test

**Not executed.** Nothing was enabled, so no rollback mutation was necessary.
Before resumption, the operator must prove they can disable schedules, stop the
staging sync worker, set the provider flag false, revoke Madar credentials and
the Google grant, preserve imported history, and restore the verified backup
under a separately authorized recovery procedure. Candidate expand migrations
must not be down-migrated casually; use compatible application rollback or
governed forward repair.

## 18. Final recommendation

**FAIL / NOT READY for production-readiness review.** This is a prerequisite
failure, not a connector defect: a conclusively non-production persistent
staging target, verified backup/restore path, valid HTTPS callback, and staging
OAuth credentials were unavailable. The mandatory safety gate correctly
prevented any external action.

Resume only when all of the following are supplied through approved operational
channels:

- an exact persistent staging hostname and environment attestation;
- staging database/Vault/storage identities that are demonstrably separate from
  production;
- the actual staging `core` schema version;
- a verified backup and disposable-restore destination;
- an approved migration executor and rollback owner;
- a TLS-valid callback reachable at the exact registered URI;
- staging-only Google OAuth credentials installed in the secret manager;
- a named synthetic Google test account and workbook owner available to perform
  interactive consent;
- confirmation that staging actions cannot trigger production CI/CD, routing,
  workers, buckets, databases, or secrets.

After those prerequisites are available, rerun from environment attestation and
backup verification; do not skip directly to OAuth or migration.

## Authoritative Google references

- <https://developers.google.com/identity/protocols/oauth2/web-server>
- <https://developers.google.com/identity/protocols/oauth2/policies>
- <https://developers.google.com/workspace/sheets/api/scopes>
- <https://developers.google.com/workspace/sheets/api/limits>
