# Implemented integration and exact remaining edges

Baseline: PR219, `caa5a31484e4c3145163f95381a5fabaf958ba7e`.
Implementation source: `1aeed83105723caadc79396c0a29d9d24841d8cc`.
Branch: `codex/final-protected-release-completion-20261020`, based directly on219.
Main remains `876b65e73ea8ceaf398145d8677019184798a95c`.
Existing worktrees, published history, migrations001–150 and active descriptor are preserved.

| Existing component | Implemented connection |
|---|---|
| `CompletedNormalUpgrade.migrate` | Historical profiles retain the madar service; the maintenance parent borrows both real locks and invokes the existing `run_migration` with the concrete provider |
| `completed_normal_migration.run_migration` | Exact parent/source/root/runtime/lock binding; private sealed candidate replaces public known-good-candidate prerequisite; backup/provider journal witness retained; ordinary runtime state is never relabeled/promoted by this branch |
| `completed_normal_runtime.validate_model` | Fenced phase requires all eight roles stopped, non-restarting, with no live endpoints; retains image/configuration/mount/capability/resource/authority checks |
| `LockedMigrationExecutor` | Optional final callback on the same advisory-locked cursor, before durable completion; failure retains committed schema and a failed attempt |
| Concrete provider/lifecycle | Strict committed150 protocols/quiescence; root+credential sealed private candidate; provider trio then private Redis/backend/frontend; workers require target authority; ingress requires all sealed roles running, proxy last |
| `CompletedNormalForwardResumption.credential` | Passes the actual parent upgrade descriptor into existing root credential logic; previously omitted it and raised AttributeError |
| Main/forward cleanup | Parent descriptor closes even when credential cleanup or subordinate lock cleanup fails |

No new controller, issuer, SQL executor, arbitrary service/path interface, deployment workflow or migration is introduced.

## Executable dependency checklist

The complete operation is **not connected**. These are engineering gaps:

1. `CompletedNormalUpgrade._execute` still performs bridge prepare/activate/publish/adopt before maintenance. It has no maintenance-first150 branch constructing and retaining the concrete provider across backup, SQL, private recovery and activation. Its new migration dispatch is an integration method, not that missing full caller.
2. Admission/profile150 remain deliberately rejected. Candidate inventory pins Docker IDs while candidate configuration references the admission context that includes the inventory hash. A measured staged extension/two-phase binding is still needed; an unknown late container cannot be adopted. Private sealed-stage verification does not solve creation/admission ordering.
3. The coordinator's `CompletedNormalBackupContext` construction still omits `provider_adapter`; actual fenced backup/escrow/independent receiver must be connected to the same operation.
4. Entrypoint acceptance still delegates to public `verify_serving`; it cannot certify preserved original private Auth/MFA/Storage on a stopped-worker candidate. Concrete acceptance/activation delegates remain unwired.
5. `CompletedNormalWriteHandoff.guard/grant` expects `candidate-runtime.json` and a running worker kernel. Connect sealed private acceptance, authority installation, compatible worker ownership/start, kernel verification and proxy/boot completion without granting from the adapter.
6. Existing forward resumption binds the bridge runtime/public kernel and SQL-only failure phase. A maintenance-specific, fresh-authorized journal observation/forward path is still needed. Never refresh an old backup witness or replay a consumed attempt automatically.
7. Install and run this combined operation in a positively identified disposable privileged guest with actual independent test authority and receiver; then test full-controller crashes/reboots. No source gate is removed in anticipation of those results.
