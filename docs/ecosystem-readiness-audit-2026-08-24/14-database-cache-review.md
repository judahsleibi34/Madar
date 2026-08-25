# Database and cache review

## PostgreSQL evidence

- PostgreSQL major 17.
- 80 provider migration-history rows through 080; migration 081 uses the separate `application_schema_state` contract, currently `core=81`.
- 64 public base tables, all with RLS enabled; 7 explicit policies because most privileged access is service-role-only and anon/authenticated grants are revoked.
- Zero invalid public indexes.
- Migration trees contain 81 matching files each; validator passes with only the documented historical 013/014 duplicate-content warnings.
- The live RLS/grant verifier completed without emitting a mismatch.

Key invariants have database constraints: unique site tenant/subdomain, tenant project slug, publication revision/integrity checks, form/reservation idempotency, cancellation token, storage nonnegative/account keys, subscription enumerations and tenant foreign keys. Live duplicate/mismatch/counter checks all returned zero. Three email delivery rows are legitimately dead; no queue row has an expired processing lease.

Remaining database work:

- add a partial unique active-base-subscription constraint;
- consider native reservation exclusion if historical cleanup allows it;
- ensure tenant predicates accompany globally unique downstream worker updates;
- automate expired reservation/asset/notification retention;
- rehearse every new migration against a provider-compatible clone and record backward-compatibility classification.

## Redis

Redis 7 is internal plus loopback, used for distributed rate limiting. Rate keys have TTLs and production fails closed on Redis loss; readiness pings Redis. The live instance had zero keys and 1.09 MiB used.

Configuration drift exists. Tracked Compose requests a 64 MiB tmpfs at `/data`, while the August 12 live container has an anonymous persistent Docker volume mounted there. `maxmemory=0` and `maxmemory-policy=noeviction`; the container cgroup is 256 MiB. A sufficiently large key burst can reach cgroup OOM instead of controlled eviction. Recreate Redis from verified Compose during a window, confirm mount type `tmpfs`, set an explicit maxmemory below the cgroup ceiling and choose a rate-limit-safe policy. Persistence is neither required nor desired for current ephemeral controls.

No unsafe deserialization or tenantless business-data cache key was found. In-process catalog/workspace caches are bounded and tenant-keyed; process-local invalidation across workers should not be relied on for authorization.
