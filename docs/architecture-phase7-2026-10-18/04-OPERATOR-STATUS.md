# Read-only operator status

`python3 -IB web/scripts/inspect_schema150_maintenance.py --context <64hex>`
reads only the fixed root-private admission, inventory, journal and barrier for
that exact context. Run from the reviewed source under its normal protected
read permissions. Unknown contexts, arbitrary paths, wrong bindings, corrupt
hash chains, invalid semantic ordering and changed barriers fail closed.

Output omits role DDL, credentials, provider responses, object paths and raw
journal payloads. It reports recorded step history and pending intent. A missing
barrier after an incomplete effect is FAIL. Other valid history remains PARTIAL:
there is no native database/service observation, fresh image acceptance, recovery
execution or independent authorization. `last_recorded_schema` is historical;
it is never labelled the current schema. The capability cannot prepare, execute,
retry, clear a barrier, issue write authority or register schema150.

Eight temporary-journal tests cover no-effects output, retained pending intent,
exact barrier digest, corrupted/out-of-order records, relabelled admission and
arbitrary-target refusal and a surviving barrier after recorded completion. CLI failures expose exception class only. Deployment
installation and the complete source-bound operator package remain subject to
the same unfinished controller integration gates.

Recorded database schema values are typed and restricted to146..150 with exact
cluster binding before output; an arbitrary private payload cannot be projected
through the historical-schema field. This remains an observation, not live proof.
