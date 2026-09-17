# Canonical entitlement current state

## Authoritative resolution path

`services/entitlement_service.py` is the server authority. It reads `tenant_subscriptions`, validates one entitlement-bearing base row, adds only explicit active `tenant_addons`, applies capability dependencies, and fails closed for missing, malformed, inactive, ambiguous, or dependency-unavailable state. Frontend visibility is not authorization.

Schema 083 aligns database invariants with the service:

- entitlement-bearing states: `active`, `trial`, `grace`;
- non-bearing workflow states: `requested`, `pending_review`, `scheduled_change`, `past_due`, `suspended`, `canceled`, `expired`, `review_required`;
- advisory/operator state `grandfathered` is recorded explicitly in `tenant_entitlement_decisions` and represented as a bounded canonical `grace` subscription;
- advisory/operator state `inactive` creates a decision record but no entitlement-bearing subscription;
- a partial unique index permits at most one `active`/`trial`/`grace` row per tenant;
- a unique `mapping_key` makes an approved mapping replayable;
- plan identifiers are restricted to `forms`, `website`, `business`, and `business_plus`.

The mapping is intentionally separate from usage evidence. Usage can suggest a candidate but cannot prove a contract, payment state, grace term, or grandfather right.

## Production facts

- tenants: 12;
- entitlement-bearing canonical subscriptions: 0;
- active legacy feature rows: 0;
- one canonical non-bearing row: tenant 8, `forms/pending_review`;
- three canceled legacy rows: tenants 3, 5, and 6;
- authoritatively mapped: 0;
- human decisions required: 12.

The production schema predates the server-authoritative quiz-attempt table, so quiz-attempt usage was marked `lookup_unavailable` rather than assumed to be zero. This does not change commercial mapping authority.

## Transition support

The apply model supports `missing -> active`, `trial -> active`, `trial -> expired` through a later explicit mapping, `active -> past_due/suspended/canceled` through canonical billing state, `grace -> active`, `grace -> expired`, and `grandfathered -> canonical plan`. Resolution tests retain fail-closed behavior for duplicate and malformed rows.
