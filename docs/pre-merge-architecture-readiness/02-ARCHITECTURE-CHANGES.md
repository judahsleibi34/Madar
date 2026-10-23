# Changes in this readiness attempt

The existing architecture is preserved. No second controller, issuer, SQL
executor, release profile, migration or deployment workflow was introduced.

`LockedMigrationExecutor.run` now includes connection creation and autocommit
setup in its failure handling. A failed setup closes a returned connection,
persists failure at `connecting`, and retains single-use attempt refusal.
Connection-close errors preserve an existing primary exception; a close error
after otherwise successful execution still reaches the caller.

`schema150_object_inventory._open_root` distinguishes ancestor identity from
the contents of unrelated siblings. Descriptor-relative opens still pin
device/inode/mode/ownership and refuse symlinks. The measured root retains its
full mutation signature; mount identity, two forest scans, byte hashes and
preservation checks remain. New tests reject permission changes, ancestor
replacement and root-content changes during opening.

Three executor regressions failed before correction. One object-root regression
reproduced the unrelated-sibling refusal before correction. A native PostgreSQL
test verifies failed setup releases its session, preserves schema146 and
original selected rows, and cannot reopen its consumed attempt.

These corrections are supporting reliability work. The missing maintenance-first
ordering, two-stage candidate binding and private handoff remain unfinished.

## CI plan/origin correction

Inspection of the first publication's authenticated CI artifacts found a Class D
source plan paired with a BLOCKED native report labeled A. The harness had
regenerated its plan from the fixture's150 origin, rather than the requested146
origin. No underlying risk classification was lowered and the full-provider gate
still refused execution. The report now retains the original plan/risk and
refuses nonroutine plans before database access; a different fixture origin
blocks instead of redefining the operation.

A native regression also reproduced advancement during backup causing the
generic executor to skip part of its path. Passing `expected_origin` into the
existing locked executor now rejects that race before further SQL, preserves
the observed151, leaves the next table absent and refuses consumed-attempt replay.
The new report-contract suite and that native race test reproduced pre-fix failures.
