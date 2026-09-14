# Privileged control-plane upgrade architecture

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

Backup operations are part of the exact-SHA installation boundary. In addition
to the original migration backup scripts, the guard protects `backup_support.py`,
`verify_latest_backup.sh`, `replicate_latest_node1.py`, both existing removable
replication helpers, `restore_madar.sh`, and `rehearse_backup.py`. The installer
backs up, checks source identity, installs, and compares all operational helpers
and local/verification/Node 1/removable systemd units. Their target files join
the shared root-ownership, mode and symlink preflight. The installed controller
retains identical helper copies for provenance attestation.

Before installation, existing operational timers are stopped and running backup
services cause a safe refusal; active backup jobs are not killed. Successful
completion or safely attested pre-install recovery restores captured timer
activity. Installation never enables these timers. New backup-state storage is
created as the unprivileged `madar` identity, not through root writes into an
application-owned tree. The minimal state directory contains only verified
creation metadata and is mounted read-only for release/refresh/rollback.

| Component | Installed location | Responsibility |
| --- | --- | --- |
| Stable launcher | `/usr/local/sbin/madar-control-plane-upgrade` | Starts Python in isolated mode, discards the caller environment, and loads the currently trusted bootstrap implementation. |
| Bootstrap implementation | `/opt/madar/control-plane/deployment/lib/control_plane_upgrade.py` | Holds locks, validates the exact SHA and production, stages the candidate, invokes the installer, runs controlled deployment cycles, attests results, records audit state, and applies phase-specific failure semantics. |
| Authorization validator | `/opt/madar/control-plane/deployment/lib/control_plane_upgrade_authorization.py` | Prevents ordinary/manual release-controller processes from racing a root upgrade. |
| Replaceable controller | `/opt/madar/control-plane/deployment` | Canonical release, migration, proxy, guard, installer, and systemd implementation. |
| Path/remote trust contract | `/opt/madar/control-plane/deployment/production-paths.conf` | Root-owned canonical production paths and expected Git remote identity. |
| Installer | `bin/madar-install-control-plane` | Backs up the old controller, atomically publishes the exact staged controller, installs units and the next-invocation launcher, and leaves automation stopped. |
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
tree, validates the exact canonical path contract, syntax-compiles every
deployment Python source in an isolated `python3 -I -B` process using built-in
`compile()` on the source bytes, checks all deployment shell syntax, checks
ownership/state-root conditions, and requires at least 1 GiB free in staging
and backup filesystems. Syntax validation writes no bytecode and does not depend
on ignored `PYTHON*` environment variables. Its child interpreter is the
resolved absolute `sys.executable` of the already-running trusted bootstrapper,
not a candidate path, `PATH` lookup, `/usr/bin/env`, or distribution-specific
filename. The original and resolved executable paths must exist beneath
non-writable real directories; the target must be executable and not
group/world writable, and root execution additionally requires root ownership.
The installer uses one
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
| 8 | `installer_dry_run` | Execute the candidate installer's complete read-only preflight without apply, including the same deterministic filesystem, source, production-path, timer/service and backup checks used by apply; verify the protected-tree digest is unchanged. |
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

## Initial bootstrap

The currently installed controller predates this command. The first merged
release containing it still requires one final execution of the existing
reviewed manual control-plane installation procedure from an exact-SHA,
root-protected staging tree, including timer quiescence, installer dry-run,
backup, apply and provenance/health verification. That installation places the
launcher in `/usr/local/sbin`. After this one-time bootstrap, future protected
control-plane releases use only the one-command workflow.

The bootstrap backup must be a unique child of the installer-owned root path,
for example
`/var/lib/madar-control-plane/backups/pre-<sha-prefix>-<UTC timestamp>`.
Do not place privileged backups below application-owned `/var/lib/madar`:
write authority over an ancestor permits replacement of an otherwise private
child. The installer may create its own mode-0700
`/var/lib/madar-control-plane` hierarchy after the shared dry-run preflight has
attested `/`, `/var`, and `/var/lib`; it never changes those system parents.

That manual controller-first publication intentionally creates a temporary
split state: installed controller at the explicitly approved future release,
serving application at its older known-good ancestor. The governed upgrader is
then run for that same exact SHA. It classifies the authorized bridge, stages
and validates the candidate, performs installer dry-run and installed-controller
attestation, but does not reinstall or downgrade the controller and does not
fabricate a new controller backup. Its controlled deployment promotes the
application through the canonical immutable release machinery, runs same-SHA
validation, and restores the timer's captured state.

## DB-ahead recovery operation

`--recover-current-schema` is an explicit operator mode and is absent from
`madar-auto-deploy`. It uses a distinct current-production preflight because
the ordinary preflight correctly refuses an incompatible serving binary. This
special preflight accepts only a clean and coherent known-good/proxy origin,
an auto-deploy timer already disabled, an actual live schema strictly above
the serving binary maximum, and no degradation beyond schema incompatibility
plus the known legacy notification-queue classification.

The paired `--rehearsal-attestation` file must be absolute, nonsymlinked,
root-owned, mode 0400 or 0600, no older than seven days, and bind the exact
approved SHA and live schema to all required backend, frontend, browser,
database, worker, RLS, and readiness checks. Candidate staging then validates
the separate exact-schema, no-migration recovery contract before any
installation or application deployment.

The installed controller invokes `madar-release-deploy <SHA>
--recover-current-schema` only through the same one-use systemd credential and
interlock boundary used by governed upgrades. The release state machine stages
the inactive slot with queue consumers disabled, performs a no-overlap worker
handoff, rechecks state/schema/backup identity, uses the existing atomic switch,
and builds a second compatible bridge slot before success. After routing has
changed, failure handling detects the actual routed candidate even if durable
known-good finalization was interrupted and records forward-repair semantics.
It never routes to the incompatible historical release.

Successful finalization marks the canonical active and compatible-fallback
records as schema-recovery artifacts and records `migration_result` as
`not_requested`. A later ordinary control-plane inspection recognizes that
terminal only when the completed recovery record, active slot/SHA/schema and
the exact zero-migration recovery contract all agree. It otherwise reports a
missing or invalid migration terminal and stops. Recovery credentials and the
recovery entrypoint are never accepted by that later normal release.

Because an installed controller that predates this mode cannot parse the new
flags, the first use requires the already-documented exact-SHA, root-protected
manual controller bootstrap. That bootstrap installs controller code only; it
does not switch application traffic or alter schema. The separately reviewed
recovery command then performs the application transition. Exact commands and
abort conditions are in
[`schema-96-forward-recovery-runbook.md`](schema-96-forward-recovery-runbook.md).

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
