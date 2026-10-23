# Phase VIII report — NOT READY for a production operation

## Repository and identity

Baseline PR216:23254c786fdfa3731ff63cd004a4160b6d2f60fa,OPEN/draft,unchanged at
refresh. Main:876b65e73ea8ceaf398145d8677019184798a95c. Dedicated branch:
`codex/phase8-automated-migration-delivery-20261020`.
Draft successor:[PR217](https://github.com/judahsleibi34/Madar/pull/217),targeting
PR216's branch. Canonical history212→213→214→215→216 is preserved. No mechanical
merge of overlapping209–211,no force push and no main mutation occurred.

All published implementation commits were locally verified with the required
Saliba Rishmawi noreply identity;GitHub author and committer mappings were checked
by exact SHA and resolve to Saliba-codes. Publication-head attribution and checks
must also be refreshed after the final documentation commit. Read the current
PR head/checks rather than treating an older green source as a later acceptance.

Implementation sequence:cc66e688 protected original-role input;72f066c9 generic
inventory/AST/plans/policy;45260e26 generic CI/native rehearsal;ff947109 official
checkout URL correction;31eb347c actual candidate SQL/roles/drift/crash recovery;
8391073f reproduced namespace corrections;a08dc870 independent automation input
pinning;44a67aba executable tool-mode correction;47709909 physical backup negative
cases;61bcbe1c bounded retained-fixture lock/session precondition;77d63759 native
root-policy filesystem checks and isolated activity-cache probes. Final evidence
publication is separate from application/runtime acceptance. No fresh full stack
is represented as running at the documentation-head SHA.

## Protected controller and migration architecture

The existing completed-NORMAL coordinator remains the only privileged release
architecture. The concrete150 provider adapter is reused;no second SQL runner,
issuer,production entrypoint or registration bypass was created. The new role-
input adapter requires the actual protected actor,fresh authority,held locks,
complete persistent fence and source/inventory/cluster/journal binding. It seals
original preimage SQL append-only with checksum-bound captured bytes and COMPLETE
last. It does not publish ordinary backup/replica success or grant restoration.

Full maintenance database/object backup,original-role-aware ordinary restore and
replica acceptance,sealed candidate preparation,coordinator/private recovery,
independent handoff,worker/proxy/boot integration and combined privileged guest
interruption testing remain unfinished. `admitted_manifest()` and `profile()`
continue to refuse150. The existing PhaseVII guest's root install/reboot proof
is historical and was not replayed as new complete-release acceptance.

The generic inventory discovers versions from exact Git objects,checks mirrored
bytes,SHA256,contiguous names,ancestor history,modes and bounded input. It preserves
the narrowly reviewed004/005 naming and141→143 branch. SQL cannot be executable or
a symlink. No real151+ migration or new database ledger was introduced. Existing
schema state plus source-bound protected receipts remain the history basis;
missing history is never silently repaired or marked applied.

Plans contain source/origin/target,ordered migration hashes/transitions,risk,
worker/runtime compatibility,backup/recovery gates,artifact status and canonical
operation identity. Captured SQL cannot be substituted by a changed pathname.
Application-only releases have no invented migration or unconditional SQL backup.
Risk uses hash-locked pglast7.21/PostgreSQL17 ASTs. Only a small canonical additive
subset can be A;recognized operational changes escalate B,privileged/protocol
changes C,and destructive/unknown/dynamic/unsupported SQL D. Metadata cannot
reduce risk. No class establishes live application compatibility by itself.

## Automation and authority

All PR bases run backend/frontend/artifact/migration checks;main pushes prepare
fresh plans/images. Checkout is exact-head,credentials are not persisted and
workflow tokens are read-only. Specialized migration/business tests remain.
Generic CI derives the source/base inventory and tests actual newly discovered
routine SQL on a minimal native fixture. Stronger/unknown SQL emits BLOCKED
coverage. It also exercises synthetic future versions and original-role restore.

Root policy is fixed-path,versioned,private,scope/expiry/controller/database/main
bound and ClassA-only. It pins exact automation/build code,locks,workflows/local
actions and executable modes independently of a moving PR base. A workflow cannot
approve its own modified verifier. Missing/stale/wrong-source/wrong-cluster/
unprotected/replayed evidence blocks. Even a fixture policy match returns
production_execution_allowed=false. Generic protected dispatch is not complete;
no root policy was installed,activated or self-signed as production authority.

## Security and operational testing

Two MEDIUM conditional verification defects were reproduced:unsafe search_path
could shadow sha256 and fake a prior catalog digest,or redirect current_database
in an ownership-marker lookup. The first required native assertion failed before
the fix and passed afterward. Namespace-safe source now covers historical/generic
catalog/identity queries,customer/reconciliation snapshots,provider internal SQL,
protected migration connections and disposable helpers. The full native suite
retains malicious-function-before-execution and marker-refusal checks. Details,
preconditions and limits are in[the security report](15-SECURITY-AND-SUPPLY-CHAIN.md).

Bounded production metadata inspection found schema146,no unsafe catalog ordering
in that administrator session and no shadow public.sha256. No function was created
or executed there and no production state changed. Raw settings remain private;
this is not a claim about every possible connection or a production exploit scan.

The native generic suite passed57 cases:38 source/AST/plan/policy plus19 actual
PostgreSQL cases,zero skips. A child was SIGKILLed after a real151 COMMIT;the
journal remained applying while a fresh connection observed151. Replaying the
consumed attempt was refused. A separate lost-reply case used a fresh inspected
151→152 remainder attempt. This does not replay protected production authority.
One/two/three migrations,wrong origin,session/row locks,transaction rollback,
physical missing/corrupt/wrong-cluster backup,metadata/ACL/history/protocol drift
and coordinated/destructive refusal were tested. A separate temporary Git
candidate automatically executed150→151→152;no controller number change or real
Madar151/152 publication occurred.

The native role drill restored an independent PostgreSQL cluster with original
LOGIN/role/password-hash/membership/settings,ownership,ACLs and synthetic data.
Actual permitted SELECT and42501 UPDATE denial passed. Substitution/truncation
and wrong-cluster role capsules reject. This is component restoration,not a full
new application restore,PITR,off-host recovery,object consistency or certified
RPO/RTO. Those larger boundaries remain unproven this phase.

## CI evidence and failures kept visible

All four checks passed on implementation source
`77d637591de19a2250d377adbf77c6749c3328ef`:

| Check | Result | Exact run |
|---|---|---|
| Backend | 3,386 passed;864 conditional skips;4,250 discovered | [39401877293](https://github.com/judahsleibi34/Madar/actions/runs/39401877293) |
| Retained native PostgreSQL | 245 executions passed,independent of backend skips | Same backend run |
| Frontend | 1,713 passed;one skipped;build passed | [39401877207](https://github.com/judahsleibi34/Madar/actions/runs/39401877207) |
| Migration safety | 57 source/native cases;10 filesystem cases;original-role restore passed | [39401877135](https://github.com/judahsleibi34/Madar/actions/runs/39401877135) |
| Fresh images | Built;archive and OCI identity independently verified | [39401877319](https://github.com/judahsleibi34/Madar/actions/runs/39401877319) |

The57 and10 suites had zero skips. Four separate loopback observer tests passed.
Suites overlap;counts are not added into a claimed unique platform total.
Publication-head checks must pass independently after this documentation commit.
The final response records those exact-head run identities without claiming that
an earlier image belongs to a later commit.

Artifact12255154707,run39401877319/attempt1,was unexpired at verification.
Authenticated ZIP digest:
`sha256:ae809dca82ca41e57e180070162f82987a67494a832a12464c99952a52a3a0ac`.
Exact Git build-input hashes,archive inventory,receipt/run/source,inner archives
and actual OCI manifest/config identity checks passed. Runtime image identities:

- Backend:`sha256:15e6d6e914a13b5a504f8d5f6d3fb35efbad68ea3f99945b60de5eec9a406d48`.
- Frontend:`sha256:624d9d648cba049a556a1453c8f846a629b1c35a4c9ee9fa2f2d751f40de63d7`.

These images were not imported or accepted as a new running full-provider stack.
Earlier exactff947109 and31eb347c checks also passed;those earlier results are
preserved rather than relabeled as current acceptance.

Initial new CI rejected the official checkout URL without .git;the exact alias
was added after reading the checkout command. Real-source policy capture exposed
executable shell tools;their modes are now explicitly pinned while SQL stays
nonexecutable. A retained native149 live-client diagnostic later failed because
its initial fixture had queue_locks=1 with zero client sessions. The production
gate correctly refused. Setup now boundedly waits for both counters;no production
assertion or guard was weakened. A repeated hosted failure showed that another
lock could start after the setup poll;the two activity-cache cases now hold a
bounded observer-owned SHARE barrier to isolate that premise. Bounded synthetic
lock metadata is retained if refusal recurs. An auxiliary staging run failed on unreadable
source-directory permissions before tests;only owned source traversal mode was
corrected and raw logs remained private. The retained native149 fixture failed in44a67aba and61bcbe1c backend CI;
77d63759 passed after the observer-barrier correction. Final exact-head checks are required;
see the current PR checks and verification matrix rather than assuming old runs
validate new code. No failed or skipped case is counted as an executed pass.

Local source/component regressions109 passed after namespace changes;the staged
57-case run and repeated native/component suites overlap and are not summed as
unique platform coverage. Dependency/history/transition/forward-release/secret/
privileged-inventory checks pass;the inventory reports78 application paths,not
platform-wide authorization proof. Historical duplicate013/014 warnings remain.

No new full-provider/browser run,combined protected installation/reboot release,
object-aware PITR or off-host recovery is claimed. Current application/function
coverage remains the selected retained native business suites and historical
PhaseVII Auth/MFA/Storage/browser acceptance,with exact identities kept separate.

Ten actual root/private-policy filesystem cases passed in a read-only
networkless container with a fresh tmpfs. No host policy/DB/socket was mounted.
The retained exact61bcbe1c schema150 database rehearsal passed193 executions on
staging;it uses synthetic provider schemas and transport fixtures,not a full
provider/controller release. The first staging attempt could not read its source
directory;only owned traversal mode was corrected and raw logs stayed0600.
These results do not supersede the required final exact-source CI.

## Performance and readiness

Five local preparation runs onff947109/150-file inventory:median discovery2.821s,
median plan0.0122s. No p95/p99,zero-downtime,speedup,SLO or production-capacity
claim. Different staging suite durations are not before/after benchmarks.
Rehearsals have bounded CPU/memory/PIDs/time,tmpfs data,no public ports and
positive ownership cleanup. Existing staging services/volumes were preserved.

Main remains unprotected,rulesets empty,credential admin=false. Follow
[administrator instructions](18-PR-INTEGRATION-READINESS.md);no settings were
applied. This draft is for independent code review. The release is NOT READY for
operator execution or production. Independent human review,current-production
backup/replica/restore evidence and fresh protected operational approval remain
external gates;the unfinished controller/dispatch/staging work is engineering,
not merely missing user permission. No production authorization exists here.

## If schema151 is added tomorrow

Matching SQL mirrors are discovered automatically;history/order/bytes/modes are
validated;the PG17 AST and declarations classify risk;CI generates an immutable
plan,executes framework/specialized tests,and rehearses actual routine SQL when
its compatibility and fixture requirements are satisfied. Exact-source artifacts
are built. No schema151 controller/profile/dispatcher needs adding for preparation.
A/B/C/D risks retain separate gates;unrecognized SQL is restrictive.

Full-provider automatic staging and protected production dispatch are still
unfinished. Current production146 cannot skip the coordinated147–150 transition.
The root policy would additionally require protected-main provenance,trusted
input hashes,authentic fresh images,real drift/compatibility/recovery/health and
independent authority. It currently never permits production execution. In the
fixture,existing captured-byte/session-lock SQL executes,post-commit schema is
observed and consumed attempts reject. Production execution/completion must use
the existing protected coordinator once its missing lifecycle is implemented
and independently accepted;it does not happen automatically today.

## What still requires human approval,and why

Independent PR/code review;administrator branch/environment protection;protected
controller installation and trust-policy enrollment/renewal;explicit coordinated
or exceptional operation approval;and any production activation,backup-scope
operation or write authority. These controls prevent a PR/CI job from authorizing
itself. Routine future execution may eventually use a previously approved narrow
root policy,but this session did not enable it. Complete the P1 engineering in
[the roadmap](21-REMAINING-ROADMAP.md) before seeking operational approval.

## Reproducible validation commands

Commands run in the source root or dedicated owned staging fixtures:

```bash
python3 web/scripts/check_dependency_locks.py
python3 web/scripts/check_migrations.py
python3 web/scripts/check_migration_transitions.py
python3 web/scripts/check_forward_release.py
python3 web/scripts/check_secret_hygiene.py
python3 web/scripts/check_privileged_inventory.py
# CI builds the locked test image before these networkless/native rehearsals.
BACKEND_TEST_IMAGE=madar-backend-test timeout 10m bash web/scripts/rehearse_generic_migrations.sh
BACKEND_TEST_IMAGE=madar-backend-test timeout 5m bash web/scripts/rehearse_maintenance_role_restore.sh
BACKEND_TEST_IMAGE=madar-backend-test timeout 2m bash web/scripts/rehearse_migration_policy.sh
BACKEND_TEST_IMAGE=madar-backend-test timeout 10m bash web/scripts/rehearse_migration_150.sh
# Backend Docker test target:
python scripts/run_tests_no_external_network.py
```

Frontend CI uses the locked install and its workflow test/build scripts.
See exact workflow logs above for environment,individual native groups and
commands. Native staging193 and CI245 executions include repeated/regression
coverage;they are not245+193 unique tests. Full browser/new-provider acceptance,
full privileged release and object-aware/off-host recovery remain NOT TESTED.
