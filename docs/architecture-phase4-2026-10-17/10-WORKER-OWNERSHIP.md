# Worker ownership

Delivery147 generation fencing remains unchanged and passes all18 native cases.
The independent outbox baseline fails five ownership invariants at148: sent,
failed/dead completion, stale resolution and expired-owner completion. Row locking
without a generation/live lease did not authenticate the claimant.

Separate149 adds outbox protocol2, claim_v2/resolve_v3/finish_v2. Resolution checks
the generation and DB-clock lease under the row lock and checks expiry again
after materialization, rolling back all inserts if ownership expired. Legacy
public materializer becomes a rejection stub; an owner-only helper retains its
reviewed body. Direct UPDATE/DELETE and old RPCs remain denied. Startup requires
both worker protocols before any auxiliary or delivery work, with no fallback.

Native cases include concurrent finish versus resolution, reclaim, lock wait,
retry/dead/revoked outcomes, crash/restart, lost response, stale reminder completion,
privileges, enqueue/cleanup and scoped deletion cancellation.109 native executions
include21 successor-specific cases and22 business cases repeated on149.

No149 production admission, full native provider stack, accepted production
image, complete supervisor cutover or boot acceptance exists. The148 preview
must not silently adopt149. External acceptance and delivery acknowledgement
remain separate: ownership fencing is not exactly-once external delivery.
Other queues/deletion-step state transitions still need ownership review.
