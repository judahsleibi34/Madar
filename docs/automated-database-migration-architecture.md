# Automated database migration architecture

Last implementation review: 2026-10-04

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

The schema-114 to schema-115 commercial bridge follows this ordering. The
candidate can read the existing schema-099 access snapshot at schema 114, but
new hold/access commands require the resolver's schema-115 contract marker.
After bridge acceptance, a verified schema-114 backup precedes migration 115.
The active application then sees holds, assignment snapshots and revision
checks. Explicit commercial holds apply even while the existing operator plan
bypass remains configured; no global enforcement setting is activated.
The prior binary cannot enforce holds and cannot be reused after the schema
advances. Post-transition recovery is forward repair only.

Protected control-plane releases may be authorized through the root-owned
one-command workflow described in
[`control-plane-upgrade-architecture.md`](control-plane-upgrade-architecture.md).
That bootstrapper synchronously invokes this same ordinary auto-deploy path and
requires this coordinator to reach an existing successful terminal state; it
does not add a migration mode, bypass backup/manifest gates, or alter the
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

## 7. Migration state machine and durable representation

Some names in the following table are architectural predicates requested for
reasoning about the flow, not additional strings written to disk. The
“implemented representation” column gives the exact durable or derived form, so
this table does not invent persistence states.

| Architectural state | Implemented representation and transition |
| --- | --- |
| `bridge_known_good` | `state.json.known_good_release.sha` equals the requested SHA, its slot equals `active_slot`, there is no in-progress/rollback failure, and release history contains `status=known_good`, `phase=complete`. Stable candidate/backend/frontend validation must also pass. |
| `migration_pending` | Derived: exact automatic policy and manifest are valid, live schema is within the bridge range and below manifest target, and no matching completed `automation.json` covers the target. No literal `migration_pending` value is stored. |
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

### Current schema 115 bridge

The source contract is schema 114, compatible range `114..115`, target 115 and
checksum-pinned `migrations-115.json`. Mutation availability is explicit during
the bridge: reads use the existing ledger while commands return a controlled
upgrade-required response until 115. The migration adds current holds without
truncating paid periods and extends the existing RPC boundary with optimistic
revisions, replay and full safe before/after audit context. Retained schema-114
code is incompatible after advancement. Protected release metadata requires a
governed controller upgrade; no migration/controller change is executed as part
of local implementation validation.

### Earlier schema 114 bridge

Production enters this release at schema 113. The release contract accepts
`113..114`, targets 114, and lists only the checksum-pinned migration 114 in
`migrations-114.json`. The verified backup is bound to schema 113. The bridge
application accepts the exact missing-function response and then executes the
same tenant lifecycle, settings, bound-project, and published-schema checks as
the old site endpoint. Other failures stop the request. The RPC uses invoker
rights, an empty search path, and service-role-only execution. Python still
validates the publication and filters protected/private schema according to
visitor membership and permissions. After schema 114 commits, recovery remains
forward-repair-only.

### Earlier schema 113 bridge

Migration 113 added the managed-asset visibility context RPC. Its historical
`migrations-113.json` remains pinned, and the application retains its secure
schema-112 fallback only for an exact missing-function response. Schema 113 is
now applied production history and must not be edited.

### Earlier schema 112 bridge

The historical release began at schema 109. Its contract accepted schema
`109..112` and targets `112` using the checksum-pinned
`migrations-110-112.json`
manifest. Migration 110 makes e-commerce order persistence and its durable
notification intent one atomic transaction by using a deferred constraint
trigger that reads finalized totals. It also replays the same deduplicated
intent for missing events on orders from the preceding 30 days (`109 -> 110`).
Migration 111 adds tenant-scoped product-category associations, backfills each
product's existing primary category, and retains the primary `category_id`
column as a compatibility field (`110 -> 111`).
Migration 112 makes the product-owned variant foreign key cascade on product
deletion while leaving order, inventory, and loyalty history foreign keys
restrictive (`111 -> 112`).
Migrations through 109 remain immutable production history. A verified
schema-109 backup is required before migration. Rollback compatibility is
bounded at schema 109; after advancement, recovery is forward-repair-only.

### Earlier schema 108 bridge

The preceding release started at schema 105. Its contract accepted schema
`105..108` and targets `108` using the checksum-pinned
`migrations-106-108.json` manifest.

The active migration sequence is contiguous:

- migration 106: order delivery-fee snapshots (`105 -> 106`);
- migration 107: ecommerce category images (`106 -> 107`);
- migration 108: tenant-scoped ecommerce brands (`107 -> 108`).

Migration 105 established canonical tenant subdomains in the prior `104 -> 105`
production release. It remains immutable production history and its historical
manifests are retained. A verified schema-105 backup is required before the
schema-108 bridge mutated the database. Rollback compatibility was bounded at
schema 105. After schema advances beyond 105, recovery proceeds forward rather
than attempting automatic downgrade SQL or traffic rollback to an incompatible
retained release.

### Earlier schema 099 bridge

The current release contract accepts schema `81..99` and targets `99` with the
pinned, contiguous `migrations-097-099.json` manifest. It can advance the
reported production source at schema 96 through the already-reviewed 097 and
098 transitions before applying the additive 98-to-99 presentation transition.
The application may be promoted on schema 96 through 99. Text-only product
aggregate saves fall back to the legacy RPC before schema 99; color presentation
saves fail clearly until the V2 RPC exists, preventing silent metadata loss.
After advancement beyond a retained release's compatible maximum, that release
is no longer an automatic rollback target.

Schema 099 adds constrained `display_type` and `color_hex` presentation
metadata. Existing attributes default to text. Its V2 aggregate RPC invokes the
existing identity-, inventory-, and archival-safe aggregate function within the
same database transaction, then validates and stores presentation metadata.

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
| 10 | Final success after an executed transition waits for target schema, worker refresh, active application validation, and stable-route validation. | `automatic_migrate_known_good()` target check followed by actual `refresh_active_workers()`; transition completion write occurs last. A proven fresh `already_at_target` release has already passed promotion workers/observation and repeats stable validation before recording its nonexecuting result. | `test_successful_102_to_104_records_target_only_after_worker_and_route_validation`, `test_stable_route_failure_prevents_final_migration_success`, `test_prior_release_migrates_then_later_release_noops_idempotently`; `test_release_bootstrap.py :: test_post_migration_refresh_requires_exact_known_good_and_schema_83`. |
| 11 | A later release accepted at an already-reached target neither borrows the prior release's backup nor bypasses a genuine current-release resume. | Fresh no-op requires no per-SHA state plus matching known-good and acceptance-time target observations. Any current-release state retains exact SHA/source backup attestation. | `test_prior_release_migrates_then_later_release_noops_idempotently`, `test_current_release_partial_state_without_backup_still_fails_closed`, `test_current_release_substituted_resume_backup_still_fails_closed`. |

Static orchestration tests in `test_monorepo_deployment.py` additionally verify
that the installed wrappers contain the same-known-good recovery branch, the
post-promotion automatic invocation, the persistent timer, immutable control
plane, and canonical production paths. Behavioral wrapper tests are preferred
for ordering and zero-migration assertions because they execute the shell
control flow rather than only matching source text.

## 17. Change discipline

Any change to automatic migration orchestration, release compatibility,
manifests, backup/verification tooling, deployment wrappers, state formats,
worker refresh, locks, or recovery semantics must review and update both this
blueprint and `production-release-policy.md` in the same change. Tests must map
new or changed invariants to executable behavior. A main-targeting change is not
ready while any locally executable mandatory gate fails or any untested safety
claim is represented as proven.

## E-Learning management bridge (schemas 116 through 123)

The active bridge supports schemas 114 through 130 and retains migrations 115 through 120
unchanged in the contiguous `migrations-115-134.json` manifest. Migration 116
adds tenant-owned E-Learning JSON configuration and a service-role-only atomic
merge RPC. Tenant owner/admin API authorization is mandatory; database access
is denied to anonymous and authenticated clients. Before schema 116, settings
reads return defaults with `available=false`, and saves return the controlled
`elearning_upgrade_required` response without touching the new table. No
learner runtime is introduced.

The source remains schema 114 because the declared commercial bridge has not
been replaced by evidence of an applied schema 115. Existing schema-115 live
instances can skip migration 115 through the normal executor. Rollback metadata
remains 114 only due to commercial holds; post-transition recovery stays forward
repair. This metadata change touches protected `web/deployment/releases` and
requires the governed exact-SHA control-plane upgrade before deployment. No
production migration or deployment is performed as part of development.

Migration 117 adds `elearning_courses` with tenant ownership, managed cover asset
references, status/access constraints, timestamps and optimistic revisions. It is
expand-only, requires schema 116 and advances the schema guard transactionally.
RLS and revoked client grants restrict access to the service role; the backend
enforces active tenant owner/admin membership and scopes every query to that
tenant. Course list reads return `available=false` with no rows before schema
117; detail reads, mutations and cover uploads return the controlled
`elearning_courses_upgrade_required` error without querying the course table.
Settings continue to function at schema 116. Cover uploads reuse the managed
image pipeline and entitlement; saved course covers, including archived courses,
retain registered assets without granting public visibility. Missing-table
reference checks tolerate only PGRST205/42P01; other failures propagate.

The checksum-pinned contiguous manifest is `migrations-115-134.json`; previously
published manifests and SQL 115/116/117/118 remain unchanged. Local validation must
cover schema-gated behavior, tenant/role isolation, optimistic conflicts, image
ownership/retention, migration mirror/checksum integrity and release transitions.
Deployment still requires the existing backup-first migration and protected
control-plane contract. Structure counts become active at schema 119; learner counts become active at schema 120; publishing a course does not activate learner access or payments.

### Group and instructor management (schema 118)

Migration 118 is an expand-only, transactionally guarded 117-to-118 transition
adding tenant-owned `elearning_groups` and `elearning_instructors`. The active
bridge accepts 114 through 132, targets 132 and uses the checksum-pinned
`migrations-115-134.json` manifest. SQL and prior manifests through 118 remain
unchanged. Lists return unavailable empty results before 118; detail reads and
mutations fail closed with `elearning_directory_upgrade_required`. Settings and
courses retain their earlier schema gates. Both new tables enable RLS and grant
only SELECT/INSERT/UPDATE to service_role; anonymous/authenticated clients and
permanent deletion are denied. Backend endpoints enforce active tenant owner/admin
membership, tenant-scoped reads/writes and revision conflicts. Instructor email
is contact metadata only: creating a profile sends no invitation, creates no
login and grants no permissions. Group enrollment and course assignments remain
future work. Production rollout requires the same governed protected-controller
upgrade, known-good bridge, verified backup and forward-repair contract; local
Docker migration verification does not authorize production changes.

### Course Structure Builder (schema 119)

Migration 119 is an expand-only, guarded 118-to-119 transaction. It adds generic
`elearning_sections` and `elearning_lessons` metadata and a separate course
`structure_revision`. Composite parent foreign keys enforce tenant/course
ownership. Deferred unique sibling positions permit atomic swaps; every
mutation normalizes contiguous positions. The command RPC locks the course,
checks the expected structure revision and active owner/admin membership, and
commits the hierarchy and revision together. Concurrent stale commands return
409 and do not overwrite accepted edits. Service-role table access is read-only;
only the service role can execute the mutation RPC. Anonymous/authenticated
clients have no table or RPC access. The API additionally checks session
permissions and never accepts client tenant/user IDs or arbitrary positions.

Before 119, structure reads return unavailable empty results after verifying
course ownership at schema 117+, and structure writes fail closed without
touching the new objects. Before 117, even structure reads fail closed. Course
reads batch active counts at 119 and use zeros earlier. Archived sections retain
lessons and are excluded, with their descendants, from active counts. Lesson
moves preserve IDs and only target an unarchived section in the same course.
Section duplication copies section/lesson metadata as Draft; content blocks do
not exist yet. Empty-section/lesson deletion requires explicit confirmation;
sections containing any lessons cannot be deleted. Future content relations
must restrict permanent deletion until their retention contract is implemented.

The active manifest is `migrations-115-134.json`; earlier SQL and manifests are
retained unchanged. Local validation covers real PostgreSQL ordering,
concurrent commands, tenant isolation, schema gates, grants and checksums.
Lesson routes host the schema-123 Content Builder described below.
Structure introduces no learner delivery. Participation
at schema 120 is governed by the additional contract below. Deployment retains the governed
control-plane upgrade, known-good bridge, verified backup and forward-repair
requirements above.

### Learner participation (schema 120)

Migration 120 expands 119 to 120 transactionally. It creates tenant-owned learner
contact profiles, course enrollments and lesson completion records with composite
tenant/course foreign keys and restricted RLS/grants. Profiles create no auth
accounts or invitations. Owner/admin-only APIs inject session identity. Enrollment
and completion commands use service-role-only RPCs with course locks; enrollment
is allowed only for active profiles and published courses. Free assignment is
restricted to Free courses; explicit manual assignment supports Paid/Private
courses without inventing or asserting payment. Completions require an active
enrollment and published course/section/lesson. Repeated completion is idempotent.
No percentage is stored: course, section and lesson reports join completion
records to currently eligible published lessons. Draft/archived content is
excluded from the denominator; archived learners/enrollments are excluded from
active counts. Completion foreign keys prevent deleting referenced lessons;
archiving retains history. Pre-120 mutations/progress reads fail closed and
course learner counts remain zero. Learner lists are unavailable empty results
before 120. The schema-119 structure count RPC remains unchanged; participation
counts are batched through a new schema-120 RPC.

The active manifest is migrations-115-134.json, preserving SQL/manifests through
119. No migration inserts dummy data. The separate development seed requires
the generated loopback local environment and a running local Supabase Docker
container, resolves the configured test account's current tenant, uses stable
IDs/ownership markers and refuses unrelated records on reset/cleanup. Production
changes remain unauthorized; governed control-plane upgrade, verified backup,
known-good bridge and forward repair remain mandatory deployment constraints.

### Confirmed course deletion (schema 121)

Migration 121 is an expand-only 120-to-121 transaction adding a service-role-only
course deletion RPC. No direct table DELETE grant is added. Owner/admin APIs
require explicit confirmation, the exact course name, and expected course and
structure revisions. The RPC verifies membership, locks the course (also used
by structure/participation commands), rejects stale revisions, and atomically
removes course completions, enrollments, lessons, sections and the course.
Learner contact profiles and managed asset files remain; normal reference-based
asset retention/cleanup still applies. Unexpected future foreign-key references
block deletion and roll back the complete transaction. Before 121, deletion
fails closed and course cards expose deletion_available=false. Migration SQL
and manifests through 120 remain immutable; active metadata targets 132 with
the contiguous migrations-115-134.json manifest. Production deployment/mutation
is not performed; all existing protected-controller, backup and bridge gates
remain mandatory.


### Course enrollment management (schema 122)

Migration 122 expands 121 to 122 without changing course/structure entities.
Existing learner contact records gain an optional reference to Madar users;
no accounts are created or auto-linked. New enrollment commands select active
users with active membership in the session tenant, atomically link their
existing contact profile, and reject duplicate active enrollment. Batches are
bounded to 100 users and roll back entirely on invalid/duplicate selection.
Service-role-only RPCs lock the course and require owner/admin membership.
Active, suspended and archived (displayed Cancelled) reuse the enrollment status
column; cancellation/suspension require confirmation and expected status.
Reactivation retains completion history and validates linked user membership.
Existing progress reads retain active-only semantics; enrollment reports include
inactive history through the same published-lesson calculator. Payment/group
fields are null until integrated. Pre-122 management fails closed. The active
manifest is migrations-115-134.json, preserving all earlier SQL/manifests.
No production mutation, account creation, payment engine or group assignment
occurs. Existing governed release, backup and forward-repair gates still apply.


### Lesson content blocks (schema 123)

Migration 123 expands 122 to 123 transactionally with tenant/course/lesson-owned
ordered content blocks and per-lesson content revisions. Initial typed content
handlers accept text, audio and video; publication is inherited from the lesson.
Existing course locks serialize revision-checked writes, and owner/admin
membership is checked in both APIs and command RPCs. Composite foreign keys,
RLS and revoked direct writes protect attachments and clients. Archived blocks
retain content/media; deletion requires confirmation. Content mutations advance
structure revisions so stale course-deletion confirmations cannot discard newer
content. Existing section/lesson duplication copies content with fresh IDs.
Confirmed course deletion includes blocks atomically; ordinary lesson deletion
is restricted while blocks remain. Tenant purge retains its cascade semantics.

Managed audio extends the shared file registry/storage/validation pipeline with
MP3/WAV; block references retain active and archived media without granting
public visibility. Content reads, mutations and uploads fail closed before 123.
Earlier E-Learning functionality keeps its existing schema gates. The bridge
supports 114..134, targets 132 and pins the contiguous migrations-115-134.json
manifest; all earlier SQL/manifests stay immutable. Protected release metadata
requires the existing governed control-plane upgrade before deployment. No
production migration/deployment is part of local development. See
[content architecture](elearning-content-architecture.md) for payloads, rendering
and validation. Existing bridge-first, verified-backup and forward-repair gates
remain mandatory.


### Learner runtime (schema 124)

Migration 124 adds service-role-only learner read, completion and media-access
RPCs without new tables. Active users/memberships, user-linked active learner
profiles and active enrollments gate published course/section/lesson content.
The existing get_elearning_progress calculator supplies all percentages and
counts; only the current enrollment row is returned. Archived blocks are
excluded. Stored positions determine Continue and prerequisite order. The
existing sequential_progression setting enforces prerequisite completion on
reads, completion and private learning media. allow_locked_content does not
override sequence prerequisites; there is no separate explicit lock model.
Completion is explicit and idempotent in elearning_lesson_completions and locks
the course against enrollment/structure changes. Opening does not complete a
lesson; no started-state or stored percentage is invented. Upload commercial
gates remain intact. Existing non-learning file rules and admin preview remain.
Player endpoints fail closed before 124. Compatibility is 114..134 with the
checksum-pinned migrations-115-134.json manifest; earlier SQL/manifests remain
immutable. The usual bridge, backup, protected-controller and forward-repair
release gates still apply. No production changes are authorized by local tests.


### Additive learning access and assignments (schema 125)

Migration 125 expands 124 with tenant-scoped group membership/course relations,
independent access grants and separate course/group instructor assignments.
Existing manual/free enrollments are backfilled to grants without changing
status or completion history. A central resolver combines valid grants with
active enrollment/profile/user membership; suspension/cancellation overrides
all grants. Removing one source never removes another or deletes progress.
Group grants retain their Group origin; repeated assignment/membership commands
are idempotent. Tenant advisory locks precede course locks for multi-course
commands, individual grant mutations and learner completion. Existing progress
calculations remain authoritative and filter effective access. Group summaries
use the same engine with lesson-level JSON disabled. Membership grants are
retained during temporary course unpublication; publication still gates runtime
access. Publication,
sequence and learning-media rules remain intact. Instructor relationships never
create enrollments; optional user links validate tenant membership. Purchase is
a reserved grant type constrained against issuance until governed Commerce
integration. New mutations fail closed before 125; existing pre-125 features
retain their schema gates. The active manifest is migrations-115-134.json with
114..134 compatibility, preserving earlier SQL/manifests. Existing protected
controller, bridge-first, backup and forward-repair release gates still apply.
No production action is authorized by local verification.


### Objective E-Learning assessments (schema 126)

Migration 126 adds generic assessments, typed questions, private immutable attempt
snapshots, answers, and retained audio references. The existing lesson block
references the engine; existing enrollment grants, sequencing and lesson-based
progress remain authoritative. Required published assessments gate new explicit
completion without invalidating existing completions. Learner RPCs serialize
whitelisted questions and never return private grading configuration. Attempts
and answers have no direct service-role SELECT or client write grants. Authoring
and attempt submission use tenant/course transaction locks; uploads retain the
commercial review gate. Historical audio remains referenced until its attempts
are purged. Expand-only compatibility is 114..134; the active checksum manifest
is migrations-115-134.json. Rehearse transaction rollback and all scoped access,
submission and completion checks on a marked local database before deployment.
Production mutation, protected path and source validation rules remain mandatory.


### Assessment placements and formal completion (schema 127)

Migration 127 extends the existing assessment engine with explicit Lesson,
Section and Course placements. Existing lesson block IDs and endpoints remain
compatible. Attempts and passing results are placement/enrollment scoped;
attachment never grants access or shares an attempt budget. Composite foreign
keys, owner/admin checks and centralized enrollment access validate all targets.
Required Section/Course assessments enforce prerequisite completion on reads,
attempts, submissions and media. Existing sequential learning waits for required
Section assessments, without another setting or locking engine.

Lesson percentages retain the existing calculator. A central policy separates
eligibility from immutable formal completion evidence. Finalized records preserve
course metadata, lesson completions and required passing attempt proofs.
Migration backfills previously established eligible-lesson completion; later
requirements cannot revoke historical completion. Completion events have no
direct client/service writes or reads and reject UPDATE. Authorized course/tenant
purge retains cascade behavior. New placement APIs fail closed before 127.
The active checksum manifest is migrations-115-134.json with 114..134 compatibility;
earlier SQL/manifests remain immutable. Local rollback, rehearsal, security and
release validators are mandatory. Production mutation is not part of this phase;
bridge-first, verified backup, protected-controller and forward-repair rules apply.


### Commerce learning entitlements (schema 128)

Migration 128 extends existing Commerce products and orders with generic offerings,
provider checkout/event records and purchase-time entitlement terms. Learning owns
only offering/course associations and consumes server-confirmed entitlements in
the existing additive grant resolver. Billing type and resource scope are independent.
All Access covers current and future published catalog courses; Private, draft,
archived and explicitly non-catalog courses are excluded. Entitlement does not create
enrollment except for an explicitly requested course checkout. Subscription expiry,
refunds and reversals remove only Purchase access and retain learning history.
Formal completion and the lesson progress engine remain unchanged. New APIs fail
closed before schema 128. Existing production payment paths are unchanged; live
learning payments are disabled. The development test adapter requires an explicit
flag, APP_ENV=development, loopback database on port 54322 and local requests.
The active checksum manifest is migrations-115-134.json, compatibility 114..134.
Earlier applied migrations/manifests remain immutable. Bridge-first promotion,
verified backup, protected-controller upgrade and forward-repair rules still apply.
Local feature verification does not authorize production mutation or deployment.


### Formal-completion credentials (schema 129)

Migration 129 adds tenant templates, course certificate configuration and immutable
issued credential snapshots. An AFTER INSERT hook consumes the existing formal
course completion event, atomically issuing at most one course credential per
completion. It does not compute progress or assessment eligibility. Historical
completions require explicit owner/admin backfill; enabling alone never backfills.
All credential APIs fail closed before schema 129. Client roles and service_role
have no direct table mutation or private issuance-hook permission. Authorized
RPCs enforce tenant membership, owner/admin management and learner ownership.
Public verification exposes only seven safe fields under an independent secure
64-hex-character token. PDFs are private and rendered synchronously from issuance snapshots
using pinned Matplotlib 3.11 native Unicode/Arabic shaping and PDF infrastructure
plus pinned QR generation. Legacy reshape/bidi preprocessing is deliberately
excluded because it would double-reverse text under 3.11.
Managed images are copied into the template design and then into each credential,
so later asset/name/template changes cannot rewrite history. Revocation updates
only lifecycle fields and never deletes formal completion. Course/completion
foreign keys protect credential history from ordinary deletion, including tenant
purge when credentials exist. Archives, deactivation and commerce expiry/refunds
do not change credential status. Reissue UI is deferred.

The active manifest is migrations-115-134.json with compatibility 114..134 and
rollback compatibility 114 only. Earlier applied SQL and manifests are unchanged.
Rehearse fresh application and transaction rollback on marked disposable local
PostgreSQL before applying to the local development database. Production remains
unchanged; image/configuration gates unavailable locally must be reported.

Certificate validation also updates the existing AnyIO, PyJWT and urllib3 pins
to advisory-fixed versions in both requirements and constraints. The backend
image context excludes the local madar_env virtualenv. These are source-only
changes; local image builds/tests and dependency audits do not deploy anything.

The schema-130 Academy projection is service-only and fails closed before 130.
It publishes only catalog-eligible courses and relevant active offerings, uses the
existing access/progress/credential engines for authenticated state, and leaves
lesson content private. Fixed presentation content uses existing tenant settings;
there are no layout blocks or new commerce/progress tables.


Academy integration (schema 131) uses existing Builder projects with immutable
usage profiles and tenant-scoped Academy bindings. Database and server checks
exclude forms, bookings, code and private learner payloads from landing schemas.
Atomic Builder publication preserves the separate main website binding. Open
registration creates existing platform users with learner tenant memberships;
verification activates that membership without provisioning owner privileges.
Staff context is denied to learner memberships, while existing learning engines
remain authoritative. Schema 130 remains immutable. The active compatibility
range is 114..134 and manifest migrations-115-134.json. Protected controller,
bridge-first, backup and forward-repair rules remain mandatory. Local verification
does not authorize production migration, deployment or control-plane upgrades.

Academy Builder expansion (schema 132) retains the shared Builder project/page/layout/chrome/history/publication models. The additive editor binding is tenant/profile checked and clears on deletion; atomic owner-only initialization recovers missing/archived bindings without replacing the separate published snapshot. Public presentation pages cannot use fixed learning/auth/checkout route names. Instructor cards expose only active identities assigned to public catalog-eligible courses; contact emails and account references remain private. Full Academy initialization fails closed until 132. Applied migrations through 131 stay immutable; production migration/deployment/control-plane upgrades are not authorized by local development.


## Group identity and deletion (schema 133)

Migration 133 adds tenant-scoped normalized group-name enforcement for new names (case and whitespace insensitive, including archived records). Existing duplicate groups and their relationships are retained unchanged; same-name edits remain available for legacy records. Transaction advisory locking serializes name checks. The service-only delete RPC checks active owner/admin membership, tenant, confirmation and expected revision under the existing relationship lock. Group memberships, course/instructor assignments and group grants cascade; users, courses, enrollments and progress history remain. Other grant sources retain access. New group create/update/delete require schema 133; prior reads and archive remain bridge compatible. Applied migrations through 132 are immutable. The active manifest is migrations-115-134.json; compatibility is 114..134. Local verification does not authorize production deployment or migration.


## Instructor deletion (schema 134)

Migration 134 adds a service-only instructor deletion RPC, requiring active tenant owner/admin membership, explicit confirmation and expected revision under the existing relationship lock. Course/group instructor assignments cascade through existing FKs; linked user accounts, courses, groups, enrollments and progress remain. The API fails closed before schema 134. Earlier migrations through 133 are immutable. The active checksum manifest is migrations-115-134.json with 114..134 compatibility; production deployment/migration remain unauthorized by local work.
