# Madar production release acceptance policy

Last implementation review: 2026-09-01

## A. Purpose and authority

This document is the maintained engineering specification of Madar's production
release safety contract. A candidate is accepted only after the immutable
release state machine records it as `known_good`; fetching or building a commit,
starting an inactive slot, switching the proxy, or passing one health request is
not acceptance by itself.

The separate [automated database migration architecture](automated-database-migration-architecture.md)
blueprint explains the post-known-good bridge, backup, migration, recovery, and
forward-repair state machine. This policy remains the specification of enforced
gates; the blueprint explains their orchestration and rationale.

The current implementation is authoritative. This document must represent that
implementation, not replace it. If code and documentation disagree, stop and
investigate the discrepancy. Do not weaken code to make this document true, and
do not follow stale prose over current code. A policy defect requires explicit
review; it is not permission to bypass a gate.

Primary implementation:

- `web/deployment/bin/madar-auto-deploy`
- `web/deployment/bin/madar-production-deploy`
- `web/deployment/bin/madar-release-deploy`
- `web/deployment/bin/madar-switch-traffic`
- `web/deployment/bin/madar-control-plane-guard`
- `web/deployment/lib/release_deployer.py :: ReleaseDeployer.deploy()`
- `web/deployment/lib/migration_executor.py`
- `web/deployment/bin/madar-migrate`
- `web/scripts/check_migrations.py`
- `web/scripts/check_migration_transitions.py`

### Canonical production path contract

`web/deployment/production-paths.conf` is the single tracked Node 2 production
path contract. Its current values are:

```text
MADAR_PRODUCTION_REPO=/srv/madar/production
MADAR_ENV_FILE=/etc/madar/production.env
MADAR_DEPLOY_STATE_ROOT=/var/lib/madar/releases
MADAR_STORAGE_ROOT=/var/lib/madar/storage
MADAR_ACTIVE_UPSTREAMS_FILE=/var/lib/madar/proxy/active-upstreams.conf
MADAR_PROXY_CONFIG_ROOT=/var/lib/madar/proxy
MADAR_CONTROL_PLANE_ROOT=/opt/madar/control-plane/deployment
MADAR_MIGRATION_BACKUP_SCRIPT=/opt/madar/control-plane/deployment/scripts/backup_madar.sh
MADAR_MIGRATION_BACKUP_VERIFY_SCRIPT=/opt/madar/control-plane/deployment/scripts/verify_backup.sh
```

The auto-deploy unit loads the protected backup environment first and this
root-owned contract second. Consequently backup credentials and
`MADAR_BACKUP_DIR` remain operator configuration, while the production,
state, storage, proxy, controller, and migration-backup executable paths
cannot be redirected by that environment file.

The installed operator-facing deployment entrypoints also load this same
root-owned contract when invoked outside systemd. The installed release
controller applies the contract before reading `production.env`, so a direct
operator invocation cannot silently lose `MADAR_STORAGE_ROOT` or redirect a
safety-critical production path through the interactive shell environment.
Repository/test invocations may retain explicit isolated-path overrides, but
the release controller always requires an explicit absolute storage root; it
has no release-local storage fallback.

For active-runtime refresh modes, non-path application settings are re-read
authoritatively from `MADAR_ENV_FILE` so stale interactive-shell values cannot
shadow an approved config-file change. The canonical path keys remain protected
from values in that file.

The one authoritative root-owned controller is
`/opt/madar/control-plane/deployment`. Historical `/home/madar/...` paths are
legacy evidence or compatibility-entrypoint locations, not current defaults.
`/usr/local/lib/madar/web/deployment` was an intermediate controller root and
must not remain simultaneously authoritative. General operational helpers such
as the alert and scheduled backup scripts may remain under
`/usr/local/lib/madar`; that does not make them a second release controller.

The installer performs an explicit cutover: it requires the canonical repo,
environment, backup environment, initialized release state, storage, and proxy
roots; requires an empty explicit backup directory outside both controller
roots; backs up both a current `/opt` controller and any legacy `/usr/local`
controller under unambiguous names; refuses to run while the timer is active or
enabled or the deploy service is active; installs and marks the `/opt` copy;
installs units that name `/opt`; then retires the legacy
controller/entrypoints before `daemon-reload`. It never
creates or relocates release state. The timer remains stopped for operator
review. Do not copy isolated files or edit the provenance marker.

The new controller is assembled in a root-owned staging directory and published
as an exact tree only after every tracked file, operational migration-backup
script, and provenance marker is ready. The backed-up prior tree is then
replaced, so removed stale files cannot survive beneath a marker for newer
source.

## B. Candidate eligibility (automatic production gate)

`madar-auto-deploy` and `madar-production-deploy` require a clean production
checkout, including tracked and untracked files, before fetching `origin/main`.
The fetched candidate is resolved to a full lowercase Git SHA. The CLI
normalizes its argument and `ReleaseDeployer.deploy()` requires 40 hexadecimal
characters.

Before eligibility evaluation, `madar-control-plane-guard` from the canonical
`/opt` root must exist and pass.
It validates the candidate SHA, the installed root-owned
`CONTROL_PLANE_SOURCE_SHA` marker, and local availability of both commits. Any
change between the installed controller source and candidate under
`web/deployment`, `web/scripts/madar_alert_hook.sh`,
`web/scripts/backup_madar.sh`, or `web/scripts/verify_backup.sh` requires a reviewed,
root-owned control-plane reinstall. The installer itself requires a clean,
committed source tree, preserves replaced files in an explicit backup directory,
and refuses to run while the auto-deploy timer is active or enabled or the
deploy service is active.

The immutable release state must already contain a full
`known_good_release.sha`. Then:

- candidate equals known-good: do not redeploy; enter the idempotent
  post-acceptance migration coordinator, which either no-ops, observes a
  completed target, suppresses a bounded retry, or continues an opted-in
  manifest;
- `origin/main` is behind known-good: no action and no rollback;
- known-good is not an ancestor of candidate: reject main divergence;
- known-good is an ancestor and no watched runtime path changed: fast-forward
  only after giving the application-equivalent known-good SHA's pending
  migration coordinator an opportunity to complete; then advance the checkout
  without a runtime deployment;
- a still-suppressed failed SHA: no retry;
- otherwise: invoke the immutable production deployer.

Watched runtime paths are exactly:

```text
web/backend
web/frontend
web/database
web/supabase
web/scripts
web/docker-compose.yml
web/docker-compose.dev.yml
web/deployment
```

`ReleaseDeployer` serializes deployments with a non-blocking exclusive lock at
`deploy.lock`. A failed SHA is suppressed until its recorded `retry_after`
(default retry interval: 60 minutes; constructor minimum: one minute). The
`--manual-retry` CLI flag bypasses same-SHA suppression for one explicit run; it
does not waive any other gate. Automation must not use it to force a bad SHA.

Implemented by:

- `web/deployment/bin/madar-auto-deploy`
- `web/deployment/bin/madar-production-deploy`
- `web/deployment/bin/madar-control-plane-guard`
- `web/deployment/bin/madar-install-control-plane`
- `web/deployment/lib/release_deployer.py :: ReleaseDeployer.deploy()`

## C. Immutable source and build rules (automatic production gate)

`DockerGitOperations.verify_source()` rechecks production cleanliness, verifies
the candidate commit, and creates or reuses a detached immutable worktree at the
release-state root's `releases/<SHA>` path. Its HEAD must equal the candidate.
The active production worktree is not the release build directory and the active
blue/green target is never rebuilt in place.

Every candidate needs backend, frontend, and worker image identities containing
`@sha256:`. The worker uses the backend artifact. Images are tagged with the full
release SHA and labeled with `com.madar.release.sha` and a common
`com.madar.release.built_at`; the frontend also records its API origin. Reuse is
allowed only when existing backend and frontend labels match the SHA, frontend
origin, and one shared non-empty build timestamp. Otherwise both artifacts are
rebuilt. Preflight resolves each recorded tag again and rejects a changed image
ID.

The production frontend build requires `VITE_API_URL` to equal
`https://api.madarportal.com`; the staging override expects
`http://127.0.0.1:18001`. Deep validation also finds a Vite JavaScript asset on
the loopback candidate frontend and verifies that the expected origin is
embedded.

Implemented by `web/deployment/bin/madar-release-deploy ::
DockerGitOperations.verify_source()`, `build()`, `_existing_artifact()`,
`_digest()`, `preflight()`, and `_validate_frontend_api_origin()`.

## D. Compatibility contract (automatic production gate)

`web/deployment/releases/release.json` defines:

- `compatible_min` and `compatible_max`: inclusive live schemas on which the
  candidate may run;
- `target`: intended schema after the reviewed migration sequence; it must lie
  within the candidate range;
- `migration_class`;
- rollback-compatible bounds and the selected migration manifest.

The release model recognizes these compatibility labels:

| Class | Enforced meaning in the current implementation |
| --- | --- |
| `none` | Valid release descriptor; no automatic migration is implied. |
| `expand-only` | Valid release descriptor and permitted on explicit migration-manifest entries. |
| `forward-compatible` | Valid release descriptor and permitted on explicit migration-manifest entries. |
| `coordinated` | Valid release descriptor, but rejected by the automatic migration executor. |
| `breaking` | Valid release descriptor, but rejected by the automatic migration executor. |

These are policy labels, not a substitute for reviewing the SQL and declared
schema range. `Compatibility.load()` validates membership in this set but does
not infer SQL safety from the name. Recognition also does not authorize
automatic migration execution: `migration_executor.py` accepts only
`expand-only` and `forward-compatible` manifest entries.

The installed controller loads its contract and preflight independently reloads
the candidate worktree's contract. Exact dataclass inequality causes
`control_plane_release_contract_mismatch`. The live schema is read from exactly
one `public.application_schema_state` row where `contract_key=core`; it must be
inside the candidate range. Candidate `/health/version` must report the same
compatible min/max.

Before the inactive slot starts, the running retained known-good target is
queried directly. Its SHA must match state and its reported compatibility range
must contain the live schema. Candidate rollback bounds are descriptive metadata
today; retained-target attestation is the operative rollback check.

Current bridge contract after this policy update is schema range `81..93`, target
`93`, class `expand-only`, rollback metadata `81..92`, manifest
`migrations-093.json`, and migration policy
`automatic-after-known-good-backup-first-forward-repair`. It promotes and is
accepted while schema 92 is live. Only afterward may the separate coordinator
create a schema-92-bound verified backup and execute 92→93. Code that touches
new objects must remain safe throughout that bridge interval.

Implemented by `web/deployment/lib/release_deployer.py :: Compatibility.load()`
and `ReleaseDeployer.deploy()`, plus `DockerGitOperations.schema_version()`,
`preflight()`, `validate_candidate()`, and `validate_rollback_target()`.

## E. General migration tree rules (production preflight and CI)

`web/scripts/check_migrations.py` enforces all of the following:

- both `web/database/migrations` and `web/supabase/migrations` must be
  directories;
- every entry must be a regular file named `NNN_description.sql`, where the
  description is lowercase letters, digits, and underscores and begins with a
  letter or digit;
- unexpected directories, malformed names, missing historical prefixes below
  044, and unapproved new files using a prefix below 044 fail;
- duplicate numeric prefixes fail unless exactly listed in
  `GRANDFATHERED_DUPLICATES` (currently empty);
- the two trees must have matching modern filenames and byte-identical contents;
- the historical database/Supabase 004/005 filename swap must remain complete
  and content-equivalent across the swapped names;
- the historical 013/014 files must remain present and byte-identical in each
  tree; their duplicate-content debt is reported as a warning, and changing it
  fails validation.

Do not edit already-applied historical migrations to make a new release pass.

Implemented by `web/scripts/check_migrations.py :: collect_tree()`,
`check_duplicate_numbers()`, `check_tree_parity()`, and
`check_tenant_relationship_debt()`.

## F. Modern migration-transition rules (production preflight and CI)

`web/scripts/check_migration_transitions.py` applies to every present migration
from 084 onward. For migration `N` it requires:

- exactly one database file and exactly one Supabase file;
- identical filenames and byte-identical content;
- leading-whitespace-insensitive start with `BEGIN;` and
  trailing-whitespace-insensitive end with `COMMIT;`;
- no PL/pgSQL variable named the reserved identifier `current_schema`;
- the declaration
  `v_schema_version public.application_schema_state.schema_version%TYPE;`;
- exactly one guard equivalent to `v_schema_version <> N-1`;
- exactly one `SET schema_version = N` transition;
- a `FOR UPDATE` lock on schema state;
- explicit `contract_key = 'core'` targeting.

The constructs must be live migration logic, not comments or dead text. A valid
skeleton, based on neighboring migrations, is:

```sql
begin;

-- Perform the real, safe, idempotent schema expansion here.

do $$
declare
  v_schema_version public.application_schema_state.schema_version%TYPE;
begin
  select schema_version
  into v_schema_version
  from public.application_schema_state
  where contract_key = 'core'
  for update;

  if v_schema_version is null then
    raise exception using errcode = 'P0001',
      message = 'migration_NNN_schema_state_missing';
  end if;

  if v_schema_version <> PREVIOUS then
    raise exception using errcode = 'P0001',
      message = format('migration_NNN_expected_schema_PREVIOUS_got_%s', v_schema_version);
  end if;

  update public.application_schema_state
  set schema_version = NEXT,
      applied_at = now()
  where contract_key = 'core';
end;
$$;

commit;
```

This is not a copy-paste substitute for business DDL. Inspect the current
validator and valid neighboring migrations before creating a migration.

Implemented by `web/scripts/check_migration_transitions.py`.

## G. Post-acceptance and explicit migration execution rules

Traffic promotion never applies or reverses database migrations. A migration-
bearing release must first pass the complete promotion state machine and be
durably `known_good` while its source schema is still serving. Automatic
migration is a separate post-acceptance phase under the same host
`deploy.lock`; the SQL executor additionally takes the PostgreSQL advisory lock.
It never calls traffic switching or the promotion rollback handler.

### Automatic post-acceptance coordinator

Automation is opt-in per release. It runs only when `release.json` contains the
exact policy
`automatic-after-known-good-backup-first-forward-repair`. `none`, the former
manual policy, missing values, and any other value do not authorize automatic
SQL. The installed and immutable-worktree `release.json` documents must be
byte-semantically equal as parsed JSON. The release class and every manifest
entry must be `expand-only` or `forward-compatible`; the manifest final target
must equal the release target; and its whole source-to-target interval must be
inside the bridge compatibility range.

Before backup creation or opening the migration-executor connection, the
coordinator requires all of the following (including a read-only live-schema
query):

- the requested full SHA is exactly `state.json.known_good_release.sha` and its
  slot is the active blue/green slot;
- no release is in progress and no rollback failure awaits recovery;
- the immutable release worktree is clean, detached at the exact SHA, and its
  installed/candidate release contract and manifest identity agree;
- both migration-tree validators pass again from immutable source;
- migration files exist and match every pinned SHA-256;
- the active slot and stable backend/frontend validate as that known-good SHA;
- live core schema is in the candidate range and within the manifest interval;
- for the first transition, rollback metadata contains the source schema and
  the completed promotion history contains a distinct retained target whose
  recorded compatibility contains that source schema; immediately before the
  forward phase, the coordinator re-attests that retained process's SHA and
  source-schema compatibility directly from its running version endpoint.

The systemd auto-deploy service loads `/etc/madar/backup.env` before the
canonical path contract; the former supplies protected libpq `PG*`
credentials and `MADAR_BACKUP_DIR`, while the latter pins the executable and
storage paths. Credentials are not placed on the command line. The root-owned,
provenance-covered `backup_madar.sh` creates a new complete PostgreSQL-and-file backup using the
canonical storage directories and identifies it with the serving release SHA
and image build timestamp. `verify_backup.sh` must validate format members,
completion metadata, all SHA-256 values, and the PostgreSQL dump TOC before the
database advisory lock is attempted. Automation additionally requires backup
output to be one timestamp-named direct child of the configured backup root,
requires format 3, and attests the backup ID, serving release SHA, and
pre-migration source schema from `manifest.json`; a merely well-formed backup for a different
release or schema is rejected.

Automation state is durable under
`/var/lib/madar/releases/migrations/<SHA>/`. `execution.json` is the SQL
executor record; `automation.json` covers backup, execution, worker refresh,
post-migration health, failure semantics, and retry time. If any transition has
already advanced the schema, a retry is allowed only with the same recorded
backup under the configured backup root. Missing or substituted resume backup
attestation fails closed. A target reached by a prior explicit reviewed run is
not given a fabricated post-fact backup claim.

After the final target is observed, the controller recreates schema-gated
workers for the active bridge, repeats active-slot and stable-proxy validation,
and only then updates the known-good record's observed schema. Backup,
execution, and post-migration validation failures are recorded as
`failed_forward_repair_required`; precondition failures stop before mutation
and are reported directly. Retry defaults to 15 minutes and is bounded to
5..1440 minutes. A failure never makes the accepted bridge bad,
never restores schema, and never routes traffic to the now-schema-incompatible
old slot. The next same-SHA auto-deploy cycle re-enters this coordinator and
either honors retry suppression or safely resumes.

Implemented by `web/deployment/bin/madar-auto-deploy`,
`madar-production-deploy`, and `madar-release-deploy ::
automatic_migrate_known_good()`, `_create_verified_migration_backup()`,
`_validate_stable_known_good()`, and `refresh_active_workers()`.

### Explicit migration runner

The operator-facing `madar-migrate` remains available for reviewed explicit
execution with an already-created backup. It uses the same manifest and
executor gates. It requires an expected release SHA, explicit Git repository
root, backup path, migration state file, and database URL supplied by
`MADAR_MIGRATION_DATABASE_URL` or `--database-url`. Prefer the protected
environment variable so the secret is not exposed in argv. The automatic
coordinator instead uses the same protected libpq `PG*` environment already
required by its backup operation.

Git top-level must equal
the supplied root; the worktree must be clean; HEAD must equal the expected SHA.
The manifest comes from the command or the clean release's `release.json` and
must be a basename matching `migrations-*.json`. A concrete manifest SHA must
match HEAD; `CURRENT` and `STAGING` are bound to HEAD at runtime.

`MigrationManifest.load()` requires a valid SHA or approved placeholder,
repository-contained paths, a non-empty list, `to_schema == number`,
`from_schema + 1 == to_schema`, contiguous transitions, and only `expand-only`
or `forward-compatible`. Before connecting, every migration file must exist and
match its pinned SHA-256.

The executor verifies migration file/checksum inputs and then runs
`web/scripts/verify_backup.sh`. The backup must contain
the required database, checksum, environment metadata, and file-asset members;
format-specific completion/manifest files must be valid; all checksums must pass;
and `pg_restore --list` must read the dump. Only then does the executor acquire
one PostgreSQL session advisory lock.

The core schema row must exist and the current version must be between the
manifest's first source and final target. Already-applied transitions are
recorded and skipped. Every unapplied transition must start exactly at its
declared `from_schema`; its SQL must advance core state to `to_schema`; and the
final target must be reached. Each modern SQL file owns its `BEGIN`/`COMMIT`
transaction. Failure is recorded, the connection is rolled back/closed, and the
system is resumed or forward-repaired—never automatically reverse-migrated.

Implemented by `web/deployment/bin/madar-migrate`,
`web/deployment/lib/migration_executor.py :: MigrationManifest.load()` and
`LockedMigrationExecutor.verify_migrations()`/`run()`, and
`web/scripts/verify_backup.sh`.

### Active known-good environment refresh

`madar-release-deploy <full-sha> --refresh-active-runtime --slot <slot>` is the
supported config-only refresh for an already accepted release. It is not a
deployment, migration, rollback, or traffic command. The deploy lock is held
for the complete operation, and all of these conditions must pass before the
first mutating Compose command:

- the requested SHA and slot exactly equal both `active_slot` and the durable
  `known_good_release`; no deployment or rollback-recovery record is active;
- the live schema exactly equals the schema recorded for that known-good
  release and remains inside the installed release compatibility range;
- immutable source identity and cleanliness pass;
- the recorded backend, frontend, and worker image tags still resolve to their
  digest-pinned identities;
- Compose configuration, migration validators, secret hygiene, and all four
  canonical storage directories pass the normal release preflight;
- the active backend, frontend, Redis, and remote-ingestion containers are
  running and healthy, with application image identities matching state;
- candidate and stable version endpoints identify the requested release and
  compatibility range; and
- readiness core components (`environment`, `database`, `redis`, `auth`,
  `storage`, and `schema`) are `ok` on both the slot and stable route.

Pre-refresh readiness may be HTTP 503 only when degradation is limited to the
services the operation is about to repair: notification worker, calendar-sync
worker, data-deletion worker, or parser isolation. This exception is scoped to
the pre-mutation refresh check; normal candidate validation is unchanged.

After preflight, Compose recreates parser worker, backend, notification worker,
calendar-sync worker, and (for schema 83+) data-deletion worker from the
already-attested images with `--no-build --force-recreate --wait`. It never
runs `down`, builds an image, invokes a migration, switches traffic, or changes
the release checkout. Full candidate readiness and stable backend/frontend
validation are mandatory afterward. Only then is an
`active_runtime_refreshed` known-good history event written. A failure before
that point leaves known-good identity and schema unchanged.

The migration-only `--refresh-active-workers` mode uses the same safe runtime
repair path after a committed forward schema transition, but permits the live
schema to be ahead of the previously recorded known-good observation and keeps
the `post_migration_workers_refreshed` completion event required by migration
automation.

Implemented by `web/deployment/bin/madar-release-deploy ::
load_production_path_contract()`, `DockerGitOperations._storage_root()`,
`preflight()`, `validate_active_refresh_prerequisites()`,
`refresh_active_runtime_services()`, `_refresh_active_runtime()`, and
`refresh_active_runtime()`.

## H. Preflight (automatic production gate)

`DockerGitOperations.preflight()` explicitly performs, in order:

1. re-read candidate compatibility and require equality with the installed
   controller contract;
2. revalidate backend, frontend, and worker image IDs against recorded digests;
3. run `docker compose ... config --quiet` with release topology;
4. run `python3 web/scripts/check_migrations.py` from the immutable worktree;
5. run `python3 web/scripts/check_migration_transitions.py`;
6. run `python3 web/scripts/check_secret_hygiene.py`;
7. require readable/traversable persistent directories for uploads, avatars,
   private uploads, and private generated charts.

Active-runtime refresh invokes this complete preflight before any recreating
Compose operation. A missing/invalid `MADAR_STORAGE_ROOT`, missing bind source,
Compose error, or changed image identity therefore fails before the active
project can be partially mutated.

Container readiness later performs the authoritative storage write probe.
`check_dependency_locks.py`, host-capacity checks, rehearsal scripts, and test
suites are not called by this preflight.

## I. Candidate startup (automatic production gate)

The inactive slot is the opposite of `state.active_slot` (default retained slot
is blue, so candidate is green). The active slot is never rebuilt in place.
Compose starts an isolated project/network topology using immutable candidate
source and `--no-build --force-recreate --wait --wait-timeout 180`.

Initial services are Redis, parser worker, remote-ingestion worker, backend, and
frontend. Queue consumers are intentionally inactive: notification and calendar
workers are disabled, and deletion worker is not required. Parser/remote workers
are slot-local and cannot consume the active slot's Redis queue.

Implemented by `DockerGitOperations._environment()`, `_compose()`, and
`start_candidate()`.

## J. Deep validation (automatic production gate)

Each attempt checks candidate backend `/health/ready` and `/health/version`,
requires readiness `ready=true`, exact candidate SHA, and exact schema compatible
min/max. Component states accepted while ready are `ok`, `disabled`,
`configured`, `not_required`, and `development`; any other component state is
reported as degraded. It then requires frontend HTTP 200 and validates its API
origin from a local Vite asset.

Defaults are 12 attempts with five seconds between attempts. Attempts are
bounded to 1..60 and delay to 1..30 seconds. Exhaustion raises exactly
`candidate_deep_validation_failed:<reason>`.

Implemented by `DockerGitOperations.validate_candidate()`.

## K. Worker cutover (automatic production gate)

After initial deep validation, retained known-good queue workers are stopped.
The candidate backend is recreated with worker-required flags and candidate
notification and calendar-sync workers start. The data-deletion worker also
starts when live schema is at least 83. Compose again waits up to 180 seconds,
then deep validation runs again.

If activation or second validation fails, candidate workers are stopped and all
existing retained workers are restarted before the deployment fails. No traffic
switch occurs.

Implemented by `ReleaseDeployer.deploy()` and
`DockerGitOperations.activate_workers()`, `deactivate_workers()`, and
`restore_workers()`.

## L. Traffic switching (automatic production gate)

`MADAR_TRAFFIC_SWITCH_COMMAND` is mandatory. The release deployer retries it 12
times by default, bounded to 1..60 attempts with 1..30 second delays.

The tracked `madar-switch-traffic` command supports `nginx`, `docker-nginx`, and
the special file-proxy mode. The default is `nginx`; deployment-specific
configuration determines the installed production driver. Before a normal
switch it requires candidate backend and frontend readiness, reads and validates
the candidate SHA, writes the durable upstream target atomically, validates the
proxy configuration/reload, and waits for stable backend SHA plus frontend HTTP
200. Stable verification defaults to 20 attempts, bounded to 2..120, with a
default 0.25-second delay bounded to 0.05..5 seconds.

On normal-driver failure the previous durable target file is restored (or the
new file removed) and proxy reload is attempted before the error propagates.
File-proxy mode prepares an atomic target file and does not perform stable-route
verification; it must not be represented as equivalent to the normal production
proxy path.

Implemented by `DockerGitOperations.switch_traffic()` and
`web/deployment/bin/madar-switch-traffic`.

## M. Observation (automatic production gate)

A successful proxy switch does not make the candidate trusted. The deployment
enters `observation` and repeats full candidate deep validation every five
seconds for a configured observation window (default 60 seconds, implementation
minimum 10 seconds). Any failure enters post-switch rollback semantics.

Implemented by `DockerGitOperations.observe()` and `ReleaseDeployer.deploy()`.

## N. Final acceptance

A SHA is accepted only after observation succeeds and the state update is
durably written. Required state/evidence is:

- `state.json.known_good_release.sha == candidate SHA`;
- the appended history entry has `status == known_good` and `phase == complete`;
- `active_slot` and history `traffic_target` equal the promoted slot;
- recorded backend/frontend/worker image identities are digest-qualified;
- the running backend reports the promoted SHA and the stable proxy was observed
  routing to that SHA with a reachable frontend.

The implementation does not currently perform a separate final
`docker inspect` comparison between running container image IDs and the recorded
digests. Its enforced running-identity evidence is preflight tag/digest
revalidation, `--no-build` candidate startup, candidate/stable health SHA, and
recorded image digests. Do not claim a stronger post-start digest attestation
unless implementation adds it.

Accordingly, the current meaning of running container/image identity agreement
is: the launched topology uses the preflight-attested digest-qualified images
without rebuilding, the backend reports the promoted SHA, and the stable route
reports that same SHA. A future independent container-ID comparison would be an
additional gate and must be documented if implemented.

Implemented by `ReleaseDeployer.deploy()`, `validate_candidate()`, `observe()`,
and `madar-switch-traffic :: _wait_for_stable_route()`.

## O. Failure and rollback semantics

Pre-switch failure destroys the isolated candidate and leaves the active target
untouched. History records `rollback = not_required_active_target_untouched`.
If workers had cut over before a pre-switch failure, candidate workers stop and
retained workers are restored first.

Post-switch failure records `traffic_switch_to_retained_known_good`, stops
candidate workers, restores old workers, switches traffic to the previous slot,
and removes the candidate topology.

If automatic traffic rollback fails, status becomes
`rollback_failed_manual_intervention`, the failure phase and required target are
preserved in state, candidate artifacts/topology are retained, and the deployer
raises `automatic_rollback_failed_manual_intervention`. Manual intervention is
then required; do not erase the evidence or force a new release through.

Implemented by `ReleaseDeployer.deploy()`.

Post-acceptance migration failures are intentionally outside these blue/green
rollback branches. Before the first schema change the retained old slot is still
a viable traffic target and the new complete backup exists. Once any schema
transition commits, the old slot may be schema-incompatible; automation records
forward-repair-required state, retains the accepted bridge in traffic, retains
the original backup and execution evidence, and retries only after the bounded
delay. It never attempts reverse SQL or a proxy switch.

## P. Interrupted deployment recovery

Every phase checkpoints `in_progress_release`. At the start of the next locked
deployment, a structurally valid interrupted record causes source restoration,
prior traffic-target restoration when needed, candidate-worker deactivation,
known-good worker restoration, and candidate cleanup. The archived history entry
uses `status = interrupted_recovered` and clears the in-progress/rollback marker.
Invalid interrupted state fails closed.

Implemented by `ReleaseDeployer._checkpoint()` and `_recover_interrupted()`.

## Q. Other repository and operational checks

| Check | Release promotion | Automatic post-acceptance migration | Explicit migration execution | CI/manual status |
| --- | --- | --- | --- | --- |
| `check_migrations.py` | Yes, preflight | Yes, rerun before backup | No | Backend CI |
| `check_migration_transitions.py` | Yes, preflight | Yes, rerun before backup | No | Backend CI |
| `check_secret_hygiene.py` | Yes, preflight | No | No | Backend CI |
| `check_dependency_locks.py` | No | No | No | Backend and frontend CI |
| `check_host_capacity.sh` | No | No | No | Installed periodic host-capacity service/timer; host-specific |
| `rehearse_migration_*.sh` | No | No | No | Manual, migration-specific rehearsals |
| backend test suite/image build | Image build only | No | No | Backend CI |
| frontend lint/tests/build/audit | Production image build runs the build | No | No | Frontend CI |
| `backup_madar.sh` | No | Yes, new complete backup | No | Scheduled/manual backup tooling |
| `verify_backup.sh` | No | Yes, before DB lock and again in executor | Yes, mandatory before DB lock | Manual/automated migration execution |

This table describes calls proven by current code. GitHub branch protection is
external configuration; workflow presence alone does not prove that checks are
required for merge.

## R. Codex pre-push/pre-merge checklist

Before saying a main-targeting change is ready:

- [ ] confirm the branch/worktree and review all local/incoming changes;
- [ ] read this policy and the current validators/affected deployment code;
- [ ] run `check_migrations.py` and `check_migration_transitions.py` when
      migrations or release-sensitive code are affected;
- [ ] verify database/Supabase migration byte parity and manifest checksums;
- [ ] validate release compatibility metadata against actual bridge behavior;
- [ ] run focused and reasonably broad backend/frontend tests;
- [ ] run `check_dependency_locks.py` and `check_secret_hygiene.py`;
- [ ] run applicable lint/type/build and production image/build checks;
- [ ] review `git diff --check`, status, stat, and full diff for secrets,
      generated/debug files, unrelated churn, dead code, or weakened gates;
- [ ] report every mandatory gate that cannot be tested locally;
- [ ] confirm no known release gate is knowingly violated.

Never claim production-ready with an unresolved mandatory gate. Never bypass a
failed gate or modify production to compensate for rejected source.

## S. Rule-update procedure

Any change to the following must include an explicit same-change review of this
document and update it when behavior changed:

- `madar-auto-deploy`
- `madar-production-deploy`
- `madar-release-deploy`
- `madar-switch-traffic`
- `madar-control-plane-guard`
- `release_deployer.py`
- `migration_executor.py`
- `madar-migrate`
- active-runtime refresh behavior in `madar-release-deploy`
- `production-paths.conf` and tracked systemd/installer path contracts
- `check_migrations.py`
- `check_migration_transitions.py`
- deployment compatibility metadata, manifests, or release contract

The review must cross-check automatic production gates, explicit migration
gates, non-automatic CI/manual checks, failure semantics, defaults, and bounded
ranges against the implementation. If no text change is needed, the PR should
say why. Control-plane changes also require the provenance-aware installation
procedure before automatic deployment can accept the changed controller source.
