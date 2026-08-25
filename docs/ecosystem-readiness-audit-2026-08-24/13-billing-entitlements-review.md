# Billing, subscriptions and entitlements

## Intended model

`commercial_catalog.py` is a single versioned server catalog. Base plans (`forms`, `website`, `business`, `business_plus`) define capabilities and allowances; add-ons extend them. Routes call `require_entitlement`, `require_any_entitlement` and quota resolvers server-side. The frontend consumes `/billing/catalog` and `/billing/entitlements`; hiding is not the authorization boundary. Canonical subscription/add-on tables have tenant foreign keys, enumerated state/plan checks and database functions for atomic commercial changes. No tenant has multiple active subscriptions.

## Effective production model — High blocker

`get_tenant_entitlements` falls back to `_unmigrated_compatibility_state` when canonical rows are absent/ambiguous. That state grants every capability except private Drive, OCR, hosted mailbox and custom domain, plus 5 GiB storage (`entitlement_service.py:23-29,153-173,256-264`). A tenant with add-ons but no active base can receive the same grandfathered base.

Live aggregate evidence:

- tenants: 11;
- tenants with any canonical subscription row: 1;
- tenants with active canonical subscription: 0;
- tenants with active legacy feature: 0;
- no duplicate active subscriptions.

Thus current paid capability enforcement is compatibility access, not subscription enforcement. It includes forms, publishing, reservations, exports, charts and AI analytics. `review_required` informs the UI but does not deny the capability.

The public runtime separately stays available on entitlement dependency 503 when a publication is already bound. That is a defensible availability policy if documented; it should have a maximum grace/cache state and alerts. It does not justify granting unpublished/admin capabilities.

## Required transition

1. Create/review one canonical base subscription state for every tenant and explicitly migrate approved grandfathering.
2. Change missing, malformed, duplicate or dependency-unknown states to deny privileged mutations and new usage. Keep only a narrowly documented, time-bounded existing-publication availability exception.
3. Database-enforce at most one active base subscription per tenant (partial unique index) in addition to application checks.
4. Test active, expired, suspended, cancelled, grace, malformed, missing, duplicate and provider-outage states for every route capability and allowance.
5. Reconcile UI with the same returned capability document and remove test-only compatibility from production behavior.

G15 is **FAIL (High)**.
