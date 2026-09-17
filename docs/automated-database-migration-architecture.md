# Automated database migration architecture

Last implementation review: 2026-09-16

## 1. Purpose, authority, and scope

This document explains the design and state machine for Madar's automated,
post-`known_good` database migrations. It complements, but does not replace,
[`production-release-policy.md`](production-release-policy.md): the policy
specifies enforceable release gates, while this blueprint explains how the
bridge release, backup, migration, recovery, and forward-repair machinery fit
together.

The implementation is authoritative. If this blueprint, the release policy,
and the code disagree, investigate and correct the discrepancy; never weaken a
gate to make documentation true. The principal implementation is:

- `web/deployment/bin/madar-auto-deploy`
- `web/deployment/bin/madar-production-deploy`
- `web/deployment/bin/madar-release-deploy`
  - `automatic_migrate_known_good()`
  - `_create_verified_migration_backup()`
  - `_attest_migration_backup()`
  - `_validate_stable_known_good()`
  - `refresh_active_workers()`
- `web/deployment/lib/release_deployer.py :: ReleaseDeployer.deploy()`
- `web/deployment/lib/migration_executor.py`
  - `MigrationManifest.load()`
  - `LockedMigrationExecutor.verify_migrations()`
  - `LockedMigrationExecutor.run()`
- `web/deployment/lib/supabase_ledger_reconciliation.py`
- `web/deployment/systemd/madar-auto-deploy.timer`
- `web/scripts/backup_madar.sh` and `web/scripts/verify_backup.sh`

This design applies only to an explicitly opted-in, compatible, forward-only
migration manifest. It does not make every migration automatic, does not merge
release promotion and schema mutation into one rollback domain, and does not
provide automatic downgrade SQL.

Protected control-plane releases may be authorized through the root-owned
one-command workflow described in
[`control-plane-upgrade-architecture.md`](control-plane-upgrade-architecture.md).
For an ordinary protected upgrade, that bootstrapper synchronously invokes the
same ordinary auto-deploy path. For an already-promoted exact SHA in an attested
forward-repair state, it instead invokes the installed
`madar-release-deploy <SHA> --automatic-migrate` directly under the same
root-owned one-use credential boundary. The privileged coordinator does not
implement SQL migration itself, bypass backup/manifest gates, or alter the
bridge-first state machine.

## 2. Architectural goals

The architecture is designed to:

1. make a schema-compatible bridge application healthy, active, and durably
   `known_good` before any automatic schema mutation;
2. bind source, release metadata, migration manifest, SQL checksums, active
   release identity, and backup identity to the same immutable release;
3. retain ordinary blue/green traffic rollback until the migration point of no
   return;
4. take and independently verify a complete backup immediately before the
   forward-only phase;
5. serialize deployment orchestration and database migration execution with
   separate locks at their appropriate layers;
6. recover safely after a process crash or reboot without replaying an already
   committed transition;
7. validate the active application, refreshed workers, and stable route before
   recording final migration completion;
8. turn post-commit failure into a bounded, observable forward-repair workflow
   rather than attempting an unsafe rollback; and
9. durably classify a later release accepted at an already-reached target as a
   backup-free no-op without confusing it with an interrupted migration owned
   by that release.

## 3. Why bridge first

A bridge release declares a compatibility range containing both the live source
schema and the migration target. Ordinary release promotion therefore validates
and activates code that can serve the source schema before automation changes
the database. Promotion still has the normal inactive-slot, worker restoration,
traffic rollback, observation, and retained-release guarantees.

Only after `ReleaseDeployer.deploy()` atomically records the candidate as the
active `known_good_release` does migration automation run. This ordering matters:

- if bridge promotion fails, no backup or migration SQL is attempted;
- until migration begins, the retained prior release remains an attested
  traffic rollback target at the source schema;
- after a migration commits beyond the prior release's compatible maximum, the
  prior binary is no longer a safe traffic target, so recovery must proceed
  forward using the bridge release and its original backup.

The bridge's `compatible_min..compatible_max` range proves that the active
application can span the transition. Its `rollback_compatible_min..max` range
proves only where an old-release traffic rollback is valid; it does not promise
schema downgrade capability.

## 4. Components and responsibilities

| Component | Responsibility |
| --- | --- |
| `madar-auto-deploy.timer` | Runs the unattended check after startup and after each inactive interval; `Persistent=true` catches a missed run after reboot. |
| `madar-auto-deploy` | Fetches `origin/main`, applies control-plane provenance and release-state eligibility checks, chooses new-runtime, same-known-good, or application-equivalent flow, and re-enters migration automation for pending known-good releases. |
| `madar-production-deploy` | For a new runtime SHA, synchronously promotes the bridge, fast-forwards the production checkout, then makes a separate synchronous `--automatic-migrate` invocation. |
| `madar-release-deploy` | Owns the process-level deployment lock and exposes normal promotion and automatic-migration modes. |
| `ReleaseDeployer.deploy()` | Runs ordinary immutable blue/green promotion and atomically establishes `known_good_release`, `active_slot`, and a `known_good`/`complete` history event. It never runs migration SQL. |
| `automatic_migrate_known_good()` | Proves bridge identity, policy, compatibility, manifest, SQL checksums, and stable health. It either records a proven fresh already-at-target no-op, or proves rollback/backup identity, invokes the executor, and then refreshes workers and validates the active/stable application. |
| `MigrationManifest.load()` | Validates manifest release identity, repository-contained paths, supported classes, sequential transitions, and non-empty contiguity. |
| `LockedMigrationExecutor` | Revalidates checksums and backup, obtains the PostgreSQL advisory lock, checks live core schema, executes each transactional SQL file, and records per-file progress. |
| Backup/verify scripts | Create a timestamped complete backup and verify its manifest and artifacts. The coordinator additionally binds its manifest to release SHA and source schema. |
| `state.json` | Durable release authority: active slot, known-good identity/schema, release history, in-progress release, release failures, and rollback-failure state. |
| `automation.json` | Per-release migration coordinator state, retry deadline, backup path, phase, and final result. |
| `execution.json` | Per-release SQL executor state, verified backup, observed schema, and per-migration status/checksum. |
| `application_schema_state` | Authoritative live database schema for `contract_key='core'`; it decides whether a transition is pending or already committed. |
| Operator ledger reconciler | After coordinator completion only, validates exact release/state/health/schema/checksum identity and records the already-applied version in Supabase's CLI ledger. It never runs migration SQL. |

## 5. Ordinary unattended call flow

The automatic path is synchronous within one service run, with timer-driven
re-entry after failure or interruption:

```text
systemd persistent timer
  -> madar-auto-deploy
     -> fetch origin/main and run madar-control-plane-guard
     -> new runtime SHA: exec madar-production-deploy
        -> madar-release-deploy SHA
           -> ReleaseDeployer.deploy()
              -> immutable build and preflight
              -> inactive candidate and deep validation
              -> worker cutover, traffic switch, observation
              -> atomic state.json: active slot + known_good SHA + complete history
        -> only after successful return: git merge --ff-only SHA
        -> madar-release-deploy SHA --automatic-migrate
           -> deployment lock
           -> automatic_migrate_known_good()
              -> identity/policy/manifest/checksum/health/compatibility gates
              -> target already observed at this SHA's acceptance and no
                 per-SHA migration state: durable already_at_target no-op
              -> rollback-target attestation at source schema
              -> verified backup
              -> LockedMigrationExecutor.run()
                 -> PostgreSQL advisory lock
                 -> contiguous transactional migrations
              -> target-schema check
              -> worker refresh and active/stable-route validation
              -> automation.json completed
```

`madar-production-deploy` notices successful bridge promotion because its first
`madar-release-deploy` process exits successfully. That can happen only after
`ReleaseDeployer.deploy()` has atomically replaced `state.json` with the
candidate as active known-good and appended a history entry with
`status=known_good` and `phase=complete`. The wrapper then invokes
`--automatic-migrate` as a distinct, synchronous command. It is not a child of
the release state machine and is not a separate one-shot unit.

`automatic_migrate_known_good()` discovers opt-in by reading the candidate's
`web/deployment/releases/release.json`, requiring the exact policy value
`automatic-after-known-good-backup-first-forward-repair`, and selecting the
basename named by `migration_manifest`. Installed and immutable-candidate
metadata and manifest JSON must match. `CURRENT` or `STAGING` in a tracked
manifest is rebound in memory to the full invoked SHA; otherwise the manifest
must already name that exact SHA.

If bridge promotion succeeds but migration automation fails, the bridge remains
known-good and serving. The error does not enter `ReleaseDeployer`'s traffic
rollback handler. Mutation-phase failures are atomically recorded as
`failed_forward_repair_required` with a bounded retry deadline. On the next
timer activation, `madar-auto-deploy` sees that `origin/main` equals the
known-good SHA and directly re-enters `--automatic-migrate`; the coordinator
returns `retry_suppressed` until the deadline. The configured retry interval
defaults to 15 minutes and is clamped to 5 through 1,440 minutes. Read-only
precondition failures that occur before `automation.json` is started do not
receive that durable backoff and are retried at the timer cadence.

The privileged same-SHA repair path is deliberately independent of a mutable
branch head. If another commit reaches `origin/main` while an already-promoted
release is waiting for forward repair, the operator can still authorize the
exact serving SHA as long as it also equals installed controller provenance and
all durable migration/serving attestations remain coherent. Repair does not
stage or deploy the newer branch head.

Likewise, process or host interruption need not manufacture a failure record.
A coherent `status=running` checkpoint may be resumed through the same exact-SHA
repair path. The database schema and durable executor state determine which
already-committed transitions are skipped; SQL is not blindly replayed.

After a reboot, `Persistent=true` causes the timer to run a missed activation.
The same-known-good branch re-enters the idempotent migration phase. If a
documentation-only commit is ahead of an application-equivalent known-good
release, `madar-auto-deploy` first gives that known-good SHA a migration attempt
and only then fast-forwards the checkout, so documentation cannot strand a
pending schema transition.

## 6. Release-promotion state machine

The migration coordinator cannot begin until the separate release state machine
has completed:

| Release phase | Meaning |
| --- | --- |
| `source_validation` | Validate full SHA, immutable source, compatibility, and release identity. |
| `immutable_build` | Build and attest immutable images for the candidate SHA. |
| `preflight` | Revalidate contracts, Compose, migration validators, images, and storage. |
| `candidate_start` | Start the inactive blue/green slot. |
| `deep_validation` | Validate candidate readiness, version/schema identity, frontend, and API origin. |
| `worker_cutover` | Move workers to the candidate and validate again, restoring old workers on failure. |
| `traffic_switch` | Switch the stable proxy only after candidate readiness. |
| `observation` | Repeatedly validate the switched candidate. |
| `known_good` / `complete` | Atomically persist active slot, known-good identity, schema observation, images, and history. This is the prerequisite for automation. |

A pre-switch failure destroys the candidate and leaves the active target
untouched. A post-switch failure stops candidate workers, restores prior
workers, switches traffic to the retained known-good release, and removes the
candidate. A rollback failure is preserved for manual intervention. None of
these release failures can fall through to migration invocation because the
first command returns nonzero.

Successful ordinary promotion retires `compatible_fallback_release` in the
same atomic write as active/known-good acceptance. That record belongs to the
preceding recovery or migration operation, whose inactive slot is reused by
promotion. The new acceptance event retains the attested previous known-good
release on the opposite slot. It does not relabel that prior binary as a
target-schema migration fallback; after a fresh verified backup, migration
automation separately establishes the accepted bridge itself on that slot.

## 7. Migration state machine and durable representation

Some names in the following table are architectural predicates requested for
reasoning about the flow, not additional strings written to disk. The
“implemented representation” column gives the exact durable or derived form, so
this table does not invent persistence states.

| Architectural state | Implemented representation and transition |
| --- | --- |
| `bridge_known_good` | `state.json.known_good_release.sha` equals the requested SHA, its slot equals `active_slot`, there is no in-progress/rollback failure, and release history contains `status=known_good`, `phase=complete`. Stable candidate/backend/frontend validation must also pass. |
| `migration_pending` | Derived: exact automatic policy and manifest are valid, live schema is within the bridge range and below manifest target, and no matching completed `automation.json` covers the target. No literal `migration_pending` value is stored. |
| `pre_mutation_pending` | Privileged-upgrader derived state only, not written to migration state. Exact automatic policy/manifest/checksums validate; the migration directory is completely absent; live and recorded schema equal the manifest source; known-good state and that SHA's completed acceptance event agree on source and target. Final serving attestation does not treat this as terminal. |
| `forward_repair_pending` | Privileged-upgrader derived state only. Durable state is either a due `failed_forward_repair_required` checkpoint or a coherent interrupted `status=running` checkpoint in backup creation, migration execution, or post-migration validation. Exact immutable contract, acceptance, backup/executor identity, known-good SHA, and live schema bounds must agree. |
| `backup_required` | `automation.json` has `status=running`, `phase=backup_creation`, and no backup path. |
| `backup_verified` | The backup scripts pass, its complete manifest matches the release SHA and source schema, and `execution.json.backup.verified=true`. There is no standalone `backup_verified` phase; the next durable executor phase is `acquiring_lock`. |
| `migration_running` | `automation.json` phase is `migration_execution`; `execution.json` is `status=running` in `acquiring_lock`, `schema_validation`, or `migration_N`. |
| per-migration committed | After a SQL file returns, the core schema must equal `to_schema`; the executor records that item as `applied` with `completed_at`. On recovery, a database schema already at or past that `to_schema` is recorded `already_applied` and not replayed. The database schema is authoritative if a crash preceded the JSON checkpoint. |
| `post_migration_validation` | `automation.json` has `status=running`, `phase=post_migration_validation`; target schema is checked before workers are refreshed. |
| `complete` | `automation.json` has `status=completed`, `phase=post_migration_validation_complete`; `state.json.known_good_release.schema` equals target and history contains `post_migration_workers_refreshed`. |
| `not_requested` | Returned, not durably created, when policy is absent or not the exact supported value; phase is `manual_or_no_migration_policy`. |
| `already_at_target` | `automation.json` has `status=completed`, `phase=already_at_target`, `execution_status=already_at_target`, and `backup=null`. It is permitted only when this SHA has no prior automation or execution file and both its known-good record and its own `known_good`/`complete` acceptance event observed the target. Identity, policy, manifest, checksum, validator, stable-route, and schema checks still run first. No backup, database connection, executor `run()`, SQL, worker refresh, or prior-release backup rebinding occurs. |
| `failed_forward_repair_required` | Durable automation failure after mutation-phase state begins. The phase becomes `backup_creation_failed`, `migration_execution_failed`, or `post_migration_validation_failed`, with bounded `retry_after` and a truncated failure code. |
| `retry_suppressed` | Returned view of a prior forward-repair failure before `retry_after`; the durable failure remains unchanged. |
| executor `failed` | `execution.json` records the SQL executor error and any connection rollback error. Committed schema, not this file alone, controls resume. |

Identity, policy, manifest, checksum, validator, stable bridge, compatibility,
and source-schema rollback-attestation failures happen before mutation-phase
state is created. They make no database change and require correction of the
release, environment, or retained target rather than manufacturing a migration
failure record.

### Privileged current-origin interpretation

The ordinary timer path still follows the unattended rules above. The
root-owned upgrader additionally needs to distinguish a legitimate origin that
needs migration work from corrupt state before it can authorize a protected
controller/application transition.

This interpretation is origin-only. It must never make final serving
attestation permissive. `pre_mutation_pending` and `forward_repair_pending`
therefore authorize only entry into the existing canonical migration machinery;
success still requires `already_at_target` or
`post_migration_validation_complete` (or `not_requested` where automatic
migration does not apply).

## 8. Migration opt-in and manifest contract

Automation is explicit. The release contract must contain:

```json
{
  "migration_policy": "automatic-after-known-good-backup-first-forward-repair",
  "migration_manifest": "migrations-NNN-NNN.json"
}
```

The policy string is an exact allow-list, not a truthy flag. A release without
it remains eligible for normal application promotion but returns
`not_requested` from the post-promotion migration call. The release-level
`migration_class` and every manifest entry must be `expand-only` or
`forward-compatible`; `none`, `coordinated`, `breaking`, and arbitrary values
cannot enter automatic execution.

The manifest must be non-empty and contiguous. Each transition must satisfy
`from_schema + 1 == to_schema == migration number`. The first source and final
target must fit the release compatibility range, and the final target must equal
release metadata. Each path resolves beneath the immutable release repository;
escaping paths are rejected. Every file must exist and match its pinned SHA-256
before backup or database access, and the migration tree and modern-transition
validators run again from that immutable source.

## 9. Backup contract and identity

The coordinator requires an absolute, non-root `MADAR_BACKUP_DIR`. The backup
tool creates a new direct child named `madar-YYYYMMDDTHHMMSSZ`, includes the
database and configured persistent assets, writes checksums and a format-3
manifest, and publishes a backup as `complete` only after successful creation.
The independent verifier must pass before SQL execution.

The coordinator additionally requires the backup manifest to bind:

- `format_version == 3`;
- `status == complete`;
- `backup_id` to the directory basename;
- `release.git_sha` to the exact active known-good release SHA; and
- `database.schema_version` to the manifest source schema.

This is the implemented freshness model: a normal first attempt creates and
verifies a new timestamped backup immediately before execution. There is no
independent maximum-age threshold. A resumed partial transition deliberately
reuses the original, verified, direct-child backup recorded in that release's
`execution.json`; requiring a new backup after schema 91 would destroy the
identity of the schema-90 recovery point. An advanced live schema without that
attestation is rejected.

Backup creation failure prevents `LockedMigrationExecutor.run()` and therefore
prevents SQL. A nonexecuting executor instance is deliberately constructed
earlier only to checksum-verify immutable migration inputs; verification or
backup-identity failure likewise prevents `run()` and SQL.

## 10. Two locks, two responsibilities

`madar-release-deploy --automatic-migrate` holds
`$MADAR_DEPLOY_STATE_ROOT/deploy.lock` around the entire coordinator. This
serializes release promotion, backup, migration orchestration, state updates,
worker refresh, and other local deployment modes.

`LockedMigrationExecutor.run()` separately acquires a fixed PostgreSQL session
advisory lock with `pg_try_advisory_lock`. This serializes database migration
execution even if another correctly configured controller reaches the same
database. It is acquired after checksum and backup verification and held for
schema validation and all manifest entries. A held advisory lock rejects the
run; it does not wait indefinitely.

Neither lock substitutes for the other: the filesystem lock protects one
deployment state universe and its side effects; the PostgreSQL lock protects
the shared database.

## 11. Schema transitions, transactions, and idempotency

Before the first transition, the executor reads
`public.application_schema_state` for `contract_key='core'`. Live schema must be
between manifest source and target. Each file starts only when live schema
equals its declared source. Modern migrations are independently validated to
be transactional, lock the core schema row `FOR UPDATE`, guard exactly the
expected source, perform exactly one schema-version update, and end in
`COMMIT;`.

After a file returns, the executor re-reads the core schema and requires the
declared target. A transaction that did not commit cannot advance it. A
transaction that committed before a process crash has advanced it regardless
of whether `execution.json` received its next atomic checkpoint. On retry, an
entry whose target is already reached is marked `already_applied`, so completed
SQL is never blindly replayed. The final live schema must equal manifest target.

The JSON files use write/fsync/atomic-replace. They provide durable diagnostics
and resumption metadata, while the database remains authoritative for committed
schema advancement.

## 12. Crash, interruption, and reboot recovery

| Interruption point | Recovery behavior |
| --- | --- |
| Before bridge acceptance | Ordinary interrupted-release recovery restores prior traffic/workers and removes the candidate. No automatic migration is invoked. |
| After bridge acceptance, before the second command | The durable known-good identity survives. The persistent timer's same-known-good branch invokes automation. |
| During backup creation | Incomplete backup directories are not accepted as complete. Retry creates and verifies a usable backup before SQL. |
| After backup, before SQL | Verification is repeated. Execution state binds the selected backup; no schema transition has been committed. |
| During one migration transaction | PostgreSQL rolls back an uncommitted transaction. If commit completed, live schema reflects it and retry skips it. |
| Between migrations 91 and 92 | Retry requires and reuses the original verified source-schema backup, records 91 as already applied, and starts only 92 from schema 91. |
| After executor completion, before post-validation completion | Retry sees target schema, revalidates the active application and workers, and records completion without replaying SQL. |
| During worker refresh or stable-route validation | Automation remains forward-repair-required; retry repeats idempotent worker activation/validation against the exact active known-good SHA. |
| Reboot while pending or failed | The persistent two-minute timer re-enters automation. Durable retry suppression prevents mutation-phase retry storms. |

The same SHA and source schema are required when reusing a backup. A completed
automation record at the observed target returns immediately. Invalid or
missing durable state fails closed.

A fresh later release accepted with the live target already recorded is a
different case from crash recovery. With no per-SHA migration files, its
acceptance-time target observation proves that the transition predates that
release's migration phase. It records `already_at_target` atomically. If either
per-SHA state file exists, or acceptance recorded the source schema, the
coordinator cannot use this classification; advanced schema then requires the
exact original release-bound backup attestation.

## 13. Worker refresh and application validation

Automation validates the serving bridge before backup: active-slot candidate
health, stable backend `/health/version` SHA, stable backend `/health/ready`, and
stable frontend HTTP 200. After SQL it requires the target schema and calls
`refresh_active_workers()`.

The fresh `already_at_target` path has no worker-refresh phase: ordinary release
promotion already activated and observed that release at the target, and the
coordinator repeats active/stable validation before recording the no-op. Any
executed or resumed transition still requires the worker refresh described
below.

Worker refresh rechecks active known-good SHA/slot identity, requires a schema
that can support the data-deletion worker, verifies immutable source, and runs
the full image/Compose/migration/secret/storage preflight before mutation. Its
pre-refresh health check requires core serving health and exact active/stable
identity while allowing only notification, calendar, deletion, or parser
outages that the refresh owns. It then recreates parser worker, backend, and all
schema-gated queue workers from the known-good image attestations, requires full
candidate readiness, and validates stable-route backend/frontend health. It
updates `known_good_release.schema` and appends the
`post_migration_workers_refreshed` history event atomically only after those
checks pass.

The same implementation underlies the separate `--refresh-active-runtime`
operator mode for config-only refreshes. That mode additionally requires live
schema to equal the already-recorded known-good schema and records
`active_runtime_refreshed`; migration automation permits the just-committed
forward schema to be ahead of the prior observation.

Only after that returns does the coordinator atomically write an executed
transition's final `automation.json` completion. Thus a target schema reached
by this release's migration without refreshed workers and active/stable-route
validation is not final success.

## 14. Point of no return, rollback, and forward repair

Immediately before the first migration at source schema, the coordinator finds
the bridge's `known_good`/`complete` acceptance event and validates its retained
previous release. That retained slot must be different, identify as the exact
attested old SHA, be running, and declare compatibility with the current source
schema. This is the last traffic-rollback assurance before an irreversible
forward-only phase begins.

A recovery or migration-retry `compatible_fallback_release` takes precedence
only when it passes the same gates. For states written by older controllers,
a stale fallback cannot mask the exact `previous_known_good_release` in this
SHA's latest completed acceptance event. The coordinator tries that acceptance
target if fallback attestation fails. Each candidate independently requires a
full lowercase SHA, the opposite active slot, recorded source-schema
compatibility, and successful `validate_rollback_target()` against its live
version endpoint (exact SHA and live source-schema compatibility). It never
invents a target by swapping slots or accepting whichever process responds.
If neither target attests, it fails before coordinator state, backup creation,
the executor connection, or SQL. Read-only selection does not repair durable
state; the backup-first same-SHA fallback step establishes the new topology.

The point of no return is the first committed schema transition that moves the
database beyond the previous release's compatibility maximum. From then on:

- automatic traffic rollback to the incompatible old release is prohibited;
- no traffic-switch or old-worker-restoration method is called by migration
  automation;
- no reverse SQL is generated, selected, or executed;
- the active bridge remains the recovery platform; and
- retries resume remaining forward transitions or repair worker/application
  validation.

Reverse SQL is prohibited because its correctness, data preservation, runtime
compatibility, and transactional behavior are not established by an expand
manifest. The verified pre-transition backup is the disaster-recovery artifact,
not an invitation for automatic restore. Backup restoration and any exceptional
traffic decision require explicit operator review.

Compatibility ranges make this boundary enforceable. The active bridge must
support source through target. The previous release is attested only at the
source schema. Once live schema exceeds its compatible maximum, using it would
violate release compatibility, so forward repair is the only automated path.

## 15. Retry, observability, and operator intervention

Automatic migration emits JSON on success/no-op and a nonzero service result on
failure. Operators have four durable evidence sources:

- release identity and history in `state.json`;
- coordinator phase, failure code, retry deadline, and backup in
  `migrations/<SHA>/automation.json`;
- advisory-lock/execution/per-migration progress in
  `migrations/<SHA>/execution.json`; and
- systemd journal/ops-alert handling for the failed service.

Mutation-phase failures are labeled `failed_forward_repair_required`. They are
retried only after the clamped retry deadline, and the deployment lock prevents
overlap. A manual retry flag is not part of automatic migration recovery and
must not be used to bypass provenance, eligibility, compatibility, backup, or
schema gates.

Operator intervention is required for invalid release/manifest contracts,
missing or corrupt durable state, missing database client or backup tooling,
unavailable retained rollback attestation before the first transition,
incompatible/unexpected live schema, missing original backup attestation after
partial advancement, persistent migration SQL failure, or persistent
post-migration worker/route failure. Operators must repair forward or perform a
separately reviewed disaster-recovery procedure; they must not edit state files
to manufacture success.

### Supabase CLI ledger boundary

The application schema row and Supabase CLI ledger are separate authorities.
The automatic executor advances only `application_schema_state`; treating a
direct SQL commit as if it also updated the CLI ledger previously caused
`db push` to attempt replay. The remedy is deliberately post-terminal and
operator-only. `supabase_ledger_reconciliation.py` refuses to act until the
exact migration SHA and checksum, completed execution state, completed
post-migration worker/stable-health state, and a live target-schema read all
agree. It then uses Supabase's ledger repair operation for that one version,
verifies the ledger result, and records a private atomic audit artifact.
Idempotent replay observes the existing row. A source-schema database, missing
health evidence, dirty/different release, checksum drift, missing predecessor,
or a ledger already beyond target fails before mutation. No tenant/business
table is queried or changed.

### Current schema 098 bridge

The current release contract accepts schema `81..98` and targets `98` with the
pinned `migrations-098.json` manifest. Migration 098 is an expand-only 97-to-98
transition. The application may be promoted on schema 97: existing website and
ecommerce paths remain compatible, public visit recording is best effort, and
dashboard visit metrics expose an unavailable zero state until the new table
and atomic function exist. After advancement, the retained schema-97 release is
no longer an automatic rollback target.

Schema 098 stores only tenant-level aggregate opening counts for the published
website and store. It does not persist visitor identity, IP address, user agent,
or other personal data. Each public runtime mount makes one best-effort request;
the database function atomically increments exactly one surface counter.

### Earlier schema 097 bridge

The preceding release contract accepted schema `81..97` and targeted `97`
with the pinned `migrations-097.json` manifest. Migration 097 was an
expand-only 96-to-97 transition adding verified-customer loyalty. Loyalty
configuration and customer reads failed closed on schema 96; verified identity
binding, ledger processing, entitlement issuance, and discounts became
available after migration 097.

### Earlier schema 095 bridge

The current release contract accepts schema `81..95` and targets `95` with the
pinned `migrations-095.json` manifest. Migration 095 is an expand-only `94→95`
transition. The application may be promoted on schema 94, but structured public
checkout and merchant delivery/order operations fail closed until their RPCs and
tables exist; catalog and settings reads keep their schema-94 bridge behavior.
After the coordinator advances the database, the retained schema-94 release is
no longer an automatic rollback target and
the standard forward-repair policy applies.
## 16. Critical invariants and architecture-to-test map

The following are the mandatory design invariants. Test names are from
`web/backend/tests/` unless otherwise stated.

| # | Invariant | Code enforcement | Principal tests |
| --- | --- | --- | --- |
| 1 | No automatic migration occurs before the bridge application is active and durably known-good. | `ReleaseDeployer.deploy()` persists `known_good`/`complete` before returning; `madar-production-deploy` invokes migration only after that return; `automatic_migrate_known_good()` rechecks SHA, slot, active slot, recovery state, and stable serving health. | `test_automatic_migration_control_plane.py :: test_ordinary_release_invokes_migration_after_promotion_and_fast_forward`, `test_bridge_promotion_failure_invokes_zero_migration`, `test_refuses_non_known_good_sha_before_backup_or_database`; `test_release_deployer.py :: test_success_records_immutable_known_good_release`, `test_every_pre_switch_failure_leaves_active_target_untouched`. |
| 2 | No automatic migration occurs unless active known-good SHA exactly matches the release/manifest being migrated. | `automatic_migrate_known_good()` exact SHA/slot checks; installed/candidate contract equality; manifest SHA rebinding or exact comparison. | `test_refuses_non_known_good_sha_before_backup_or_database`, `test_refuses_manifest_drift_before_backup_or_database`. |
| 3 | No automatic migration occurs without the explicit supported automatic migration policy. | Exact comparison with `AUTOMATIC_MIGRATION_POLICY`; otherwise `not_requested`. | `test_unapproved_migration_policy_is_a_noop`. |
| 4 | Only migration classes permitted by `migration_executor.py` run automatically. | Release class check plus `MigrationManifest.load()` per-entry allow-list for `expand-only`/`forward-compatible`. | `test_unsupported_release_class_is_rejected_before_backup`; `test_migration_executor.py :: test_manifest_rejects_repository_escape_and_unsupported_class`. |
| 5 | No migration occurs without a verified backup satisfying implemented identity/freshness rules. | `_create_verified_migration_backup()`, `_attest_migration_backup()`, executor `backup_verifier`, and resume-backup validation. | `test_backup_failure_is_durable_and_next_attempt_is_suppressed`, `test_backup_manifest_is_bound_to_release_and_source_schema`, `test_committed_transition_reuses_backup_without_old_release_rollback`; `test_backup_tooling.py :: test_backup_is_published_only_after_verified_completion`, `test_failed_backup_never_occupies_final_recovery_path`, `test_verifier_rejects_missing_member_and_checksum_mismatch`. |
| 6 | Every migration is repository-contained, manifest-listed, checksum-pinned, contiguous, and starts from attested expected schema. | `MigrationManifest.load()`, `verify_migrations()`, executor schema/transition checks, and both migration validators. | `test_migration_executor.py :: test_manifest_rejects_repository_escape_and_unsupported_class`, `test_manifest_rejects_noncontiguous_transitions`, `test_refuses_checksum_mismatch_before_opening_database`, `test_applies_contiguous_manifest_and_writes_durable_state`; `test_automatic_migration_control_plane.py :: test_backup_and_execution_begin_only_after_known_good_validation`. |
| 7 | A completed schema transition is never blindly replayed after interruption. | Executor compares live schema to each `to_schema` and records `already_applied`; database schema is authoritative. The persistent timer and same-known-good branch re-enter that idempotent path after reboot. | `test_migration_executor.py :: test_resume_from_schema_82_skips_first_migration`; `test_automatic_migration_control_plane.py :: test_committed_transition_reuses_backup_without_old_release_rollback`; `test_monorepo_deployment.py :: test_auto_deploy_suppresses_bad_sha_and_refuses_uninitialized_state`, `test_timer_waits_after_completion_instead_of_retrying_immediately`. |
| 8 | Once DB schema exceeds the previous release's compatibility maximum, automatic traffic rollback to it is prohibited. | Retained target is validated only at source before mutation; automatic migration has no switch/restore path and partial resume requires the original backup. | `test_committed_transition_reuses_backup_without_old_release_rollback`; `test_release_deployer.py :: test_retained_target_is_attested_against_observed_schema_before_start`. |
| 9 | Reverse SQL migrations are not automatically attempted. | Manifests require one-step forward transitions; executor skips reached targets and has no reverse executor; coordinator failure semantics are forward-repair-only. | `test_committed_transition_reuses_backup_without_old_release_rollback`; `test_migration_executor.py :: test_resume_from_schema_82_skips_first_migration`. |
| 10 | Final success after an executed transition waits for target schema, worker refresh, active application validation, and stable-route validation. | `automatic_migrate_known_good()` target check followed by actual `refresh_active_workers()`; transition completion write occurs last. A proven fresh `already_at_target` release has already passed promotion workers/observation and repeats stable validation before recording its nonexecuting result. | `test_successful_94_to_95_records_target_only_after_worker_and_route_validation`, `test_stable_route_failure_prevents_final_migration_success`, `test_prior_release_migrates_then_later_release_noops_idempotently`; `test_release_bootstrap.py :: test_post_migration_refresh_requires_exact_known_good_and_schema_83`. |
| 11 | A later release accepted at an already-reached target neither borrows the prior release's backup nor bypasses a genuine current-release resume. | Fresh no-op requires no per-SHA state plus matching known-good and acceptance-time target observations. Any current-release state retains exact SHA/source backup attestation. | `test_prior_release_migrates_then_later_release_noops_idempotently`, `test_current_release_partial_state_without_backup_still_fails_closed`, `test_current_release_substituted_resume_backup_still_fails_closed`. |
| 12 | The database cannot finish a normal automatic migration with every inactive fallback incompatible. | Before SQL, `_establish_compatible_migration_fallback()` recreates the inactive slot from the accepted bridge with consumers disabled. After SQL and active-worker validation, it revalidates that slot at target schema and records it as the compatible fallback. | `test_successful_97_to_98_records_target_only_after_worker_and_route_validation`, `test_automatic_migration_control_plane.py`; recovery/fallback failure injection in `test_release_deployer.py`. |
| 13 | A pre-existing DB-ahead state is repaired only by exact-schema, zero-migration forward recovery. | The ordinary manifest remains authoritative for normal releases. `schema-96-recovery.json`, root-protected exact-SHA rehearsal evidence, generation-bound worker authority, Docker restart inhibition, shared routing/slot mutation exclusion, local plus Node 1 backup verification, no-overlap worker cutover, atomic traffic switching, and compatible-fallback establishment are mandatory in the explicit recovery path. | `SchemaRecoveryDeployerTests`, schema-recovery coordinator and contract tests in `test_control_plane_upgrade.py`, auto-deploy inaccessibility in `test_monorepo_deployment.py`, and the disposable real-runtime rehearsal. |
| 14 | Ordinary promotion retires the preceding operation's fallback; stale historical fallback claims cannot bypass or mask an attested retained acceptance target. | Atomic promotion removes `compatible_fallback_release`; source-schema migration selection independently attests fallback then exact acceptance target before mutation. | `test_ordinary_promotion_retires_prior_operation_fallback`, `test_stale_recovery_fallback_uses_only_exact_live_acceptance_target`, `test_stale_recovery_fallback_invalid_acceptance_targets_fail_pre_mutation`, and `test_schema96_recovery_installed_layout.py :: test_installed_layout_interruption_resume_and_next_release` through migrations 097/098/099, verified fresh backup, inactive same-SHA fallback, worker refresh and byte-idempotent completion. |

Static orchestration tests in `test_monorepo_deployment.py` additionally verify
that the installed wrappers contain the same-known-good recovery branch, the
post-promotion automatic invocation, the persistent timer, immutable control
plane, and canonical production paths. Behavioral wrapper tests are preferred
for ordering and zero-migration assertions because they execute the shell
control flow rather than only matching source text.

The unit suites remain state-machine evidence. Installed-runtime evidence comes
from `web/scripts/rehearse_schema96_real_runtime.py`, executed in an empty,
network-isolated Docker-in-Docker daemon with distinct project/container names,
ports, state, proxy, storage, networks, and volumes. It uses actual
`DockerGitOperations`, Docker Compose worker health/restart state, the file-proxy
traffic switch, release-state files, and the ordinary release/manifest parser.
After recovery it derives the normal migration path from the immutable
candidate manifest and proves prepare plus interrupted retry without executing
SQL. Sanitized output is retained outside the repository.

## 17. Change discipline

Any change to automatic migration orchestration, release compatibility,
manifests, backup/verification tooling, deployment wrappers, state formats,
worker refresh, locks, or recovery semantics must review and update both this
blueprint and `production-release-policy.md` in the same change. Tests must map
new or changed invariants to executable behavior. A main-targeting change is not
ready while any locally executable mandatory gate fails or any untested safety
claim is represented as proven.

The current-schema recovery operation is not a migration coordinator shortcut.
It rejects candidates requiring SQL, never invokes `LockedMigrationExecutor`,
and leaves the schema unchanged. Its only purpose is restoring compatible
application and fallback targets around an already-advanced database. See the
dedicated recovery runbook for its distinct approval and interruption model.

## Historical commercial access schema 099 bridge (2026-09-14)

The production-baseline release used `web/deployment/releases/migrations-099.json`.
That release was compatible with schemas 081 through 099; its target was 099.
The release manifest contains the contiguous 096→097→098→099 chain so a host
that has not deployed the intervening mainline releases cannot skip their
schema changes. Before the target exists, the commercial snapshot service
accepts the existing resolver only after independently verifying schema 098.
Missing RPCs at any other schema fail closed. Manual-ledger administration
remains unavailable until migration 099 completes.

The existing controller first accepts the backwards-compatible application,
creates and verifies its governed pre-migration backup, then applies the exact
ordered migration checksums and revalidates the serving release. Migration 099
adds the tenant review state and append-only manual financial/access ledger.
It seeds review-required rows only: no tenant plan assignment, historical payment
backfill, production enforcement activation, provider activation, or database
endpoint change. Financial deletion guards reject before any account/workspace
freeze or file purge when retention review is needed.

Rollback to the retained schema-098 binary is allowed only before the migration
advances the schema. After 099, use governed forward repair. The privileged
exact-SHA controller upgrade is required because the release metadata and
manifest are protected control-plane files; its procedure is unchanged.

The synthetic `rehearse_migration_099.sh` gate applies all canonical migrations
on a pinned disposable PostgreSQL image, runs concurrency/isolation tests and
the exact RLS/grants verifier, and restores a dump containing commercial receipt,
period, revision and audit records. It does not replace the required fresh
production backup and Node 1 round-trip after deployment.


## Current production-based forward schema-101 release

The release base is `1e6b739a43759309a45ede2dff28a859209e4a64`, with
production schema 099. All 198 migration files numbered 001 through 099 remain
byte-identical to that baseline, including the original visit-counter migration
098 and `099_commercial_access_ledger.sql`. The historical 004/005 mirror swap
is retained. `production-001-099.json` pins every baseline file; migration
validation rejects changes, replacements, deletions, and historical additions.

The current manifest is `migrations-100-101.json`, ordered 099->100->101.
Migration 100 replaces only `record_public_site_visit_safe`: null/invalid
surfaces are rejected and the active tenant gate uses `lifecycle_state`.
Counters, keys, RLS, and existing visit totals are retained. Migration 101 adds
`display_type`, `color_hex`, their constraints, and the V2 variant aggregate
RPC. Existing option rows default to text; existing swatches remain null.
Product identity, SKU, inventory, order history, and the commercial financial
ledger are preserved. Schema 099 identifies the commercial ledger; variant
presentation requires schema 101, and color saves fail explicitly before its
RPC exists while legacy text saves continue through the existing aggregate.

The bridge remains compatible with schemas 081..101 for ordinary application
behavior, but this migration manifest accepts only the production source 099
through target 101. Its retained-release rollback range is 081..099. The
source-099 release must be accepted before the governed source-schema-bound
backup and locked forward execution. After advancement beyond a retained
binary's range, recovery is forward-only. No older manifest is substituted to
skip source-schema validation.

Reconciliation requires an explicit manifest version (100, then 101), exact
candidate SHA, canonical checksum/mirror, linked-project identity, live schema
101, and exact serving identity/readiness. Each non-dry-run confirmation is
`NNN:<manifest-sha256>`. Completed SQL execution uses its real execution record;
a fresh later release accepted at 101 can use the canonical coordinator
`already_at_target` record only with target acceptance evidence and no execution
file. Reconciliation never manufactures execution evidence. Ordering, host lock,
private atomic audits, audit identity/drift checks, and timestamp-preserving
idempotent repeats remain mandatory.

`check_forward_release.py` validates this current lineage, bridge, namespace,
manifest ordering, and checksums. `rehearse_migration_101.py` uses only a new
network-isolated PostgreSQL 17 container, restores a seeded source-099 custom
dump, proves financial/counter/product/variant/order/inventory preservation,
checks constraints and V2 atomic saves, and separately replays 001..101 fresh.
It destroys only its own disposable target. Historical schema-096 recovery
regressions retain an explicit historical 096->099 metadata fixture; they do
not change the current 099->101 transition.

Source qualification does not attest production configuration, an operational
backup/off-host copy, live runtime acceptance, or a production ledger repair.
Those operator gates remain separate; this candidate must qualify in an
isolated environment with the canonical production migration lineage before
any production action.
