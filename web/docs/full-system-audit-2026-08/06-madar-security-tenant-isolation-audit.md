# Madar security and tenant-isolation audit

## Authorization chain

Authenticated request → Supabase session validation → local active-user lookup → trusted tenant/user context → role/capability helper → tenant-qualified Supabase query/RPC → controlled response. The backend uses a service-role client, so this application chain is security-critical; database RLS is defense-in-depth rather than the primary backend barrier.

Reviewed builder, form submission, reservation, analytics, asset, calendar, notification, and admin routes consistently bind resource IDs to trusted tenant/project context before mutation. Queries using `.limit(1)` are generally preceded by tenant/project/id predicates. Current production grants independently confirm that `authenticated` cannot directly mutate the reviewed privileged tables; only `SELECT` remains where needed. This closes the previously documented self-promotion/direct-builder-write class in the actual schema.

## Public-site identity chain

`hostname/path/subdomain → unique site row → tenant + explicitly bound project → active published revision/snapshot → page/form/reservation/assets`.

The current code fetches at most two rows to detect ambiguity; distinguishes hosted path, subdomain, and custom hostname; rejects duplicate home/routes/forms; verifies that the published snapshot carries matching tenant/project/publication state; and tenant-checks managed asset references. ETags include site identity, tenant/project/publication version, and schema hash. CDN responses are no-store while browser validators can use the publication-specific ETag. Publication activation uses an atomic RPC with expected revision.

This is a strong correction to the historic "wrong tenant content on hostname" failure. No confirmed cross-tenant IDOR was found in the reviewed current routes or production grants. Required ongoing regression tests should exercise same UUID-shaped IDs across two tenants, duplicate host/site rows, stale activation, cross-tenant asset IDs, and cache replay.

## Authentication threat review

- Enumeration: controlled login/reset errors and rate limits reduce signal; external behavioral testing with real accounts was not performed.
- Session replay: Supabase refresh behavior is used; a 15-second in-process refresh replay cache is not distributed, so multi-backend scale requires a shared replay/revocation design.
- CSRF/CORS: strong, fail-closed production defaults and correct middleware ordering.
- MFA: sensitive system-admin operations use AAL2; factor removal requires current AAL2 when present.
- Admin support access: short-lived consent-code/session design, audited, and kept separate from ordinary user authorization.
- Password policy: provider-based hashing is outside this codebase; breached-password screening was not found.

## Billing and quota authorization

Current commercial schema models tenant subscription, plan/add-ons, capability snapshots, storage accounts/reservations/objects, and AI token reservations/ledger. Critical writes are service-role RPCs, not frontend trust. Storage and token reservations use atomic database checks to avoid check-then-act overuse; invalid/missing capability state generally fails closed.

One production subscription exists. Full payment-provider lifecycle is not implemented and should not be marketed as automated billing. Redis failure causes production rate-limit checks to fail closed; database failure produces hard outage rather than granting capability.

## Attack conclusions

A normal Tenant A member was not found to have a route or direct database grant that can read/mutate Tenant B resources. The dominant tenant-wide compromise path is instead backend compromise, because its Supabase service role and direct PostgreSQL superuser credential bypass every tenant boundary. Removing that credential and splitting service roles by function materially changes the threat model.
