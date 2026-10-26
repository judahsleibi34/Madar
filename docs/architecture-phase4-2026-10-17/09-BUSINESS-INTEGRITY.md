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

A final adversarial check reproduced another confirmed calendar integrity defect:
`update_event` and `delete_event` checked a revision before writing, then omitted
that revision from the UPDATE predicate. Two independent PostgreSQL connections
both succeeded at version1, losing an edit or racing a deletion. The correction
uses one database UPDATE with tenant/id/version and `deleted_at IS NULL` predicates;
losers receive409 before child replacement or audit effects. The same helper
guards recurring parent edits and exclusions. Optional client-version behavior
remains compatible while the server-read version always fences the write.
Recurring splits and child replacement still use multiple provider requests;
this change does not make those workflows fully transactional. No migration is
needed. The new races use actual route logic and native SQL, with authorization
and side-effect transports explicitly stubbed. Final results are in evidence.
