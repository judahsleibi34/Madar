# R0.2 staging and release-readiness record

Date: 2026-09-14

Historical record: R0.2 targeted schema 097 with `migrations-097.json`.
Its commands and results describe that release, not the current candidate.
The operator-reported current production source and CLI ledger are both 096;
097, 098, and 099 objects are absent. The current candidate targets 099 with
pending sequence 097, 098, 099 in `migrations-097-099.json`.
No production access was performed to prepare this correction.

Decision: **NOT READY**. No production mutation was performed. The linked
Supabase project was not used as a staging substitute.

## Blocking evidence

- Repository HEAD is d12926cc076d4726f1675ac31bb1fa4b70370ab6, but
  release-critical source, migrations, manifests, policy, and tests remain
  modified or untracked. It is not an immutable candidate.
- The secret-safe validator reports missing production database, URL/origin,
  storage, cookie/CSRF, and MFA settings.
- No E2E isolation attestation, base URL, isolated database identity,
  clean-migration attestation, delivery-disable declaration, or
  PUBLISHED_FORM_PATH is configured. No approved staging target is available.

## Gate matrix

| Gate | Status | Evidence |
| --- | --- | --- |
| Immutable candidate SHA | BLOCKED | Dirty/untracked release-critical worktree |
| Production config | BLOCKED | Validator has missing fields |
| Linux suite | PASS | R0.2 rebuilt image: 1,307 tests; no external attempts/sites |
| Images | PASS | R0.1 builds and nginx validation |
| Migration validators | PASS | 97/97 parity and transitions |
| Staging | BLOCKED | Isolation and endpoint attestations absent |
| Backup | BLOCKED | No schema-096 staging source or approved destination |
| Restore rehearsal | BLOCKED | No disposable restore target |
| 096-to-097 staging migration | BLOCKED | No staging database |
| Ledger reconciliation staging | BLOCKED | No staging project; local guards pass 8/8 |
| Desktop browser QA | BLOCKED | No target or published form |
| Mobile QA | BLOCKED | No browser target |
| EN QA | BLOCKED | No browser target |
| AR/RTL QA | BLOCKED | No browser target; source tests are not visual evidence |
| Transaction smoke | BLOCKED | No staging tenant/database |
| Delivery smoke | BLOCKED | No staging tenant/database |
| Order lifecycle | BLOCKED | No staging tenant/database |
| Inventory restoration | BLOCKED | No staging tenant/database |
| Loyalty E2E | BLOCKED | No verified staging customer/database |
| SEO runtime QA | BLOCKED | No staging runtime |
| Analytics runtime QA | BLOCKED | No staging browser; focused tests pass |
| Tenant isolation browser gate | BLOCKED | No two-tenant fixture; backend tests pass |
| Security | PASS | Secret/lock/audit/dependency checks; backend 60/60, ledger 8/8, frontend 27/27 |
| Rollback/failure runbook | PASS | Defined below |
| Production runbook | PASS | Defined below; not executed |

## Controlled production runbook (do not execute during R0.2)

Commands use existing repository interfaces. Angle-bracket values require
reviewed operator evidence and must never be guessed.

1. Freeze automation and record its prior state:

       sudo systemctl disable --now madar-auto-deploy.timer
       sudo systemctl stop madar-auto-deploy.service

2. Establish the reviewed immutable candidate:

       git -C /srv/madar/production status --porcelain --untracked-files=normal
       git -C /srv/madar/production fetch origin main
       git -C /srv/madar/production rev-parse origin/main

   Stop unless the checkout is clean and origin/main is the approved full SHA.

3. From the exact checkout, validate configuration and source:

       cd /srv/madar/production/web
       python3 scripts/check_production_config.py --production-env /etc/madar/production.env --e2e-env <approved-isolated-e2e-env>
       python3 scripts/check_dependency_locks.py
       python3 scripts/check_migrations.py
       python3 scripts/check_migration_transitions.py
       python3 scripts/check_secret_hygiene.py

4. With read-only database and CLI inspection, confirm
   application_schema_state=096, the Supabase ledger ends at 096, migration 097
   is the only pending transition, and migrations-097.json pins its SHA-256.

5. Confirm /etc/madar/backup.env, /etc/madar/production.env,
   /var/lib/madar/storage, /var/lib/madar/backups, and the off-host mount satisfy
   the protected path contract. Manual rehearsal interfaces are:

       sudo --preserve-env /opt/madar/control-plane/deployment/scripts/backup_madar.sh
       sudo --preserve-env /opt/madar/control-plane/deployment/scripts/verify_backup.sh <backup-directory>
       sudo --preserve-env /opt/madar/control-plane/deployment/scripts/replicate_backup_offhost.sh <backup-directory>

   Do not substitute a manual backup for the coordinator-owned production
   backup. The coordinator creates a fresh candidate-SHA/schema-096-bound
   backup and verifies manifest, checksums, and freshness before the DB lock.

6. Execute the existing production wrapper once:

       sudo /opt/madar/control-plane/deployment/bin/madar-production-deploy

   It guards origin/main, promotes the schema-96 bridge, validates candidate and
   stable health, switches traffic, fast-forwards the checkout, then separately
   invokes madar-release-deploy with --automatic-migrate. The coordinator
   creates/verifies the backup, locks the DB, applies checksum-pinned 097,
   verifies schema, refreshes workers, and repeats health checks. Never run
   supabase db push.

7. Inspect /var/lib/madar/releases/state.json and
   /var/lib/madar/releases/migrations/<sha>/automation.json and execution.json.
   Require exact SHA/slot/schema 097, post_migration_workers_refreshed,
   completed automation/execution, and the pinned checksum. Verify:

       curl --fail --silent http://127.0.0.1:8001/health/version
       curl --fail --silent http://127.0.0.1:8001/health/ready
       curl --fail --silent http://127.0.0.1:3000/

8. Run the reviewed commerce smoke checklist on safe operator fixtures. Stop
   before ledger repair unless checkout, inventory, order, delivery, COD, and
   confirmation checks are green.

9. Dry-run and then execute guarded ledger-only reconciliation:

       cd /srv/madar/production
       python3 web/deployment/lib/supabase_ledger_reconciliation.py --migration-version 097 --release-sha <approved-full-sha> --repository-root /srv/madar/production --state-root /var/lib/madar/releases --dry-run
       python3 web/deployment/lib/supabase_ledger_reconciliation.py --migration-version 097 --release-sha <approved-full-sha> --repository-root /srv/madar/production --state-root /var/lib/madar/releases --confirm 097:<pinned-sha256>

   Verify the ledger contains 097 and retain
   /var/lib/madar/releases/ledger-reconciliations/097.json. Repeat must report
   already_reconciled.

10. Monitor application/proxy logs and health for uncaught exceptions,
    database/migration/auth/tenant errors, retry storms, analytics errors, and
    confirmation-token errors. Restore the timer to its recorded pre-freeze
    state only after formal sign-off.

## Failure runbook

### A. Failure before 097 commits

Stop and preserve logs/state. The controller may retain or restore the prior
traffic target under its pre-commit rollback state machine. Do not repair the
ledger or claim a schema transition. Correct the cause and use the reviewed
retry path without bypassing backup or health gates.

### B. Migration 097 fails and rolls back

Keep the healthy schema-96 bridge serving. Preserve backup and state. Diagnose
and retry only with the same SHA, manifest, checksum, and backup through the
coordinator/manual-retry contract. Do not run reverse SQL or supabase db push.

### C. Schema 097 commits but application health fails

This is forward-repair-only; schema 96 is no longer an automatic rollback
target. Do not switch to an incompatible retained release or restore
automatically. Repair forward, rerun exact-SHA validation and worker refresh,
and reconcile the ledger only after stable health succeeds.

### D. Ledger reconciliation fails after healthy schema 097

Leave schema and business data untouched. Diagnose the project/SHA/checksum/
state/health/ledger guard and rerun the idempotent reconciler after correction.
Never replay migration SQL merely to populate the ledger.

### E. Post-release functional regression

Classify compatibility first. After schema 097, prefer a compatible forward
application repair. Explicit restore is a separately reviewed operator
disaster-recovery action using restore_madar.sh and a verified backup; it is
never automatic and must first be rehearsed on an isolated target.

## Evidence still required

An approved clean candidate, complete production config, isolated staging,
real schema-096 backup and restore, timed 096-to-097 coordinator exercise,
staging-only ledger repair, desktop/mobile EN and AR/RTL visual QA, commerce and
loyalty smokes, runtime SEO/analytics checks, two-tenant browser isolation,
performance timings, and staging log review.
