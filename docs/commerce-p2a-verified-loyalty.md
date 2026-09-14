# P2-A verified customer identity and loyalty core

P2-A binds loyalty only to Madar's existing verified account identity:
`(store tenant_id, public.users.id)`. Checkout email and phone fields remain
untrusted delivery contact data and are never used to find or merge a loyalty
account. Guests can continue to check out and receive no loyalty benefits.

The append-only loyalty ledger is authoritative. `ecommerce_loyalty_accounts`
is a locked/versioned projection; deterministic event keys make earning,
threshold consumption, and forced-revocation compensation exactly once. Points
are whole integers calculated as `floor(collected product total after discounts
* earning basis points / 10000)` and are awarded only after an order is both
delivered and collected, regardless of which condition occurs first.

Each merchant save creates a new immutable rule version. A threshold crossing
consumes one threshold and creates at most one active equivalent entitlement.
Entitlements snapshot their product, fixed 10% discount, threshold, and validity
terms. They remain reusable while active; normal expiry does not restore points.
A forced merchant revocation restores the consumed threshold once through a
compensating ledger entry.

Checkout applies an eligible entitlement automatically and authoritatively to
the selected product and all its explicit variants. Each order item snapshots
list price, discount amount/source, entitlement ID, final unit price, quantity,
and line total. Client-submitted discount fields are forbidden by the public
checkout request model and ignored by the database function.

Returns and refunds remain outside P2-A. A later returns workflow must append
explicit earning-reversal transactions instead of editing ledger history.

Migration 097 is local-only until the standard bridge-first release process is
approved. Do not run `supabase db push` to compensate for a schema-state or
migration-ledger mismatch.
