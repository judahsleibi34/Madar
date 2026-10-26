# Confirmed inherited deletion ownership defect and containment

Native reproduction at published213 source5fb997bf and exact schema149 produced
three safety FAILs: stale A's failure clears B's active request lease, stale A's
finalization completes B's request, and stale A's step completion overwrites B's
processing step. Two additional cancellation/resolver lock-order cases PASS.
Existing111 native integrity executions also PASS. These are distinct results:
passing149 queue fencing does not repair retained083 deletion state transitions.
Raw synthetic diagnostics are private; the opt-in test states the required
invariant and remains a known-failure diagnostic, not claimed as corrected.

The source worker now requires exact integer2 from
`data_deletion_ownership_protocol()` at enabled startup and on every consuming
poll. Missing/unavailable/legacy/malformed protocol refuses before claim or step
work, with no legacy fallback or provider-error disclosure. A READ_ONLY batch
never claims. All001–149 schemas lack this complete protocol, so the new worker
must remain disabled/stopped there. This is deliberate containment, not database
fencing of direct service-role calls. Thirteen focused worker/standby tests PASS.

A separately reviewed forward successor is required: database-clock, generation-
aware claim/step/finish/fail/finalize RPCs; atomically lock and compare original
request owner/attempt/live lease; update request and step together; revoke direct
state mutation. External deletion calls need stable idempotency or explicit
reconciliation after lost replies, outside long DB transactions. Published149
and001–148 are unchanged. No150 migration is silently introduced.

The149 cancellation RPC itself has no newly confirmed defect in the reviewed
scope: native resolver-first and cancellation-first serialization both preserve
scope/ownership. Full deletion remains a FAIL/BLOCKED production gate. A healthy
legacy deletion container is not acceptance; final staging keeps it stopped.
