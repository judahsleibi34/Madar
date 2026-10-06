# Madar Auto-Deploy Merge Contract

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

Do not add fake strings/comments merely to satisfy validators.

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
the unchanged 115/116 migration manifest. The preceding bridge descriptor is
retained as `schema-114-116-bridge.json` for migration regression tests; it is
not the selected release contract. Neither schema114 nor schema116 passes this
candidate's compatibility gate. Any future schema transition needs its own
reviewed bridge contract. No automatic migration was invoked in rehearsal.

The installed controller must agree with this exact candidate contract before
an approved deployment. That remains a governed production change, not part of
pre-cutover engineering. Existing provenance, backup, deployment lock, exact-main,
readiness, traffic, worker and observation gates remain unchanged.
