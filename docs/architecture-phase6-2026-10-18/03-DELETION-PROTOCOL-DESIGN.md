# Deletion protocol2 design under native validation

A request claim carries immutable original request ID,owner,durable bigint claim
generation and attempt. Each processing step also carries request generation and
its own incrementing attempt. A reused worker ID is insufficient. Every RPC
locks request before step/effect/resource and rechecks PostgreSQL clock after
lock waits and business changes; an exception rolls back the whole RPC.

The fixed transition API begins the earliest incomplete step,completes/fails it,
or renews an ALREADY live original claim. It never accepts arbitrary table/column
names or SQL. Required local mutations run in a separate fixed,scope-derived RPC
and persist authoritative applied-generation evidence before step completion.
Finalization completes the final step and request together only after all earlier
steps and authoritative verification pass. Runtime direct lifecycle writes and
legacy claiming/notification cancellation calls are revoked. Owner-controlled
migration/restore privileges remain available.

External calls run outside database transactions. Each target has a canonical
stable intent identity bound to request/step/generation/attempt. Intent commits
before the call. Only the same live claim may confirm it and update frozen
resource/subject evidence. A lost reply,crash or uncertain effect is not blindly
retried: unconfirmed intent blocks reclamation into manual intervention. A
confirmed target may be skipped without reissuing its effect. Stable keys alone
do not imply provider idempotency. Explicit independently controlled
reconciliation remains required where the provider cannot prove an outcome.

Cancellation locks eligibility and unfreezes recorded preimages atomically;
claiming/any step attempt makes cancellation ineligible. New overlapping tenant/
user workflows are rejected. Tenant subject status is captured BEFORE freezing
(the retained083 order lost that preimage). Exact protocol2 is available only at
schema150; schemas001–149 remain blocked without fallback.

Scope limitation: these APIs fence lifecycle and reviewed local-step execution,
not arbitrary malicious code holding broad service-role credentials. Existing
service-role grants on users/tenants/providers are not blanket-revoked. Full
cutover must exclude old/manual/supervised actors; narrower dedicated deletion
credentials and a scoped external-effect broker remain follow-up security work.
Native tests,full runtime acceptance and controller admission are separate gates.
