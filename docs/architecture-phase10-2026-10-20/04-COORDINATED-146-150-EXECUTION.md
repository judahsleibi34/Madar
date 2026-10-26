# 146→150 native SQL integration — PARTIAL release evidence

`tests.test_schema150_cutover_database` now runs inside the existing marked,
disposable146 bootstrap in `rehearse_migration_150.sh`. The existing
`LockedMigrationExecutor` consumes captured checksum-verified published147–150
SQL, with the concrete provider's new advisory-locked cursor hook. No new SQL
executor or operational schema profile is created.

Seven native cases passed. One advances146→147→148→149→150, verifies each SQL
checksum and protocol2/2/2, checks legacy direct UPDATE denial and compares selected
original Auth-user, Storage bucket/object metadata and synthetic application rows.
Four lose the reply after a real COMMIT. Two actually exit the executor process
with os._exit after147/150 commits. In every interruption, fresh observation sees
the committed schema, the same attempt refuses and a distinct model-authorized
forward attempt skips already applied SQL and reaches150. It never restores a
backup over newer data or treats a stale journal as proof of rollback.

PostgreSQL transactions, advisory locks, selected rows, immutable SQL, journal
files/flock and process exits are native. Authority, backup, host/supervisor/role
fencing and activation are MODEL fixtures. All admin/setup connections are closed
before entry; no foreign client is exempted. This is NOT the full protected root
controller, real GoTrue/MFA/Storage-byte preservation, independent write handoff,
proxy activation or boot acceptance. Gate1/full146→150 remain blocked/partial.

The owned staging fixture is network/CPU/RAM/PID/time bounded, uses synthetic data,
and preserves retained stacks. The source snapshot and overlays are hashed and
raw diagnostic logs remain private. No published migration bytes change.
