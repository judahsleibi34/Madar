# Credential incident response

This record intentionally contains credential classes and metadata only. It contains no credential values, connection strings, tokens, or reversible fingerprints.

## Incident scope

The original audit transcript exposed Supabase-related credentials. During this remediation, a read of a Compose file accidentally rendered an additional hardcoded host PostgreSQL administrator password in the tool transcript. That value was not copied into this package, but the transcript exposure is real and must be treated as compromise.

No credential was rotated in production because the required off-host recovery and replacement-path gates were not met. Consequently, old credentials have **not** been verified dead.

## Rotation dependency graph

```text
verified off-host recovery point
  -> replacement least-privilege paths proven
    -> issue replacement credentials
      -> update one bounded consumer group
        -> health and negative-privilege verification
          -> update remaining consumers
            -> revoke old credential
              -> prove old credential fails
                -> review provider/security logs
```

## Credential classes

### Madar Supabase direct PostgreSQL credential

- Provider/system: Supabase PostgreSQL.
- Consumers: current production API/notification/calendar environments (unneeded), development equivalents, operator backup/restore/migration/verification tools, and historical environment copies.
- Privilege: current role is not marked `rolsuper`, but has create-database, create-role, replication, and bypass-RLS; catastrophic effective privilege.
- Rotation mechanism: provider-side database password rotation combined with removal from all runtime services; issue a separate operator-only path if direct SQL remains necessary.
- Overlap: provider behavior must be confirmed; assume a password replacement is non-overlapping unless explicitly supported.
- Sessions: terminate/revoke old DB sessions after cutover where provider controls permit.
- Dead-key verification: attempt an authenticated connection using only a protected operator test facility and confirm authentication failure without logging the URL.
- Rollback: time-bounded replacement path proven before revocation; do not retain the old credential indefinitely.

### Madar Supabase service-role key

- Provider/system: Supabase API/PostgREST/Auth/Storage.
- Consumers: backend and the notification/calendar workers; historical environment copies.
- Privilege: bypasses normal public RLS access paths and is high value.
- Rotation mechanism: Supabase signing/service-key rotation using provider-supported overlap if available.
- Sessions/tokens: determine whether the provider operation also invalidates user JWTs; plan customer session impact explicitly.
- Dead-key verification: old service key must receive an authentication/authorization failure on a harmless metadata request.
- Rollback: provider-supported overlap only; never restore the exposed key after revocation.

### Madar Supabase anon/public key

- Provider/system: Supabase public API.
- Consumers: browser/backend configuration and historical environment copies.
- Privilege: public by design, but tied to the signing-key incident and configuration inventory.
- Rotation mechanism: rotate consistently with provider signing-key procedure.
- Sessions/tokens: assess user JWT invalidation as part of the same change.
- Dead-key verification: provider-defined invalid-key response.

### Separate host PostgreSQL administrator credential

- Provider/system: `/home/madar/saas/database` PostgreSQL instance.
- Consumers: two local Compose definitions; no application consumer found.
- Privilege: login superuser.
- Exposure: newly rendered in this remediation transcript.
- Rotation mechanism: create/update a protected operator credential, alter the database role through an authenticated local channel, then update protected configuration. Container initialization environment alone does not rotate the existing database role.
- Overlap: one controlled overlap until the new credential is proven; then revoke the old password.
- Dead-key verification: Tailscale/local connection with the old password must fail.
- Rollback: new operator credential escrowed before old credential revocation.

### Briefedly production database bootstrap/runtime credential

- Provider/system: local Briefedly PostgreSQL.
- Consumers: production backend and DB initialization/configuration; currently over-injected into runtime configuration.
- Privilege: login superuser and object owner.
- Rotation mechanism: create tested DBA/owner/migrator/runtime/backup roles, cut API/worker to runtime, then rotate, disable login, and rename the legacy bootstrap identity.
- Overlap: bounded cutover only.
- Sessions: terminate legacy-role sessions after application cutover.
- Dead-key verification: the old `briefedly_app` identity must not exist or authenticate.
- Rollback: forward repair with escrowed operator DBA; never reconnect application runtime as bootstrap superuser.

## Completion state

| Credential class | Rotated | Old verified invalid | Consumers updated in production | Least privilege achieved in production |
|---|---:|---:|---:|---:|
| Supabase direct PostgreSQL | no | no | no | no |
| Supabase service role | no | no | no | no |
| Supabase anon/public key | no | no | no | n/a |
| Host PostgreSQL administrator | no | no | no | no |
| Briefedly bootstrap/runtime DB | no | no | no | no |

AUDIT-SEC-001 cannot be marked fixed until provider-side revocation and old-credential failure are both evidenced.
