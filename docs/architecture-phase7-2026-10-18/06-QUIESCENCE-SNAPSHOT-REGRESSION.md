# PostgreSQL activity snapshot admission regression

## Confirmed source failure

`schema150_release.observe_database_quiescence(cursor, ...)` originally read
`pg_stat_activity` without refreshing the connection's statistics snapshot.
PostgreSQL can retain that observation within a transaction. A source caller
reusing a transaction could therefore accept a cached zero after an independent
live client connected. Conversely, a cached one could keep rejecting after the
server confirmed that the client backend had exited.

Actual PostgreSQL17, marked disposable schema149, two independent client
connections and a read-only monitor in a different database reproduced both
states. The unchanged strict SQL/counters accepted the new live client behind a
cached zero; after `pg_stat_clear_snapshot()` the same strict query rejected it
with one other client. The inverse stale-one state cleared only after refresh.
A separate busy-client close probe confirmed that returning from client.close()
does not itself establish server-side backend exit.

Two retained native regressions against captured source4bd32241 produced
**1 FAIL +1 ERROR,0 skips,0.046349 seconds**. With the source correction, those
regressions plus the original three legacy-backlog assertions produced
**5 PASS,0 failures/errors/skips,0.238541 seconds**. The fixed source module was
captured independently with SHA256
`67f413b79d6cb2b2fde11c217f85af5e622fd18ddbeda6a511ee117783fe99e8`.
No production or retained application database was used.

## Correction and scope

Every helper observation now executes the fixed
`select pg_catalog.pg_stat_clear_snapshot()` immediately before the existing
quiescence SQL and exact protocol checks. This clears only the current session's
statistics cache. It neither changes database business state nor ignores a
counter. The source validator remains stdlib-only and operational150 admission
remains closed. Published migrations001–150, their checksums and release
metadata are unchanged. No schema151 is needed.

The model cursor test now requires cache refresh first, the same raw observation
second, and the unchanged three actual protocol calls afterward. Native tests
exercise stale-zero rejection and stale-one recovery in the SAME transaction;
no fixture-side cache clearing substitutes for the function under test.

The concrete adapter's current SQL transport creates fresh psql transactions,
but that does not make the generic cursor helper safe for every caller. Prior
business ownership/SQL evidence is not a proof of this source admission property;
source admission and exact-head acceptance must be rerun after this correction.

## Earlier hosted failure: cause remains unproven

Hosted backend run39136334705 at4bd32241 passed3338 backend cases with831 skips
and the frontend/artifact workflows passed, but its native stage rejected the
terminal-cancelled positive fixture. That rejection must remain visible. The
original three native cases then passed30 repetitions/90 executions unchanged;
its precise failing counter was not captured in the original hosted exception.
Do not claim the snapshot defect caused that particular occurrence. Transient
server cleanup or background queue locks remain possible until observed.

The test fixture now establishes a bounded, server-confirmed zero-client baseline
before loading its own transaction. It only waits using read-only autocommit
observations in the positively marked disposable database. It cannot terminate
sessions, reset queues, retry a privileged operation or weaken the production
gate. Unexpected positive-fixture failures now retain the exact observed numeric
schema/protocol/counter projection as an exception note; credentials, cluster
identity and resource records are excluded. Fresh hosted execution is required.

The sole owned investigation PostgreSQL was removed. Source150's eleven retained
services remain running, recovery remains stopped, and the disposable guest
remains powered off. Private logs and the source-bound experiment summary remain
outside Git.
