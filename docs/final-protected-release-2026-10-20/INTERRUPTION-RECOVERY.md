# Interruption and recovery evidence

| Injection | Actual state and decision | Scope |
|---|---|---|
| Lost COMMIT reply147/148/149/150 | Fresh connection observes committed boundary; original executor attempt refuses replay; separate MODEL-authorized forward attempt skips committed SQL | Native PostgreSQL, retained cases |
| Executor os._exit after147/150 | Process actually exits; durable applying state remains, fresh connection sees committed SQL; separate MODEL-authorized attempt reaches150 | Native process/SQL, retained cases |
| Forked child invokes parent migration | Actual flock PID ownership rejects before SQL; schema stays146 | New native process/lock test |
| Foreign session before SQL | Cluster-wide quiescence rejects; schema stays146, ordinary state unchanged | New native database test |
| Parent lost150 reply | Actual schema150/data preserved; failed executor record; temporary synthetic credential removed; ordinary slot unchanged; another invocation refuses changed witness | New native database + actual credential cleanup, MODEL issuer |
| Late session after150 COMMIT | Final same-session guard rejects completion; durable failed record says observed150; no promotion | New native database test |
| Forward credential wrapper | Old code omitted held lock and raised AttributeError; corrected wrapper borrows real descriptor and requests fresh resumption witness | Native filesystem/flock, MODEL issuer |
| Clear/close cleanup errors | Remaining cleanup executes and parent upgrade descriptor closes | Native filesystem + controller MODEL failures |
| Same-attempt process race | Before:both filesystem claimants completed; after:one atomically claims,another refuses before DB; native PostgreSQL winner retains completed150receipt/data | Native process/filesystem/SQL, MODEL outer gates |
| Directory durability | File fsync,exclusive claim/rename,and new directory entries fsync observed; no host power-loss acceptance claimed | Native filesystem |
| Provider start failure | Fixed private sequence stops before candidate/proxy; no continued activation | MODEL transport |
| Missing worker activation | Target-authority flag alone cannot start ingress | MODEL transport and stage witness |

No complete-controller crash/reboot, actual consumed-approval recovery or real
private-provider interruption has passed. The retained guest was inspected, not
booted or modified. It has1vCPU/1GiB/8GiB and old consumed attempts are preserved.
No physical host or shared staging VM was rebooted.

A safe failed state is not a completed recovery. Maintenance forward repair still
needs the operation-specific integration described in INTEGRATION-IMPLEMENTATION.
No backup was restored over newer data, old grants reinstated, or unknown provider
outcome guessed. No complete normal-operation RPO/RTO is asserted.
