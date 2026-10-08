# Privileged control-plane upgrade architecture

Active local-Supabase integration profile: **schema115 only**, migration class
`none`, migration policy `none`, no selected migration manifest. Retained bridge
examples below describe reviewed migration history/future work and authorize no
SQL for this profile. Main's 116..135 artifacts remain checksum-verified; features
requiring those schemas retain their existing unavailable/upgrade-required gates.
Production installation, promotion and migration require separate approval.

## Purpose and authority

This document explains the security architecture and operator workflow for
`madar-control-plane-upgrade`. It complements, but does not replace,
[`production-release-policy.md`](production-release-policy.md). The current
implementation remains authoritative. Changes to the bootstrapper, installer,
provenance guard, path contract, deployment entrypoints, or systemd unit must
review and update both documents in the same change.

Ordinary application releases remain unattended. A release that changes a
protected control-plane path is intentionally blocked by
`madar-control-plane-guard`. A human authorizes one exact immutable
`origin/main` commit with one privileged command:

```bash
sudo madar-control-plane-upgrade <exact-40-character-sha>
```

The explicit `sudo` plus exact SHA is the approval boundary. This command does
not grant the non-root deployer permission to install future commits and does
not turn the upgrader into a general application deployment path.

## Components and trust boundaries

| Component | Installed location | Responsibility |
| --- | --- | --- |
| Stable launcher | `/usr/local/sbin/madar-control-plane-upgrade` | Starts Python in isolated mode, discards the caller environment, and loads the currently trusted bootstrap implementation. |
| Bootstrap implementation | `/opt/madar/control-plane/deployment/lib/control_plane_upgrade.py` | Holds locks, validates the exact SHA and production, stages the candidate, invokes the installer, runs controlled deployment cycles, attests results, records audit state, and applies phase-specific failure semantics. |
| Authorization validator | `/opt/madar/control-plane/deployment/lib/control_plane_upgrade_authorization.py` | Prevents ordinary/manual release-controller processes from racing a root upgrade. |
| Replaceable controller | `/opt/madar/control-plane/deployment` | Canonical release, migration, proxy, guard, installer, and systemd implementation. |
| Path/remote trust contract | `/opt/madar/control-plane/deployment/production-paths.conf` | Root-owned canonical production paths and expected Git remote identity. |
| Installer | `bin/madar-install-control-plane` | Backs up the old controller, atomically publishes the exact staged controller, installs units and the next-invocation launcher, and leaves automation stopped. |
| Hosted-domain synthetic monitor | `/usr/local/lib/madar/monitor_hosted_domains.py` with `madar-hosted-domain-monitor.service/.timer` | Performs unauthenticated read-only public checks; installed and attested as a protected operational helper, with timer activation left to a separate operator decision. |
| Authorized transient unit | `madar-control-plane-upgrade-<pid>-<cycle>.service` | Runs the exact `madar-auto-deploy` entrypoint as `madar` with the ordinary path/backup environment, hardening properties, and a systemd `LoadCredential` visible only inside that cycle. |

No `NOPASSWD` rule or automatic invocation is added. The `madar` account
cannot invoke the root upgrader. The bootstrapper never reads security-sensitive
paths from its caller environment.

## Exact-SHA candidate authentication

The argument must be exactly 40 hexadecimal characters and is normalized to
lowercase. Branch names, tags, abbreviations, revision expressions, paths, and
extra arguments are rejected.

The canonical repository URL is pinned in the root-owned path contract. Git
network operations run as the existing least-privileged `madar` identity. The
bootstrapper freshly fetches `origin/main` and requires all of the following:

1. configured `origin` exactly matches the pinned URL before and after fetch;
2. freshly resolved `refs/remotes/origin/main^{commit}` equals the approved SHA;
3. the object is a commit;
4. the deployed production commit is its ancestor;
5. the production checkout is clean.

If main advances, rewrites, diverges, or changes remote identity after the
operator chose the SHA, the transaction fails. It never substitutes a newer
head or accepts a local arbitrary ref.

Candidate authorization deliberately precedes controller-compatibility
classification. The current serving application is attested first without
interpreting a guard failure. Only after the approved SHA has been verified as
canonical `origin/main`, as a commit, and as a forward descendant may the
upgrader run the installed guard and classify one of these states:

- `normal_compatible`: the installed guard accepts the currently serving
  application SHA. Existing installation/protected-change behavior applies.
- `controller_ahead_bridge`: the guard rejects the serving SHA specifically
  because protected trees differ, while installed provenance exactly equals
  the approved current-main SHA, the serving SHA is its strict ancestor, both
  objects are available commits, the repository remains canonical and clean,
  and the installed guard accepts the approved SHA.

The second state is a narrow privileged-upgrader exception for the intentional
controller-first bootstrap boundary. It does not make a generic failed guard,
unrelated/rewritten history, an arbitrary CLI SHA, a different installed SHA,
or a downgrade acceptable. Ordinary `madar-auto-deploy` and
`madar-production-deploy` continue to invoke the unchanged guard against their
candidate and remain blocked on protected changes.

Every installed-guard invocation made by the privileged coordinator runs under
the sanitized canonical `madar` deployment identity. The production repository
is owned by `madar`; running its Git inspection as root would correctly trigger
Git's dubious-ownership defense. The coordinator does not add a root
`safe.directory` exception, alter repository ownership, or modify Git
configuration. This identity rule covers current-controller compatibility,
approved bridge attestation, post-install candidate attestation, and the
pre-install restoration-safety check. Ordinary deployers already run as
`madar`, so their execution model is unchanged.

The guard retains its existing exit-code contract, where status 1 can describe
either a protected-tree difference or a guard-internal failure. The privileged
bridge never treats that status alone as authorization: it independently
requires an exact protected-path diff, canonical candidate identity, forward
ancestry, clean repository, exact installed provenance, and a successful guard
against the approved SHA. A context or Git failure therefore remains
fail-closed without changing the ordinary deployers' guard semantics.

## Privileged staging and TOCTOU boundary

After fetching, root creates a unique mode-0700 transaction below
`/var/lib/madar-control-plane/upgrades/staging`. The sibling root is deliberate:
application-owned `/var/lib/madar` is writable by `madar` and therefore cannot
parent privileged trust state. The upgrader creates a Git bundle pinned
to the fetched remote-main ref and requires its complete advertised-head set to
be exactly `<approved SHA> refs/remotes/origin/main`. Because a remote-tracking
ref is not a clone branch, the upgrader does not use ordinary `git clone`.
Instead it initializes a template-free repository, verifies the bundle there,
and explicitly fetches only the attested remote-main ref from the local bundle
into a private temporary ref. All network protocols and extension helpers are
disabled for this import; hooks, credentials, fsmonitor, caller Git config, and
replacement objects are disabled throughout staging. The imported commit must
equal the approved SHA before detached checkout. The temporary ref is then
deleted, and staging is accepted only if detached `HEAD` still equals the
approved SHA, the worktree is clean, and no refs or remotes remain. The source
production repository's refs and worktree are never changed by staging.

Before candidate code executes, the bootstrapper verifies required paths,
rejects symlinks anywhere in protected paths, hashes the complete protected
tree, validates the exact canonical path contract, compiles Python, checks all
deployment shell syntax, checks ownership/state-root conditions, and requires
at least 1 GiB free in staging and backup filesystems. The installer uses one
shared read-only filesystem preflight before both dry-run success and apply. It
walks every existing privileged source/destination component without following
symlinks; requires root ownership with no group/world write bit or effective
non-root ACL write grant; requires private state directories to be mode 0700;
checks destination mounts are writable; and proves `renameat2(RENAME_EXCHANGE)`
on the target filesystem using disposable directories inside the protected
candidate staging parent. Standard system parents such as root-owned mode 0755
`/var/lib` satisfy this contract. The protected-tree hash
is checked again after installer dry-run. Candidate code is not claimed to be
intrinsically safe: operator approval of the exact reviewed SHA remains the
code-trust decision.

## Locks and one-time authorization

Provider402 traffic switching publishes canonical callback-safe proxy logging
before recovery Auth traffic is served. A running legacy single-file bind is
recreated only through the installed, attested proxy service, after offline
syntax validation and inside the authorized switch/rollback boundary. Private
preparation cannot invoke that production service: its checked scoped proxy
must discard Docker logs. No fixture flag or CLI parameter selects this behavior
in production, and Phase-2 authorization remains mandatory.

The provider402 trusted installer also quiesces all four backup timers before
installer apply. It first rejects running backup services and records the timer
states in a private, exact-contract installation snapshot. It then stops and
verifies the timers and rechecks backup services. This uses the credential-free
pending installation interlock, never ordinary upgrade authorization, and does
not cancel backups or automatically resume timers after failure or recovery.

Provider402 installation consumes the immutable preparation record
`provider402/rehearsal.json`: exact contract/source/images/schema115,
non-migrating policy, provider402/provenance, checkpoint and private target
preconditions. Human and rollback gates may remain PENDING during preparation;
installation remains explicitly root-authorized, not automatic. Only successful
installation/attestation/witness permits the one-time preparation credential.
Completing rehearsal does not rewrite that contract or refresh its credential.
Phase 2 instead consumes `provider402/completed-rehearsal.json` with every
mandatory gate PASS and human outcomes explicitly matching source SHA and both
image IDs. Its receipt binds the immutable preparation digest, completed report
digest, human-evidence digest, provider evidence and exact contract. Every
Phase-3 boundary verifies all of these. Pending, historical-image, modified or
missing completion evidence cannot activate traffic or consumers. This separates
fresh-install acceptance from final human admission without any bypass flag.

Provider402 trusted installation may supersede an older normal-upgrade quiesce
only when its exact protected file digest is included in the recovery contract.
The record must be version 2, `quiesced`, credential-free, and for the same
installed/serving legacy SHA, with valid preserved backup-timer state. Every
deployment/backup operation must be inactive; any recovery credential, witness,
or prior controller transition rejects the operation. After canonical staging
and installer dry-run, under both locks, the trusted installer archives the
original record privately with a durable receipt, then atomically replaces it
with the pending-install interlock. It never leaves an unprotected interval,
restores automation, grants runtime authorization, or modifies normal upgrade
authorization. Missing/unpinned/changed/authorized records fail closed.

The upgrader holds an exclusive root-owned `upgrade.lock` for its entire
transaction. During current-production preflight it also acquires the normal
`/var/lib/madar/releases/deploy.lock`, proving no release or migration is
active.

After systemd is quiesced, root writes an `in-progress.json` interlock below
`/run/madar/control-plane-upgrade`, then releases `deploy.lock` so the canonical
release controller can acquire it. Every `madar-release-deploy` invocation
checks this interlock before any release operation. It rejects the invocation
unless a transient systemd unit supplied both the exact approved SHA and a
fresh random bearer token through `LoadCredential`, whose SHA-256 digest
matches the root-owned interlock. The source credential is mode 0600, is copied
into systemd's per-unit credential boundary rather than a process environment,
is removed when each cycle returns, and is regenerated for the second cycle.
The public interlock contains only the SHA and one-way digest.

The timer stays disabled throughout. Thus an auto-deploy cycle cannot start,
manual controller entrypoints cannot pass the interlock, and the authorized
service still uses the existing deployment lock. The interlock is retained on
post-install failure and removed only on success or safely attested pre-install
failure. The explicit `madar-migrate` and traffic-switch entrypoints enforce the
same credential check while the interlock exists, so a parallel manual schema
or proxy mutation cannot race the transaction. Canonical deployment rollback
switches remain authorized inside the credential-bearing transient unit.

## Upgrade phases

| Phase | Audit name | Mutation boundary and result |
| --- | --- | --- |
| 0 | `exclusive_lock` | Root-only upgrade lock; a second invocation fails before mutation. |
| 1 | `current_production_preflight` | Validate caller, installed provenance, clean production HEAD, release state, active/stable identity/readiness, schema compatibility, migration terminal state, workers/frontend/proxy, canonical paths, service and timer. Existing degradation stops the run. This phase does not trust the CLI SHA to authorize a bridge. |
| 2 | `candidate_resolution` | Least-privileged fetch/read-only remote check; exact origin/main, commit, canonical remote and forward ancestry checks. |
| 3 | `controller_compatibility` | Run the current guard and classify only `normal_compatible` or the fully attested `controller_ahead_bridge` described above. |
| 4 | `protected_change_detection` | In normal state, no protected diff returns `not_required`; ordinary auto-deploy remains responsible. An authorized controller-ahead bridge continues even though installed provenance already equals the candidate. |
| 5 | `automation_quiesce` | Capture timer state, disable/stop timer, stop service, arm interlock, release normal deploy lock. |
| 6 | `candidate_staging` | Create the protected exact-SHA Git bundle and detached root-owned tree. |
| 7 | `candidate_static_preflight` | Required-path, symlink, digest, syntax, contract, ownership, ACL, filesystem capability and capacity validation. |
| 8 | `installer_dry_run` | Execute the candidate installer's read-only preflight without apply. Re-run the shared deterministic filesystem, source, and production-path checks; require the auto-deploy timer/service to remain quiesced and reject any running backup/verification/replication service, while allowing scheduled backup timers to remain active because dry-run is non-mutating. Verify the protected-tree digest is unchanged. Installer apply later requires those backup timers to be quiesced. |
| 9 | `control_plane_install` / `control_plane_install_attestation` | Normally create a protected backup and atomically install, then attest provenance, guard, modes, units, paths, backup hashes and absence of legacy authority. For `controller_ahead_bridge`, skip publication and backup creation and instead use `preinstalled_control_plane_attestation` to verify the already-installed exact candidate controller. |
| 10 | `controlled_candidate_deployment` | Issue a one-cycle systemd credential and synchronously run the exact ordinary auto-deploy entrypoint in a hardened transient unit while the timer remains disabled. The canonical controller alone may build, migrate, promote or advance production Git. |
| 11 | serving attestation | Require production HEAD, installed provenance, active/known-good state, stable and slot SHA/readiness, schema range, workers, frontend and proxy target to agree. Require a terminal migration outcome. |
| 12 | `same_sha_idempotence` | Run the same systemd path with a new token. Require stable health and byte-identical release state, proxy target and migration automation state: no rebuild, switch, SQL, backup, or identity mutation. |
| 13 | `automation_restore` | Remove interlock and restore the captured timer enabled/active state exactly. An initially disabled timer stays disabled. |
| 14 | cleanup | Remove only this transaction staging tree; retain backup and audit history. |
| 15 | `complete` | Print the concise non-secret operator result. |

## Current-production and post-deploy attestation

Current preflight intentionally ignores degraded readiness of the retained
inactive slot after worker cutover. It requires the active slot and stable
routes to be ready and identical to the durable known-good SHA. It rejects an
in-progress release, rollback failure, nonterminal migration, dirty checkout,
unknown traffic target, incompatible schema, missing worker readiness, or an
active deployment service.

After deployment the same checks are repeated against the candidate SHA. The
bootstrapper does not hard-code schema 93. It uses durable release state and the
candidate health compatibility range. Automatic migration is successful only
when its coordinator is terminal: `already_at_target` or
`post_migration_validation_complete`. A release without automatic migration
policy may return `not_requested`. Incomplete or forward-repair-required state
fails the upgrade and leaves automation disabled for diagnosis.

## Failure semantics and point of no return

Failure handling is phase-aware; there is no generic trap that restores old
files, traffic, schema, or timer state.

- **Before candidate installation:** production is untouched. If automation
  was quiesced, the old installed SHA, old guard, serving release, schema and
  readiness are re-attested. Only then is the original timer state restored.
- **After controller installation but before durable application promotion:**
  success is never claimed. No ad-hoc controller restoration occurs. The
  interlock remains and timer stays disabled for operator diagnosis using the
  protected backup.
- **After durable promotion:** durable known-good state is the point of no
  return even if later health/service checking fails. Traffic is not switched
  back, old controller files are not restored, and the timer remains disabled.
  Repair proceeds forward.
- **After schema advancement:** database rollback and reverse SQL are never
  attempted. Migration backup, attestation, execution state, release state and
  artifacts are retained. The accepted compatible bridge remains the repair
  base.

For a preinstalled controller-ahead bridge, there is no old-controller restore
boundary inside the governed transaction: the approved controller was already
installed before invocation. A failure before application promotion keeps the
old application serving, preserves the approved controller, leaves automation
disabled, and records
`controller_ahead_bridge_application_untouched_timer_disabled`. A failure after
promotion uses the ordinary forward-repair semantics. Dry-run failures never
quiesce automation or alter an interlock. On success the exact pre-transaction
timer state is restored, so an initially disabled timer remains disabled.

An inactive previous slot with stopped queue workers is not a production
failure. An active/stable readiness failure always is.

## Self-update semantics

The launcher and implementation loaded at invocation are transaction authority
for the entire run. The candidate installer atomically replaces the controller
tree, then installs the candidate launcher only after publication. Python has
already loaded the old implementation and does not import or re-exec candidate
bootstrap code. Therefore bootstrapper A validates, installs and attests
candidate B under A semantics; the next invocation uses B. A half-published
candidate launcher never takes over the running transaction.

## Audit, logs, and secrets

Every authorized root invocation creates atomic mode-0600 JSON plus a detailed
mode-0600 log below:

```text
/var/lib/madar-control-plane/upgrades/history/
```

Controller backups remain below:

```text
/var/lib/madar-control-plane/backups/pre-<sha-prefix>-<UTC timestamp>/
```

Records include phases, exact identities, slots, schemas, timer states,
migration result, backup path, same-SHA result and failure semantics. Commands
run with an allowlisted environment. Output is redacted for secret-bearing
assignment names. Environment files, credentials, tokens, private keys,
database passwords and secret values are never printed or copied into audit
JSON.

## Operator commands

Inspect without stopping automation or installing:

```bash
sudo madar-control-plane-upgrade --dry-run <exact-40-character-sha>
```

Authorize and complete the upgrade:

```bash
sudo madar-control-plane-upgrade <exact-40-character-sha>
```

On success the command reports provenance, slot/schema change, migration
terminal result, readiness, same-SHA result, restored timer state, backup and
audit paths. On failure it reports the phase, safe traffic identity, mutation
boundary and next safe action; detailed output stays in the audit log/journal.

Do not work around failure by pulling `/srv/madar/production`, hand-copying
controller files, modifying provenance/state, running migration SQL, switching
traffic, or re-enabling the timer after a post-promotion failure without first
diagnosing retained evidence.

## Initial bootstrap (completed)

The one-time production bootstrap is complete. The privileged launcher is now
installed at `/usr/local/sbin/madar-control-plane-upgrade`, and the canonical
root-owned controller is established under `/opt/madar/control-plane/deployment`.
Future protected control-plane releases use the governed one-command exact-SHA
workflow; they must not repeat the historical manual publication procedure
merely because ordinary auto-deploy rejects a protected-path change.

The bootstrap was required because the first release containing the privileged
upgrader could not be installed by a command that did not yet exist in the
trusted controller. Its reviewed procedure used an exact-SHA, root-protected
staging tree, timer quiescence, installer dry-run, a protected backup, apply,
and provenance/health verification.

The bootstrap backup contract requires a unique child of the installer-owned
root path, for example
`/var/lib/madar-control-plane/backups/pre-<sha-prefix>-<UTC timestamp>`.
Privileged backups must not be placed below application-owned
`/var/lib/madar`: write authority over an ancestor permits replacement of an
otherwise private child. The installer-owned mode-0700
`/var/lib/madar-control-plane` hierarchy is separate from application-owned
release state.

The historical controller-first publication intentionally created a temporary
split state: the installed controller was at the explicitly approved future
release while the older known-good application was still serving. The governed
upgrader then ran for that same exact SHA, classified the authorized bridge,
staged and validated the candidate, performed installer dry-run and
installed-controller attestation, promoted the application through the
canonical immutable release machinery, ran same-SHA validation, and restored
the captured automation state. That bootstrap boundary is historical; normal
future protected releases start from the already-established privileged
upgrader.

## Implementation and test map

- orchestration, staging, audit, attestation, failure boundaries:
  `web/deployment/lib/control_plane_upgrade.py`
- shared dry-run/apply filesystem trust contract:
  `web/deployment/lib/control_plane_filesystem.py`
- isolated launcher: `web/deployment/bin/madar-control-plane-upgrade`
- one-time interlock: `web/deployment/lib/control_plane_upgrade_authorization.py`
  plus `madar-release-deploy`, `madar-migrate`, and `madar-switch-traffic`
- protected-path rule/operator message:
  `web/deployment/bin/madar-control-plane-guard`
- atomic install/backup/self-update:
  `web/deployment/bin/madar-install-control-plane`
- systemd transient-unit authorization loading:
  `web/deployment/lib/control_plane_upgrade.py :: run_deploy_service()`
- focused security/state-machine coverage:
  `web/backend/tests/test_control_plane_upgrade.py`
- integration coverage: `web/backend/tests/test_monorepo_deployment.py` and
  `test_schema_compatibility_control_plane.py`
- post-terminal operator-only Supabase CLI ledger reconciliation:
  `web/deployment/lib/supabase_ledger_reconciliation.py` (never invoked by the
  privileged upgrade transaction itself)


## Optional local Supabase client topology (pre-cutover preparation)

The candidate release controller accepts the opt-in setting
`MADAR_SUPABASE_CLIENT_NETWORK=madar-supabase-client`. It appends the immutable
application client overlay after normal release topology for startup, config
validation and candidate cleanup. This does not use MADAR_COMPOSE_OVERRIDE and
does not select staging frontend API origins. Preflight requires exactly
`SUPABASE_URL=http://madar-supabase:8000` and attests the external network is an
internal Docker bridge. Backend and three queue workers join it; parser/remote
networks remain unchanged. The local Supabase gateway must have the stable alias;
connectivity is verified by normal readiness and separate worker probes.

The option is absent by default. This is a protected controller source change;
installation still requires explicit governed approval. It adds no port, schema,
migration mode, timer action, worker handoff, traffic switch or promotion bypass.
Core schema 115 was used in pre-cutover rehearsal. The existing 116 manifest must
not be invoked for this migration. Refer to `web/precutover/README.md` and the
private operator cutover report before proposing production execution.


### Exact schema-115 local Supabase candidate contract

The reviewed `local-supabase-schema115` deployment profile declares minimum,
maximum, target and rollback schema115, migration class `none`, policy `none`,
and no selected migration manifest. `check_forward_release.py` validates that
whole exact contract and continues to verify all historical checksum pins and
the unchanged 115/116 and 115..135 migration manifests. The preceding descriptors are
retained as `schema-114-116-bridge.json` and `schema-114-135-bridge.json` for regression tests; it is
not the selected release contract. Neither schema114 nor schema116 passes this
candidate's compatibility gate. Any future schema transition needs its own
reviewed bridge contract. No automatic migration was invoked in rehearsal.

The installed controller must agree with this exact candidate contract before
an approved deployment. That remains a governed production change, not part of
pre-cutover engineering. Existing provenance, backup, deployment lock, exact-main,
readiness, traffic, worker and observation gates remain unchanged.


### Credential-safe callback proxy logs

Prepared frontend/stable proxies log method and normalized URI without query or
Referer. Exact verification callback locations suppress access logs and reduce
request-bearing error logging to critical failures. The prepared local gateway
LDS template uses Envoy PATH(NQ:ORIG_OR_PATH) and omits Referer, generated to a new
file by a checksum-guarded helper. Set MADAR_SAFE_ENVOY_LDS_TEMPLATE to that
reviewed file before loading the gateway overlay. Existing API callbacks,
upstreams, port bindings and routing headers are unchanged. No live proxy was
reloaded. This protected proxy source still needs governed installation approval;
edge logging policies remain an operator gate.

## Provider402 restricted recovery contract

See [provider402 sign-in recovery](provider402-signin-recovery.md). This source
adds an explicitly scoped transaction contract and application fence; it does
not authorize installation or activation. Normal readiness gates remain
unchanged. The separate durable recovery state rejects ordinary release and
migration ownership, and local runtime rollback must preserve current Auth
sessions. A protected production adapter and exact-image rehearsal are
required before activation review.

The provider402 recovery bootstrap is independent of normal upgrades, forward
repair and schema recovery. Its root launcher uses fixed paths and a clean
environment; authorization binds the entire protected recovery contract digest.
It reuses trusted root bundle staging, filesystem preflight, installer backup and
installed provenance verification. Only a root-protected exact-contract receipt
can account for the approved old-to-new controller transition; other production
fingerprints remain exact. Auto-deploy stays inhibited until a separately
reviewed recovery exit. Runtime rollback uses the registered private local
fallback without restoring PostgreSQL/Auth or reactivating consumers. See
`docs/provider402-signin-recovery.md`; source implementation alone does not prove
a rehearsed or authorized production path.

### Protected provider402 phase separation

`PREPARE_AND_REHEARSE` runs through the fixed-path `madar-provider402-prepare`
launcher and a root-protected private-resource adapter. It checks exact source,
images, schema115, no migrations, actual provider402 origin/provenance, a verified
checkpoint, private target health and source write-fence validation. It does not
require human Auth or completed runtime rollback evidence to start the private
candidate and fallback. It cannot mutate production traffic, worker authority,
configuration or slots. Preparation receipts do not authorize activation.

`AUTHORIZE_ACTIVATION` requires all fifteen completed rehearsal gates, including
human Auth, MFA/AAL2, tenant isolation, business write denial, both-slot worker
inhibition, traffic/interruption rehearsal, passive fallback, runtime-only local
rollback and failure injections. A root-protected receipt binds the exact source,
image IDs, schema contract, checkpoint, provider402 evidence, production
fingerprints and completed rehearsal digest. Changing an input invalidates it.

`ACTIVATE_RECOVERY` and production traffic changes independently require that
completed receipt. Installation and credential issuance require immutable
preparation evidence and trusted root attestation. No fixture switch,
environment flag or Phase-1 receipt waives it. Normal deployment, schema recovery,
forward repair and migration checks remain unchanged. Recovery rollback changes
only runtimes using the current local provider; it never restores a checkpoint
over accepted Auth sessions and never routes to hosted Supabase HTTP.

### Fresh provider402 bootstrap ordering

Root recovery provenance reads disable Git optional locks as well as replacement
objects. A clean-worktree status check cannot refresh or replace the canonical
operator-owned Git index. Canonical fetch/staging continues through the existing
operator identity and trusted resolver.

The recovery installation adapter translates canonical staging's transaction
parent/repository pair into the actual repository plus a separate, fresh backup
path under the protected backup root. Static validation and both installer
invocations use that repository. A staging directory can never be selected as
an installation backup, and an existing backup destination is rejected.

Initial installation is a root-only operation from trusted protected source,
bound to the complete exact contract and immutable preparation record. It retains
the canonical current-origin/main resolver, staging, static preflight, installer
dry run, checkpoint/provenance validation and production locks. It does not
require a bearer credential before the installer can issue one. Installation
and installed-controller attestation precede an exclusive protected installation
witness and one-time contract-bound credential. An existing credential/interlock
or installation witness rejects fresh installation rather than refreshing it.
No untrusted/non-root entrypoint can issue the credential.

Subsequent activation authorization and runtime operations require that
credential/interlock. Phase 2 still requires all exact rehearsal gates; Phase 3
still independently requires Phase-2 authorization. Installation never switches
traffic, starts consumers or executes migrations. There is no skip-auth flag or
arbitrary-ref resolver. Normal deployment/upgrade authorization is unchanged.

A root-written pending installation interlock is armed before quiescing/install.
It contains no bearer token and authorizes no runtime operation. Ordinary
mutators fail closed while it exists. Only successful installation attestation
can advance this exact interlock to the issued one-time credential; failure
retains the pending interlock for operator review. No prior credential is reused.

### Governed graduation to the local provider

`madar-local-provider-transition` is a separate fixed-path root transaction.
Ordinary deployment still rejects provider402 state. Graduation requires the
installed exact canonical source/images, existing protected recovery credential
and Phase-2 receipt, a new contract-bound exclusive graduation authorization,
final typed reconciliation, synthetic-account cleanup, source-fence evidence,
a fresh complete checkpoint with independent restore and off-host proof, Auth
SMTP, local service health and private transition/failure-injection evidence.
No operation executes a migration, imports hosted sessions, or restores a DB.

Preparation archives the inactive hosted containers with restart policy `no`,
preserves their complete Redis container storage, and starts the exact normal local candidate on an
unpublished application bridge with outbound HTTPS capability. The separate
`madar-supabase-client` bridge remains internal. Both consumer sets must be stopped before exactly one new
owner is designated. Notification, calendar and deletion workers start in that
order with individual health checks; notification email remains disabled.
Only the newly created exact-source backend/consumers join the existing internal
recovery network. Existing Redis/fallback topology is unchanged. The candidate
preserves recovery Redis and Auth/security configuration; no keys, accepted
sessions or historical queues are cleared or replayed. Consumer restart policies
remain `no`; only governed single-owner operations may start them.

The normal backend mounts a root-owned authority directory read-only. Its
schema115/source/contract-bound authority begins as `READ_ONLY` and applies the
existing request and provider mutation fences. Missing, untrusted or changed
authority denies requests. A switch to the normal runtime preserves this fence.
Only the finalization transaction, after every bound production smoke gate,
publishes normal local configuration/release ownership, retires hosted writers,
and atomically grants `NORMAL` writes. No process restart is needed to grant or
revoke writes. Recovery-profile runtimes remain fenced regardless of this file.
Fenced normal-candidate reads retain commercial authorization through only the
schema115 `resolve_commercial_access(integer)` STABLE SQL lookup. Other RPCs
remain denied. Calendar bootstrap reads do not create default calendars.

Interrupted handoff/switch keeps a durable rollback-required state. Governed
rollback fences the candidate, inhibits consumers, restores RECOVERY ownership
and switches only to the registered local-compatible runtime using current
Auth/DB/Storage state. Even after normal writes, no checkpoint rewind is allowed.
Deployment requires checkpoint freshness. Runtime-only rollback still verifies
the bound archive's integrity and restore proof, but does not expire merely
because that deployment checkpoint is older than its freshness window.
The normal automation interlock remains retained until separately attested;
graduation does not automatically re-enable deployment or migration automation.

`auth-configure` is a bounded preparation operation under the same protected
root entry. It requires the existing recovery Phase-2 credential, exact source,
schema115, fresh independently restored checkpoint, final reconciliation and all
graduation proofs except SMTP, which must explicitly be PENDING. It cannot issue
normal authorization, start consumers, change traffic, or grant business writes.
It authenticates Gmail on port587 with certificate-verified STARTTLS and checks
the sender without generating mail. Only native GoTrue receives the six approved
SMTP variables and the exact public mediated verification/recovery callbacks.
The prior native configuration is quarantined. The pinned Auth image, native
Auth ledger, password/MFA fingerprints and current database are preserved.
Subsequent normal authorization still requires SMTP PASS with all other gates.
Existing operator-owned native Compose/environment files are read-only inputs
pinned by the protected reconciliation digest. Public Compose templates receive
no authority to execute controller code or mint credentials; the environment
file remains private. Mail/callback editing preserves every other native line,
including its original secret quoting. Failure repairs only the prior native
configuration and pinned Auth runtime, never the current database or sessions.
After SMTP preparation, create the final coordinated checkpoint/reconciliation
packet with the resulting native input fingerprints before normal authorization.
Normal consumers retain restart policy `no`. Protected `restart-worker` repairs
only the already designated normal owner under the deploy lock, with the same
source/image/configuration/credential bindings and no traffic or ownership
change. It cannot start a consumer from any recovery/preparation state, use a
hosted provider, or enable notification email. Runtime repair preserves current
data and does not expire solely with the old deployment checkpoint's age.

Before enabling Auth email callbacks, the protected `auth-configure` transaction
also verifies the stable proxy's effective configuration. A legacy single-file
bind mount may retain the old inode after controller installation. If needed,
the transaction preflights the exact canonical callback-safe configuration in a
networkless, read-only container using the pinned nginx image, then recreates
only the existing proxy through its installed systemd/Compose service. It
preserves upstreams, slots, worker ownership and the current local database;
serving recovery and worker inhibition are checked immediately afterward.

Normal graduation binds the existing private backup environment's before-digest
in reconciliation. Finalization preserves it in a protected archive and publishes
only the six PostgreSQL connection fields for the local loopback session pooler.
Native database credentials never enter backend or worker environments. The
protected publication receipt binds before/after configuration and the exact
transition contract; unaccounted edits reject all later operations. Scheduled
backups map only the exact internal Supabase API alias to its loopback host API,
and require matching local database settings. Other endpoints remain unchanged.
Publication does not run a backup, refresh a marker or enable a timer: actual
complete backup, independent restore and off-host proofs remain mandatory.
