# Madar pricing and entitlements implementation

**Implementation date:** 2026-07-30 UTC

**Pre-migration hardening rehearsal:** 2026-07-31 UTC

**Authorized live migration execution:** 2026-07-31 UTC

## 1. Executive summary

This work introduces a compatibility-first, server-authoritative commercial
catalog and entitlement architecture for the finalized Forms, Website, Business,
and Business Plus plans. It preserves manual activation, existing billing
records, published sites, and operational abuse controls. Project counts remain
unmetered because no customer-facing numeric limit has been approved.

This document is updated throughout the implementation and records validation
results and remaining limitations without treating unfinished work as complete.
Migrations 071 and 072 were applied to Madar's single shared live database only
after a fresh verified backup and disposable rehearsals. Application code was
not deployed or restarted.

## 2. Git state before implementation

- Checkout: `/home/madar/saas/Madar-dev`
- Branch: `builder-backend`
- Initial commit: `3a84a286be8de435095c125fc7963a2f12a69e49`
- Initial worktree: clean
- Initial remote relationship after fetch: zero unique local commits and ten
  commits behind `origin/main`
- Safe update: fast-forward-only to
  `92b90bcceda9405441f50f68ae69bbab8331373a`
- No merge commit, rebase, reset, stash, commit, or push was used.

## 3. Existing billing architecture

The legacy `features` table stores full-platform or individual-builder selections
with `pending`, `active`, `past_due`, `canceled`, or `expired` states.
`POST /billing/checkout` saves a pending manual request; no payment provider or
automatic charging is present. Existing publishing enforcement reads those
records behind a deployment switch. Public pricing and the backend use
conflicting hard-coded plan vocabularies.

## 4. Canonical catalog design

`backend/services/commercial_catalog.py` is the versioned application catalog.
It uses stable identifiers, integer USD minor units, explicit capabilities,
exact byte/token allowances, public/coming-soon state, display order, and an
effective date. The backend exposes it read-only; React consumes the API rather
than maintaining prices independently.

Mutable tenant state is stored in normalized subscription, add-on, address,
usage, and token-accounting tables. Legacy records remain readable during a
compatibility phase. A tenant with a canonical subscription is evaluated from
the new model; an unmigrated tenant receives explicit legacy/grandfathered
behavior rather than a destructive inferred conversion.

## 5. Final plan matrix

The catalog version is `2026-07-30`, the currency is USD, prices are integer
minor units, and the interval is monthly.

| Plan ID | Price | Storage | Website | Data tools | Reservations/calendar | Operators |
|---|---:|---:|---|---|---|---:|
| `forms` | $15 | 1 GiB | Hosted public form links only | Import and standard analysis | No | 1 |
| `website` | $20 | 2 GiB | Builder, one published site, standard path, images | Response tools only | No | 1 |
| `business` | $25 | 5 GiB | Everything in Website | Import, standard/expanded analysis, cleaning, charts, exports | No | 1 |
| `business_plus` | $30 | 5 GiB | Everything in Business | Everything in Business | Requests, management, internal calendar, analytics | 1 |

Forms, form submissions, and reservation requests have `null` commercial
allowances: they are not monthly quotas. Existing request, payload, file,
field-count, spam, idempotency, and abuse controls remain active. Aggregate
counts are written best-effort to `commercial_usage_monthly`.

Active builder-project counts are deliberately unmetered. A project can contain
pages, forms, and drafts, and no approved numeric project policy exists.

## 6. Add-on matrix

| ID | Price | Allowance/capability | Public state |
|---|---:|---|---|
| `branded_madar_subdomain` | $5/month/site | One branded Madar subdomain; requires builder | Available for manual request |
| `additional_storage_5gb` | $5/month | +5 GiB per quantity | Available for manual request |
| `additional_workspace_seat` | $3/month | +1 workspace seat | Coming soon; admin-assignable |
| `workspace_seat_pack_5` | $10/month | +5 workspace seats | Coming soon; admin-assignable |
| `ai_analytics_starter` | $5/month | 500,000 standard tokens/UTC period | Available for manual request |
| `ai_analytics_plus` | $10/month | 1,500,000 standard tokens/UTC period | Available for manual request |
| `ai_token_pack_750k` | $5 one time | 750,000 tokens in an assigned period | Available for manual request; requires active AI package |
| `google_drive_private` | Indicative $5 | Private Drive connection | Coming soon; not activatable |
| `ocr` | TBD/page | Arabic, English, Hebrew | Coming soon; not activatable |
| `hosted_email_mailbox` | TBD/mailbox | Hosted mailbox | Coming soon; not activatable |
| `custom_domain` | TBD/site | Customer-owned domain | Coming soon; not activatable |

WhatsApp is absent from the catalog and current pricing/My Plan surfaces.

## 7. Hosted-address architecture

Migration 071 adds `website_settings.standard_path_slug`, backfills it from the
legacy identifier or the deterministic `site-<tenant_id>` fallback, normalizes
whitespace/case and replaces unsupported character runs with hyphens, rejects
reserved/invalid values, and enforces global case-insensitive uniqueness.
Collisions receive a deterministic tenant suffix, including collisions with
another tenant's generated fallback. The existing `/site/:identifier` frontend route and
`/sites/:identifier` backend API now resolve the standard slug first, with a
legacy subdomain fallback during transition.

`frontend/src/utils/hostedAddress.js` generates the path address. Publishing
continues to require a published project and the existing validated,
revisioned, filtered public schema. Archived and unpublished projects remain
unavailable.

## 8. Standard path versus premium subdomain

`standard_hosted_address` is included only in Website, Business, and Business
Plus. Forms may configure the same safe tenant identifier solely so its hosted
public-form links can function; that does not grant website publication.

Changing `website_settings.subdomain` requires
`branded_madar_subdomain`. Public resolution detects a branded request from the
trusted forwarded host/host/origin and calls the same backend entitlement check.
Migration 071 does **not** commercially grandfather every historical hostname.
It separately records `legacy_subdomain_routing_preserved=true` and a
`branded_subdomain_commercial_status` of `pending_review`. A currently published
legacy binding continues resolving only through the compatibility path while
pending review. Unpublished/archived content does not resolve. New assignment or
change still requires the paid add-on or an explicit administrator-reviewed
`grandfathered` status; `removed` disables compatibility. Wildcard routing is
not changed.

The frontend labels `madarportal.com/site/name` as the included address and
`name.madarportal.com` as the paid branded Madar subdomain. Customer-owned
domains remain future functionality.

## 9. Existing-tenant migration strategy

Migration 071 is additive and idempotent in the rehearsed scenarios. It never edits or
deletes legacy `features` rows and does not automatically activate a new base
plan. It inserts a review record and a recommendation only.

| Legacy signal | Recommendation | Automatic entitlement behavior |
|---|---|---|
| `forms_data`; individual `forms` or `data` | Forms | Read-compatible until admin confirmation |
| `cms`; individual `website` | Website | Read-compatible until admin confirmation |
| `cms_plus` | Business | Read-compatible until admin confirmation |
| `complete`; individual `reservation` | Business Plus | Read-compatible until admin confirmation |
| `starter`, `pro`, `business`, multiple active rows, or conflicting/unknown active values | None/review required | Compatibility only; no destructive inference |
| No active legacy row | No mapped review record | Compatibility only; administrator decision required |

Only the single active legacy `features` row can produce a recommendation.
Inactive history is retained in `legacy_records` but cannot raise or change the
plan. The exact active row is copied into `active_legacy_record` and identified
by `active_legacy_feature_id`. Multiple active rows and unknown/ambiguous active
labels are `review_required`; tenants without an active row are not marked
`mapped`.

Existing branded routing is recorded separately as pending review, not as a
paid exception. Existing files are not removed, and a tenant remains on a
legacy compatibility allowance until a canonical base plan is deliberately
activated. Administrators inspect
`GET /admin/billing/tenants/{tenant_id}/commercial-state` and
`legacy_billing_migration_reviews` before assignment.

Dry-run/reconciliation query:

```sql
select tenant_id, recommended_plan_id, migration_state, reason, legacy_records
from public.legacy_billing_migration_reviews
order by migration_state desc, tenant_id;
```

## 10. Backend entitlement enforcement

`backend/services/entitlement_service.py` computes explicit capabilities.
Canonical active records take precedence; inactive, past-due, suspended,
canceled, and expired records do not grant paid capabilities.

Enforcement is present at project creation, image upload, website/form
publication and public resolution, response management, data import/standard
analysis/cleaning/charts/exports, reservation publication/submission/management,
calendar entry points, storage reservation, premium address change/resolution,
and AI reservation. Client feature flags are ignored.

Public form/reservation writes are never rejected by usage totals. A billing
dependency outage is fail-open only for an already-published runtime record; an
authoritative inactive state still fails closed. Entitlement reads are currently
fresh rather than cached, so no entitlement cache invalidation is required.

## 11. Storage calculation

Quota is exact bytes:

```text
base plan bytes + quantity(additional_storage_5gb) × 5 × 1024³
```

`storage_quota_service` supplies that tenant quota to the existing locked
reservation/finalization/release RPCs. Downgrades do not delete data. Reads and
deletion remain possible, while new reservations fail if used plus reserved
bytes exceed the new allowance. Existing tenant/user isolation, disk-floor
checks, content hashes, and failed-write release remain intact.

The authoritative commercial row is exactly `scope_key='tenant' and user_id is
null`. Tenant usage is not summed with hierarchical `user:<id>` safety rows.
Commercial plan/add-on changes update only that tenant row's `quota_bytes`;
`used_bytes` and `reserved_bytes` are never rewritten, and per-user safety
quotas remain 1 GiB. Regression coverage uses equal physical bytes in tenant
and user scopes and proves My Plan reports them once.

## 12. Workspace-seat calculation

Capacity is:

```text
1 + quantity(additional_workspace_seat)
  + 5 × quantity(workspace_seat_pack_5)
```

Usage counts accepted active `tenant_memberships` only. Public-site users and
site-role memberships are separate tables and do not consume seats. Pending
invitations do not consume seats.

The repository does not yet have a complete customer-facing tenant invitation
and activation lifecycle. This implementation provides authoritative capacity,
usage, and availability primitives but deliberately keeps both seat products
unavailable to public purchase. Atomic invitation acceptance, last-owner
removal integration, and their concurrency tests remain prerequisites before
selling seats.

## 13. AI token-accounting design

Migration 071 adds model multipliers, allocations, reservations, and an
immutable ledger. The application creates one idempotent monthly allocation on
first use of each UTC period for the active Starter/Plus package through
`ensure_ai_monthly_allocation`. A partial unique index allows only one active
monthly allocation per tenant/period, and package changes revoke the previous
period allocation under the tenant/period lock. Admin-assigned packs preserve
their period and allocation history.

Before provider execution, the backend reserves a conservative maximum under a
tenant/period advisory lock. Finalization uses the same lock namespace, then
locks the reservation, and remains idempotent by request ID. It records
provider/model/user/tenant/period/request/operation/status plus actual standard
tokens, reserved capacity applied, additional capacity applied, covered tokens,
and an explicit deficit.

Actual trusted provider usage is always written, even above the reservation.
Additional available allocation is consumed atomically; if it is insufficient,
the ordinary balance remains zero and the remainder is written to
`deficit_standard_tokens` rather than rejected or lost. Concurrent finalizers
cannot cover more than the allocation.

Expired reservations stop consuming capacity automatically and are marked
`expired` on the next accounting operation. A repeated reserve for an expired
ID is rejected before provider execution. Because finalization is
service-role-only and receives server/provider-derived usage, a provider call
that completed after expiry (or after an explicit release) may still be
finalized; reused capacity becomes a recorded deficit. Genuine abandoned
reservations therefore release capacity, late completion is not unmetered, and
late duplicate finalization returns the existing ledger result.

Provider metadata is preferred and captured in the Gemini planner. If metadata
is absent, UTF-8 input/output is conservatively estimated server-side and marked
`estimated=true`. Provider exceptions consume nothing when usage is unknown;
confirmed metadata is finalized as `provider_error`. No client count is trusted.
The current route is non-streaming; future streaming endpoints must use the same
reservation contract.

Normalization uses scaled integer millionths from a versioned table:

```text
ceil((input × input-micros
    + cached-input × cached-micros
    + output × output-micros) / 1,000,000)
```

Legacy daily question/message counters remain for historical schema
compatibility and noncommercial code-generation safeguards, but the commercial
AI route passes zero usage counters and does not enforce question counts.

## 14. Billing states

Canonical states are `requested`, `pending_review`, `active`,
`scheduled_change`, `past_due`, `suspended`, `canceled`, `expired`, and (for
subscriptions/reconciliation) `review_required`. Only `active` grants access.
An advisory lock and partial unique index ensure one active base plan per
tenant. Add-ons have nonnegative quantities and active recurring uniqueness.
Starter and Plus share the `ai-analytics-package` advisory-lock namespace and a
database partial unique index on tenant ID ensures at most one active recurring
AI package even if application serialization is bypassed.
Administrative assignment preserves old rows as scheduled history and uses
idempotency keys.

No automatic card charging, renewal, invoice, card field, or fabricated payment
data was added.

## 15. API changes

Customer/read APIs:

- `GET /billing/catalog`
- `GET /billing/current-plan`
- `GET /billing/usage`
- `GET /billing/entitlements`
- `GET /billing/add-ons`
- `POST /billing/plan-request`
- `POST /billing/add-on-request`

Administrative APIs (system admin plus AAL2, audited):

- `POST /admin/billing/subscriptions`
- `POST /admin/billing/addons`
- `POST /admin/billing/token-packs`
- `POST /admin/billing/token-adjustments`
- `POST /admin/billing/subdomain-grandfathering`
- `GET /admin/billing/tenants/{tenant_id}/commercial-state`

Public customer requests create pending manual-review records only.

## 16. Database migrations

Migration `071_create_commercial_entitlements.sql` exists identically under
`database/migrations/` and `supabase/migrations/`. It adds:

- `tenant_subscriptions`, `tenant_addons`, `billing_addon_requests`;
- `legacy_billing_migration_reviews`;
- deterministic standard-path fields/constraints and hosted-address review
  provenance;
- `commercial_usage_monthly`;
- AI multiplier/allocation/reservation/ledger tables;
- locked usage, monthly-allocation, token, plan, and add-on RPCs.

All new commercial tables have RLS enabled. Mutation rights and security-definer
RPC execution are revoked from public/anon/authenticated and granted only to the
service role. Sequence grants are limited to the six identity sequences created
by 071; the prior schema-wide sequence grant was removed. Tenant-scoped indexes
and nonnegative/integer constraints are present. The migration has not been
applied outside disposable rehearsal databases.

Final mirrored SHA-256 after hardening:
`b76c139ca1bcf25e09527eee6ceb071d17c01da481e20c624c70d8fdbeff9704`.
Migration 071 was applied to the live database at 2026-07-31T12:06:57Z,
followed by migration 072; execution completed at 2026-07-31T12:07:35Z.
Migration 072's mirrored SHA-256 is
`54b7e653a4d8e78290a79e906e9a5599b0f6427c4f8fe7ab98f067f35e702953`.

## 17. Frontend changes

The pricing page fetches prices, allowances, product state, ordering, and
catalog-owned feature keys from `/billing/catalog`; React contains only
localized labels. It shows the four final plans, manual activation, fair-use
qualification, standard versus branded address, AI add-ons, and unavailable
email/custom domains.

My Plan fetches the catalog, current plan, usage, entitlements, and add-ons. It
shows real activation state, storage, seats, address eligibility, token period
and balances, active/future add-ons, and informational operational counts. Fake
cards and renewal dates were removed.

Signup, Website Settings, and builder publication copy use the standard path.
Premium Madar subdomains are not called custom domains. No purchase control is
shown for future products.

The administrator user-management plan editor also fetches the canonical
catalog, displays canonical plans/states, and assigns through the new
AAL2-protected subscription API. The admin user list returns the tenant's
canonical subscription alongside legacy feature rows during compatibility.

## 18. Tests added

Coverage includes catalog IDs/prices/states/no-WhatsApp, capability matrices,
forged client flags, exact storage/add-on aggregation, seat calculations,
reviewed grandfathering versus routing compatibility, operational no-quota
behavior, model normalization and estimation, atomic monthly AI allocation,
token hard stop/finalization/release/error/overrun/deficit/expiry behavior,
standard path resolution, malformed/duplicate/uppercase/whitespace/reserved/
empty legacy identifiers, premium subdomain enforcement, storage downgrade, and
updated pricing/My Plan/settings UI behavior.

## 19. Test and build results

- Migration ledger: pass, 72 mirrored migrations; two known historical
  duplicate-content warnings for migrations 013/014.
- Dependency locks: pass.
- Python syntax: pass using an isolated bytecode cache (repository caches are
  root-owned).
- Disposable migration rehearsal: **passed** using `postgres:17-alpine` on a
  tmpfs-backed, non-published Docker container. It applied 001–070, seeded the
  scenarios below, proved a deliberately failed 071 transaction left neither a
  new table nor column, applied 071, ran assertions, reapplied 071, and ran
  concurrent accounting/package tests.
- Backend complete suite: **799/800 passed**. The sole failure is the same
  pre-existing synthetic unhandled-exception CORS-header assertion in
  `test_app_middleware`; no CORS or middleware source changed in this work.
- Entitlement-focused backend set: **41/41 passed** after hardening (commercial
  catalog/entitlements, AI token metering, and website/public routing).
- Frontend Vitest: **476 passed, 1 skipped** across 80 files.
- Frontend production build: pass; only existing large-chunk warnings remain.
- Frontend lint: **pass with zero errors and zero warnings** on the final
  worktree. The previously recorded 9 errors and 4 warnings did not reproduce
  after the complete preserved implementation was assembled; lint rules were
  not weakened.
- Backend `pip check`: the earlier implementation run passed. A final rerun was
  blocked by the execution environment's Docker approval/usage limit after all
  migrations and application suites completed; this limitation is reported,
  not treated as a pass.
- Base Compose config: pass. Development overlay plus base: pass.
- `git diff --check`: pass.
- Targeted secret scan: pass; no private-key, common provider-key, or JWT-shaped
  material found outside excluded environment/dependency/build paths.
- `npm audit`: fail with six current findings (one low, one moderate, four
  high), all reported as having fixes available. No automatic dependency
  changes were made.

The incoming `test_ecommerce_routes.py` used pytest-style functions even though
the locked backend CI image and runner use unittest and do not install pytest.
It was converted mechanically to unittest so its six existing assertions now
execute in the established suite; e-commerce application behavior was not
changed.

## 20. Operational rollout order

Steps 1-3 below were completed on 2026-07-31. Remaining rollout starts at step
4; production application code has not been deployed.

1. Back up the database and verify both migration trees/checksums. **Complete.**
2. Apply migrations 071 and 072 in a controlled database change window.
   **Complete.**
3. Verify the ledger, validated slug constraint, narrowed grants, RLS,
   deterministic backfill, publication review state, and active-only legacy
   review results. **Complete.**
4. Deploy the backend in compatibility mode. Do not deploy the new frontend yet.
5. Inspect every review-required tenant, current storage use, publication
   binding, and active legacy feature. Assign canonical plans/add-ons with
   unique idempotency keys only after human confirmation.
6. Allocate any manually purchased current-period token packs. Monthly package
   allocations are created on first AI use.
7. Verify standard-path and pending-compatible legacy branded-host resolution.
   Explicitly approve or remove each commercial grandfather status, then verify
   forms/reservations, storage reservation, My Plan APIs, and audit events.
8. Deploy the frontend.
9. Re-run smoke tests and clear only public-site/catalog caches if operational
   tooling shows stale content. Entitlement evaluation itself is uncached.
10. Continue reconciliation; canonical records automatically become
    authoritative per tenant. Remove broad legacy compatibility only in a later
    reviewed release after the review table is empty.

Production automation does not apply database migrations automatically.

## 21. Feature flags or deployment requirements

Migrations 071 and 072 are now present before deployment of these backend routes. Existing
`CALENDAR_FEATURE_ENABLED` and AI provider configuration still govern runtime
availability in addition to entitlements. No production environment variable,
deployment script, or service was changed.

Compatibility is data-driven: tenants without a canonical plan remain legacy
or grandfathered; assigning a canonical active plan enables strict evaluation
for that tenant. There is no global switch that could accidentally flip every
tenant at once.

## 22. Known limitations

- The tenant invitation/membership lifecycle is incomplete; public seat
  purchases and atomic activation enforcement are deferred.
- Negative token adjustments are intentionally unsupported by the positive-only
  allocation schema; revocation is performed by marking an allocation revoked.
- No payment provider, invoices, renewal scheduler, tax, or automated dunning
  exists.
- Project quantities remain unmetered pending a founder-approved definition.
- Customer-owned custom domains, hosted mail, OCR, and private Drive are catalog
  placeholders only.
- The standard path schema is live and end-to-end development tests pass, but
  the development backend/frontend still require controlled deployment before
  the feature can be called production-ready.
- The full migration rehearsal uses upstream PostgreSQL with minimal local
  Supabase-compatible `auth`/`storage` scaffolding. A final staging rehearsal
  against the project's actual Supabase version and installed extensions is
  still required before production.
- There is no entitlement cache. This favors correctness now but may require a
  bounded, invalidated cache at higher scale.
- `npm install` reports six dependency audit findings (one low, one moderate,
  four high); they were not auto-fixed because that could introduce unrelated
  dependency changes.
- Existing lint debt remains as listed in the validation results.
- `frontend/src/content/pages/myPlanContent.js` and the legacy plan/builder
  exports in `frontend/src/content/dashboard/userManagementContent.js` remain
  unused compatibility content. Current My Plan, pricing, and admin plan UI do
  not import them; remove them only in a separately reviewed cleanup.

## 23. Files changed

Primary implementation files:

- `backend/services/commercial_catalog.py`
- `backend/services/commercial_billing_service.py`
- `backend/services/entitlement_service.py`
- `backend/data_analysis/ai/token_metering.py`
- `backend/data_analysis/ai/planner.py`
- billing/admin, builder, public-site, website, calendar, storage, and
  data-analysis route/service files under `backend/`
- migration 071 in both migration trees
- `frontend/src/components/MainPages/BasePlansPage.jsx`
- `frontend/src/components/DashboardBuilder/MyPlanPage.jsx`
- Website Settings, signup, builder publication, hosted-address utility,
  localized pricing content, API routes, and associated tests
- `README.md` and this document

No production-checkout file is part of this diff.

## 24. Manual verification steps

Against a disposable database after migration:

1. Activate each plan and compare `/billing/entitlements` with the matrix.
2. Publish a Website tenant at `/site/<standard_path_slug>`; confirm unpublished
   and archived projects return 404.
3. Confirm the branded host is 402 without an add-on, works with an active
   add-on, permits only a currently published pending-review legacy route during
   compatibility, and works for an explicitly grandfathered record. Confirm
   `removed`, unpublished, and archived cases do not resolve.
4. Create and submit multiple forms/reservations; verify counters grow and do
   not reject by monthly count while rate/payload/spam controls still reject
   abuse.
5. Reserve two concurrent uploads at the quota boundary; fail one write and
   verify reserved bytes are released.
6. Downgrade an over-quota tenant; verify read/delete works and new upload is
   blocked.
7. Exercise AI Starter/Plus concurrent assignment, package switching,
   concurrent exhaustion, retry IDs, provider failure/timeout with incurred
   usage, overrun deficits, expiry/late finalization, pack allocation, UTC
   period change, and token summary.
8. Verify every admin mutation requires AAL2 and creates an audit event.
9. Check My Plan contains no fabricated payment or renewal information.

## 25. Rollback considerations

Rollback the application/backend/frontend first while leaving migration 071's
additive tables and columns in place. The legacy `features` data was preserved,
so the prior application can continue reading it. Do not drop commercial or AI
tables until all reservations are finalized/released and subscription,
allocation, ledger, add-on, legacy review, hosted-address review, and commercial
grandfathering history is exported.

If strict enforcement exposes a reconciliation error, remove/deactivate the
incorrect canonical record through an audited administrative correction and
return the tenant to review-required compatibility; do not delete published
content or stored objects.

## 26. Pre-migration 071 hardening corrections

The 2026-07-31 review corrected every blocking issue found before migration 071
is applied:

| Issue | Correction and evidence |
|---|---|
| Inactive history influenced legacy recommendations | `legacy_summary` retains history, but `active_record` derives the recommendation solely from the exact single active feature. Rehearsal tenant 102 remained `forms` despite a newer canceled `complete` row. |
| Ambiguous legacy activation | Zero active rows are not mapped; multiple active rows and unknown/ambiguous active labels are `review_required`; no canonical subscription is silently activated. |
| Unsafe standard-path backfill | `normalize_website_standard_path_slug` trims/lowercases, replaces unsupported runs, handles empty/reserved values, caps length, and applies a deterministic tenant suffix for case-insensitive collisions and fallback collisions. |
| Slug constraint was left unvalidated | Cleanup completes before the unique index and explicitly runs `validate constraint website_settings_standard_path_slug_check`. Verification asserts `convalidated=true`. |
| Routing and commercial grandfathering were conflated | `legacy_subdomain_routing_preserved` is independent from `branded_subdomain_commercial_status`; migration starts historical routes at `pending_review`, records immutable migration provenance, and does not mark them paid/grandfathered. |
| Starter and Plus could both be active | `tenant_addons_one_active_ai_package_idx` enforces the package group in the database; `assign_commercial_addon` uses one `ai-analytics-package` lock namespace. Concurrent rehearsal left exactly one active row. |
| Monthly AI allocations could overlap after package switches | `ai_token_allocations_one_monthly_package_idx` and `ensure_ai_monthly_allocation` serialize tenant/period allocation changes and revoke the old recurring allocation before activating the new one. |
| Token overruns were rejected and lost | Finalization records full actual usage, atomically covers the reservation and additional balance, and writes any uncovered amount to `deficit_standard_tokens`. |
| Expiry could lose incurred usage | Expired capacity is reusable, but trusted service-role finalization may record late provider usage; reused capacity appears as deficit. Retry remains ledger-idempotent and an expired ID cannot start another provider call. |
| Sequence grant was schema-wide | Grants now name only the six identity sequences introduced by 071. Verification checks both `USAGE` and `SELECT`. |

### Slug collision strategy

Migration cleanup computes all assignments in a temporary map ordered by
`tenant_id,id`. The base slug is canonicalized from an existing standard slug,
then the legacy subdomain, then `site-<tenant_id>`. Empty and reserved results
use the fallback. A candidate colliding with an already assigned normalized
value receives `-<tenant_id>` (then a deterministic numeric suffix only if
still necessary). A legacy candidate equal to another tenant's future
`site-<tenant_id>` fallback is treated as a collision before that other row is
processed. The final check constraint is validated before the case-insensitive
unique index is relied upon.

The original and normalized values, collision/material-change flags,
publication snapshot, compatibility flag, and commercial review state are
stored in `hosted_address_migration_reviews`. The branded `subdomain` field is
not repurposed as the standard path.

### Grandfathering and removal policy

- `pending_review` plus `legacy_subdomain_routing_preserved=true` permits only a
  currently bound published legacy site to continue resolving.
- It does not permit creating or changing a branded hostname.
- `grandfathered` is an explicit AAL2 administrator decision with reason,
  reviewer, timestamp, audit event, and review-table update.
- `removed` prevents compatibility unless a separate active paid add-on grants
  the capability.
- Unpublished rows, archived projects, and internal/test tenants remain review
  records; they do not become commercial exceptions automatically.

### Token overrun and expiry policy

Reservation, monthly allocation, release, and finalization use the same
tenant/UTC-period advisory-lock namespace. Finalization excludes the current
reservation from other reserved capacity, calculates available allocation,
and persists:

```text
actual standard tokens
covered standard tokens
reservation-applied tokens
additional-applied tokens
deficit standard tokens
```

Ordinary remaining balance is clamped to zero; the immutable actual ledger may
exceed allocation only through the explicit deficit field. Duplicate
finalization returns the first result. Failed/time-out calls with confirmed or
partial provider usage are recorded with their actual status/source. Calls
with no confirmed usage follow the application release path.

Reservations must initially expire in the future and no more than one hour
ahead. An expired reservation no longer consumes capacity and is marked
`expired` during accounting cleanup. Late service-role finalization is allowed
because the caller supplies trusted provider/server usage, not client counts.

### Disposable database setup and seed scenarios

`scripts/rehearse_migration_071.sh` creates an isolated, non-network-published
`postgres:17-alpine` container whose data directory is tmpfs. It bootstraps only
the minimal local Supabase `auth.users`, `auth.uid()`, `storage.buckets`,
`storage.objects`, and roles required by repository migrations. It then:

1. Applies repository migrations 001–070 in order.
2. Seeds `database/verification/071_rehearsal_seed.sql`.
3. Substitutes an intentional error immediately before 071's commit and proves
   both `tenant_subscriptions` and `standard_path_slug` are absent afterward.
4. Applies 071 and runs the read-only verification plus destructive disposable
   assertions.
5. Reapplies 071 to prove the seeded state is not corrupted.
6. Runs simultaneous token finalizations and simultaneous Starter/Plus
   assignments.
7. Proves a direct second active AI-package insert is rejected by the partial
   unique index.
8. Removes the disposable container through the script's exit trap.

Seed cases include no billing row; a recognized active low tier plus inactive
higher-tier history; one recognized active plan; multiple active rows;
ambiguous active label; live published, unpublished, archived, and internal/test
sites; uppercase, whitespace, malformed, empty, reserved, duplicate-normalized,
and fallback-colliding subdomains; storage use above the new base allowance;
legacy AI usage; and existing forms, submissions, reservations, calendars, and
events.

Result: **passed**. Existing representative rows were preserved; standard paths
and the live legacy binding resolved in the database model; unpublished and
archived bindings were not made live; RLS was enabled on all ten new tables;
the slug check was validated; grants were correct; reapplication succeeded;
and the intentionally failed transaction left no partial 071 schema.

### Remaining rollout blockers

Migration application, backup, live preflight, and schema verification are
complete. Before application deployment:

1. Review all six pending branded-route commercial decisions; the routing
   compatibility flag is not a paid grandfather entitlement.
2. Decide whether the current frontend dependency audit (six findings,
   including production-reachable React Router advisories) blocks deployment.
3. Fix or formally accept the existing backend CORS test failure and production
   readiness degradation caused by the storage configuration check.
4. Deploy backend compatibility code before frontend code, then smoke-test
   standard paths, branded compatibility, forms, reservations, storage, and My
   Plan.
5. Reconcile canonical plans before enabling any stricter commercial policy.

### Files added or changed by this hardening pass

- `backend/data_analysis/ai/token_metering.py`
- `backend/routes/admin_billing_routes.py`
- `backend/routes/public_site_routes.py`
- `backend/routes/website_routes.py`
- `backend/services/entitlement_service.py`
- `backend/services/hosted_address_service.py`
- `backend/tests/test_ai_token_metering.py`
- `backend/tests/test_commercial_entitlements.py`
- `database/migrations/071_create_commercial_entitlements.sql`
- `supabase/migrations/071_create_commercial_entitlements.sql`
- `database/verification/071_rehearsal_assertions.sql`
- `database/verification/071_rehearsal_seed.sql`
- `database/verification/071_verify_commercial_entitlements.sql`
- `scripts/rehearse_migration_071.sh`
- `docs/madar-pricing-entitlements-implementation.md`

All other modified/untracked paths listed by `git status --short` are preserved
implementation work from the original commercial-entitlements and publication
isolation tasks. The authorized shared live database received migrations 071
and 072. No production checkout, running service, deployment configuration, or
remote branch was changed.

## 27. Authorized shared-database migration execution

The owner explicitly authorized use of the single shared live database because
Madar is still pre-customer and contains internal/test tenants only. This did
not reduce the production safeguards: a fresh backup was mandatory, migrations
were rehearsed and dry-run first, application services were not restarted, and
all test mutations used a transaction that was rolled back.

### Repository and pending migrations

- Branch: `builder-backend`
- Starting commit: `92b90bcceda9405441f50f68ae69bbab8331373a`
- `origin/main`: the same commit (`0` ahead, `0` behind before changes)
- Live ledger before execution: migrations 001-070
- Pending: 071 commercial entitlements and 072 publication isolation
- Official dry run listed exactly 071 and 072; the post-run dry run listed none.

### Backup gate

The successful protected backup is
`/home/madar/backups/madar-20260731T120207Z`. Its custom database dump is
837,143 bytes; the full backup directory is 26,151,726 bytes. Database-dump
SHA-256 is
`18060ae3c7452dd9cf6efc8cc8dce28adee54b456abca97e59108edf96f3aab2`.
`scripts/verify_backup.sh` passed, and `pg_restore --list` read the archive.
The backup also contains the four configured protected file trees. An earlier
attempt at `madar-20260731T120056Z` was terminated at the execution-tool timeout
and is explicitly invalid (zero-byte dump, no manifest); it was not used.

### Live preflight and migration result

Immediately before migration the database had 7 tenants, 3 canceled legacy
feature rows, 6 website settings, 5 builder projects, 5 published bindings, 5
form submissions, 0 reservations, 6 storage accounts, and zero reserved bytes.
Storage objects/reservation-history counts changed while the system remained
live, and tenant 4's used bytes increased during preflight. Migration 071 does
not update storage-account usage fields; the live application continued normal
storage writes during the observation window, so those moving values are not
misreported as migration drift.

The official Supabase CLI 2.111.0 applied 071 then 072 from
2026-07-31T12:06:57Z through 2026-07-31T12:07:35Z. Both migrations issued the
supported PostgREST schema-reload notification. The ledger contains each once
and reports no pending migration.

### Post-migration validation

- All 11 expected commercial/publication review tables exist with RLS enabled.
- The one-active-base-plan and one-active-recurring-AI-package partial unique
  indexes exist.
- `website_settings_standard_path_slug_check` is validated; six slugs are
  nonnull, valid, nonreserved, and unique case-insensitively.
- All six historical routes are preserved only as routing compatibility with
  commercial state `pending_review`; five remain published and tenant 5
  (`email`) remains unpublished.
- All three legacy feature rows remain canceled. No active canonical
  subscription or add-on was created. Three review rows explicitly say no
  active legacy record and provide no recommendation.
- `publication_integrity_reviews` contains zero live issues. Migration 072's
  historical publication constraint intentionally remains `NOT VALID`; it
  enforces new/updated rows while later explicit validation remains a rollout
  task.
- Direct sequence checks confirmed `USAGE` and `SELECT` only for the new named
  identity sequences inspected; no schema-wide sequence grant was introduced.
- The existing production backend stayed healthy at `/health/live`, retained
  database/schema/auth/Redis health, served `/public/sites/palcode`, and the
  frontend served `/site/palcode`. `/health/ready` remains 503 because its
  pre-existing storage readiness component is unavailable; this was not caused
  by the migration.

Rollback-only live AI checks on internal tenant 7 proved below/equal/above
reservation finalization, a 200-token explicit deficit, package replacement
leaving one active AI package, expired-reservation finalization, duplicate
finalization idempotency, and no negative ordinary balance. The transaction was
rolled back and follow-up counts found zero persistent test add-ons or ledger
rows.

The concise execution record is
`docs/madar-commercial-migration-071-execution.md`. The final Git commit hash is
reported by `git rev-parse HEAD` and the terminal completion report; embedding
a commit's own hash inside its content is cryptographically self-referential
and therefore not possible.
