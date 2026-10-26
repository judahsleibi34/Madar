# Native reservation, inventory/order and payment integrity

## Confirmed reservation defect and correction

A clean schema147 baseline ran15 native business tests:14 PASS, one FAIL.
`update_builder_reservation_status_notified_safe` could reactivate a cancelled
exclusive reservation after another booking occupied the slot. Creation held a
block advisory lock and checked overlap, while this status mutation did neither.

New mirrored148 replaces only that routine and revokes direct runtime UPDATE on
builder_reservations. It reads identity, takes the exact creation block lock,
then locks/rechecks the row and checks the retained overlap semantics before new/
confirmed status and notification intent. Lock order avoids a cycle with an
idempotent creation retry. A changed identity rejects instead of mutating under
the wrong block lock. Valid free/adjacent/nonexclusive behavior is preserved;
existing overlaps are not silently repaired. Backend maps capacity conflict to409
without exposing provider detail; tenant and entitlement checks remain unchanged.
Normal SDK status/cancellation and atomic record-ownership updates already use
security-definer RPCs. The direct-update fallback is only for in-memory tests.
No immutable001–147 SQL or existing manifest was edited.

## Native evidence

`BACKEND_TEST_IMAGE=madar-schema136-preparation-test:working bash web/scripts/rehearse_migration_148.sh`
creates a new marked, loopback-only768MiB/0.75CPU PostgreSQL container on the
verified staging VM. It runs146→147 upgrade/ownership tests first, proves148
function/ACL/schema rollback, applies148, executes business tests, and verifies
second148 execution refuses. Every Python connection checks loopback and the
synthetic DB comment before fixture writes. Owned resources are cleaned on exit.
Create/start are separate so port-allocation failures also clean the owned
container. No existing staging/production database or customer data is selected.

Expanded run:22 native business tests PASS,3.066s, plus5 upgrade and17 notification
fencing tests. Covered:

- Concurrent exclusive capacity-one bookings, exact reservation replay/event
  deduplication, adjacent slots, cancellation/reuse, foreign tenant denial.
- Occupied-slot reactivation rejection, free reactivation, nonexclusive capacity,
  reactivation/new-create race and a deterministic held-transaction contention.
- Direct service-role status UPDATE denial and successful guarded status RPC.
- Concurrent stock allocation, one allocation for duplicate requests, rollback of
  partial multi-item allocation/order/notification writes, one inventory restore.
- Variant stock exhaustion/restoration without modifying parent stock; foreign
  tenant product denial; decimal price and delivery-fee snapshots retained.
- Concurrent checkout/payment-event replay, COD collection replay, amount/currency/
  transaction tampering, stale event ordering, duplicate refund and paid/refund
  race, unique external transaction refusing credit to a second checkout.

No inventory or payment defect was confirmed by these tests, so their production
functions were not changed. Local_test events and a synthetic provider boundary
were used; no live charge, refund, email or push operation occurred. Tests exercise
canonical SQL financial effects, not live gateway authentication or settlement.

## Corrections during development

Initial fixture publication `{}` violated the existing homepage integrity check;
fixtures now include an actual default root page without weakening that check.
A repeated cancellation-token fixture collided across test tenants; fixture
secrets are now tenant-scoped. One overlapping rehearsal hit the fixed loopback
port; only its label-verified Created container was removed. Later runs were
serial and the creation trap was hardened. These are not product defects.

Broad hermetic suite after148/API changes:3687 discovered,727 conditional skips,
2960 executed PASS,43.335s; external attempts/sites empty. Native tests separately
execute the conditional database categories. Final committed-source reruns and
hosted CI are recorded in FINAL-REPORT.md.

## Limits

No historical overbooking repair, generalized seats>1 allocator, full external
payment webhook/settlement certification, distributed inventory integration,
load/capacity claim or production deployment follows from these scoped checks.
The existing protected controller still needs separate reviewed target148
admission and approved maintenance/backup/consumer handoff before production.
