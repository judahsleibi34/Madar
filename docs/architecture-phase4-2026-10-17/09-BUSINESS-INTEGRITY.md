# Business integrity

The native schema148 suite revalidated22 real-transaction cases: concurrent
reservation capacity, cancellation/reactivation/overlap, idempotent retries,
foreign project/status rejection, variant stock allocation/restoration,
order rollback, duplicate payment/reversal/provider transaction identity and
commercial continuity. All passed with independent PostgreSQL connections.

The separate149 rehearsal executes those22 cases again after queue privilege
changes. Both schemas pass; there are no real payment/refund/gateway transactions.
The full successor rehearsal has109 successful executions,87 distinct cases,
including22 repeated business cases at the two schema boundaries.

New calendar business defect:501 authorized events caused a19662-byte provider
query and414→API500.50-ID batching restores successful native reads while keeping
the global newest50 review limit and tenant authorization.

147/148 deletion workflow direct delivery UPDATE is incompatible with the new
ACL. A dedicated request/lease/attempt-scoped cancellation RPC is confined to
successor149, preserving restricted direct access. Schema148 itself remains
unrepaired for this compatibility issue. See successor README and native evidence.
Full deletion-step ownership, external gateway behavior and broader business
browser workflows remain unproven.
