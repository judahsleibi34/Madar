# Madar production release acceptance policy

Active local-Supabase integration profile: **schema115 only**, migration class
`none`, migration policy `none`, no selected migration manifest. Retained bridge
examples below describe reviewed migration history/future work and authorize no
SQL for this profile. Main's 116..135 artifacts remain checksum-verified; features
requiring those schemas retain their existing unavailable/upgrade-required gates.
Production installation, promotion and migration require separate approval.

Last implementation review: 2026-10-05

Provider402 preparation and activation use separate protected evidence records.
Trusted root installation validates immutable preparation preconditions and
issues its one-time credential only after attestation/witness; it grants no
traffic or worker authority. Human/rollback evidence may be pending at that
preparation boundary. Phase 2 requires the separate completed rehearsal with
all mandatory gates PASS and human results for the exact SHA/image pair. Its
receipt pins preparation, completed report and human-evidence digests, checked
again at every Phase-3 boundary. Updating completion never rewrites or reissues
the preparation credential. Normal deployment, schema/forward repair and
migration protections remain unchanged.

Provider402 bootstrap may replace a credential-free legacy normal-upgrade
`quiesced` interlock only through its trusted installation transaction. The
exact old record is bound into the approved recovery contract, must match the
installed/serving legacy SHA, and requires all upgrade/backup operations to be
inactive. The original timer snapshot is archived privately and the pending
installation interlock replaces it atomically under both locks. This grants no
runtime authority; installation attestation, witness, one-time credential and
complete Phase-2 authorization remain required. Unknown, changed, active or
already-authorized interlocks reject installation. Normal deployment,
forward-repair and schema-recovery protections are unchanged.

## A. Purpose and authority

Coordinated local-Supabase checkpoints may opt into protected configuration
escrow in a format-3 backup. They explicitly declare configuration values are
included and bind a schema115 coordinated manifest covering the database,
roles, native Storage/xattrs, native configuration/init dependencies, function
cache, managed files, production/controller state, images, ledgers and Auth
metadata. Backup verification and Node1 replication require the complete
checksum-bound independent restore proof, including private runtime/asset and
tenant-isolation checks. Ordinary backups still exclude configuration values;
the opt-in does not change routing, credentials, deployment or migration policy.
Custom dumps retain ownership and ACL metadata. The ordinary restore command
keeps its existing explicit ownership/ACL policy; pinned native recovery can
restore the original managed role permissions from the same archive.
A coordinated capture may supply a validated exported snapshot while holding
its read-only exporting connection open. The dump and opaque per-table restore
comparisons then share one consistent database snapshot. Scheduled backups keep
their existing default snapshot behavior; this does not fence or mutate source
data and does not authorize any configuration publication.
Provider byte backup accepts plaintext HTTP only at the exact host-loopback
gateway `127.0.0.1:18000`, paired with the reviewed local session endpoint
`127.0.0.1:15432`, project-scoped PostgreSQL user and explicit local SSL policy.
Transaction pooling and arbitrary plaintext provider destinations are rejected.
Hosted provider backups retain their HTTPS requirement. Governed production
handoff uses direct native PostgreSQL (`supabase-db:5432`, role `postgres`), never
either pooler. Each scheduled job resolves the healthy, unpublished native DB's
private IPv4 address from its fixed Docker service and canonical stack directory;
the address is confined to the child libpq environment and is never persisted.
The governed post-cutover backup child runs as `madar` with empty supplementary
groups and no-new-privileges. Its root coordinator resolves the native DB and
hands off only a root-owned, sealed anonymous address descriptor, bounded to the
backup deadline. The child never receives Docker access. Provider subprocesses
validate the same descriptor; untrusted descriptors and stale leases fail closed.
A read-only database/credential/managed-file execution gate runs before staging
and again before the final write grant. Nonsecret canonical path configuration
retains its 0644 permissions; secret backup and provider credentials remain private.
Wrong service identity, public bindings, unhealthy DB, ambiguous networks or
non-private addressing fail closed. Existing hosted backup configuration remains
unchanged until the exact-bound normal-local finalization publishes its pre-image
and the six reviewed database fields. The session-route allowance above remains
only for previously reviewed isolated captures, not scheduled local production.

The governed provider402 traffic switch enforces canonical query/referrer-safe
proxy logging before serving recovery authentication, including runtime-only
local rollback. Publication is part of traffic switching, not a pre-switch
production mutation. It uses the installed proxy service and pinned image;
failed publication follows the existing local-compatible rollback rule. SMTP
configuration reuses the same guard. Normal deployment readiness and all
recovery authorization, worker, schema and migration checks remain unchanged.

Provider402 installation requires backup operations to finish and all four
backup timers to be stopped before controller apply. Trusted bootstrap records
their original states in a root-private exact-contract snapshot and verifies
quiescence. The pending installation interlock grants no runtime authority;
normal upgrade credential issuance and installer backup checks are unchanged.
Automation resumption remains a separate governed decision after recovery.

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
- `web/deployment/lib/supabase_ledger_reconciliation.py`
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

The application Compose file is rooted at `web/docker-compose.yml`. Both
documented repository use and the immutable release controller evaluate it with
`web` as the Compose project directory. Therefore its development-only relative
defaults are `.env` and `./backend`; production never relies on those defaults
because the controller supplies the absolute protected environment and storage
paths above.

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

Installer dry-run and apply share the same read-only static filesystem
preflight before the first directory, backup, or controller mutation. Every
existing component of privileged source and destination paths must be a real
root-owned directory with no group/world write bit and no effective non-root
POSIX ACL write grant; private upgrade state directories, when present, must
be mode 0700. Root-owned mode 0755 system parents such as `/var/lib` are valid.
The shared preflight also checks launcher/controller/unit parents and existing
targets, the backup and upgrade state hierarchy, writable destination mounts,
source cleanliness and identity, required production paths, and working
`renameat2(RENAME_EXCHANGE)` support on the publication filesystem.

Operational quiescence is deliberately mode-aware. The auto-deploy timer must
be inactive and disabled and the auto-deploy service must be inactive for both
installer modes. A currently running backup, verification, or replication
service also blocks both modes. Scheduled backup timers may remain active
during installer dry-run because dry-run is read-only; installer apply requires
those backup timers to be quiesced first by the governed upgrader. Apply
re-evaluates the static checks after quiescence to remain fail-closed against
races. The installer never stops those backup timers merely to make its own
preflight pass, and it never chmods or chowns `/`, `/var`, or `/var/lib`.

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

The production frontend build requires `VITE_API_URL=/api`, which the frontend
Nginx service proxies to the backend on the same public origin; the staging
override expects `http://127.0.0.1:18001`. `PUBLIC_SITE_DOMAIN` supplies the
trusted tenant-host suffix. Deep validation also finds a Vite JavaScript asset
on the loopback candidate frontend and verifies that the expected API base is
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

The retained future learning bridge spans schema `114..135`, targets `135`, and uses
`migrations-115-135.json` with class `forward-compatible` and rollback metadata
`114..114`. Migrations through 114 remain immutable. The candidate reads the
schema-099 commercial resolver at schema 114; new commercial mutations fail
closed with `commercial_upgrade_required` until migration 115 is complete.
Only after bridge acceptance and a verified schema-114 backup may the
coordinator apply the contiguous 115 through 135 manifest. Migration 115 adds
reversible tenant commercial holds, snapshot
product assignments, revision-checked commands and immutable financial/event
history guards. No assignment or payment is inferred from historical usage.
Existing production configuration of commercial enforcement is not changed;
explicit holds take precedence over its temporary bypass.

After advancement to 115, the prior application cannot enforce holds and its
schema range ends at 114. Recovery is forward repair only; never serve the prior
binary at 115. Changes to `web/deployment/releases` require the existing governed
control-plane upgrade workflow before this candidate can be deployed. No such
upgrade or deployment is authorized by this development change.

The earlier schema-113 to 114 public-runtime bridge and schema-112 to 113
asset-visibility bridge remain immutable historical release contracts.

The preceding schema-109 bridge used `migrations-110-112.json`. Migration 110
atomically creates the durable e-commerce order notification intent with the
order transaction, installs a deferred order trigger so finalized totals are
included, and safely repairs missing intents for orders from the preceding 30
days. Migration 111 adds tenant-scoped product-category associations, backfills
the existing primary category, and preserves `ecommerce_products.category_id`
for compatibility. Migration 112 changes the product-owned variant relationship
to cascade when an unreferenced product is deleted; order, inventory, and loyalty
foreign keys remain restrictive so transaction history cannot be erased.
That historical manifest and its migration checksums remain retained.

The preceding schema-108 bridge contract used schema
range `105..108`, target `108`, class `forward-compatible`, rollback metadata
`105..105`, and the checksum-pinned `migrations-106-108.json`. Migrations 100
through 105 are applied production history and remain immutable. Migration 105
established canonical tenant subdomains in the prior `104→105` release; its
historical manifests remain retained. Only after bridge acceptance at schema
105 the coordinator could create a verified source-schema-105 backup and execute
the ordered `105→106→107→108` sequence. Migration 106 snapshots order delivery
fees, 107 adds e-commerce category images, and 108 adds tenant-scoped
e-commerce brands.

The preceding schema-097 bridge added verified-customer loyalty through atomic
functions. Identity is `(store tenant_id, public.users.id)`; checkout email and
phone are never identity keys. The append-only ledger is authoritative, balances
are locked/versioned projections, and returns remain a future
compensating-ledger flow.


Schema 096 caps one product aggregate at 50 descriptive attributes, 5 options,
50 values per option, 500 explicit variants, and 4 images per variant. These
are abuse and payload-size safeguards rather than catalog dictionaries: five
dimensions and 500 explicitly stocked combinations cover normal v1 catalogs
without permitting pathological lock time or request size.

An earlier bridge contract was schema range `81..95`, target
`95`, class `expand-only`, rollback metadata `81..94`, manifest
`migrations-095.json`, and migration policy
`automatic-after-known-good-backup-first-forward-repair`. It promotes and is
accepted while schema 94 is live. Structured delivery checkout and merchant
order operations deliberately fail closed until the schema-095 RPCs and tables
are present. Only afterward may the separate coordinator create a
schema-94-bound verified backup and execute 94→95. Existing catalog and settings
reads remain safe throughout that bridge interval.

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

Traffic promotion never applies or reverses database migrations. When a schema
transition is pending, its migration-bearing bridge release must first pass the
complete promotion state machine and be durably `known_good` while its source
schema is still serving. Automatic
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
attestation fails closed.

A later application release may be accepted after an earlier release already
reached the same manifest target. After all identity, policy, manifest,
checksum, validator, stable-route, and live-schema checks pass, the coordinator
records a durable backup-free `already_at_target` completion only when all of
the following prove that this is not a resume:

- this SHA has neither `automation.json` nor `execution.json`;
- its current `known_good_release.schema` already equals the target; and
- its own `known_good`/`complete` acceptance history event records the target as
  the observed schema.

This no-op does not create or attest a backup, open a database connection, call
the executor's `run()`, run SQL, rebind an earlier release's backup, or recreate
workers. The nonexecuting checksum verifier still validates every manifest
input. Subsequent
same-SHA cycles return the same completed record. The presence of any
current-release migration state, or an acceptance observation below target,
disqualifies the no-op and preserves the original release-bound resume backup
requirements. A missing or substituted backup then fails closed.

After an executed transition's final target is observed, the controller
recreates schema-gated workers for the active bridge, repeats active-slot and
stable-proxy validation, and only then updates the known-good record's observed
schema. Backup,
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

### Operator-only Supabase ledger reconciliation

Madar's executor owns `application_schema_state` and intentionally does not
write Supabase CLI's `supabase_migrations.schema_migrations` table. After an
executed migration reaches its target and the coordinator has completed worker
refresh plus active/stable health validation, an operator may reconcile that
single version with:

```bash
python3 web/deployment/lib/supabase_ledger_reconciliation.py \
  --release-sha <exact-40-character-sha> \
  --repository-root /srv/madar/production \
  --state-root /var/lib/madar/releases \
  --confirm 097:<pinned-sha256>
```

The command requires a clean exact-SHA checkout; the release contract and
manifest transition; the pinned SQL checksum; matching completed
`automation.json` and `execution.json`; target-schema known-good history; a
direct live schema read; stable version/readiness identity; and a contiguous
remote predecessor. Only then does it invoke the supported
`supabase migration repair --status applied` ledger-only operation. It verifies
the postcondition and writes a private atomic audit record. Repeated execution
is idempotent. It never applies SQL or reads/writes tenant or business rows.
This is a separate reviewed operator action, not part of automatic migration,
and `supabase db push` remains prohibited as a replacement for the coordinator.

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
| `check_production_config.py` | No | No | No | Operator/staging presence and shape validation; never prints values |
| `check_dependency_locks.py` | No | No | No | Backend and frontend CI |
| `check_host_capacity.sh` | No | No | No | Installed periodic host-capacity service/timer; host-specific |
| `monitor_hosted_domains.py` | No | No | No | Read-only public HTTPS synthetic monitor; its timer is separately governed and does not enable deployment |
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
- [ ] run `check_production_config.py` against the intended production and
      isolated-E2E environment files and resolve every `MISSING`/`INVALID` item;
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

The hosted-domain monitor script and its service/timer are protected operational files. The installer backs up, installs, and attests them but does not enable either the monitor timer or `madar-auto-deploy.timer`. The monitor's live success history, current backup/Node 1 state, and exact-main CI are operator prerequisites to a separate decision to resume automatic deployment; see the [hosted-domain runbook](../web/docs/hosted-tenant-domains-operations-runbook.md). This adds no release-promotion or migration gate to the current controller.

## T. Privileged protected-control-plane upgrade gate

Ordinary releases remain automatic. When `madar-control-plane-guard` detects a
protected-path difference between installed provenance and the exact candidate,
it blocks the non-root deployer and prints the authorization command:

```text
sudo madar-control-plane-upgrade <exact-candidate-sha>
```

The root-owned upgrader pins freshly fetched `origin/main` to that full SHA,
requires fast-forward ancestry and the canonical remote, validates healthy
current production, quiesces automation, stages an immutable root-owned Git
bundle whose sole attested remote-main ref is imported with local-file transport
into a template-free repository and checked out detached at the exact SHA,
runs installer dry-run and apply with a verified backup, deploys once through a
hardened transient systemd unit executing the exact ordinary
`madar-auto-deploy` entrypoint, independently attests known-good health and
migration terminal state, runs a deterministic same-SHA cycle, and restores the
captured timer state. Its root interlock prevents concurrent ordinary/manual
release, migration, and traffic-switch entrypoints. Post-install and
post-promotion failures leave automation
disabled; it never automatically restores old controller code, traffic, or
schema across an irreversible boundary.

The privileged upgrader also recognizes one temporary controller-first
bootstrap state. It does so only after canonical candidate resolution: installed
provenance must exactly equal the explicitly approved current `origin/main`
SHA; the serving production SHA must be its strict forward ancestor; the
repository, objects, serving identity, service state and canonical paths must
remain valid; the current guard failure must correspond to the protected-tree
delta between those two commits; and the installed guard must accept the
approved SHA. This is recorded as `controller_ahead_bridge`. The upgrader stages
and validates the candidate, skips redundant controller publication and backup,
attests the already-installed exact controller, and completes application
promotion and same-SHA validation. It never treats the serving SHA as a
controller downgrade candidate.

All installed-guard calls made by this privileged coordinator execute through a
sanitized `runuser` boundary as the canonical `madar` deployment identity,
which owns the production repository. The upgrader does not bypass Git's
dubious-ownership protection with root `safe.directory` configuration. A
status-1 result from the current guard is not sufficient bridge evidence: the
independent exact protected-tree delta and every candidate/provenance/ancestry
attestation above must pass, followed by a successful guard against the
approved SHA. The guard and ordinary deployer exit semantics are unchanged.

This exception exists only inside the exact-SHA privileged transaction.
`madar-auto-deploy`, `madar-production-deploy`, and the guard itself remain
unchanged and fail closed for protected candidate changes. A pre-promotion
bridge failure retains the approved controller, old serving application and a
disabled timer; a post-promotion failure remains forward-repair-only. Successful
completion restores the timer's captured state exactly, including preserving an
initially disabled/inactive state.

The detailed trust model, phases, self-update behavior, audit locations,
failure boundaries, operator commands and initial bootstrap procedure are in
[`control-plane-upgrade-architecture.md`](control-plane-upgrade-architecture.md).

Implemented by:

- `web/deployment/lib/control_plane_upgrade.py`
- `web/deployment/lib/control_plane_filesystem.py`
- `web/deployment/lib/control_plane_upgrade_authorization.py`
- `web/deployment/bin/madar-control-plane-upgrade`
- `web/deployment/bin/madar-install-control-plane`
- `web/deployment/bin/madar-control-plane-guard`
- `web/deployment/bin/madar-migrate`
- `web/deployment/bin/madar-switch-traffic`

Any change to these files or the protected-path set requires same-change review
of this section and the architecture document.

## E-Learning management bridge (schemas 117 through 124)

The active bridge supports schemas 114 through 135 and preserves main migrations
115 and 116 in the contiguous `migrations-115-135.json` manifest. Migration 117
adds tenant-owned E-Learning JSON configuration and a service-role-only atomic
merge RPC. Tenant owner/admin API authorization is mandatory; database access
is denied to anonymous and authenticated clients. Before schema 117, settings
reads return defaults with `available=false`, and saves return the controlled
`elearning_upgrade_required` response without touching the new table. Logo uploads also fail closed before schema 117.
At schema 117, owner/admin
uploads require the existing image-upload entitlement and reuse managed storage
quotas, content validation, rate limiting, durable storage and cleanup. Only
registered PNG/JPG/WebP files owned by the session tenant may be saved as managed
logo paths. Saved E-Learning logo references retain assets without granting
public visibility. Reference lookup tolerates only the explicitly missing-table
errors on pre-117 schemas; other database failures propagate to preserve the
existing fail-closed visibility and cleanup behavior. No learner runtime is introduced.

The source remains schema 114 because the declared commercial bridge has not
been replaced by evidence of an applied schema 115. Existing schema-115 live
instances can skip migration 115 through the normal executor. Rollback metadata
remains 114 only due to commercial holds; post-transition recovery stays forward
repair. This metadata change touches protected `web/deployment/releases` and
requires the governed exact-SHA control-plane upgrade before deployment. No
production migration or deployment is performed as part of development.

Migration 118 adds `elearning_courses` with tenant ownership, managed cover asset
references, status/access constraints, timestamps and optimistic revisions. It is
expand-only, requires schema 117 and advances the schema guard transactionally.
RLS and revoked client grants restrict access to the service role; the backend
enforces active tenant owner/admin membership and scopes every query to that
tenant. Course list reads return `available=false` with no rows before schema
118; detail reads, mutations and cover uploads return the controlled
`elearning_courses_upgrade_required` error without querying the course table.
Settings continue to function at schema 117. Cover uploads reuse the managed
image pipeline and entitlement; saved course covers, including archived courses,
retain registered assets without granting public visibility. Missing-table
reference checks tolerate only PGRST205/42P01; other failures propagate.

The checksum-pinned contiguous manifest is `migrations-115-135.json`; previously
published manifests and SQL 115/117/118/119 remain unchanged. Local validation must
cover schema-gated behavior, tenant/role isolation, optimistic conflicts, image
ownership/retention, migration mirror/checksum integrity and release transitions.
Deployment still requires the existing backup-first migration and protected
control-plane contract. Structure counts become active at schema 120; learner counts become active at schema 121; publishing a course does not activate learner access or payments.

### Group and instructor management (schema 119)

Migration 119 is an expand-only, transactionally guarded 118-to-119 transition
adding tenant-owned `elearning_groups` and `elearning_instructors`. The active
bridge accepts 114 through 135, targets 135 and uses the checksum-pinned
`migrations-115-135.json` manifest. SQL and prior manifests through 119 remain
unchanged. Lists return unavailable empty results before 119; detail reads and
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

### Course Structure Builder (schema 120)

Migration 120 is an expand-only, guarded 119-to-120 transaction. It adds generic
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

Before 120, structure reads return unavailable empty results after verifying
course ownership at schema 118+, and structure writes fail closed without
touching the new objects. Before 118, even structure reads fail closed. Course
reads batch active counts at 120 and use zeros earlier. Archived sections retain
lessons and are excluded, with their descendants, from active counts. Lesson
moves preserve IDs and only target an unarchived section in the same course.
Section duplication copies section/lesson metadata as Draft; content blocks do
not exist yet. Empty-section/lesson deletion requires explicit confirmation;
sections containing any lessons cannot be deleted. Future content relations
must restrict permanent deletion until their retention contract is implemented.

The active manifest is `migrations-115-135.json`; earlier SQL and manifests are
retained unchanged. Local validation covers real PostgreSQL ordering,
concurrent commands, tenant isolation, schema gates, grants and checksums.
Lesson routes host the schema-124 Content Builder described below.
Structure introduces no learner delivery. Participation
at schema 121 is governed by the additional contract below. Deployment retains the governed
control-plane upgrade, known-good bridge, verified backup and forward-repair
requirements above.

### Learner participation (schema 121)

Migration 121 expands 120 to 121 transactionally. It creates tenant-owned learner
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
archiving retains history. Pre-121 mutations/progress reads fail closed and
course learner counts remain zero. Learner lists are unavailable empty results
before 121. The schema-120 structure count RPC remains unchanged; participation
counts are batched through a new schema-121 RPC.

The active manifest is migrations-115-135.json, preserving SQL/manifests through
120. No migration inserts dummy data. The separate development seed requires
the generated loopback local environment and a running local Supabase Docker
container, resolves the configured test account's current tenant, uses stable
IDs/ownership markers and refuses unrelated records on reset/cleanup. Production
changes remain unauthorized; governed control-plane upgrade, verified backup,
known-good bridge and forward repair remain mandatory deployment constraints.

### Confirmed course deletion (schema 122)

Migration 122 is an expand-only 121-to-122 transaction adding a service-role-only
course deletion RPC. No direct table DELETE grant is added. Owner/admin APIs
require explicit confirmation, the exact course name, and expected course and
structure revisions. The RPC verifies membership, locks the course (also used
by structure/participation commands), rejects stale revisions, and atomically
removes course completions, enrollments, lessons, sections and the course.
Learner contact profiles and managed asset files remain; normal reference-based
asset retention/cleanup still applies. Unexpected future foreign-key references
block deletion and roll back the complete transaction. Before 122, deletion
fails closed and course cards expose deletion_available=false. Migration SQL
and manifests through 121 remain immutable; active metadata targets 135 with
the contiguous migrations-115-135.json manifest. Production deployment/mutation
is not performed; all existing protected-controller, backup and bridge gates
remain mandatory.


### Course enrollment management (schema 123)

Migration 123 expands 122 to 123 without changing course/structure entities.
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
fields are null until integrated. Pre-123 management fails closed. The active
manifest is migrations-115-135.json, preserving all earlier SQL/manifests.
No production mutation, account creation, payment engine or group assignment
occurs. Existing governed release, backup and forward-repair gates still apply.


### Lesson content blocks (schema 124)

Migration 124 expands 123 to 124 transactionally with tenant/course/lesson-owned
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
public visibility. Content reads, mutations and uploads fail closed before 124.
Earlier E-Learning functionality keeps its existing schema gates. The bridge
supports 114..135, targets 135 and pins the contiguous migrations-115-135.json
manifest; all earlier SQL/manifests stay immutable. Protected release metadata
requires the existing governed control-plane upgrade before deployment. No
production migration/deployment is part of local development. See
[content architecture](elearning-content-architecture.md) for payloads, rendering
and validation. Existing bridge-first, verified-backup and forward-repair gates
remain mandatory.


### Learner runtime (schema 125)

Migration 125 adds service-role-only learner read, completion and media-access
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
Player endpoints fail closed before 125. Compatibility is 114..135 with the
checksum-pinned migrations-115-135.json manifest; earlier SQL/manifests remain
immutable. The usual bridge, backup, protected-controller and forward-repair
release gates still apply. No production changes are authorized by local tests.


### Additive learning access and assignments (schema 126)

Migration 126 expands 125 with tenant-scoped group membership/course relations,
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
integration. New mutations fail closed before 126; existing pre-126 features
retain their schema gates. The active manifest is migrations-115-135.json with
114..135 compatibility, preserving earlier SQL/manifests. Existing protected
controller, bridge-first, backup and forward-repair release gates still apply.
No production action is authorized by local verification.


### Objective E-Learning assessments (schema 127)

Migration 127 adds generic assessments, typed questions, private immutable attempt
snapshots, answers, and retained audio references. The existing lesson block
references the engine; existing enrollment grants, sequencing and lesson-based
progress remain authoritative. Required published assessments gate new explicit
completion without invalidating existing completions. Learner RPCs serialize
whitelisted questions and never return private grading configuration. Attempts
and answers have no direct service-role SELECT or client write grants. Authoring
and attempt submission use tenant/course transaction locks; uploads retain the
commercial review gate. Historical audio remains referenced until its attempts
are purged. Expand-only compatibility is 114..135; the active checksum manifest
is migrations-115-135.json. Rehearse transaction rollback and all scoped access,
submission and completion checks on a marked local database before deployment.
Production mutation, protected path and source validation rules remain mandatory.


### Assessment placements and formal completion (schema 128)

Migration 128 extends the existing assessment engine with explicit Lesson,
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
purge retains cascade behavior. New placement APIs fail closed before 128.
The active checksum manifest is migrations-115-135.json with 114..135 compatibility;
earlier SQL/manifests remain immutable. Local rollback, rehearsal, security and
release validators are mandatory. Production mutation is not part of this phase;
bridge-first, verified backup, protected-controller and forward-repair rules apply.


### Commerce learning entitlements (schema 129)

Migration 129 extends existing Commerce products and orders with generic offerings,
provider checkout/event records and purchase-time entitlement terms. Learning owns
only offering/course associations and consumes server-confirmed entitlements in
the existing additive grant resolver. Billing type and resource scope are independent.
All Access covers current and future published catalog courses; Private, draft,
archived and explicitly non-catalog courses are excluded. Entitlement does not create
enrollment except for an explicitly requested course checkout. Subscription expiry,
refunds and reversals remove only Purchase access and retain learning history.
Formal completion and the lesson progress engine remain unchanged. New APIs fail
closed before schema 129. Existing production payment paths are unchanged; live
learning payments are disabled. The development test adapter requires an explicit
flag, APP_ENV=development, loopback database on port 54322 and local requests.
The active checksum manifest is migrations-115-135.json, compatibility 114..135.
Earlier applied migrations/manifests remain immutable. Bridge-first promotion,
verified backup, protected-controller upgrade and forward-repair rules still apply.
Local feature verification does not authorize production mutation or deployment.


### Formal-completion credentials (schema 130)

Migration 130 adds tenant templates, course certificate configuration and immutable
issued credential snapshots. An AFTER INSERT hook consumes the existing formal
course completion event, atomically issuing at most one course credential per
completion. It does not compute progress or assessment eligibility. Historical
completions require explicit owner/admin backfill; enabling alone never backfills.
All credential APIs fail closed before schema 130. Client roles and service_role
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

The active manifest is migrations-115-135.json with compatibility 114..135 and
rollback compatibility 114 only. Earlier applied SQL and manifests are unchanged.
Rehearse fresh application and transaction rollback on marked disposable local
PostgreSQL before applying to the local development database. Production remains
unchanged; image/configuration gates unavailable locally must be reported.

Certificate validation also updates the existing AnyIO, PyJWT and urllib3 pins
to advisory-fixed versions in both requirements and constraints. The backend
image context excludes the local madar_env virtualenv. These are source-only
changes; local image builds/tests and dependency audits do not deploy anything.

The schema-131 Academy projection is service-only and fails closed before 131.
It publishes only catalog-eligible courses and relevant active offerings, uses the
existing access/progress/credential engines for authenticated state, and leaves
lesson content private. Fixed presentation content uses existing tenant settings;
there are no layout blocks or new commerce/progress tables.


Academy integration (schema 132) uses existing Builder projects with immutable
usage profiles and tenant-scoped Academy bindings. Database and server checks
exclude forms, bookings, code and private learner payloads from landing schemas.
Atomic Builder publication preserves the separate main website binding. Open
registration creates existing platform users with learner tenant memberships;
verification activates that membership without provisioning owner privileges.
Staff context is denied to learner memberships, while existing learning engines
remain authoritative. Schema 131 remains immutable. The active compatibility
range is 114..135 and manifest migrations-115-135.json. Protected controller,
bridge-first, backup and forward-repair rules remain mandatory. Local verification
does not authorize production migration, deployment or control-plane upgrades.

Academy Builder expansion (schema 133) retains the shared Builder project/page/layout/chrome/history/publication models. The additive editor binding is tenant/profile checked and clears on deletion; atomic owner-only initialization recovers missing/archived bindings without replacing the separate published snapshot. Public presentation pages cannot use fixed learning/auth/checkout route names. Instructor cards expose only active identities assigned to public catalog-eligible courses; contact emails and account references remain private. Full Academy initialization fails closed until 133. Applied migrations through 132 stay immutable; production migration/deployment/control-plane upgrades are not authorized by local development.

Academy verification also pins compatible frontend development-tool fixes:
Vitest 4.1.11, brace-expansion 5.0.12 and Undici 7.30.0. These clear the
full npm audit without introducing a runtime dependency or forced major upgrade.
Normal Builder behavior remains covered by the shared frontend regression suite.


## Group identity and deletion (schema 134)

Migration 134 adds tenant-scoped normalized group-name enforcement for new names (case and whitespace insensitive, including archived records). Existing duplicate groups and their relationships are retained unchanged; same-name edits remain available for legacy records. Transaction advisory locking serializes name checks. The service-only delete RPC checks active owner/admin membership, tenant, confirmation and expected revision under the existing relationship lock. Group memberships, course/instructor assignments and group grants cascade; users, courses, enrollments and progress history remain. Other grant sources retain access. New group create/update/delete require schema 134; prior reads and archive remain bridge compatible. Applied migrations through 133 are immutable. The active manifest is migrations-115-135.json; compatibility is 114..135. Local verification does not authorize production deployment or migration.


## Instructor deletion (schema 135)

Migration 135 adds a service-only instructor deletion RPC, requiring active tenant owner/admin membership, explicit confirmation and expected revision under the existing relationship lock. Course/group instructor assignments cascade through existing FKs; linked user accounts, courses, groups, enrollments and progress remain. The API fails closed before schema 135. Earlier migrations through 134 are immutable. The active checksum manifest is migrations-115-135.json with 114..135 compatibility; production deployment/migration remain unauthorized by local work.

## Ecommerce schema116 reconciliation bridge

The ecommerce bridge on main retains source114 and rollback metadata114, preserves immutable
commercial migration115, and targets116 with migrations-115-116.json. Commercial
holds/access behavior remains unchanged. Catalog writes fail closed until116 installs
service-only V3 atomic product, brand/category/tag/aggregate/publication/registry
commands. Historical identities remain tenant-scoped and uniqueness covers inactive
rows; final-valid swaps defer semantic checks only within V3. Separate catalog and
inventory guards permit descriptive edits without overwriting checkout stock.

Promotion does not execute migrations. Follow the governed control-plane upgrade,
verified backup and known-good bridge sequence. Preserve forward-repair recovery
after the existing rollback bound; no deployment or production mutation is authorized.

## PR #165 migration namespace reconciliation

Main already reserves migration 116 for ecommerce catalog reconciliation. Its SQL,
mirror and historical migrations-115-116.json manifest are preserved byte for byte.
The unpublished E-Learning migrations have been rebased from 116–134 to 117–135;
all learning schema gates, transition guards and checksum manifests follow that
sequence. The retained learning bridge supports 114..135, targets 135, and uses
migrations-115-135.json; it is archived as schema-114-135-bridge.json and is
not selected by the active local-Supabase release contract. Rollback compatibility remains 114 only. Promotion,
verified backup, protected control-plane upgrade and forward repair requirements
remain unchanged. Existing development databases with the old unpublished learning
sequence require a disposable database rebuild; their old schema numbers must not
be treated as this release’s migration ledger. No production mutation is authorized.


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

The migration namespace validator allows only the checksum-verified retained
116..135 artifacts beyond this exact schema115 no-migration target, using the
byte-pinned canonical-main migrations-115-135.json inventory. It rejects136,
renamed/changed retained files, altered manifests or historical files, and any
schema115 descriptor that selects a migration. Retention never authorizes SQL.
No migration file was changed; learning features keep their existing schema gates
and remain unavailable at115 wherever they require117..135.


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

Provider402 sign-in recovery is a separate explicit root-authorized operation;
normal deployment, automatic deployment, migration and ordinary traffic switching
must reject its durable state. A source merge never authorizes installation or
activation. Its protected bootstrap retains the canonical remote, source/image,
schema115, no-migration, installer backup, provenance and unrelated-health gates.
See `docs/provider402-signin-recovery.md` and the exact recovery validation report;
missing accepted Auth evidence or live fixture proof is a NO-GO. Exact-image
human verification remains the default; only the explicit protected emergency
automated acceptance policy below provides an alternative.

### Protected provider402 phase separation

`PREPARE_AND_REHEARSE` runs through the fixed-path `madar-provider402-prepare`
launcher and a root-protected private-resource adapter. It checks exact source,
images, schema115, no migrations, actual provider402 origin/provenance, a verified
checkpoint, private target health and source write-fence validation. It does not
require human Auth or completed runtime rollback evidence to start the private
candidate and fallback. It cannot mutate production traffic, worker authority,
configuration or slots. Preparation receipts do not authorize activation.

`AUTHORIZE_ACTIVATION` requires all fifteen completed rehearsal gates, including
accepted Auth evidence, MFA/AAL2, tenant isolation, business write denial, both-slot worker
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

Root recovery Git status/provenance reads disable optional index updates and
replacement objects. They must preserve the operator-owned canonical index;
fetch/staging retains the existing operator identity and exact-main policy.

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

### Provider402 graduation to normal local production

Recovery exit uses only `madar-local-provider-transition` and its fixed protected
contract/evidence paths. It requires all final migration, checkpoint, independent
restore, off-host, SMTP, security and rehearsal gates; the ordinary deployer,
forward-repair and schema-recovery protections remain unchanged. Schema115 and
migration policy/class `none`, with no manifest, are mandatory throughout.

The normal local backend remains application-fenced through preparation, single
worker handoff and traffic switch. A root-owned read-only directory mount binds
write authority to exact source/schema/contract. Finalization alone grants writes
after the exact production smoke record passes. Unknown or missing authority
fails closed. Notification-worker email is explicitly disabled. Worker ownership
is durable and all retained/archived hosted consumers remain inhibited.

Rollback is a governed current-data runtime switch to the rehearsed local
fallback, preceded by write fencing and worker quiescence. It never restores a
checkpoint or routes traffic to hosted Supabase. Automatic deployment remains
inhibited until its local topology/provenance is independently attested.

Protected `auth-configure` preparation may configure only native GoTrue using
the approved Gmail/STARTTLS secret file after the other final migration proofs
pass. It grants no traffic, worker or write authorization. Canonical callbacks
use `https://api.madarportal.com/auth/v1/verify` and exact frontend verify/reset
redirects; no extra `/api` prefix is introduced. Notification email remains off.
Normal graduation continues to require all gates, including verified Auth SMTP.

Auth SMTP preparation must verify callback-safe effective stable-proxy logging
before enabling public verification/recovery links. Legacy bind-mount replacement
uses only the protected transaction's canonical-config preflight and installed
proxy service; no manual upstream or controller edit is permitted.

Normal local finalization also publishes exact-bound local backup connectivity
through the existing private backup-service environment, retaining a protected
pre-image. Application/worker configuration receives no backup database password.
Backup freshness still requires a real completed verified backup and off-host
proof. Neither connectivity publication nor controller installation attests a
backup or starts automation.


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

SMTP preparation consumes the same explicit acceptance-mode gate set as normal
graduation. Only `auth_smtp` may be PENDING at this preparation boundary; all
other emergency or default gates and their exact-bound evidence remain required.

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


### Repeated local runtime rollback

The governed normal-local `rollback` operation also accepts its completed
`local_rollback_active` phase so an operator can repeat current-data fallback
routing after a runtime address change. It retains the same credential,
exact-contract evidence, archive integrity, production fingerprint, write-fence
and worker-inhibition checks. It grants no writes, starts no consumers, restores
no data and provides no graduation/resumption operation. Lost volatile recovery
credentials remain a blocking condition; this change cannot regenerate them.

### Independently approved emergency routing for active local rollback

`web/deployment/lib/emergency_routing_repair.py` is a standalone standard-library
package for the exact already-active `local_rollback_active` incident. Its fresh
operator approval binds the reviewed code digest, immutable recovery and local
transaction bytes, registered fallback, exact running container IDs/images/
configuration, networks, schema115 and READ_ONLY/consumer authority. Approval is
issued exclusively in its new root-private durable namespace only after the
operator approves that exact independently observed plan. It consumes no old
acceptance PASS record and recreates no `/run` credential, witness or interlock.
It grants no normal deployment, graduation, worker-start, migration, restore or
business-write authority. The existing controller, receipts, checkpoints and
transaction bytes remain unchanged. A separate routing audit records the overlay;
normal-production resumption must independently account for that overlay.

The reviewed bootstrap hashes the exact source and plan before executing source
as root. The additive protected installation publishes only the new package,
`madar-emergency-routing.service`, and a root-only proxy startup gate drop-in.
Nginx uses fixed loopback backend/frontend endpoints 29401/39401. Before every new
forwarded connection the relay independently resolves and validates the approved
fallback's current role/address, local provider, live schema, readiness, write
fence and stopped canonical/retained consumers. It caches no Docker IP. The
persistent approval permits only the same identities and original bound state
until revoked or any binding changes. Reboot/service restart does not mint a new
approval or depend on volatile `/run` records. Unavailable or changed authority
returns 503; unverified destinations receive no customer traffic.

Routing reconciliation holds existing deploy/runtime locks, records exclusive
pre-images and audit events, validates candidate Nginx configuration before
atomic publication, revalidates immediately before publication, reloads and
checks stable/public frontend/API, live identity/readiness/fence and proxy health.
On failure it restores the exact pre-image only when independently safe now.
The known reversed-IP pre-image is preserved but compensated with a bounded
Nginx 503 maintenance route. Failed maintenance publication/reload stops only
the Madar proxy with restart disabled and closes its systemd startup gate;
failed final stop is reported as critical, never as successful rollback.
Every failure retains its package, authorization, pre-images and audit evidence.
Only an explicit governed invocation can retry publication. This service does
not consume queues, mutate database contents or change original write authority.
Production apply requires separate explicit operator approval after review of
the exact operation, affected resources, customer impact and compensation plan.

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

Normal-local candidates use the verified canonical backup-health directory through
a read-only directory bind. They never inherit the disputed provider preparation
marker, and atomic scheduled-marker replacements remain visible without restarting
an accepted image. A format-2 health datum preserves the sealed checkpoint's
actual `checkpoint-<UTC>` identity and manifest creation time. It can only be
constructed after exact complete thirteen-component approved restore validation;
component-only or old PASS packets cannot satisfy that gate. The datum grants no
authority. Source timestamps determine age, so copying/touching cannot renew it.
The subsequent genuine scheduled verifier can publish its existing format-1
marker into the same canonical directory. Any initial publication must preserve
the previous marker under the new governed transaction and have explicit approval.
Privileged child configuration rejects process-loader, PATH, shell and Git
controls; root's command search path remains fixed after application values.


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

### Executable active-rollback normal continuation

The frozen `resume_active_recovery.py` bootstrap is the only new normal
continuation entrypoint. Its exact source inventory and canonical plan hashes
must be explicitly approved. It accepts no driver or production-path override.
Before authorization it independently validates the existing coordinated restore,
original-factor compatibility, reconciliation and NEW final application execution.
Application evidence must bind the final source and backend/frontend image IDs,
unchanged local configuration, schema115 and actual isolated API cases. It must
cover backend existing-account MFA/AAL2, pending-cookie protection, tenant denial,
business permissions, forms, reservations, builder, schema115 ecommerce, readiness,
worker fencing and current-data runtime rollback. No human result is implied.

Production effects use the reviewed resumption components in their existing
order. Public read-only convergence and old Nginx worker drain precede installation
and ownership changes. Configuration publication precedes the positive grant;
actual normal runtime/public verification and post-normal local restore/Node 1
replication precede completion and backup timer resumption. All historical
transactions, credentials, receipts, checkpoints and emergency installation files
remain preserved. Compensation revokes writes, stops bound consumers and serves
the registered fallback against CURRENT local data, or fails closed to maintenance.
There is no customer database restoration or migration in this operation.

Post-normal backups use the existing ordinary format3 implementation in a new
per-plan directory. A real private logical restore and append-only Node 1 checksum
verification are required. The previously verified coordinated checkpoint retains
its original manifest and evidence scope; ordinary post-normal backup proof does
not claim a full native platform or bare-host disaster restore. Final approval is
requested only after implementation, mandatory checks and exact-artifact execution
have passed. No production invocation is authorized by these source changes.

The post-normal backup is created once in its new temporary per-plan namespace.
After actual restore and append-only Node 1 verification, that same directory is
published with rename-noreplace into the existing configured ordinary backup root.
Exact prior local LATEST bytes are archived before the marker points to this new
verified local data. No historical backup directory or Node 1 LATEST is replaced,
and capture retention cannot touch historical scopes. This connects the verified
new backup to the unchanged configured timers without creating another checkpoint.

The post-normal logical restore uses role names from the exact verified checkpoint as NOLOGIN prerequisites for native policy definitions. It does not execute role/password SQL or claim restored role authorization; the coordinated restore evidence retains that separate scope.


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

Fresh authorization may include the narrow pre-publication candidate retirement
specified in the control-plane architecture. Original failed-attempt evidence and
all customer data remain; no historical authorization is replayed. Read-only
preflight must identify exact retained loopback owners and verify their READ_ONLY
state. The fresh operation stops only their unpublished backend/frontend/parser,
then requires free sockets before staging newly accepted exact-source images.
Old CREATED business consumers remain unstarted. Unknown ownership, altered
protected bytes/identities/configuration/networks or a post-publication prior
attempt reject this continuation. No database restore or migration is authorized.

Staging port checks distinguish retired TCP TIME_WAIT from live listeners using
exclusive bind+listen with SO_REUSEADDR, retaining strict Docker identity and
reservation checks and prohibiting SO_REUSEPORT. Actual real Docker lifecycle
regressions, including interruption and a separate serving fallback, are required
for this correction. A subsequent passing preflight does not prove a historical
failure cause. Future failures retain only sanitized operation/type/phase and
source-relative traceback/errno in the protected append-only journal; messages,
locals, command text and private data are excluded. Consumed approvals remain
unusable and fresh deployment approval remains mandatory.

### Post-NORMAL compensated continuation (state F)

A published/installed NORMAL attempt later compensated to restricted recovery
must not use the original pre-installation baseline. A fresh plan embeds the
independently measured `post_compensation` contract inside its destination;
older plan serialization and consumed authorization bytes remain unchanged.
The read-only observer verifies the genuine exact-image acceptance, protected
NORMAL observations and grant boundary, complete compensation chronology,
revoked authority, unchanged transactions/native provider/fallback, all stopped
consumers, frozen original installed source, complete installed tree, production
checkout, proxy controls, retained resources and quiesced backup controls.
Historical records are data and grant no new authority.

The same state-bound resolver checks the opposite stopped slot's actual original
container/image/specification identities and exclusive sockets before approval
and staging under both locks. Only the recorded retained-writer restart-policy
change may explain a historical specification difference; the new baseline pins
all current bytes exactly. Obsolete hosted containers remain stopped evidence
and are never a database or runtime rollback destination. Redis attachment is
resolved from the verified installed continuation, not a slot-name assumption.

The unchanged restricted listener may be reused only with independently measured
frozen source/unit and live READ_ONLY behavior. A new reconciliation record names
that exact resource and its historical source; it does not claim a new install.
The consumed boot unit is retained but disabled in the freshly authorized
operation. Only the measured `92-normal-local-continuation.conf` is atomically
superseded after its exact preimage and replacement intent are durably archived;
all other controls are preserved and effective dependencies are re-attested.
Blind reinstall, additional conflicting Requires gates, consumed replay and
old-data restoration remain prohibited. Controller supersession requires its
complete exact preimage immediately before the governed installer.

No state-F production execution is authorized by this source implementation.
A faithful post-compensation lifecycle rehearsal, actual future-release restricted
backup pipeline/private restore, final exact-image acceptance, mandatory CI and
complete exact-source/plan operator approval remain prerequisites.

NORMAL runtime acceptance must sustain at least three complete native/worker/authority/direct-readiness/public-request rounds over at least five seconds within one 180-second verification deadline. Availability transitions reset the streak; integrity failures immediately invoke governed compensation.

Post-compensation continuation requires a new independently executed read-only reconciliation at the root-private `normal-local-preparation/local-post-compensation-reconciliation-<exact source SHA>/run-<12 hex>/actual-execution.json` path, selected by a protected append-only `index-<exact execution hash>.json`. Its actual invocation, immutable runner, transcript hash and retained-resource scope must match the new plan. Historical pre-install reconciliation remains historical data and cannot satisfy this current-state gate. Original prepublication reconciliation rules remain unchanged.

Failed read-only reconciliation executions remain at their original paths. A later successful run creates a new immutable source snapshot and execution record; only successful actual executions receive a new exact-hash index. Foreign paths, source namespaces and execution hashes fail closed.

A state-F plan may declare a source-bound `pre_grant_backup` with exact ordinary LATEST and health-marker preimages. Read-only preparation may observe readiness 503 solely for stale backup freshness while database, Auth, schema, storage, Redis, environment, MFA policy, parser isolation, identities, transactions and consumer fences remain verified. This observation does not authorize forwarding, worker startup or writes. The hash-gated `finish_compensated_normal.py` first consumes a separate append-only, exact-plan recovery-backup namespace. It captures current authoritative data with a root-sealed database lease and an unprivileged, no-new-privileges, empty-group child with Docker denied. A private portless unprivileged Nginx proxy exposes the genuinely retained installed release's version; no normal release is invented. Independent native logical restore and distinct append-only Node 1 replication must pass before ordinary freshness publication. The unchanged normal bootstrap then requires the protected backup publication, sustained full fallback/public/proxy readiness and every normal source-bound gate. Test backups are never promoted; no checkpoint date, historical receipt or customer database is restored or changed. A failed backup-first attempt remains consumed and stops before candidate creation.


### Schema-115 continuation after routing restoration

A freshly approved state-F continuation may retain the already-compensated local
release as its READ_ONLY fallback. It binds the completed routing-only operation
as historical data and independently verifies current container/image/specification,
loopback ownership, network objects, revoked authority and stopped original workers.
The fallback requires healthy core services and genuinely current ordinary backup
freshness; only intentionally stopped business-worker readiness remains unavailable.
This does not satisfy NORMAL readiness. Original registered fallback records and
expired preparation markers remain unchanged.

The existing continuation listener may be superseded on its existing ports only
under fresh exact-source authority, after detached candidate verification. Preserve
its exact unit and attested preimage; validate the replacement before stopping the
consumed listener and restore the prior service if activation fails. Retain the
working green route throughout preparation. Preserve the genuinely verified current
backup rather than rewriting its marker with a historical checkpoint timestamp.
The normal source fence preserves this explicitly verified READ_ONLY rollback
release; all other source, tenant, worker, final grant, backup and boot gates remain
mandatory. This profile authorizes no migrations or customer database restoration.

A continuation may explicitly bind a separate `controller_source_sha` while
retaining the accepted application `source_sha` and immutable image pair. The
controller package, exact-main installer, production checkout and installed-tree
attestation bind the controller revision; image labels, application runtime,
write-authority release, ordinary backups and application acceptance continue to
bind the unchanged application revision. Existing authorization bytes/digests are
preserved by omitting an absent controller revision from canonical serialization.
No acceptance is transferred to another application revision or image.
