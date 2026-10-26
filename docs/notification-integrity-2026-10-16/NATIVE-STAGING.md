# Full native provider staging validation

The retained project is exclusively synthetic and owned by the architecture
harness on madar-staging. Its ownership marker still contains146; that is not a
current schema assertion. Production and the unrelated original staging-data
project remain untouched.

The follow-up harness targets148 and refuses to start its new consumers against
an older populated schema. `upgrade_notifications.py` is an explicit staging-only
operation: strict host/marker/resource checks; exact pinned147/148 artifacts;
stop only owned writers; refuse unresolved processing deliveries; retain private
logical backup; compare original public/Auth/MFA/Storage rows and sequences; record
committed checkpoints. Only the new generation column (if starting from146) and
core schema state are excluded from preservation comparison. It restores original
writers on failure only while schema remains146. After147 commits it leaves them
stopped for forward repair. A148 checkpoint lacking preservation verification
blocks consumer admission. It never requeues ambiguous sends automatically.

Twelve staging orchestration/admission tests PASS, including146 rejection,
unmarked refusal, failure before147/after147/after148 mismatch, and preservation
checkpoint refusal. Initial broad worker standby regression was corrected before
committing the fencing change; existing protected standby assertions are intact.

Procedure on the verified VM, from a fresh exact committed archive:

```bash
python3 web/staging/integration/upgrade_notifications.py
python3 web/staging/integration/manage.py up --source-sha <exact-commit>
python3 web/staging/integration/smoke.py
python3 web/staging/integration/worker_recovery.py
python3 web/staging/integration/restore.py
```

`up` builds and attests the source-overlay image, confirms actual148, then publishes
148 runtime bounds. Native worker uses real PostgREST, not the SQL adapter used
by process-crash unit integration fixtures. `worker_recovery.py` now uses protocol2
and all four stale outcome denials; restore reports actual schema instead of a
hardcoded146. Results and actual deployed source are recorded in FINAL-REPORT.md
only after execution. No production admission/provenance or full parity claim.
