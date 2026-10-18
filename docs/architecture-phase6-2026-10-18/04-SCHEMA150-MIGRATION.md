# Unselected migration150

File: web/database/migrations/150_fence_data_deletion_ownership.sql, mirrored
byte-for-byte under web/supabase/migrations/.
SHA256:63d4d0c7af93bd3c3e93158a2e281b41eed23b83bfafd4b3f1ba22313533b722.
Exact149 origin,core row lock,atomic schema150 transition. Processing requests,
processing steps (including orphan/expired work),and outstanding lease metadata
reject admission. No queue reset or provider-outcome inference is performed.

New durable request/step generations,local-operation generation evidence,and
external-effect ledger accompany fixed SECURITY DEFINER RPCs with empty search
paths. Runtime INSERT/UPDATE/DELETE/TRUNCATE on all five lifecycle tables is
revoked. Public/anon/authenticated cannot execute the RPCs; service_role can
execute the public protocol APIs but not internal lock helpers. Legacy claim and
notification-cancellation runtime invocation is revoked. The new local-step RPC
retains owner access to the existing scoped notification cancellation function.

Before publication,independent review identified three additional native failures:
crashed idempotent freeze became stuck at its one-attempt limit;two sequential
owner closures counted a frozen owner as an active replacement;confirmed object
deletion failed to release tenant quota/registry state. All three were reproduced
on the unpublished draft (35executions,3FAIL,32PASS) and corrected before this
migration was committed/pushed. No previously published migration was rewritten.

Idempotent local recovery may resume under a successor generation,bounded by
request attempts. External uncertainty remains manual. Enrollment serializes
owner decisions across scopes;another owner must have an active account and no
pending deletion. Atomic resource confirmation releases retained storage quota
and tombstones eligible builder metadata. Shared/published builder assets under
user closure require explicit review rather than deleting tenant publication.
Canonical target IDs prevent duplicate intent identities. Finalization requires
the exact ten-step plan as well as completed authoritative steps/verification.

Before commit,transaction rollback/disconnection restores149 and its ACLs.
After commit,do not restore legacy broad lifecycle grants or restart old deletion
workers. Recovery is reviewed forward repair with compatible protocol2 components.
A database restore is a separate data-loss-sensitive operation,not an ordinary
application rollback. Production admission remains blocked/unselected.
