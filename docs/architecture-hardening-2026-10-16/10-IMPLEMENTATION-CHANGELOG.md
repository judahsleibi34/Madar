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
