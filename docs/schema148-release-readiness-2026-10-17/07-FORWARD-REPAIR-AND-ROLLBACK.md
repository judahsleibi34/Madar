# Commit boundaries and recovery

Before147 COMMIT, a failed SQL transaction/disconnect rolls back its DDL, grants
and schema transition. The coordinator must still inspect actual DB/history and
owned runtime state before restoring origin authority; an interrupted journal is
not proof of rollback. A consumed attempt remains consumed.

After147 COMMIT, unfenced legacy delivery RPCs and direct mutation grants stay
revoked. Do not reinstall the old worker, restore old privileges, replay consumed
authority, switch to an incompatible source or overwrite the customer database
from a backup. Keep maintenance/READ_ONLY and the old consumer stopped. The
observed DB schema/RPC/history, source hashes and retained journal determine
progress. A new independently approved forward-repair scope can finish148 after
all fresh prerequisites. Native executor tests prove147 retention and fresh
continuation; they do not issue real repair approval.

After148 COMMIT, application rollback is limited to explicitly148-compatible
accepted images and grants. The new bridge rollback range is148 only.147 is not
a completed deployment target and is not admitted by the new backup receiver.
Missing completion/target SQL/preservation evidence prevents NORMAL and old boot
recovery. New compatible boot gates supersede the measured146 gate rather than
silently editing its historical receipt.

Lost provider acknowledgement requires separate reconciliation. Neither backup
restoration nor migration replay proves whether an email/push was accepted.
No script here resets ambiguous work or creates production authorization.
