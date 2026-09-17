# Production-based forward schema-101 candidate

This source candidate starts from production baseline
`1e6b739a43759309a45ede2dff28a859209e4a64` on
`candidate/forward-only-101` in a new independent worktree. The old candidate
`c55d5a1ee37bf5044498a657c6ef51cafd43574c` supplies reviewed source patches,
not the release base or migration history.

## Immutable production lineage

All 198 migration files numbered 001..099 in both trees are identical to the
production Git blobs, including their original line endings. Historical SQL is
marked `-text` to prevent Git normalization; new migrations use LF. The existing
004/005 swap is preserved. `production-001-099.json` records each baseline hash.

- 097 verified loyalty: `d4068175a555f610e590a94313ed600fcfac2f54b3fe902da1f6539fe227870e`
- 098 visit counters: `28f0f8c2fc6b47501dc5d8622897a0ebd6cb2b6185b2d89dd7cedffdf09f9b8b`
- 099 commercial ledger: `a94a58c0aa112946ebc1abe00d2438ff354e64448c3ceef4b9115c2ed588294f`

The release manifest is `migrations-100-101.json`. It applies only 99->100->101;
no migration above 101 is included. Migration 100 replaces the visit RPC without
recreating counters. Migration 101 introduces variant presentation; commercial
schema 099 is never interpreted as evidence that display/color columns exist.
Legacy text saves fall back to the original aggregate; color saves require the
new RPC and report migration 101 when it is unavailable.

## Source port and commercial compatibility

The port includes the authenticated checkout/loyalty tuple unpacking,
merchant variant matrix and color validation, storefront presentation, product
media, commerce navigation/loading and account-scoped administration caches.
Three-way source merging retains production commercial access, tenant selection,
financial retention, operational backup and recovery functionality. The route
conflict retains WorkspaceCapabilitiesProvider and WorkspaceRouteAccess.

Product-media uploads use the production `ecommerce_management` entitlement,
authenticated tenant/role guard, commercial revision, private no-store response,
rate limit, storage reservation and audit. They do not require the builder image
upload entitlement. A denial regression proves no storage is reserved.

The current bridge supports ordinary schemas 81..101, with rollback compatibility
bounded at 99; its forward manifest source is strictly 99. Historical schema-96
recovery tests retain an explicit historical contract, not the current manifest.
The corrected reconciliation accepts real completed execution or the canonical
already-at-target coordinator outcome, never a fabricated execution file.

## Reproducible local source validation

Use the official backend workflow image and no-external-network runner with its
exact environment and mounts. Source qualification includes 1,580 backend tests
(15 expected opt-in/host skips), the complete frontend suite, lint, shipped
high-severity dependency audit, and both backend and frontend production builds.
The frontend production image requires the canonical public API-origin audit.

Run deterministic validators:

```text
python web/scripts/generate_commercial_contract.py --check
python web/scripts/check_privileged_inventory.py
python web/scripts/check_dependency_locks.py
python web/scripts/check_migrations.py
python web/scripts/check_migration_transitions.py
python web/scripts/check_forward_release.py
python web/scripts/check_secret_hygiene.py
```

The privileged inventory gate runs on official Linux, where canonical inventory
paths use forward slashes. `check_forward_release.py` has negative regressions
for rewriting immutable 098, an unexpected 102, reordered manifest entries and
a bridge excluding source 99.

Run database proofs only on self-created, network-isolated disposable targets:

```text
python web/scripts/rehearse_migration_101.py
python web/scripts/rehearse_authenticated_checkout.py
```

The checkout script uses the official test image, configurable through
`BACKEND_TEST_IMAGE`. It runs all six HTTP/database regressions, including COD,
correct profile/store association, inventory decrement/restoration, eligibility,
delivered-and-collected earning, guest behavior, and exactly-once replay.
The upgrade rehearsal seeds real products, explicit variants, orders, inventory
movements, counters, commercial payment/access/event/revision and audit records
at schema 99. It restores a verified custom-format source dump, applies 100/101,
compares pre-existing data, checks commercial RPC identity, color constraints and
atomic V2 saves, then replays 001..101 into a separate fresh database. Both
scripts remove only their newly created disposable containers.

## Scope of qualification

This is source work only. No production/staging application or database was
accessed, migrated, reconciled or refreshed. No protected environment values or
production/staging credentials were used. Production configuration, operational
backup/off-host copy, and live acceptance are unqualified by this source run.
The next staging qualification must use the canonical production lineage and
this candidate; earlier staging schema-099 variant evidence is not transferable.
