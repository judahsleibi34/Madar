# Supabase Secret API Key compatibility assessment

Date: 2026-08-26 UTC

## Stop decision

Production was not changed. It remains on release
`4faf63a67cbcfe884d3cbeeaa2f39ae9f0a37467`; the legacy auto-deploy timer is
inactive. The newly created provider key was not read, installed, tested,
printed, logged, hashed, compared, or otherwise handled during this phase.

The new server key is **not a direct drop-in for the currently active code**.
The pinned `supabase-py==2.30.0` client copies its API key into both `apiKey`
and `Authorization: Bearer` across PostgREST, Auth Admin, Storage, and
Functions. Madar's direct readiness and release schema probes did the same.
Supabase's current migration guidance requires opaque publishable/secret API
keys to use `apikey`; copying the opaque key into Bearer authorization causes
JWT parsing failure.

Primary provider references:

- <https://supabase.com/docs/guides/getting-started/api-keys>
- <https://supabase.com/docs/guides/getting-started/migrating-to-new-api-keys>
- <https://supabase.com/docs/reference/python/admin-api>
- <https://supabase.com/docs/guides/auth/signing-keys>

## Consumers

The production environment supplies `SUPABASE_SERVICE_KEY` to:

- the backend API;
- the notification worker;
- the calendar synchronization worker;
- the data-deletion worker;
- the inactive retained backend slot when it is recreated;
- the immutable release controller's schema-state probe.

The backend's singleton privileged client is shared by tenant-scoped and
administrative table queries, RPCs, Auth Admin, Storage, public-site services,
password administration, verification services, administrator-access
services, notification services, calendar services, lifecycle deletion,
entitlements, quota/storage tooling, AI metering, and operational scripts.
Consequently, correcting only the readiness probe would not make the
credential migration safe.

Not consumers of this variable:

- the migration executor and backup/restore tooling use direct PostgreSQL
  configuration instead;
- the frontend, proxy, Redis, parser worker, and remote-ingestion worker do not
  receive the server credential;
- staging uses a generated local service JWT;
- CI uses an explicit non-secret fixture.

Several services retain `SUPABASE_SERVICE_KEY` as a last-resort signing-secret
fallback for development compatibility. In production, the independently
configured `CSRF_SECRET` and `CALENDAR_CREDENTIALS_SECRET` take precedence, so
the server-key replacement does not rotate production CSRF, session-activity,
pending-verification, verification-hash, reservation-token, administrator
access, or calendar-encryption material.

## Development remediation

The development tree now:

- detects opaque Supabase API keys and sends them through `apikey` only;
- retains dual `apikey` plus Bearer behavior for legacy JWT API keys;
- uses that behavior for the shared official client and the separate password
  administration client;
- uses the same behavior for readiness and release schema probes;
- prepares the MFA client for a future legacy-anon to publishable-key migration;
- rejects a publishable key placed in the server credential variable in
  production;
- provides a hidden-prompt/protected-file, atomic provisioning tool that backs
  up the environment file and preserves restrictive ownership and modes.

Validation on the final development image:

- focused Secret API key, runtime, readiness, release, MFA, password, and
  provisioning suites: pass;
- full backend suite: **1,082 passed, 0 failed**;
- external network attempts: **0**.

## Location and reuse assessment

The production `.env` contains the variable and is mode `0600`. The same
runtime value is distributed to the active backend and three active workers;
the retained backend slot also contains its deployment-time copy. Development
has a separately configured variable, but no value comparison was performed,
so equality with production is **not verified**. Staging and CI do not reuse
the production credential by design.

Three protected historical environment snapshots contain the variable name:

- `/home/madar/backups/Madar-prod-env-before-vapid-20260813T170449Z`
- `/home/madar/backups/Madar-dev-env-backup-before-env13-8-20260813T155449Z`
- `/home/madar/backups/madar/config/.env.20260825T154555Z.pre-security-provision`

All three are mode `0600`. Their values were not read or compared. They must be
treated as potentially containing the compromised credential and reviewed for
secure retirement after rollback dependence ends. Current manifest backups
explicitly exclude configuration values.

## Rotation impact and order

Supabase supports creating new Secret API keys in parallel with the legacy
JWT-based service-role key, so the application replacement can be performed
without downtime. Swapping this API key does not rotate the JWT signing key and
does not itself invalidate user sessions.

However, fully disabling the legacy service-role credential is coupled to the
legacy API-key retirement process. Madar still uses the legacy anon key.
Supabase's documented path requires migrating legacy anon usage to a
publishable key before disabling the legacy anon/service-role API keys. A JWT
signing-secret rotation is a separate, higher-impact operation and is not the
recommended way to perform this server-key migration.

Safe order:

1. Promote the compatibility code while the old server credential remains
   valid.
2. Validate the compatibility release with the old credential.
3. Provide the new key through the hidden prompt or a root/operator-owned mode
   `0600` one-line file; never use argv or shell history.
4. Atomically back up and update `/home/madar/saas/Madar/.env`.
5. Start the inactive slot with the new key and workers disabled; verify
   database, schema, Auth Admin, Storage, and RPC behavior.
6. Perform the controlled worker handoff and traffic switch; soak while the old
   key and old-key rollback slot remain valid.
7. Recreate and validate the retained rollback slot with the new key.
8. Confirm or replace any development/operator credential copies separately.
9. Migrate the backend anon-key consumers to an approved publishable key and
   validate authentication/MFA.
10. Only after no consumer depends on legacy API keys, disable them through the
    Supabase Dashboard and revalidate production. Do not rotate the JWT signing
    secret as part of this application-key change.
11. Review protected historical configuration snapshots and securely retire or
    sanitize obsolete copies under an approved backup-retention procedure.

Expected application downtime is zero when this order and blue/green handoff
are followed. The compatibility release must be promoted before provisioning;
the currently active release is not ready for the new key.
