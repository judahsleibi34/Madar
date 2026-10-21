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
