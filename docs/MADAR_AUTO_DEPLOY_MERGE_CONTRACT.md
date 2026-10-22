# Madar Auto-Deploy Merge Contract

## Schema156 source-candidate boundary

The automatic Data Source synchronization migration, worker, and systemd templates
are unselected candidate artifacts. Merging source must not select schema156, enable
its timer, provision a provider, create a credential, or cause outbound traffic.
Promotion requires the release-policy rehearsals and an explicit reviewed release
descriptor change in a later deployment-authorized change.

## Unselected schema155 Data Sources credential-vault candidate

Migration155 is an additive, unselected candidate requiring exact schema154 under the
locked `core` schema-state row. It adds encrypted credential versions, append-only
secret-free lifecycle events, source credential revisions, CAS activation/revocation/
rewrap RPCs, and a credential-fenced wrapper around the existing atomic incremental
commit. Both migration trees, the candidate manifest, compatibility bridge, and
candidate validator are checksum-bound. The active release remains schema136.

Automatic deployment must not install, initialize, unseal, configure, or bootstrap
Vault, and must not apply/select155 without separate exact-source approval. Root
tokens, unseal shares, AppRole SecretIDs, application tokens, and Transit root key
material are prohibited from source, manifests, Compose environment, and PostgreSQL.

## C1.8.1 migration154 transition correction

The still-unselected migration154 candidate begins its transaction before all other
statements, locks the `core` schema-state row through a typed version variable before
DDL, requires exact schema153, and advances to154 only after the expansion succeeds.
Its mirrored SQL and candidate manifest checksum are pinned together. The transition
validator removes comments, requires the declaration, core query, row lock, and guard
inside one executable `DO` block, and requires that block to precede DDL for the
guard-first migration series117 onward. Immutable migrations084–116 retain their
historical statement ordering but must still contain the live same-block contract.

## Unselected C1.8 bounded reconstruction refinement

C1.8 changes application processing only and creates no schema155 candidate. The
active release and candidate147–154 selection remain unchanged. Private immutable
downloads use the existing server-only Supabase URL/service-role boundary with
redirects disabled, identity encoding, bounded retry, incremental size/SHA-256
verification, and atomic publication to private worker scratch.

Exact historical replay uses a mode-0700 worker workspace and disk-backed SQLite
state, pages history metadata, streams one verified chunk at a time, and emits the
checkpoint CSV and hashes incrementally. Scratch cleanup is restricted to expired
`checkpoint-*` directories below the configured fixed root. Existing lease/fence,
quota, object-verification, publication, compensation, record/event limits, legacy
local fallback, and Data Logs boundaries remain mandatory. These source changes do
not authorize migration, bucket access, worker scheduling, deployment, or production
data processing.

## Unselected schema154 shared immutable-storage candidate

The additive153→154 shared immutable-storage candidate is not selected by the
active release. It reuses the existing private Supabase Storage provider and the
authoritative storage reservation/object ledger; it does not authorize bucket
creation, production network access, customer-file copying, worker activation, or
deployment. The private `madar-data-immutable` bucket must be separately provisioned
and verified before any later activation.

The mirrored SQL, manifest, compatibility bridge, checksum validator, disposable
rehearsal, and two-process loopback fixture are protected release artifacts. New
schema154 incremental history and checkpoint versions fail closed unless provider
identity, byte size, SHA-256, and verification time are durable. Existing local
objects remain readable and unchanged. Accounting release must succeed before an
unreferenced provider object may be physically removed; referenced history and
published versions remain protected.

## Unselected schema153 background-checkpoint candidate

The additive152→153 background-checkpoint candidate is not selected by the active
release and grants no automatic deployment or worker-start authority. Its manifest,
bridge, mirrored SQL, validator, exact152 precondition, lease/fencing RPCs, bounded
retry behavior, and disposable rehearsal are part of the protected release contract.
The provided worker is one-shot only; any scheduler, service unit, Compose process,
or production activation requires a separately reviewed release change. Do not
bypass ambiguous storage evidence or publish a checkpoint without the current lease.

## Unselected incremental-ingestion candidate151→152

The mirrored schema152 candidate, `migrations-151-152-incremental-ingestion.json`
and `schema-151-152-incremental-ingestion-bridge.json`, is checksum-pinned by
`web/scripts/incremental_ingestion_candidate.py`. It requires exact schema151 and
additively introduces stable source resources, bounded durable staging, immutable
quota-accounted change chunks, an atomic current/history/cursor commit, and sparse
analytical checkpoints bound to exact committed revisions.

Legacy spreadsheet uploads and schema151 snapshot completion remain unchanged.
Incremental reconciliation retains the schema150 lease/fence and storage-evidence
rules; referenced history objects fail closed against release. Checkpoints reconstruct
from accepted immutable history rather than mutable current rows, so later commits
cannot contaminate an older target revision. The active release descriptor is
unchanged, and this candidate grants no deployment, migration, production-data,
provider-network, OAuth, webhook, scheduler, or worker authority.

## Unselected API-source ingestion candidate150→151

The mirrored schema151 candidate, `migrations-150-151-api-source-ingestion.json`
and `schema-150-151-api-source-ingestion-bridge.json`, is checksum-pinned by
`web/scripts/api_source_ingestion_candidate.py`. It requires exact schema150,
additively admits an `api_provider` source identity with bounded provider/resource
metadata, and adds service-role-only 151 reservation and atomic completion RPCs.

Runtime code retains the schema148–150 spreadsheet behavior. The only API adapter
in this milestone is a deterministic synthetic-orders fixture, enabled only in
development/test and absent from the user-facing connector UI. It accepts no URL,
headers, credentials, OAuth material, webhook, schedule, or arbitrary network
instruction. The active release descriptor is unchanged; the candidate grants no
deployment, migration, production-data, worker, traffic, or real-provider authority.

## Unselected source-ingestion recovery candidate149→150

The mirrored schema150 candidate, `migrations-149-150-source-ingestion-recovery.json`
and `schema-149-150-source-ingestion-recovery-bridge.json`, is checksum-pinned by
`web/scripts/source_ingestion_recovery_candidate.py`. It requires exact schema149
and additively introduces renewable upload leases, fencing tokens, durable storage
reservation/object attachment, and service-role-only bounded reconciliation.

Lease expiry is only an investigation signal. A claimant rotates the fence before
examining authoritative run and storage-accounting records; it marks failure only
after reservation/accounting compensation is confirmed, and records unverifiable
outcomes as ambiguous for later inspection. Late upload requests cannot complete
after fencing, and successful dataset/version/source lineage remains atomic.

The one-shot backend command is not an HTTP endpoint and is not automatically
scheduled. This candidate remains absent from `release.json`, cannot skip schemas
147–149, and grants no deployment, migration, production-data, worker, or traffic
authority.

## Unselected source-ingestion candidate148→149

The mirrored schema149 candidate, `migrations-148-149-source-ingestions.json`
and `schema-148-149-source-ingestions-bridge.json`, is checksum-pinned by
`web/scripts/source_ingestions_candidate.py`. It requires exact source
schema148 and adds durable manual-upload ingestion runs plus service-only RPCs
that reserve an idempotent attempt and atomically complete source, dataset,
version, and run lineage.

The application continues to use the existing upload parser, quota accounting,
and private storage path. Filesystem writes remain outside PostgreSQL; a failed
metadata completion therefore uses the existing accounting release before file
deletion, while the run stores only a bounded failure code. No connector,
credential, webhook, scheduler, queue, or worker is introduced.

This candidate is source preparation only. It is absent from `release.json`,
cannot skip schemas147 or148, and grants no deployment, migration,
production-data, worker, or traffic authority.

## Unselected project data-sources candidate147→148

The mirrored schema148 candidate, `migrations-147-148-data-sources.json`
and `schema-147-148-data-sources-bridge.json`, is checksum-pinned by
`web/scripts/data_sources_candidate.py`. It requires exact source schema147,
adds tenant/project-bound source identities and nullable source lineage on the
existing dataset registry, and advances schema state only after all additive
objects and constraints are installed.

The first supported identity type is manual `spreadsheet_upload`. The candidate
does not store credentials or general-purpose connector configuration, and it
adds no OAuth flow, API connector, webhook, polling schedule, ingestion worker,
or customer-data mutation. Existing datasets remain valid with a null source.

This candidate is source preparation only. It is not selected by `release.json`,
cannot skip the governed path through schema147, and grants no deployment,
migration, production-data, worker, or traffic authority. Runtime access remains
authenticated and explicitly tenant-, project-, and creator-scoped; service-role
database access is never treated as user authorization.

## Unselected project-datasets candidate146→147

The mirrored schema147 candidate, `migrations-146-147-project-datasets.json`
and `schema-146-147-project-datasets-bridge.json`, is checksum-pinned by
`web/scripts/project_datasets_candidate.py`. It requires exact source schema146,
adds tenant/project-bound dataset identities and immutable dataset-version
metadata over the existing private storage-accounting objects, and advances the
schema state only after those additive objects and service-only creation RPC are
installed. It adds no connector, worker, scheduler, webhook, collaboration, or
customer-data mutation.

This candidate is source preparation only. It is not selected by `release.json`,
cannot skip the governed path to schema146, and grants no deployment, migration,
production-data, or traffic authority. Runtime access remains authenticated and
explicitly tenant-, project-, and uploader-scoped; the service-role client is not
treated as authorization.

## Unselected revised launch price-book candidate145→146

The mirrored schema146 candidate, `migrations-145-146-price-book.json` and
`schema-145-146-price-book-bridge.json`, is checksum-pinned by
`web/scripts/launch_price_book_candidate.py`. It requires exact source schema145, refuses to run if
`launch_2026` ever recorded a sales start, inserts the prepared `launch_2026_v2` book (Commerce USD 25;
Forms, Website and bundles unchanged), and adds a trigger that permanently prevents `launch_2026` from
opening. It opens no book for sales and mutates no tenant, subscription, payment, or access record.

This candidate is source preparation only. It is not selected by `release.json`, cannot be applied to
production schema115, and grants no deployment, migration, activation, or production-data authority.
The application catalog targets `launch_2026_v2`, so public pricing fails closed until schema146 is
present; the governed path to schema145, a verified backup, and all ordinary release gates remain
prerequisites.

## Unselected strict commercial-continuity candidate144→145

The mirrored schema145 candidate, `migrations-144-145-commercial.json` and
`schema-144-145-commercial-bridge.json`, is checksum-pinned by
`web/scripts/commercial_continuity_candidate.py`. It requires exact source schema144 and preserves
the active release descriptor, all001–144 SQL, and all production data. It derives closed-book
protection from uninterrupted confirmed paid periods at the database clock, retains half-open access
intervals, and provides only a dedicated AAL2/revision/idempotency/audit protected historical-price
exception. It creates no grace, retry-recovery, expiration job, deletion, or production mutation.

This candidate is source preparation only. It is not selected by `release.json`, cannot be applied
directly to production schema115, and grants no deployment, migration, customer-data, or traffic
authority. A governed path to schema144, a verified backup, exact candidate selection, compatible
images, and all ordinary release gates remain prerequisites to any later execution.

## Approved unselected generic Forms review candidate143→144

The separately approved mirrored144 candidate follows learning143 consecutively.
It does not execute or select Exchange142, change001–143 SQL, or change the active
main115→136 descriptor. Exact144 SQL/manifest/bridge hashes are validated by
`web/scripts/forms_review_candidate.py`; source namespace acceptance extends to144
only for those verified artifacts. Ordinary executor backup, locks and resume
rules remain unchanged. Candidate compatibility is143..144; rollback is143 only.
The normal local application remains141.

Independent E-Learning Forms keeps the only definitions, immutable versions,
answers, files and response inbox.144 adds generic decisions/history and a nullable
reference on existing domain applications; it stores no copied answers. Explicit
versioned owner binding and a configured terms field drive generic Affiliate,
Tuition or Exchange intake without hardcoded Form fields or a specialized Exchange
engine. Submission cannot grant privileges. Backend/SQL recheck authentication,
active membership, programme flags and canonical eligibility. Four verified sales
apply to Tuition only; generic Exchange requires independent active learning access.

Forms decisions call the retained privileged domain review in the same transaction
for Affiliate/Tuition. Existing domain UI dispatches linked decisions back through
Forms, preserving revision, history and atomicity. Self-approval, conflicting
revisions, revoked access and duplicate applications reject. Idempotent exact
retries do not duplicate decisions/notifications. Legacy applications and all
withdrawal accounting retain their existing authority. Applicant status endpoints
exclude internal notes and reviewer information; private file rules remain.

A new marked disposable rehearsal retains141→143 preservation/backup checks and
adds143 backup verification,144 transactional rollback, exact locked144 execution,
re-entry, generic/domain permissions and history tests. Source preparation and
isolated validation authorize no application141 upgrade, production installation,
production SQL, customer import or traffic switch.


## Unselected learning-only141→143 candidate

The approved learning-only route is now finalized as an exact source-pinned
candidate: `learning-141-143-path.json`, `migrations-141-143-learning.json`,
`schema-141-143-learning-bridge.json`, and mirrored
`143_complete_learning_capabilities.sql`. It contains exactly one transition
from141 to143 and explicitly excludes142. Migration142, all001–141 SQL, all
retained manifests, and active `release.json` remain unchanged. The incoming main release retains its reviewed115→136 bridge and selects
only migrations116–136. The learning137–143 candidates remain unselected;
the existing local application database is141.
Finalization is source authority for this candidate, not production deployment,
installation, traffic switching, or upgrading the application database.

The descriptor pins SQL, manifest and bridge digests. Every ordinary transition
remains consecutive. Source gates accept namespace001–143 only after validating
the exact learning descriptor, SQL mirrors, manifest and bridge. The executor
retains checksums, verified backup, advisory locks and forward repair; it rejects
live142 before SQL and resumes143 without executing142. Automatic orchestration
requires explicit bridge selection and its usual known-good acceptance gates.

Compatibility is141..143 with excluded version142; rollback compatibility is
exactly141. Backend readiness, runtime configuration, candidate identity and
release promotion/rollback attestations carry/enforce the exclusion. Missing or
arbitrary exclusions fail closed. `settings_available(142)` is false on the
learning143 branch, so143 never implies Exchange142 features. CLI reconciliation
accepts only the pinned143 transition, requires the141 predecessor and rejects
any142 ledger row; it never invents or repairs142. Repository identity, clean
source, stable health, execution/acceptance evidence and operator confirmation
remain mandatory for any ledger mutation.

143 extends the existing assessment engine with picture/audio choices, local
unscored speaking practice, bounded private PCM WAV exam responses, bounded
written answers, authorized human review, immutable decisions and snapshots,
pending-review finalization, optional question pools/shuffling and feedback.
Objective grading remains deterministic; no AI or subjective automated scores
are introduced. Selected recordings remain immutable assessment evidence;
retryable cleanup fences unused objects before deleting bytes and releasing
quota. CEFR configuration reuses required published graded exams with the
owner's configured passing threshold instead of a global70% requirement.

A populated disposable141 rehearsal verifies old attempts/answers/completion
preservation, complete transactional rollback, an actual schema141 dump,
locked143-only execution, excluded142 rejection and143 re-entry. Native browser
validation uses separate disposable auth/REST/storage services and original
synthetic content. None of this seeds the original academy course. See
[the implementation report](elearning-final-learning-implementation.md) for
validation evidence and any remaining acceptance limits.

## Unselected Exchange Forms candidate (schema142)

The exact checksum-pinned `migrations-115-142.json` /
`schema-114-142-bridge.json` pair retains immutable115–141 and adds mirrored142.
Both source validators accept this explicit transition and namespace001–142 only.
The retained exact115 profile selects no SQL. The active main bridge selects
only116–136; this candidate remains unselected. No production
installation, migration or deployment authority is granted; orchestration is unchanged.

142 links tenant-owned opportunities to independent E-Learning Forms and records
immutable opportunity context on Forms responses. Exchange stores only decisions
and immutable decision history, never copied answers. Approved legacy and Forms
applications both consume capacity under the opportunity lock. Historical legacy
Exchange answers/reviews remain intact; new specialized Exchange submissions reject.
Affiliate and Support workflows remain independent and unchanged. Local142 requires
explicit contract selection after a preservation-checked upgrade; production still
requires its accepted bridge, verified backup and governed upgrade.

## Unselected independent E-Learning Forms candidate (schema141)

The exact checksum-pinned `migrations-115-141.json` /
`schema-114-141-bridge.json` pair retains immutable115–140 and adds mirrored141.
Both source validators accept only this additional transition and namespace001–141.
The active main115→136 bridge selects only116–136; Forms141 remains unselected. No production
installation, migration or deployment authority is granted.

141 adds tenant-owned learning form definitions, immutable versions/responses,
private response attachment ownership, guarded lifecycle/submission/read functions,
and a tenant-checked Academy Builder form reference. Builder definitions, drafts,
submissions and specialized programme workflows remain independent. Existing Forms
capabilities, storage quotas and learning notifications are reused. Browser and
server enforce conditional visibility; historical answers reference immutable
schemas and survive lifecycle changes. Local development may explicitly select141
after a preservation-checked local upgrade. Production requires its own accepted
bridge/backup/governed upgrade; orchestration is unchanged.

The current unselected Academy owner candidate is the exact checksum-pinned
`migrations-115-140.json` / `schema-114-140-bridge.json` pair. Both validators
verify namespace001–140 and immutable history. The retained exact115 profile selects no SQL. Main’s active115→136 bridge
selects only116–136; the owner candidate remains unselected. See the schema140 candidate sections
in `production-release-policy.md` and
`automated-database-migration-architecture.md` for the owner-tool expansion.
This candidate grants no production deployment or mutation authority.

The active candidate descriptor now selects the existing schema115..136 bridge
and checksum-pinned migrations116..136. The former exact115/no-SQL descriptor
is retained as `schema-115-local.json`; historical SQL and manifests remain
unchanged. This is upgrade preparation, not production authorization. Production
continues serving its accepted schema115 application until exact-image acceptance,
current-data application/migration rehearsal, forward-repair validation and one
complete governed operation have passed and received explicit approval.

Completed-NORMAL boot repair is separately hash-approved and changes no
application image, production checkout, customer database or automatic-deploy
timer. Its source-role attestation preserves legitimate distinct controller and
application SHAs, while live upgrade readiness remains mandatory. Source fixes
do not update old frozen boot actors or permit consumed-authorization replay.

An additional unselected source115-to-136 bridge and migrations116..136 manifest
preserve the exact historical SQL/checksums without changing the active115
no-migration release. Selection requires separately accepted compatible images,
current-data rehearsal and governed production approval. Default-DNS container
specification comparison tolerates only Docker's null/empty-list encoding change;
it grants no authority and does not silently update installed frozen boot code.

The referral candidate retains an additional checksum-pinned, unselected
`migrations-115-136.json` / `schema-114-136-bridge.json` pair. The 115..135
manifest and its pinned history remain unchanged. `check_migrations.py` accepts
only the exact additional 136 artifact and verifies the old entries are
identical; `check_forward_release.py` also validates this additional pinned
candidate and exact namespace 001..136. Unknown future migrations still fail. The historical schema115 profile
still selects no SQL; the new upgrade candidate selects only116..136. Migration136 requires schema135 and adds tenant-private
referrals plus monetary reward/reversal records tied atomically to a verified
first learning purchase. Runtime endpoints and enabling referrals fail closed
before schema136. Historical rewards keep their amount/currency; local payment
simulation is displayed separately. Payouts, redemption, payment-provider
activation and production migration are outside this candidate. A separately
accepted bridge, backup and approved upgrade are required before production use.


Previous local-Supabase integration profile: **schema115 only**, migration class
`none`, migration policy `none`, now retained as `schema-115-local.json`. Retained bridge
examples below describe reviewed migration history/future work and authorize no
SQL for this profile. Main's 116..135 artifacts remain checksum-verified; features
requiring those schemas retain their existing unavailable/upgrade-required gates.
Production installation, promotion and migration require separate approval.

**Audience:** AI coding agents and engineers preparing changes that will eventually merge into `main`.

**Purpose:** Make changes that fit Madar's existing production release contract so that, after a normal merge to `main`, the server can either deploy the new release automatically or clearly require the one governed control-plane action that is intentionally not automatic.

> The implementation is authoritative. If this document and the code disagree, stop and investigate. Never weaken a release gate merely to make a merge deploy.

---

## 1. Read this before touching release-sensitive code

Before changing any of the following, read this document and the existing architecture documents listed at the end:

- backend or frontend code intended for production
- Docker/Compose
- database or Supabase migrations
- release metadata
- `web/scripts`
- anything under `web/deployment`
- backup / restore helpers
- production runtime paths
- control-plane logic
- a PR targeting `main`

The goal is not "make `main` deploy at any cost." The goal is:

1. produce a candidate that satisfies the release contract,
2. preserve immutable production history,
3. let ordinary auto-deploy handle ordinary application changes,
4. use the governed privileged upgrade only when protected control-plane files actually changed,
5. never repair production by hand to compensate for a bad merge.

---

# 2. Production architecture in one page

## Canonical production locations

```text
Production Git checkout:
  /srv/madar/production

Installed control plane:
  /opt/madar/control-plane/deployment

Production environment:
  /etc/madar/production.env

Release state:
  /var/lib/madar/releases

Persistent application storage:
  /var/lib/madar/storage

Stable proxy state:
  /var/lib/madar/proxy

Control-plane audit / staging / backups:
  /var/lib/madar-control-plane
```

The tracked canonical path contract is:

```text
web/deployment/production-paths.conf
```

Do not introduce a second production path convention.

## Production identities

There are intentionally two privilege domains:

### Root-owned control-plane authority

Root owns installation, privileged upgrade orchestration, protected staging, audit state, and control-plane backups.

The operator entrypoint is:

```text
/usr/local/sbin/madar-control-plane-upgrade
```

### `madar` runtime mutation authority

Actual production release mutation runs as:

```text
user:  madar
group: madar
```

The auto-deploy systemd service is `User=madar`, `Group=madar`.

Installed runtime-mutating entrypoints must not be run as root:

```text
madar-auto-deploy
madar-production-deploy
madar-release-deploy
madar-switch-traffic
madar-migrate
```

The installed copies enforce this identity. Do not remove or bypass that guard.

---

# 3. What happens after `main` changes

The timer checks `origin/main` approximately every two minutes after the prior cycle becomes inactive.

Normal entrypoint:

```text
/opt/madar/control-plane/deployment/bin/madar-auto-deploy
```

High-level decision flow:

```text
fetch origin/main
        |
        v
candidate = exact origin/main SHA
        |
        v
control-plane guard passes?
        |
   +----+----+
   |         |
  no        yes
   |         |
   |         v
   |   release state initialized?
   |         |
   |         v
   |   compare candidate to known-good
   |         |
   |         +--> same SHA
   |         |      run idempotent post-known-good migration coordinator
   |         |
   |         +--> candidate behind known-good
   |         |      no action
   |         |
   |         +--> history diverged
   |         |      reject
   |         |
   |         +--> no watched runtime path changed
   |         |      finish any pending known-good migration,
   |         |      then fast-forward checkout only
   |         |
   |         +--> candidate still suppressed after a failure
   |         |      timer path: quiet no-op
   |         |
   |         +--> eligible runtime change
   |                immutable blue/green release deployment
   |
   +--> protected control-plane change:
         ordinary auto-deploy stops intentionally and asks for
         `sudo madar-control-plane-upgrade <exact-sha>`
```

Auto-deploy must never be changed into "always pull and restart."

---

# 4. Watched runtime paths

A change under any of these paths is considered runtime-relevant:

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

If **none** of those paths changed between the active known-good SHA and the new `main`, auto-deploy may advance the production checkout without rebuilding/redeploying the application, after giving any pending migration coordinator a chance to finish.

This is why this document belongs under `docs/`, not under `web/deployment/`.

---

# 5. Protected control-plane paths

These paths are protected and cannot silently self-update through ordinary auto-deploy:

```text
web/deployment

web/scripts/madar_alert_hook.sh
web/scripts/backup_madar.sh
web/scripts/verify_backup.sh
web/scripts/backup_support.py
web/scripts/verify_latest_backup.sh
web/scripts/replicate_latest_node1.py
web/scripts/replicate_latest_offhost.sh
web/scripts/replicate_backup_offhost.sh
web/scripts/restore_madar.sh
web/scripts/rehearse_backup.py
```

If a candidate changes any protected path, ordinary auto-deploy must stop.

That is not a deployment bug.

The correct flow is:

```bash
sudo madar-control-plane-upgrade --dry-run <exact-40-character-origin-main-sha>
sudo madar-control-plane-upgrade <exact-40-character-origin-main-sha>
```

The privileged upgrader validates the exact SHA, canonical Git remote, forward ancestry, clean production checkout, protected-tree safety, backup/timer state, and the installed controller before publication.

Never weaken `madar-control-plane-guard` simply to make a protected change deploy automatically.

---

# 6. Branch and Git history requirements

A future merge into `main` must preserve these properties.

## Required

- `origin/main` must be canonical.
- The candidate must be the exact commit currently at `origin/main`.
- Production must be able to fetch that commit.
- The candidate must be a forward descendant of the serving known-good release.
- The production checkout must remain clean.
- Do not rewrite already-deployed `main` history.

## Do not

- force-push `main` behind or away from the deployed known-good lineage;
- merge unrelated history;
- create a release that only works if production performs a local manual commit;
- make production contain untracked repair files;
- manually `git pull` or `git reset --hard` production to make a release "match";
- change the configured canonical remote as part of a normal product feature.

If `known_good` is not an ancestor of the new main candidate, auto-deploy correctly rejects it.

---

# 7. Ordinary application change contract

For backend/frontend/runtime changes that do **not** modify protected control-plane files:

1. Start from current `origin/main`.
2. Keep the commit history forward-only.
3. Keep production paths and deployment contracts unchanged unless the change actually needs them.
4. Run the applicable CI-equivalent backend and frontend checks.
5. Make sure the candidate can run on the currently serving schema.
6. If no DB transition is required, do not invent a migration.
7. Merge to `main`.
8. Let the server discover the new SHA through its timer.
9. Verify the release through health/version and durable release state; do not manually advance the production checkout.

The immutable release controller will build or reuse exact-SHA backend/frontend artifacts, validate the inactive slot, promote traffic only after readiness, record known-good state, and preserve a compatible passive fallback.

---

# 8. Database migration contract

Migrations are production history. Treat applied migration files as immutable.

## Never edit an applied migration

Do not modify an older migration to make a new feature work.

Create the next migration instead.

The database and Supabase trees must remain mirrored:

```text
web/database/migrations/
web/supabase/migrations/
```

For modern migrations, the filename and bytes must match between both trees.

## Modern migration shape

For migration `N`, the current validator requires the transition to be exactly:

```text
N-1 -> N
```

The migration must:

- start with `BEGIN;`
- end with `COMMIT;`
- lock the schema-state row `FOR UPDATE`
- use `public.application_schema_state`
- target `contract_key = 'core'`
- use the typed `v_schema_version` variable
- contain exactly one source-schema guard
- contain exactly one transition to schema `N`
- keep the typed declaration, core schema-state query, row lock, and predecessor
  guard together in one executable `DO` block
- for the guard-first series from migration117 onward, place that block before any
  schema-changing DDL

Comments are removed before validation. Do not add fake strings, comments, or
unrelated `FOR UPDATE` statements merely to satisfy validators.

## When adding a new production schema transition

Update all release artifacts that describe the active bridge, including the pieces that are applicable at that time:

```text
web/deployment/releases/release.json
web/deployment/releases/migrations-*.json
web/scripts/check_forward_release.py
```

Also preserve checksum pins for already-applied production history.

The active migration manifest must be:

- ordered,
- contiguous,
- checksum-pinned,
- source-schema correct,
- final-target correct,
- composed only of migration classes allowed by the automatic executor.

Current automatic policy name:

```text
automatic-after-known-good-backup-first-forward-repair
```

Do not rename or approximate this policy string without intentionally changing the implementation and its tests.

---

# 9. Promotion and migration are separate phases

This distinction is critical.

A bridge release is promoted and becomes `known_good` **before** an opted-in database migration runs.

Traffic promotion does not directly execute or reverse SQL.

Simplified sequence:

```text
candidate app built
    ->
inactive slot validated
    ->
traffic promoted
    ->
candidate recorded known_good on source schema
    ->
verified source-schema-bound backup created
    ->
forward migration manifest executed
    ->
active runtime refreshed / revalidated
    ->
known_good observed schema advanced
```

If schema advancement begins, recovery is forward-repair oriented. Do not invent reverse SQL or automatically switch traffic to a schema-incompatible retained release.

---

# 10. Release metadata must match reality

`web/deployment/releases/release.json` is part of the production contract.

Its schema block describes:

```text
compatible_min
compatible_max
target
migration_class
rollback_compatible_min
rollback_compatible_max
```

Do not blindly copy the previous values into a new schema-bearing release.

For every candidate ask:

- What schema is production serving before this release?
- Can the candidate safely run on that source schema?
- What target schema will the reviewed migration sequence reach?
- Is the full source-to-target range inside candidate compatibility?
- Is the retained release actually safe after schema advancement?
- Does the rollback bound reflect reality?

A release descriptor that lies about compatibility is a release bug even if tests are green.

---

# 11. Failed candidate suppression

A failed candidate is recorded under durable release state with a retry deadline.

Ordinary timer behavior while still suppressed:

```text
log suppression
exit 0
do not redeploy
```

This avoids turning every timer tick into an alert.

During a governed control-plane upgrade, the same suppression is intentionally reported as a distinct temporary failure so the privileged coordinator does not mistake a no-op for deployment success.

Current controlled result:

```text
exit 75
candidate_retry_suppressed
```

Do not collapse controlled suppression back into generic success.

Do not use `--manual-retry` in automation to force a known-bad SHA.

---

# 12. Control-plane upgrade behavior

A protected change uses the root-owned exact-SHA upgrade transaction.

Important properties:

- exact 40-character SHA only;
- SHA must be current `origin/main`;
- canonical remote must match;
- candidate must descend from deployed production;
- production checkout must be clean;
- the timer is quiesced before apply;
- backup/verification/replication services must not be running;
- candidate is staged under root-owned upgrade state;
- protected tree is syntax/ownership/symlink/digest checked;
- installed controller is published atomically;
- actual deployment cycle still runs as `madar`;
- authorization is one-time and passed through systemd `LoadCredential`;
- serving state is attested after deployment;
- the same SHA is run a second time to prove idempotence;
- automation is restored only after successful attestation.

The privileged controller is an orchestrator. It does not make root the application deployment user.

---

# 13. Backup timer rules

Do not "fix" the following distinction.

## Control-plane installer dry run

Scheduled backup timers may remain active.

A currently running backup / verification / replication service blocks the dry run.

## Control-plane installer apply

A running backup service blocks apply.

An active backup timer also blocks apply because the privileged coordinator must quiesce timers before operational files change.

Matrix:

```text
                         dry run     apply
backup timer active      allowed     blocked
backup service active    blocked     blocked
```

The installer itself must not silently stop the timers as a way to make preflight pass.

---

# 14. Runtime identity and ownership rules

Production mutation state under `/var/lib/madar/releases` belongs to the canonical `madar` runtime identity.

Do not invoke installed production mutators with `sudo`.

Bad:

```bash
sudo /opt/madar/control-plane/deployment/bin/madar-release-deploy ...
sudo /opt/madar/control-plane/deployment/bin/madar-switch-traffic ...
sudo /opt/madar/control-plane/deployment/bin/madar-migrate ...
```

The privileged upgrader may itself be invoked with `sudo`, but when it needs to perform an application deployment it creates a hardened transient systemd unit with:

```text
--uid=madar
--gid=madar
NoNewPrivileges=yes
```

This boundary exists specifically to prevent root-owned contamination of release state.

Do not remove it.

---

# 15. Failure semantics are phase-aware

Do not write generic cleanup code that blindly restores old traffic, old controller files, or timers.

## Before controller installation

Production application/controller are unchanged.

If automation was quiesced, the old state must be re-attested before restoring the timer.

## Controller installed, application not promoted

Fail closed:

```text
timer disabled
interlock retained
manual diagnosis required
```

## Application promoted

Promotion is a durable point of no return for the transaction.

Failure after promotion uses:

```text
post_promotion_forward_repair_timer_disabled
```

Do not automatically roll traffic back after schema or durable known-good advancement.

## Preinstalled controller-ahead bridge

If the approved control plane is already installed but the old application is still serving, a pre-promotion failure leaves:

```text
old application serving
approved controller retained
timer disabled
interlock retained
```

---

# 16. Merge classification checklist

Before opening or merging a PR to `main`, classify the change.

| Change type | Expected path |
| --- | --- |
| `docs/**` only | checkout fast-forward; no runtime deployment |
| ordinary backend/frontend change | normal auto-deploy |
| Docker/runtime change | normal auto-deploy after full release validation |
| DB schema change | normal bridge deployment + post-known-good migration contract |
| `web/deployment/**` change | governed control-plane upgrade required |
| protected backup/restore helper change | governed control-plane upgrade required |
| rewritten/divergent main history | reject; fix Git history, never production |
| incompatible release metadata/schema | reject; fix candidate |
| currently suppressed failed SHA | wait/diagnose; do not bypass automatically |

A protected change requiring `madar-control-plane-upgrade` is expected behavior, not a failed auto-deploy design.

---

# 17. Required pre-merge checks

Use the repository CI/workflows as the source of truth. Do not invent a shortened test subset and call it equivalent.

At minimum, run every applicable release gate:

```bash
python3 web/scripts/check_dependency_locks.py
python3 web/scripts/check_migrations.py
python3 web/scripts/check_migration_transitions.py
python3 web/scripts/check_forward_release.py
python3 web/scripts/check_secret_hygiene.py
```

Then run the CI-equivalent backend suite and the frontend suite/build defined by the repository workflows.

Typical frontend checks:

```bash
cd web/frontend
npm ci
npm run lint
npm test
npm run build
npm audit --omit=dev --audit-level=high
```

For backend validation, follow the current `.github/workflows/backend-check.yml` and the hermetic no-external-network test path. Do not replace it with a smaller local-only test command.

For deployment/control-plane work also run the focused suites covering:

```text
test_control_plane_upgrade.py
test_monorepo_deployment.py
test_automatic_migration_control_plane.py
test_release_*.py
test_schema_compatibility_control_plane.py
```

If the release policy or deployment implementation changes, update the relevant architecture documentation in the same PR.

---

# 18. Agent rules for changes targeting `main`

An AI coding agent preparing a merge should treat the following as hard constraints.

## MUST

- inspect current `origin/main` before starting;
- preserve forward ancestry from deployed known-good;
- determine whether protected control-plane paths changed;
- inspect the current live/declared schema contract before changing release metadata;
- create new migrations instead of editing applied ones;
- mirror migration files between database and Supabase trees;
- update migration/release validators when the active production bridge changes;
- keep runtime mutation under the `madar` identity;
- run applicable CI-equivalent checks;
- report any release gate it cannot execute;
- leave production untouched during development/PR preparation.

## MUST NOT

- bypass `madar-control-plane-guard`;
- disable compatibility checks to make a candidate deploy;
- run installed production mutators as root;
- edit `/var/lib/madar/releases/*.json` manually;
- edit `worker-ownership.json` manually;
- manually switch blue/green traffic;
- manually apply production migration SQL;
- manually `git pull` or reset `/srv/madar/production`;
- use `--manual-retry` from automation;
- erase failed-release evidence to force a retry;
- enable auto-deploy after a failed governed transaction without understanding the recorded failure semantics;
- treat a single HTTP 200 as proof of release acceptance.

---

# 19. Post-merge verification

For an ordinary eligible application release, verify **state**, not just process exit.

Expected high-level evidence:

```text
production Git HEAD == candidate SHA
known_good_release.sha == candidate SHA
active_slot is blue or green
known_good_release.slot == active_slot
in_progress_release == null
rollback_failure == null
stable /health/version reports candidate SHA
public /health/version reports candidate SHA
readiness ready == true
backup_freshness == ok
worker authority matches active candidate
production worktree clean
```

For a protected control-plane release, also verify:

```text
CONTROL_PLANE_SOURCE_SHA == candidate SHA
same-SHA validation passed
upgrade audit status == success
interlock removed
timer restored to its pre-transaction state
```

Do not declare success while any of those authoritative identities disagree.

---

# 20. Common reasons a future merge will be rejected

If auto-deploy does not accept a new main, inspect the candidate before touching production.

Typical causes:

```text
production checkout dirty
origin/main diverged from known-good
candidate changed protected control-plane paths
installed controller provenance differs
candidate release metadata incompatible with live schema
migration tree / checksum / transition contract invalid
candidate readiness failed
candidate image identity changed unexpectedly
failed SHA still inside suppression window
migration forward-repair state not terminal
upgrade interlock still present
backup service currently running during a protected upgrade
```

The correct response is to diagnose the candidate or recorded transaction state.

The wrong response is to weaken the server until it accepts the merge.

---

# 21. Current remediation guarantees added in September 2026

The following hardening was added after real production recovery work and must be preserved.

## Runtime identity hardening

Installed release mutators reject root/incorrect runtime identity before production mutation.

## Controlled suppression semantics

A suppressed SHA remains a quiet timer no-op, but governed deployment reports distinct temporary failure so serving attestation cannot run against an undeployed candidate.

## Dry-run / backup-timer contract

Read-only installer dry run tolerates scheduled backup timers while still refusing to race a running backup operation.

## Failure-state integration coverage

The control-plane test suite exercises failures before quiescence, before installation, after controller installation, during deployment, after promotion, during same-SHA verification, and during timer restoration.

These are safety contracts, not temporary workarounds.

---

# 22. Repository documents that remain authoritative references

Read these together with this merge contract:

```text
AGENTS.md
docs/production-release-policy.md
docs/automated-database-migration-architecture.md
docs/control-plane-upgrade-architecture.md
```

Important implementation files:

```text
web/deployment/bin/madar-auto-deploy
web/deployment/bin/madar-control-plane-guard
web/deployment/bin/madar-control-plane-upgrade
web/deployment/bin/madar-install-control-plane
web/deployment/bin/madar-production-deploy
web/deployment/bin/madar-release-deploy
web/deployment/bin/madar-migrate
web/deployment/bin/madar-switch-traffic

web/deployment/lib/control_plane_upgrade.py
web/deployment/lib/control_plane_upgrade_authorization.py
web/deployment/lib/release_deployer.py
web/deployment/lib/migration_executor.py
web/deployment/lib/runtime_authority.py

web/deployment/releases/release.json
web/deployment/releases/migrations-*.json
web/deployment/production-paths.conf

web/scripts/check_migrations.py
web/scripts/check_migration_transitions.py
web/scripts/check_forward_release.py
web/scripts/check_secret_hygiene.py
```

---

# 23. Short version for an AI agent

Before merging to `main`:

1. Fetch current `origin/main`.
2. Keep history forward-only from deployed known-good.
3. Classify whether the change touches protected control-plane paths.
4. If schema changes, create a new immutable migration and update the active release contract/manifest/validator.
5. Run all applicable CI-equivalent release checks.
6. Do not modify production manually.
7. Merge only a clean, reviewed, exact candidate.
8. Ordinary runtime changes are handled by auto-deploy.
9. Protected control-plane changes intentionally require:
   `sudo madar-control-plane-upgrade <exact-main-sha>`.
10. If a gate rejects the candidate, fix the candidate or the declared release contract. Never weaken production to accept it.

That is the system.


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
