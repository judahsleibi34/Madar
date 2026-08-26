# Supabase Secret API key rotation cutover

Date: 2026-08-26 UTC

## Outcome

Madar production and its prepared rollback slot now use the replacement
Supabase Secret API key. The old exposed key remains active only at the
provider pending operator deletion; no current Madar runtime depends on it.
No credential value, digest, fragment, or request header was recorded.

- Active release: `67aff17f4a521a01f87bd8ad76a570acaf07df9b`
- Active slot: green
- Prepared rollback release: `67aff17f4a521a01f87bd8ad76a570acaf07df9b`
- Prepared rollback slot: blue
- Schema: 83
- Auto-deploy timer: inactive
- Production environment: mode `0600`, ownership preserved

## Provisioning verification

The reviewed hidden-prompt tool atomically replaced only
`SUPABASE_SERVICE_KEY`. Structural validation proved all non-target environment
lines remained byte-for-byte unchanged, a dedicated `CSRF_SECRET` remained
configured, and the new key classified as an opaque Secret API key. The
protected pre-change backup was moved intact from the Git worktree to:

`/home/madar/backups/madar/config/.env.pre-supabase-rotation-20260826T092312Z`

It remains mode `0600`, owned by `madar:madar`. Moving it was necessary because
the release controller correctly rejects untracked files in the production
worktree.

## Inactive green validation and cutover

Green was recreated from the exact immutable release using the updated
environment, with notification, calendar, and deletion queue consumers
inactive. It passed:

- live, ready, exact version, schema 83, and storage readiness;
- release-controller schema probe;
- privileged read-only PostgREST;
- harmless read-only RPC;
- Auth Admin list metadata probe;
- Storage bucket list metadata probe;
- frontend HTTP 200 and canonical production API origin;
- controlled invalid-login JSON 422;
- exact allowed-origin CORS and rejected unapproved origin.

Eight published-site records were available for a safe GET probe, but each
returned HTTP 402 because canonical commercial assignments remain deliberately
unapproved. This is the existing fail-closed G15 deferral, not a credential or
tenant-routing regression.

The controller stopped blue queue consumers before recreating and starting
green consumers, validated all green workers, atomically switched the proxy,
and completed its observation period. Repeated post-switch readiness, provider,
worker, public frontend, and API checks passed. No real password was available
or handled, so a fresh authenticated dashboard session was not created.

## Rollback reconstruction

Blue core services were recreated after credential provisioning from the same
immutable schema-83-compatible release and validated while inactive. Readiness,
version, PostgREST, RPC, Auth Admin, Storage, and frontend checks passed.

The three blue queue-worker containers were then force-recreated through the
checked-in Compose environment builder with `--no-start --no-deps`. They remain
in `created` state and cannot double-consume green queues. The durable prepared
release record identifies blue as `candidate_validated_workers_inactive`.

## Old-key non-use proof

Value-free provenance checks established:

- active green backend and notification/calendar/deletion workers were created
  after the atomic environment replacement;
- inactive blue backend and its stopped rollback workers were created after
  the replacement;
- each server consumer has exactly one opaque Secret API key assignment;
- the installed release controller loads the current protected environment and
  its post-rotation schema probe passed;
- `state.json` and `prepared-release.json` contain no credential variable or
  Secret API key material;
- active logs contained zero Invalid-JWT, provider-authorization, readiness,
  or worker-failure patterns during the rotation window.

No request was made with the old key after cutover, and no old/new value
comparison was performed.

## Provider revocation decision

Format-only classification established that the exposed key is an opaque
`sb_secret_` Secret API key, not a legacy JWT-shaped service-role key. Supabase's
current documentation says compromised Secret API keys are rotated by creating
a replacement, moving every component, and then deleting the individual old
key. Disabling legacy anon/service-role keys and rotating JWT signing keys are
separate operations and are not required to revoke this individual key.

Provider references:

- <https://supabase.com/docs/guides/getting-started/api-keys>
- <https://supabase.com/docs/guides/getting-started/migrating-to-new-api-keys>

The operator should now delete the individual exposed old Secret API key in the
Supabase Dashboard. Codex did not perform that action.

## Historical snapshot recommendations

All files below remain protected mode `0600`; no secret value was inspected.

| Snapshot | Classification | Recommendation |
| --- | --- | --- |
| `/home/madar/backups/Madar-prod-env-before-vapid-20260813T170449Z` | Retention-required but potentially compromised | Do not restore unchanged. Retain only until configuration rollback/audit policy permits secure retirement. |
| `/home/madar/backups/Madar-dev-env-backup-before-env13-8-20260813T155449Z` | Safe to retire later | Confirm no development rollback need, then securely retire under the approved backup-retention process. |
| `/home/madar/backups/madar/config/.env.20260825T154555Z.pre-security-provision` | Retention-required but potentially compromised | Preserve only for the incident/configuration rollback window; never restore secret fields unchanged; securely retire afterward. |
| `/home/madar/backups/madar/config/.env.pre-supabase-rotation-20260826T092312Z` | Retention-required and known to contain the superseded credential by design | Keep only through operator revocation and immediate rollback verification, then securely retire under policy. |

No snapshot was deleted.
