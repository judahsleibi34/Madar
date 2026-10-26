# Native business integrity

The22 existing native cases pass again both after exact146→147→148 and in the
independently restored application database. Multiple independent PostgreSQL
connections exercise real transactions/locks, not only SDK mocks.

- Reservations: concurrent capacity1 winner, duplicate booking/event retry,
  adjacent slots, cancellation/reuse, cancelled reactivation conflict,
  creation/reactivation serialization including held transaction, free/nonexclusive
  behavior, direct role update denial and cross-tenant project/status rejection.
- Inventory/order: concurrent stock allocation without oversell, variant/parent
  restoration, foreign-tenant product rejection, duplicate allocation once,
  failure rolling back inventory/notifications, idempotent cancellation and
  decimal immutable price/delivery snapshots.
- Payments: concurrent COD collection, checkout/event replay, altered/stale events,
  refund replay and refund/late-paid race, one provider transaction cannot credit
  two checkouts. Gateway responses are synthetic; no real CyberSource transaction,
  refund, paid subscription or billing activation occurs.

No additional confirmed defect justified changing financial routines or adding149.
Migration148 and PR210 behavior are preserved, not reimplemented. The tests do
not establish every gateway reconciliation/chargeback/subscription path, external
provider exactly-once semantics, full product checkout browser coverage or
production dataset correctness. See prior PR210 BUSINESS-INTEGRITY.md for the
original confirmed defect and correction; this report records rerun evidence.
