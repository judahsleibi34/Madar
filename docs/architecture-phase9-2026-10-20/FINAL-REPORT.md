# Phase IX final engineering report — NOT READY

## Source and publication scope

Parent [PR217](https://github.com/judahsleibi34/Madar/pull/217) remains OPEN/draft at
`e5cbc740f437e24c4fde3bfcbd52933c03070d4c`. The dedicated successor is draft
[PR218](https://github.com/judahsleibi34/Madar/pull/218),targeting217,on
`codex/phase9-protected-release-execution-20261020`,in the separate
`Madar-phase9-protected-release-execution-20261020` worktree.

Main remains `876b65e73ea8ceaf398145d8677019184798a95c`. All209–217 heads were
refreshed;they remain OPEN/draft and unchanged. Actual Git ancestry verifies the
contained209→210→211 histories and canonical212→213→214→215→216→217→218 chain.
No overlapping PR was merged,no published history rewritten and no worktree or
branch removed. Initial uncommitted work/evidence elsewhere was preserved.

The source/application acceptance head is
`91a1ebf6597e2ddfaa2c569f9f1dd8ef2f1a4fb1`. A later CI-only hardening commit
`2d74b543b12aa9d345e245e96b1b8c0cfc7e58ba` binds the conditional mobile workflow
to explicit read-only,nonpersistent,exact-source credentials. Documentation
publication is a separate commit. Resolve its exact head through PR218 or
`git log -1 --format=%H`;do not transfer91a receipts to it. Its own fresh CI and
native acceptance artifact are required and are reported in the final session
response/[PR checks](https://github.com/judahsleibi34/Madar/pull/218/checks).

## What was implemented

1. The existing ordinary backup pipeline now supports a concrete maintenance
   adapter under existing authority/locks. Runtime-owned dump output is copied
   through descriptors into protected staging before original privileged role
   material and fenced object archives are added. An independently stored inner
   digest binds restore/replica consumption. Native restore compares original
   roles/password verifiers/memberships/global and per-database settings,owners,
   ACLs,data,sequences and object bytes. No generic role defaults are restored.
2. The existing coordinator captures authenticated CI archive bytes before
   candidate preparation while both locks remain held. Actual OCI config/manifest,
   source/build/API-origin metadata and exact-source run/attempt are checked.
   Subsequent guards requery GitHub and use the retained archive. Partial attempts
   cannot overwrite/adopt state or fall back to operator-owned mutable input.
3. Confirmed admission defects were reproduced and corrected:foreign-database
   clients/prepared transactions escaped old counts;replication-mode connections
   reported `walsender` while executing ordinary SQL;an evidence pathname could
   change between hashing and JSON parsing. Original failing assertions remain.
   Background writer counts are measured during preimage/migration/private
   boundaries,not fabricated as zero. Unknowns deny;no backend was force-killed.
4. Independent automation trust captures complete release/staging and nested
   backend/frontend tooling,required verification runners,bundler configuration,
   workflows/Actions and executable modes. A moving Git base cannot enroll a new
   verifier/helper in an old root policy. Remaining mutable Actions are pinned.
5. Automatic full-provider CI now waits for independent exact-head checks,
   authenticates fresh artifacts,creates its own bounded synthetic native provider
   state,discovers/captures SQL from Git,checks actual protocols,starts accepted
   images and runs native application,tenant,deletion,worker-restart and browser
   acceptance. Owned resources stop before completion publication. Public
   diagnostics omit private logs,credentials,exception messages and customer IDs.

Source files and boundaries are detailed in
[02](02-PROTECTED-CONTROLLER-COMPLETION.md),[03](03-MAINTENANCE-BACKUP-AND-REPLICA.md),
[04](04-SEALED-CANDIDATE-PREPARATION.md),[10](10-AUTOMATIC-FULL-STAGING.md) and
[15](15-SECURITY-AND-SUPPLY-CHAIN.md). Policy documents were updated with source
changes;repetitive PhaseIX tails were consolidated while preserving all prior
policy bodies and initial maintenance sections.

## Commits and attribution

| Commit | Change |
|---|---|
|fa4656b5d42bec304375b343af07884efea552d9|Maintenance backup custody and original-role restoration|
|22f9d3087904993567d393f32344aa8df20cc459|Imported release/staging helper trust pins|
|9932e088bdfb69f29a5f3897cebe140d7fe8a8ac|Cluster-wide client/prepared quiescence|
|e4afe266c320f4ef071ed82799414bd517859c93|Candidate archive seal and single-capture evidence|
|8dda41603ee73a0cda6768c1fc311e06f5915343|Automatic fresh full-provider CI|
|4b6e2560949bc052b5d5259fdd00516c6cf2b833|Exceptional-risk refusal before artifact preparation|
|019b875fa83ebc34153f34b70679e0154bea06ff|Native OCI identity,locked browser,Action pins and diagnostics|
|e3d01a22e9b5c9073b6f61e00b1742c4f7d24516|Actual replication-mode SQL writer rejection|
|c3d60bb80f9fe6355efd9609915c96ee63b3ef5f|Nested build/test tooling pins|
|91a1ebf6597e2ddfaa2c569f9f1dd8ef2f1a4fb1|Strict consuming-worker restart and component health|
|2d74b543b12aa9d345e245e96b1b8c0cfc7e58ba|Read-only exact-source conditional mobile CI|

All local new authors/committers use
`Saliba Rishmawi <75858844+Saliba-codes@users.noreply.github.com>`.
Published implementation mappings through91a were independently verified as
Saliba-codes for both fields. Publication/CI-only commits require the same actual
GitHub API check after push. Historical attribution is unchanged.

## Executed validation at91a

| Category | Actual result | Evidence |
|---|---|---|
|Backend|3,436passed;869conditional skips;0failures,4,305discovered|[39422044127](https://github.com/judahsleibi34/Madar/actions/runs/39422044127)|
|Retained native PostgreSQL|245executions passed|Same backend run,specialized115/145/146/147/148/149/150 scripts|
|Generic safety/rehearsal|64cases passed:40Git/parser/policy and24native DB|[39422044174](https://github.com/judahsleibi34/Madar/actions/runs/39422044174)|
|Root policy filesystem|10passed|Same migration-safety run;actual UID/path/mode/symlink fixtures|
|Native maintenance backup|PASS,8.963s|Same run;independent original-role/owner/ACL/data/sequence/object-byte restore|
|Frontend|1,713passed;1skipped,233test files;lint/build/audit PASS|[39422044126](https://github.com/judahsleibi34/Madar/actions/runs/39422044126)|
|Fresh candidate archive|PASS|[39422044168](https://github.com/judahsleibi34/Madar/actions/runs/39422044168)|
|Full-provider application/browser|PASS,291.322s,11components,9browser groups|[39422044167](https://github.com/judahsleibi34/Madar/actions/runs/39422044167)|

No skips count as passes and no overlapping tests are summed as unique coverage.
The conditional mobile application job does not run on this stacked PR base;its
new credential/source configuration is source-contract tested,not a new native
mobile application acceptance claim.
The native generic fixture is not full-provider evidence;the separate new workflow
supplies real provider/application acceptance. Local focused runs,87staging
component tests and9actual root backup-execution-context tests are additional
executions,not an aggregate unique-test claim.

The full backend command is the Docker-isolated
`python scripts/run_tests_no_external_network.py` from backend-check.yml;native
commands are retained `rehearse_migration_115.sh`,145,146,147,148,149,150 and150
business scripts. Generic/native and root-policy commands are:

```bash
bash web/scripts/rehearse_generic_migrations.sh
bash web/scripts/rehearse_maintenance_role_restore.sh
bash web/scripts/rehearse_migration_policy.sh
python3 web/staging/integration/phase9_maintenance_backup.py REHEARSE
python3 web/scripts/check_migrations.py
python3 web/scripts/check_migration_transitions.py
python3 web/scripts/check_forward_release.py
python3 web/scripts/check_dependency_locks.py
python3 web/scripts/check_privileged_inventory.py
```

The last checker reports78classified application files. Migration validation has
150files in each tree,0errors and two retained duplicate-content warnings for
013/014. Actual001–150 Git diffs are empty. Migration150 remains
`63d4d0c7af93bd3c3e93158a2e281b41eed23b83bfafd4b3f1ba22313533b722`.

## Native runtime and supply-chain identity

The accepted source is91a above;the fresh candidate build is run39422044168,
attempt1,artifact12264990628. Its outer API digest is
`sha256:9d51871d8ceffc25f865fe587f36203d5875658148b83b75a05726cfec179ff9`.
Accepted runtime images:

- Backend:`sha256:ce6a73e4309498211770da3a51612afae04c3fb811e33b031356e03fc14a3ff0`.
- Frontend:`sha256:9f9c78e302f6fe1a483a508b86552630ff477c47b0239b54866031c7d5f4d8ba`.

The independently API-hashed staging report is artifact12264837132 from
run39422044167,attempt1,digest
`sha256:eb84c5832086f6ed41c6acecfb6e3427b3843d5a516941eb06b49c9a738706c8`.
It binds plan
`c658f164fe430b9aabfede23ab902fba2acc3d716a6d68178f2586862135d974`,schema150,
delivery/outbox/deletion protocols2/2/2,all11service identities and runtime code
hashes. Source overlays were absent. The owned stack stopped after acceptance.

Real user and tenant deletion each completed all ten steps on attempt1,with two
confirmed effects and final state `completed_with_retained_records`. Native Auth
identities and Storage objects were removed;an unrelated tenant/Auth/object
snapshot stayed unchanged. The worker restarted and resumed consumption. Actual
integration revocation,host-file deletion and lost external-response recovery were
not exercised by this happy-path probe.

Chromium151.0.7922.34 passed nine login/MFA/admin/cookie/session/mobile groups,
with0page errors and0blocked external hosts. These are selected browser cases,
not full forms/builder/commerce/reservation/calendar E2E. Retained native business
regressions remain in the245executions.

## Preserved failures and safety observations

The native before-fix diagnostics failed for foreign clients,prepared work and a
real replication-mode writer;their unchanged assertions pass after correction.
The evidence checksum/reopen race and omitted nested tooling were separately
reproduced before correction. Logs remain private;see
[the interruption matrix](13-FAILURE-INJECTION.md).

Initial native backup attempts exposed a fixture CLI output-path issue and
semantically identical ACL-array ordering. The wrapper now streams actual output;
canonical ACL comparison retains every grantor/privilege andNULL/empty distinction.
A later readiness fixture raced PostgreSQL's initialization socket and now waits
for final TCP readiness. No important assertion was removed.

The first full-provider job refused failed backend CI. The next stopped before
providers because the classic image store could not resolve the accepted OCI
manifest identity. The isolated runner now verifies an empty daemon,retains its
root-private configuration preimage and prepares the required native store;no
image identity is relabeled. Native019b then passed application/deletion assertions
but failed the supervisor restart wait. The corrected real-supervisor start plus
strict source/image/protocol/health/consumption observation passed at91a,and every
required component must be healthy before completion. Prior failures stay visible.

Initial bounded production observation found schema146,a valid installed
controller source marker and disabled/inactive auto-deploy timer. An additional
metadata query was stopped before SQL because expected ownership labels did not
match;that is a blocked observation,not evidence of a production incident. Its
Docker inspection was broader than needed,stayed in-process and was not logged;
further inspection must select metadata fields and bind independently verified
ownership. No production service,SQL state,controller,role,ingress or backup was
modified. Private operational identifiers are not published here. The installed marker and
schema observation do not establish the complete current descriptor/configuration/
controller-tree or actor-ownership acceptance.

## Three required demonstrations

1. **Existing coordinated146→150 protected release:BLOCKED.** Native SQL and fresh
   genesis150 acceptance are not this demonstration. The actual maintenance
   coordinator/private-provider/handoff/boot/replica integration is unfinished.
2. **Future automatic protected150→151 release:BLOCKED.** Discovery,canonical
   planning,AST classification and native minimal future SQL work without a
   schema151module. Full-provider acceptance correctly refuses published150's
   protocol0 at151;the user retained150. Protected generic dispatch is also not
   connected. No separate test-domain authority was issued for a full operation.
3. **High-risk refusal:PARTIAL.** Conservative parser/policy/native negative cases
   and ClassD staging refusal pass,without unauthorized writes. A complete actual
   generic privileged dispatcher demonstration remains unexecuted.

**Is the existing protected release complete?NO.**
**Is the architecture technically complete?NO—NOT READY.**

## Recovery and operational boundaries

Independent original-role/database/object-byte component recovery passed. It did
not activate original native object metadata or restore the complete application/
configuration/controller journal/worker stack. Fresh full-provider genesis is not
restoration. No new full-application PITR,DB/object recovery-point reconciliation,
corrupt/missing-WAL drill or off-host disaster recovery was completed. RPO/RTO and
production downtime remain uncertified. Historical PhaseVII installation/reboot
and PhaseVI full restore remain historical rather than current-head proof.

Generic native tests retain real lost-COMMIT observation/process interruption and
replay refusal. Full privileged interruption at each migration/private recovery/
write-handoff/worker/proxy/boot boundary remains NOT TESTED. No consumed authority
was replayed,no queue reset to force admission and no backup restored over newer
production data. See[02](02-PROTECTED-CONTROLLER-COMPLETION.md).

## If151 is added tomorrow

CI automatically discovers exact committed mirrored SQL,checks immutable history,
ordering/checksums and reserved142 semantics,classifies with the locked PG17 AST,
generates a canonical source-bound plan,rehearses supported routine SQL natively,
builds fresh authenticated images and launches the full-provider workflow.
Unknown/destructive SQL is restrictive;ClassD cannot enter automatic staging.
The full-provider run initializes its independent base,applies captured forward
bytes,observes committed schema and checks real worker protocols before startup.

With the current150 contract,a151candidate fails that real deletion protocol
probe;there is no silent fallback or synthetic protocol2. Correcting that contract
requires an independently reviewed coordinated successor. Even after compatibility
is fixed,the production engine remains blocked until the protected coordinator,
live runtime/backup/replica/health checks and independent policy/issuer integration
are completed. A declared ClassA or source-controlled PASS is not authorization.
Application-only changes generate no fake migration. Old/new rolling compatibility
is an additional required live gate,not proven by new-image genesis acceptance.

## What needs approval,and what still needs implementation

Human/administrator controls:main ruleset and protected environments,independent
review,current-production backup/replica/restore acceptance,approved installation
and fresh protected operation authority. GitHub currently reports protected=false,
rulesets=[],admin=false,maintain=false. Required actual check names and safe
integration order are in[18](18-PR-INTEGRATION-READINESS.md).

Engineering first:complete the existing maintenance coordinator,candidate/runtime
and backup/replica/configuration connection,positive complete writer inventory,
private provider recovery,existing write handoff and durable worker/proxy/boot
recovery. Then prove the combined operation and generic automatic routine path in
an independent privileged test domain. Scoped deletion credentials and uncertain
external-effect reconciliation remain P1security work;full object-aware recovery,
off-host restoration and broader product coverage remain P2. No P3expansion was
introduced. See[21](21-REMAINING-ROADMAP.md).

The recommendation is to review these verified source changes while retaining
the150admission block,and finish/prove the specific remaining connections in the
existing controller. Do not treat the remaining engineering as merely missing
production permission. No production merge,rollout or automation activation is
recommended by this report.
