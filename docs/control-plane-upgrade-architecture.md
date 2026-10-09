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


### Operator-authorized emergency automated Auth acceptance

The separately named `operator-authorized-automated-exact-images-v1` mode is
available only for this protected provider402 transaction. It replaces the
`human_auth` evidence gate with `automated_auth`; it never creates or relabels
`human_evidence`. A root-private, fixed-path operator authorization record must
contain explicit Madar operator approval, the exact preparation binding
(source/images/schema/checkpoint/provider/provenance), and an expiry no longer
than 24 hours. The completed protected report must bind that record digest and
actual isolated exact-image password, invalid-password, logout, refresh, TOTP,
AAL2, tenant/dashboard, cross-tenant, business-fence and browser/API checks.
Customer credentials and secrets are not used or recorded. Missing, pending,
expired or changed evidence rejects authorization and every activation boundary.
Normal graduation must consume the same acceptance mode and digest. Normal
deployment, migration, provenance, worker, rollback and all other recovery gates
remain unchanged. Historical human results remain historical evidence only.
This policy does not authorize activation by itself; protected credentials and
Phase-2 receipts remain mandatory.

### Source-only provider402 controller identity and unused-install repair

Protected recovery/prepare/normal entrypoints disable bytecode writes before
controller imports and reject existing Python caches before loading controller
modules. Trusted direct module imports use `python3 -IB`; the helper package also
disables subsequent bytecode writes. Bare entrypoint execution re-executes in
the same isolated `-IB` interpreter before loading any controller module. Installation builds an explicit source-only tree, archives the old
tree (including caches) and publishes atomically. Fingerprints continue to hash
**every** installed file; source, manifests, configuration and authorization are
not excluded. Cached substitute code is rejected, never executed.

The existing pre-activation installed-but-unused transaction can be repaired
only by an explicit root-approved canonical contract containing the previous
context digest. The trusted installer verifies the live old one-time credential,
witness, Phase-2 receipt, exact previous evidence, all non-cache attested files,
unchanged production fingerprints and absence of any traffic/ownership activation.
Only recognized paired Python cache files may be archived in this narrowly
bounded repair attestation. Under both locks it preserves prior credentials and
receipts, atomically replaces the interlock with credential-free pending state,
and retires the old unused credential. A new credential is issued only after
canonical reinstallation and attestation. This cannot repair an active recovery,
refresh/reuse an authorization, waive Phase2, alter traffic, or restore data.
The explicit installer inventory also includes the existing normal-local
transition entrypoint, launcher and six helper modules.

### Active local-rollback emergency routing authority

The isolated emergency routing package is an independently approved additive
repair, not an ordinary upgrade, unused-install repair or credential refresh.
Its development source is `web/deployment/lib/emergency_routing_repair.py`.
An operator-approved source/plan digest bootstrap installs an immutable root-owned
copy below `/var/lib/madar-control-plane/emergency-routing/<plan-digest>/`, with
exclusive fresh authorization, original-state hashes, audit and routing pre-images.
The installed canonical controller and all historical authorization/transaction
records remain byte-identical. Old PASS records provide no authority for this path.

A dedicated root systemd relay starts after Docker and before the existing stable
proxy. Its gate runs explicitly as root despite the proxy unit's `User=madar`;
ordinary proxy startup remains under madar. Both listeners bind only loopback.
Every new connection verifies the original approved runtime identities, current
Docker role addresses, local connectivity, schema115, recovery write fence and
consumer inhibition. The route references stable loopback ports rather than
container IPs, so restarts/reboots require no stale-address publication or new
volatile credential. The relay preserves HTTP streaming and WebSocket bytes
without logging requests, credentials or payloads; concurrency and systemd
resources are bounded. Docker access is pinned to the host's local Unix socket.

The one-time installer and subsequent explicit reconcile use only their fresh
narrow authorization. Source, destination, ref, driver and production paths cannot
be supplied through CLI/environment overrides. State changes/revocation deny new
connections. Publication uses the existing locks and preserves full pre-images.
Unsafe pre-images compensate to Nginx 503 maintenance; failed compensation stops
only the proxy, disables Docker restart and closes the startup gate. Audit records
retain success/failure and current independent observations, without upgrading
historical recovery receipts or granting business writes. New package/units are
installed only after separate approval of the exact reviewable operation.

The emergency Nginx include also supplies a loopback frontend router on 39402.
It routes API, uploads and existing legacy backend paths through the verified
backend relay, preserving existing rewrites and the independently inspected
frontend security headers. Other frontend paths retain the original frontend
behavior. This prevents the frontend image's static backend DNS cache from
reintroducing stale addresses. Public verification includes frontend `/api`
readiness, identity, recovery status and the write-denial probe.

A fresh emergency retry from verified 503 maintenance uses a new source/plan
approval and exclusive sibling package/authorization/audit namespace. It preserves
the original installed relay, authorization, status, audits, service and drop-in
byte-for-byte. A new 91 retry drop-in replaces only the reviewed effective startup
gate; collisions or unknown startup controls refuse the operation. The old relay
continues under its original authority; that authority cannot approve new code.
Candidate validation through sustained activation has a hard 180-second wall-clock
watchdog, with remaining-budget command and HTTP timeouts. Each convergence round
checks exact live identities, transaction/write fences and stopped consumers,
then proves the intended loopback frontend router is serving the bound backend
identity. Only transient availability errors are retried. Three consecutive full
successful rounds spanning at least five seconds, including public readiness,
recovery restriction, denied writes and healthy proxy, are required. Integrity
failures abort immediately. Failure-stage/type and monotonic timing are sanitized
and recorded exclusively in the new audit. Compensation has a separate 60-second
watchdog before the existing proxy-only shutdown fallback (two 30-second commands).
No historical receipt is rewritten, no image is rebuilt, and no database restore,
write grant, migration or worker start occurs.

### Normal-local preparation after emergency availability recovery

Forward transition verification must reject historical `restore_verified` flags
and aggregate PASS summaries as proof for a supplemented coordinated manifest.
The fresh, explicitly approved evidence digest must bind a root-protected
`restore-execution.json` packet, the exact manifest and complete restored file
inventory, retained runner/transcript bytes, successful network-isolated execution,
and a separately retained independently restored off-host receipt. A changed
manifest needs new verification. No validator emits production authorization.
Runtime-only rollback retains its integrity checks and never restores that backup.

The protected read-only write-authority directory is mounted into the normal
backend and all three normal workers. Worker polls, claims and scheduling stay
in standby until the root authority grants NORMAL; missing/invalid authority
fails closed. Standby health is not permission to consume jobs. Recovery-profile
workers still cannot start. No source test grants production write authority.

The emergency relay pins the old controller, protected inputs and consumer
inventory. Normal preparation must fail before changing authority or renaming
containers while public upstreams still use its loopback listeners. A separately
governed, verified READ_ONLY routing handoff is required first. Merely allowing
`local_rollback_active` or reconstructing lost /run credentials is prohibited.
The current source does not yet supply that fresh active-transaction resumption
adapter; these guards must not be presented as a completed writable cutover.

`checkpoint_execution_proof` validates scope and byte bindings only; it does not
establish execution provenance from JSON or approve a runner. A trusted restore
supervisor and its actual independent execution still have to be verified. The
existing online Node 1 SSH replica is unencrypted; encryption must be described
accurately rather than inferred from the separate age-backup mechanism.

The logical restore runner can preload only pg_cron/pg_net. It verifies cron job
launching is off and pg_net is assigned an absent database before restoring any
data. Role prerequisites use verified role names with NOLOGIN, never saved
password SQL. Its result excludes role attributes, ownership/ACLs and complete
coordinated/platform recovery. It cannot issue a normal-production PASS.


The independently executed sealed-checkpoint component restore uses a networkless
native PostgreSQL with the original cluster bootstrap identity, preserved roles,
membership grantors, database ownership and ACLs. Internal archive hardlinks are
materialized as independent files; unsafe paths/links/devices and changed bytes
fail closed. A completed quarantine can be independently measured again without
overwriting it. Every restored controller/configuration file remains inactive.
Native Storage attributes omitted by tar are derived only from the exact restored
database; all object versions must have identical bytes, every file must map,
and an independent read-only source comparison must match every attribute.
Only a new private restore quarantine receives these attributes. Original backup
manifests and historical restore flags remain unchanged. Off-host verification
reads the exact fourteen-file Node 1 replica and restores its database anew;
no remote write, decryption-key export, new capture or historical evidence reuse
is needed. Component recovery is not private platform/application acceptance.


Detached normal-local candidate preparation reuses the existing configuration and
application factory under a NEW exact-plan root-private continuation receipt.
The only permitted stage is the one durably claimed pending detached preparation;
missing /run credentials do not authorize or prevent that fresh operation.
Candidate images must bind the accepted source revision. Every retained input,
registered fallback identity and local provider restriction is rechecked before
effects. Existing namespaces, ports (including stopped Docker reservations) or
candidate resources reject staging; no existing resource is overwritten.
New names avoid the emergency relay's pinned business-consumer inventory. The
candidate has a separate traversable read-only authority directory, while its
three business standbys remain stopped. Backend/frontend destinations use the
inactive slot's fixed loopback ports and never persist Docker-assigned IPs.
The component has no traffic-publication, controller-installation, consumer-start
or NORMAL-write-grant operation. A complete independently validated continuation
adapter and fresh explicit cutover approval remain required. These development
regressions are not independent platform restore or production acceptance proof.

The fresh continuation observes twenty-five fixed input bindings, including the
entire installed controller tree as inactive bytes. Operator-owned canonical
runtime state and native configuration are hashed observations to the approved
plan; they are not root-protected authorization/execution evidence. Root-private
continuation authorization, journals, checkpoint proof and positive write fences
retain their separate strict hierarchy checks. No ownership is repaired by hand.
Read-only publication validates candidate Nginx syntax before replacing routes,
then reloads and requires three consecutive complete rounds spanning five seconds
inside a hard 180-second window. Only explicit availability failures reset that
streak. Image, source, fence or network-integrity failures abort immediately.
The exact routing pre-image is preserved exclusively. Restoring the old emergency
route is safe only before retained controller/worker/state bindings change; later
compensation requires the complete fresh current-data fallback adapter. The
current source components alone must not be advertised as a writable entrypoint.


Fresh active-rollback preparation also binds a fixed retained dependency
inventory: all eleven native services, the registered fallback's Redis and both
canonical release slots. Native/Redis health and all six stopped consumers are
checked before staging. Container IDs, exact images, secret-free specification
hashes, network IDs and bridge/IPAM configuration are pinned; ephemeral container
IP addresses are excluded. These hashes are observations to the new plan, never
historical authorization. No production installation is authorized by these
source changes or isolated restore results.


The current-data compensation verifier uses the fresh continuation's protected
receipt and compensation phase, revoked positive write authority, exact retained
fallback/native identities and all stopped consumers. It resolves role addresses
again for every verification. It intentionally does not require the superseded
installed controller hash to remain old after an authorized installation, and
never changes or relabels the old authorization. The original transactions and
native configuration must remain unchanged. This verifier is not yet a complete
relay installer or writable bootstrap; source unit tests do not authorize its
production use. No checkpoint restore is a compensation operation.


Fresh worker handoff occurs only after sustained public READ_ONLY publication and
controller resumption. It reuses the existing CANDIDATE single-owner authority,
archives exact ownership bytes and renames stopped inactive-slot resources into
unique retained names before naming the accepted candidate canonically. Identity
and collision checks precede effects; no resource/volume is deleted. Three new
workers may start only as healthy non-consuming READ_ONLY standbys, with bounded
startup checks and exact source/image/specification bindings. Compensation stops
bound candidate IDs even if renaming was interrupted. The retained origin SHA
comes from the existing recovery contract, not the candidate revision. These
source components still require a complete governed bootstrap and fresh cutover
approval before any production invocation.

The continuation quiesces configured backup timers through its fresh durable
authorization before detached staging or initial coordinated-marker publication.
Exact timer states are saved once; installation verifies and reuses that protected
preimage without overwriting it. Active backup services or automatic deployment
block this operation. Runtime validation after canonical naming uses the original
six candidate container IDs, image/specification digests and network IDs, allowing
IP reassignment while rejecting changed roles, ownership or write restrictions.
These source components still require the complete reviewed continuation entrypoint
and fresh exact cutover approval; unit tests do not authorize production effects.

The positive authority effect component requires a NEW root-private exact-source
receipt, durable write-grant-pending boundary, completed read-only/standby phases,
new controller attestation, executing prerequisite verifier and complete actual
read-only runtime/owner checks. It saves the prior authority and write boundary
once before atomically publishing NORMAL using the reviewed directory-permission
fix. Revocation does not require compensation journaling. It does not create
acceptance proof, publish normal release state or constitute a complete cutover
entrypoint; fresh operator approval and the complete adapter remain mandatory.

Current-local reconciliation observes all public table row counts and canonical
JSON SHA-256 roots in one read-only repeatable snapshot, with schema115 in that
same snapshot. Catalog and retained runtime bindings must remain unchanged. No
rows, password verifiers or secret values are emitted, and no migration/ledger
repair is permitted. The retained origin-slot writer fence is a separate guarded
effect after sustained read-only handoff; it stops only original bound backend
and frontend IDs and retains their containers. Read-only reconciliation records
do not themselves authorize production or prove current-source app acceptance.

The fresh normal configuration/state publication is distinct from the write
grant. It executes only after the durable write-boundary event and successful
read-only runtime/owner checks. It archives exact current environment, release
state, traffic and backup configuration under the new root-private plan, then
publishes local connectivity and a schema115/no-migration known-good overlay.
Historical recovery transactions and authorization stay intact. Canonical runtime
outputs retain the madar identity; secret-bearing archives stay root-private.
These outputs do not grant writes or enable automation and do not substitute
for independently executing application acceptance or a complete cutover adapter.

Compensation listeners use an additive exact-plan service and two NEW loopback
ports. The source package is root-private, source-only and hash-checked under an
isolated interpreter before serving and before every connection. Until fresh
compensation phase/receipt, revoked write authority and stopped consumers verify,
listeners fail closed. Installation validates a staged .service unit, refuses
existing units/records and preserves the original emergency service and drop-ins.
This component does not publish routing or constitute normal boot resumption.

Durable candidate contract bindings may be reconstructed from new protected
records for read-only boot inspection/revocation. Reconstruction verifies the
new receipt, accepted source/images and unchanged local configuration without
reusing stage permission or old emergency runtime authorization. It starts no
container, grants no write authority and never reconstructs /run credentials.
The worker verifier follows each real health contract: notification/deletion
require HTTP200 plus status=ok; calendar requires HTTP200 plus healthy=true; all
three require consuming=false while the positive authority remains READ_ONLY.

Prospective normal boot resumption requires the completed NEW continuation,
actual accepted source/image/backup evidence and bound runtime IDs/specifications.
It fences writes before starting those exact IDs, verifies native locality and
schema115, and requires three complete direct read-only rounds spanning five
seconds within180 seconds before restoring NORMAL. Lost /run credentials and
historical PASS records grant nothing. Failure after its first effect must invoke
current-data compensation. This source component still requires the complete
reviewed adapter, boot service/drop-in installer and fresh prospective approval.

Read-only public convergence alone does not permit controller/owner changes.
The handoff captures the actual proxy instance and old Nginx worker PIDs before
reload, then requires all old workers to exit while a new generation serves the
accepted candidate. This drain shares the same180-second deadline; it never
forces client connections closed. A proxy restart/image/specification change
aborts. Only after drain may the pinned old controller/worker inventory change.

Future boot-gate preparation is additive: retain the old emergency drop-ins and
effective unit bytes, validate a new exact-plan oneshot service and a NEW92
override, and enable it without starting it during staging. The listener unit
must match its protected receipt and be active. Existing normal boot overrides
are never silently replaced. The boot entrypoint must implement both completed
NORMAL resumption and interrupted current-data recovery before this installation
can form part of an approved executable cutover.

The active-rollback continuation now has a concrete adapter,
`active_recovery_operations.py`, and a stdlib-only entrypoint,
`web/scripts/resume_active_recovery.py`. The entrypoint measures the complete
root-private source inventory and canonical plan bytes before importing any
privileged deployment module. `verify` executes read-only preconditions;
`execute` creates a new exclusive authorization namespace and runs the existing
ordered protocol once. Changed bytes and consumed attempts cannot reuse approval.

The adapter connects detached staging, the bounded read-only public handoff and
old-worker drain, canonical installation, retained-writer fencing, typed local
reconciliation, single-owner standbys, normal configuration publication and the
positive write grant. It requires actual exact-image application acceptance; unit
tests and previous recovery PASS packets cannot supply it. Interrupted execution
uses the existing boot actor and current-data compensation. Compensation attempts
to stop every independently bound consumer even when another identity fails.

After actual normal readiness, the adapter runs the existing ordinary backup in
a NEW per-plan local namespace, actually restores that logical backup in an
isolated target, and streams it to the append-only Node 1 receiver. The approved
application execution binds the existing Node 1 alias, filesystem UUID and backup
configuration hash. Historical LATEST/retention scopes stay untouched. This is a
post-normal data backup, not a relabelled coordinated checkpoint. Root completion
binds actual acceptance, backup/restore/replica, installation, ownership and
publication records; backup timers resume only after completion. Automatic
deployment remains disabled pending separate recovery-interlock supersession.
Implementation alone does not authorize production execution: final-source
acceptance and fresh exact-plan operator approval remain mandatory.

The post-normal backup is created once in its new temporary per-plan namespace.
After actual restore and append-only Node 1 verification, that same directory is
published with rename-noreplace into the existing configured ordinary backup root.
Exact prior local LATEST bytes are archived before the marker points to this new
verified local data. No historical backup directory or Node 1 LATEST is replaced,
and capture retention cannot touch historical scopes. This connects the verified
new backup to the unchanged configured timers without creating another checkpoint.


A fresh active-rollback retry may bind the root-protected original backup-timer
preimage of a consumed pre-candidate staging failure. The new plan binds the old
plan, authorization, phase journal and timer snapshot bytes; it accepts only the
exact authorized/pending/failed sequence, unchanged retained runtime inputs and
no candidate contract/identity. This snapshot is data, never reused authorization.
Timers must remain idle/inactive and are restored to their ORIGINAL configured
states only after normal local backup/restore/Node 1 completion. No obsolete
hosted backup job is resumed during preparation. Nonsecret backup-health marker
reads accept the established readable 0644 mode; secret and credential readers
continue to require private permissions.


Detached continuation allocation is now bound to current RECOVERY worker ownership,
protected active-local-rollback state and local-fallback traffic identities, not
the historical recovery origin slot. Exact retained container/image/specification
and network bindings, stopped target resources, free sockets and stopped Docker
reservations, Redis locality, candidate/archive names and a non-overlapping subnet
are checked by the SAME read-only feasibility path before authorization and under
the deployment locks immediately before staging. The exact target/ports/retained
writer/Redis/subnet are sealed in the new plan; changed allocation fails closed,
without stopping or displacing existing resources. Saved normal runtime and
post-handoff retained-writer fencing use that sealed allocation. Historical
transactions, consumed attempts and currently serving recovery stay unchanged.

A stopped Docker port declaration may be retained during detached staging ONLY
for the exact two already-retired known-good backend/frontend containers named
by the protected local-transition contract digest. Source labels, original
known-good image identities, loopback role ports, stopped state and restart=no
are independently verified and their IDs/specifications sealed in the NEW plan.
These archived resources are neither started, displaced nor edited. Host sockets
must still be free; unknown, changed, running or restartable declarations reject
preflight/staging. This narrow retirement predicate never permits reuse of a
live port or arbitrary stopped Docker reservation.


Created normal-local business standbys bind exact container/image/configuration
and declared network names/role aliases to the existing bridge object IDs.
Before first start Docker may leave NetworkID empty; this allowance applies ONLY
to State.Status=created, Running=false, the exact primary NetworkMode and no
allocated endpoint/IP. Changed or extra networks/aliases/objects still reject.
The governed single-owner handoff records a new root-private, plan/CID-bound
start intent before starting each worker. After start, runtime verification
requires populated exact network IDs and all identity, owner, fencing and health
checks. Docker's observed OomKillDisable=false to null first-start metadata change
is compared against the original receipt only for governed business-worker
starts; all other specification bytes remain bound. Original receipts are never
rewritten. Repeated start commands cannot overwrite the exclusive start intents.
The same narrow comparison permits safe stopping during compensation; it grants
no start/write authority. Production deployment still requires fresh approval.

A new continuation may bind a retained detached candidate only when its original
protected journal is exactly authorized/pending/failed before publication. The
old plan, authorization, journal, candidate contract/identities and READ_ONLY
write-authority bytes are hashed as data in the NEW plan; they issue no authority.
Exact bridge objects, configurations, image/container identities, role endpoints,
three never-started CREATED consumers and unchanged fallback/transaction inputs
must pass the corrected read-only verifier. Shared preflight/staging resolution
recognizes only those exact already-published detached loopback ports as planned
retirement; all unrelated reservations still fail closed. Fresh authorization
permits stopping ONLY that unpublished backend/frontend/parser by exact ID,
recording a new exclusive retirement receipt and checking actual free sockets
before creating the new-source candidate. All original resources, networks,
volumes and protected records remain. The three old CREATED business workers are
never started. New source/image acceptance cannot be relabeled from the old
candidate. Existing original timer states are usable only with this independently
bound pre-publication failure proof; timers resume after verified normal backup.
Failure before public handoff leaves the original restricted fallback serving.

Detached-port feasibility uses Docker-compatible SO_REUSEADDR and an exclusive
bind+listen probe, never SO_REUSEPORT. Retired TCP TIME_WAIT connections are not
live resource owners; a real listener still rejects, and exact stopped Docker
reservations/identities are checked separately. The same probe runs before
approval and immediately after governed retirement under both locks. Disposable
real Docker reproduction demonstrated the frozen no-reuse probe failing errno98
with no listener while a replacement could start, and the corrected complete
retirement/replacement sequence preserves its independent restricted fallback.
Historical failed-attempt messages remain unrecoverable; this demonstrated
mechanism must not be relabeled as a captured historical exception.

Staging failures append sanitized diagnostics to the existing protected journal:
source-defined operation, phase, exception type, source-relative function/line
traceback and numeric OS errno when available. No exception message, command,
configuration value, locals, customer information or source line is recorded.
The plan/source hashes and append-only timestamp bind the diagnostic to the
frozen executed source. Original receipts/journals are never rewritten, and a
recorded failure remains consumed. Pre-publication failure preserves the working
restricted route; post-publication failures retain existing compensation rules.

### Compensated post-publication baseline

`active_recovery_compensated.py` observes state F separately from the original
prepublication observer. Original installed-source and emergency effective-unit
gates remain unchanged. Fresh source-bound plans embed the measured baseline,
including historical consumed execution as data, revoked NORMAL authority,
current installed tree, startup/backup controls and exact retained runtimes.
No historical receipt is rewritten or converted into new authority.

The continuation rechecks actual stopped-slot ownership, immutable resource
specifications, Redis/network identity and exclusive sockets under both locks.
The previous restricted listener remains installed; the consumed boot actor
requires explicit controlled supersession. The future installer preserves its
unit, archives the exact 92 preimage and installation intent, publishes the new
92 atomically, disables only the consumed boot actor and attests effective
controls before routing. Failures retain their phase/type and sanitized stack
locations in the protected journal; customer rows and configuration values are
never diagnostics. All post-publication compensation preserves current local
PostgreSQL and returns to verified restrictions or maintenance.

The compensated continuation may permit append-only audit growth between preparation and execution. It proves the exact original audit prefix (count and complete row hash) unchanged at the bound timestamp, rejects backdated insertions/deletions/edits, and keeps all other 95 public table roots and security-critical identities exact. The original snapshot remains historical data; source fencing captures the actual latest snapshot. This exception grants no business-write permission.

The state-F database binding also hashes Auth users/identities (excluding only last-sign-in and updated timestamps), complete original MFA factors, storage metadata/buckets, table ownership/ACL/RLS settings and policy expressions inside PostgreSQL. Only a SHA-256 root is emitted. Changes to credentials, factors, tenant records or authorization catalogs require a new baseline and plan.

Post-compensation continuation requires a new independently executed read-only reconciliation at the root-private `normal-local-preparation/local-post-compensation-reconciliation-<exact source SHA>/run-<12 hex>/actual-execution.json` path, selected by a protected append-only `index-<exact execution hash>.json`. Its actual invocation, immutable runner, transcript hash and retained-resource scope must match the new plan. Historical pre-install reconciliation remains historical data and cannot satisfy this current-state gate. Original prepublication reconciliation rules remain unchanged.

Failed read-only reconciliation executions remain at their original paths. A later successful run creates a new immutable source snapshot and execution record; only successful actual executions receive a new exact-hash index. Foreign paths, source namespaces and execution hashes fail closed.
