# Commercial product assignment and effective access

Implementation baseline: schema 114, extended by paired migration 115. This is a
backend/database foundation; the commercial administration panel is subsequent
work. No production enforcement configuration is changed.

## Authority

`tenant_subscriptions` and `commercial_catalog.py` assign the product. An
eligible assignment is active/trial/grace, has a recognized base plan and is
within any explicit assignment bounds. These states do not provide access by
themselves. There is no implicit trial or grace grant.

The existing schema-099 ledger decides whether that assignment is usable.
`resolve_commercial_access` returns the tenant revision, review state, current
hold, current half-open dated period, effective time, dated add-ons, assigned
subscriptions and next time transition in one statement snapshot on schema 115.
A usable assignment must match the period's plan. Mismatches, missing coverage,
unknown products, unresolved review and malformed state provide no paid
capabilities under normal enforcement. No payment is inferred from usage.

The access period is finite `[valid_from, valid_until)` and its existing
`effective_during` accounts for revocation. Effective add-ons are restricted to
the same statement time and their required base capability. Subscription bounds
can restrict a period further; they cannot extend it. Grandfathered hosted
addresses remain a reviewed add-on equivalent for an otherwise entitled tenant.
The existing catalog's website_publish capability governs storefront/catalog
and checkout: no separate ecommerce plan taxonomy is introduced.

## Temporary operator compatibility policy

Every runtime capability lookup first reads the ledger. An explicit hold denies
access even when `COMMERCIAL_ENTITLEMENTS_ENFORCED=false`. A verified unheld
snapshot then retains the existing temporary all-capabilities policy under that
configuration. Normal enforcement intersects assignment, dated access and dated
add-ons when the flag is true. A missing/unverifiable ledger cannot hide a hold
and returns a controlled dependency error. Review-required legacy tenants retain
compatibility access while the flag is false; clearing a hold does not mark them
reviewed. The flag's value is never changed by an admin commercial command.

## Hold and commands

Migration 115 adds a consistent tuple to tenant_commercial_state:
commercial_suspended_at, commercial_suspended_by and
commercial_suspension_reason. The timestamp is finite, actor is a restrictive
foreign key, and reason has 3–1000 non-whitespace characters. No auth or
membership field is involved.

`apply_commercial_access_command` remains the application mutation boundary.
`suspend` sets the current hold without modifying any period/payment;
`reactivate` clears it. Both preserve review state, bump revision, append a
commercial event and write an audit record in the transaction. Reactivation
clears only the hold. Expired coverage, missing assignment or unresolved review
continues to deny normal commercial capabilities. Payment or complimentary
access establishes dated evidence and marks review complete, but deliberately
does not silently clear an administrator's hold; clear it through an authorized
reactivate command after review.

Existing manual_payment, correct_payment, complimentary, revoke and
review_inactive commands retain their ledger semantics. Corrections append
payment evidence rather than edit previous payment rows. New immutable triggers
forbid update/delete of payments and access events. Period revocation remains an
explicit ledger action; temporary suspension never truncates coverage.

Dedicated routes under `/admin/billing/tenants/{tenant_id}`:

- GET commercial-state: existing entitlement/storage/usage inspection, usable
  during suspension. Assigned-product metadata remains separate from access.
- GET access-history: current ledger and the latest 100 events, periods and
  payments, each scoped to the target tenant.
- POST suspend / reactivate: reason, optional safe reference, idempotency_key,
  expected_revision.
- POST manual-payments: the same command fields plus plan, method, positive
  actual amount, dated evidence, billing months, currency and receipt. Server
  catalog pricing supplies the quote; a mismatch requires an override reason.
  The API checks that calendar-month coverage matches the billing months.
- POST complimentary-access: explicit plan and finite dates, optional period
  supersession. It does not assert that a payment occurred.
- POST revoke-access: period ID and revision-checked command fields.
- POST correct-payment: payment ID, corrected amount/evidence and command fields.
- POST review-inactive: records review only after future/current coverage has
  been revoked or expired according to the existing RPC policy.

Every route uses the existing server-authenticated platform-admin identity and
canonical provider AAL2 guard. New mutation payloads forbid extra fields and
cannot supply actor/role/AAL. The common `_commercial_command` authorization
seam can gain a Billing Admin permission later without changing ledger logic.
Existing plan/add-on assignment routes retain their existing authorization and
idempotency conventions; their changes bump the ledger revision via existing
triggers. Plan assignment no longer synchronizes a paid storage allowance from
state=active and never creates a payment/period. Storage reservations always
resolve their current commercial allowance. Retained storage is never deleted
when allowance becomes zero; usage inspection reports the effective allowance.

## Revision, replay and audit

Each new command requires a positive expected_revision in the request. The
transaction checks server actor/AAL, locks the active tenant and serializes its
ledger. An existing matching key/request returns its original durable result
before the stale revision check. Key reuse with changed request or operation
conflicts. A new stale revision raises commercial_revision_conflict and leaves
all records intact. Suspend/reactivate bump revision once; payment/period
commands may also invoke existing revision triggers, so callers use the
returned revision rather than assuming an increment of one for every operation.

Ledger events preserve actor, tenant, AAL, operation, idempotency/hash, request
ID, revision, result and timestamp. Result and transactional audit metadata
include reason, safe reference, previous/resulting snapshot and revisions.
Assignment projection and add-on snapshots exclude free-form provenance/reason
fields. Existing financial context stays bounded to amount/currency/method.
There is no separate commercial audit table. Request IDs use the existing
correlation context. Application error logs omit tokens, payment evidence and
provider exception details.

The resolver uses no process/Redis capability cache. Each relevant request
reads current revision/time; suspension/restoration takes effect on the next
request, and expiry needs no job or revision change. Internal ecommerce payload
caches remain, but the store-settings boundary checks current ledger access
before returning cached data. Public storefront response caches no longer
allow browser/CDN reuse without reaching the backend. No frontend polling or
additional bootstrap request is added.

## Public and historical operations

Website `/runtime`, bootstrap/site, public forms/quiz/drafts/submissions and new
reservations resolve canonical paid capabilities. Store profile/catalog/product,
sitemap, delivery/cart, orders, discounts and customer loyalty all use the
reauthorizing storefront boundary. Checkout fails before the order RPC on a
hold. Anonymous denial is HTTP 503 with code tenant_service_unavailable, a
generic temporary-unavailability message and no tenant/plan/revision diagnostics.
Published-runtime dependency fallback was deliberately removed: a dependency
outage cannot establish that a commercial hold is absent.

Authenticated APIs use HTTP 402 commercial_access_suspended,
commercial_access_expired, commercial_access_required,
commercial_review_required or commercial_state_invalid as applicable. AAL1
uses the existing HTTP 403 aal2_required contract; stale updates use HTTP 409
commercial_revision_conflict. Authentication, MFA, logout and membership
resolution have no commercial gate. Billing/assigned-plan/entitlement inspection
returns a normal authenticated response even when capabilities are empty.
Existing frontend HTTP error handling recognizes these as service errors;
public runtime exits its loading state and shows unavailable. The full
restricted-workspace experience remains part of the subsequent UI PR.

Builder business writes and merchant catalog/settings writes require the same
canonical capability boundary. Merchant authenticated order reads/status/COD
collection and loyalty revocation retain existing role/tenant authorization and
are explicitly treated as historical operations. No refund system is introduced;
no data lifecycle route, order history, form history, upload or public publication
is deleted. Existing static asset authorization and visitor security flows remain
separate. Robots.txt remains a generic crawler policy, not paid business content.

No commercial state is cached across tenant IDs. Tests select A/B/A through the
existing server-context boundary and verify only A is restricted. This PR does
not add a tenant-switch UI or a new membership-selection protocol; the current
membership resolver uses the authenticated server-selected tenant. Platform
commercial inspection uses its own admin context and remains usable on hold.

## Schema bridge and deployment

The candidate declares compatible schemas 114–115 and target 115. On 114 it can
read the existing ledger resolver, using the assignment reader only for normal
enforcement; commands fail with commercial_upgrade_required until 115 exposes
the contract marker. No old RPC silently ignores expected_revision.

The migration changes protected release metadata under web/deployment. A reviewed
governed control-plane upgrade is required for any future deployment. Bridge
acceptance at schema 114 and a verified source-schema-114 backup must precede
115. The prior application cannot enforce holds and its declared schema range
ends at 114. After 115, recovery is forward repair; no reverse migration or old
binary rollback is safe. Migration 114 and all previous checksum pins remain
unchanged. Production deployment, migration and enforcement activation have not
been performed.

Future payment providers must drive these same dated grant/correction records
and revision semantics through an authorized provider boundary, while respecting
explicit administrator holds. Source type cybersource remains available in the
existing schema, but provider signature/settlement integration is future work.
No third access authority is required.
