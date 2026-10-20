# Root-governed eligibility and trusted CI inputs

Implemented a read-only policy reader/evaluator, not a production executor or
approval issuer. Its fixed location is `/etc/madar/migration-policy.json`; the
reader requires root-protected ancestry, root ownership, private regular files,
no symlink, bounded strict JSON and exact fields. Ordinary repository/CI writers
cannot publish that file. No production policy was installed or enabled.

Policy1 binds policy/environment/database/controller identity, repository,
protected-main branch, expiry, max migration count, only ClassA, and an exact
SHA256 digest of trusted automation/build inputs. Inputs include pinned artifact
build files/locks, parser, migration/classification/planning/evaluation code,
verification/rehearsal/build scripts, all workflows and local actions. Generated
plans capture those Git bytes and the digest. Missing inputs reject. A PR cannot
renew policy by changing its CI checks; even after its workflow change becomes
the next PR's base, the old root-pinned digest still rejects that source. The
native/CI PASS booleans in unit fixtures never become production credentials.

Every policy match still returns production_execution_allowed=false and
protected_dispatch=BLOCKED_INTEGRATION_INCOMPLETE. Required gates separately
include protected integration, exact source/controller/database, authenticated
images, staging, compatibility, drift/history, recovery, deployment locks and
fresh independently issued authority. A source intent cannot lower SQL risk.
B requires live size/lock review; C maintenance/quiescence/private acceptance;
D an exceptional reviewed contract and no routine automatic dispatch.

A future administrator-approved activation must use the existing independent
protected issuer, revocable root policy and live receipt verification. It must
not trust a serialized policy_match field or source-controlled workflow marker.
That dispatch, protected controller lifecycle and interrupted operation proof
remain unfinished engineering. This framework does not enable automation merely
because passwordless sudo or a successful CI run exists.

Current CI behavior: all PR bases run backend, frontend, candidate and Migration
Safety checks. Main pushes prepare fresh plans/images too. Tokens are read-only,
checkout credentials not persisted and trusted Actions pinned. Actual discovered
routine SQL receives a bounded minimal PostgreSQL rehearsal; stronger SQL emits
BLOCKED coverage. Synthetic future and original-role restore cases always run.
Full-provider candidate staging/compatibility and protected post-merge dispatch
are not yet automatic. These required coverage gaps prevent production admission.

Trusted build inputs include regular executable shell tools, so their Git mode
is explicitly captured alongside SHA256. SQL discovery remains nonexecutable-
only. A real-source plan exposed the original overstrict shared mode check;
it now permits executability only for the fixed automation input capture, with
regressions retaining executable-SQL refusal and detecting tool-mode changes.
The actual source inventory has no missing required automation inputs.
