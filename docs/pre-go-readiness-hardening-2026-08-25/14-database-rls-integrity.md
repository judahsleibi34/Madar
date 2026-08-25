# Database, RLS, and integrity

## Migration and privilege result

- PostgreSQL 17 rehearsal: PASS.
- Migration parity: 83/83, zero errors.
- Tenant-sensitive RLS/grant verification: PASS.
- Backend-only quiz, entitlement, deletion, and storage state is not directly exposed to public/anonymous/authenticated roles.
- Service-role worker access is scoped through reviewed functions and explicit tenant context.

## Integrity queries

The staging integrity checker returned zero for:

- duplicate hostname/subdomain bindings;
- duplicate tenant settings;
- tenant/project/publication mismatch;
- invalid publication identities;
- duplicate active entitlement-bearing subscriptions;
- orphan deletion steps;
- stale deletion leases;
- asset tenant mismatch;
- storage counter mismatch;
- overlapping exclusive reservations;
- invalid indexes.

Database constraints enforce subscription ambiguity denial, immutable quiz attempt publication identity, deletion request/step state constraints, and the reservation exclusivity invariant where capacity is exclusive. Lifecycle semantics are not replaced with indiscriminate cascades; the saga owns cross-provider ordering and verification.
