# Target and decisions

Retain the existing modular FastAPI monolith and React public/portal entries. Keep PostgreSQL as authority, Redis for disposable rate limiting/cache, and existing durable PostgreSQL queues. Preserve Supabase-compatible Auth/MFA/REST/Storage until actual native replacements pass compatibility and recovery drills. Use dedicated staging networks, synthetic data and no production secrets. Do not modify release controller, selected release metadata or migration history merely to simplify development.

## ADR 001 — Incremental hardening without provider replacement

Context: source already implements provider adapters, transactional RPCs and sophisticated protected release machinery; the live state differs from Git checkout.
Decision: fix evidenced request/configuration/cache/testing defects within current interfaces, and validate on the isolated VM. Keep current schema146 and immutable SQL unchanged unless a separately tested transition is indispensable.
Alternatives: wholesale ORM/Auth migration, new broker, microservices. These expand regression and operational risk without a measured justification.
Benefits: reviewable changes, preserved compatibility and existing release boundaries.
Costs/risks: privileged service-role queries still need application authorization; process-local caches cannot provide immediate cross-worker invalidation.
Migration impact: application-only changes require normal review and existing production admission gates; no automatic production actions.
Reversibility: isolated application commits can be reverted without database reversal. Configuration tightening needs a pre-deployment review of rejected unsafe settings.

## ADR 002 — Fence cache publication without durable per-tenant metadata

Context: a database read can finish after a tenant mutation invalidates the cache,
reintroducing stale catalog/calendar state. Calendar generation entries previously
persisted per tenant. Public host resolution learns ownership only after its read.
Decision: retain bounded LRU/TTL caches; use per-tenant tokens only during active
fills, plus a single generation object for direct/unscoped public fills. On
invalidation old fills can return to their original request but cannot publish.
Alternatives: hold a global lock across provider calls (serializes tenants),
persistent per-tenant generations (growth), new Redis cache/invalidator (larger
operational change without measured need).
Benefits: explicit race protection, no new dependency, bounded idle metadata.
Costs/risks: an unrelated invalidation can suppress a public direct fill; already
running reads and other processes can remain stale. TTL is still required.
Migration impact: none; cache is disposable. Reversibility: application revert.

## ADR 003 — Native offline staging with guarded synthetic ownership

Context: old facade/schema81/83 cannot validate native MFA/Storage/PostgREST;
dedicated VM has no default route or DNS and shares a physical HDD with the host.
Decision: independently named native services, generated private credentials,
marked database, pinned imported images, no-network source-overlay build, internal
bridge plus loopback-only proxies; preserve existing staging and production.
Alternatives: relabel synthetic facade as parity (insufficient), alter production
routing for registry access (outside scope), provider replacement (unproven).
Benefits: real authentication/RPC/storage/worker/recovery interactions; reproducible
configuration. Costs/risks: reused base dependencies, incomplete external services,
HDD/noisy resource limits and same-host failure domain. Fresh locked CI image
build and complete restored-app acceptance remain distinct gates.
Migration impact: staging-only synthetic history initialization; never a production
cutover. Reversibility: stop owned project and preserve volumes/evidence.

## ADR 004 — Withdraw an unproven admin count optimization

Context: requesting count metadata on a page could eliminate a sequential count
request; native semantics passed but controlled comparisons showed no stable
latency gain and worse observed tails.
Decision: restore baseline service exactly, retain pagination/error contracts
and benchmark evidence. Alternatives: keep fewer network calls as a presumed gain,
add concurrency/SQL paths without profiling. Benefits: avoids a measured concern;
maintains reviewable evidence. Cost: duplicate read remains. Risk:60-request samples
are noisy; no general query-performance conclusion is warranted.
Migration impact: none. Reversibility: future profiling may justify a revised
implementation independently tested against the native provider.
