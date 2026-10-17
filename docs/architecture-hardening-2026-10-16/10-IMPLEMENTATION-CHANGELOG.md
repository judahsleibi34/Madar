# Implemented changes

## Request and configuration security

`services/runtime_config.py` rejects CSRF origin checking disabled, missing-origin bypass enabled, unsafe origins in either consumed frontend/CSRF list, embedded credentials, malformed ports/IPv6, query/fragment and whitespace/backslash. Errors expose configuration names, not values. `request_security.py` rejects malformed explicit Origin without falling back to a trusted Referer; absent-Origin Referer compatibility remains. Secure cookies use one boolean parser/default for Auth and CSRF, including staging. Tests cover accepted and rejected paths.

Deployment implication: review production-like configurations before adoption. Unsafe CSRF bypass/origin settings now stop startup. No production settings were read wholesale or changed.

## Cache correctness

Catalog and calendar caches fence in-flight fills during invalidation and clear. Snapshot loads run outside the cache lock; publication is conditional on the same live fill set. Tracking exists only for active fills and is removed even after exceptions; repeated invalidation of new tenants cannot grow an idle generation dictionary. Calendar cache additionally checks the expected tenant before reusing a key. In-flight callers may finish with their old snapshot; the snapshot cannot replace newer shared state. TTL and existing API remain intact. Multi-process invalidation remains bounded by TTL, not globally immediate.

## CI coverage

Converted21 previously undiscovered function tests to existing `unittest.TestCase` conventions without adding dependencies or weakening assertions. Notification monkeypatch fixtures use unittest patch cleanup; route tests install explicit canonical commercial fixtures. New AST-based discovery-contract test rejects future silently omitted top-level tests unless the module supplies `load_tests`.

## Public-store direct cache fills

`public_site_routes.py` has two direct writers outside the get-or-create helper:
identity resolution (tenant unknown until lookup) and catalog price bounds.
Both now capture a bounded global generation before provider reads and suppress
publication if any tenant invalidation/clear intervenes. Warm entries for other
tenants remain untouched. Added route-level mutation interleavings and direct
publication tests:31 focused cache/catalog tests PASS on native staging's isolated
test container. The initial focused invocation used identical placeholder keys
and correctly failed startup validation; distinct CI placeholders fixed the command.
An already-running request can still return its pre-mutation snapshot; this
change prevents that snapshot from repopulating the cache. Cross-process immediate
invalidation remains unimplemented.

## Measured admin-query experiment withdrawn

Commit595dff8d requested an exact count on the existing page query to avoid a
second provider round trip. Native pagination behavior passed, but repeated
same-stack comparisons showed no stable latency benefit and worse observed
admin tails (DB2CPU experiment p95 baseline391.888ms/candidate468.463ms).
The runtime service is restored byte-for-byte to baseline876b65e7; three
pagination/filter/empty-offset/error-redaction contract tests are retained.
No latency improvement is attributed to the withdrawn implementation.

## Native staging isolation and resource validation

Added real two-tenant builder access checks and controlled owned-Redis failure
and recovery. Provider startup now checks the disposable database marker before
native Auth/Storage migrations can execute. Eight orchestration safety tests
PASS. PostgreSQL is bounded at2CPU/768MiB after observed throttling at1CPU;
Auth remains1CPU/192MiB. Staging-only pg_stat_statements exports query IDs and
aggregate costs without SQL text. The benchmark rejects anonymous session-status
HTTP200, records effective provider quotas and CPU throttling. None of these
changes touch production configuration or authorize production resource changes.

## Continuous SQL rehearsal gates

Backend Check now runs existing validated115/145/146 disposable SQL rehearsal
scripts sequentially, each with a10-minute timeout, using its freshly locked
backend test image. The deterministic preflight also checks the existing forward
release contract. No production deployment workflow or automatic promotion was
added. Exact script bodies ran successfully on the clean staging candidate;
GitHub-hosted fresh-build execution is reported separately from that evidence.

## Staging artifact provenance

Final image inspection found inherited base-image release SHA/build labels even
though OCI revision and runtime environment correctly identified the candidate.
The staging Dockerfile now overrides both release and OCI identity/timestamp,
records the old dependency base revision separately and labels its offline source
overlay mode explicitly. This avoids presenting the old release as the newly
built artifact; it does not confer production provenance or admission authority.
