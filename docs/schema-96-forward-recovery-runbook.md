# Schema 96 forward recovery runbook

Status: prepared for independent production review; do not execute without a
separate production authorization.

## Purpose

This procedure replaces a schema-93-era serving and fallback binary with one
exact candidate independently proven at the already-live schema 96. It never
changes the database schema, applies migration 97/98/99, edits release state,
or manually changes the proxy.

## Preconditions

Record the exact approved merged `origin/main` SHA as `RECOVERY_SHA`. Require:

- production HEAD and durable known-good SHA are the same old serving release;
- stable and active `/health/version` identify that SHA and max schema 93;
- the live database reports schema 96;
- the proxy identifies the durable active slot;
- no deployment, migration, backup, or rollback operation is in progress;
- auto-deploy is disabled/inactive and its service is inactive;
- current degradation is schema incompatibility plus, at most, the historical
  notification readiness classification;
- a fresh fully verified format-3 local backup exists at schema 96;
- the exact backup has a verified copy on Node 1 at
  `/srv/data2/madar-backups` on the attested `/dev/sdc1` ext4 filesystem;
- schema-96 clone, backend, frontend, browser, worker, RLS/grant, and dependency
  checks passed for `RECOVERY_SHA` within seven days;
- the candidate recovery contract has min=max=target=rollback min=rollback
  max=96, migration class `none`, and no migration manifest;
- an independent reviewer approved the candidate SHA and evidence.

Abort if any identity, SHA, schema, timer, backup, proxy, health, or evidence
value differs. Never reinterpret a failed check.

## First-use controller bootstrap

Skip this section only when installed controller provenance already equals
`RECOVERY_SHA` and the installed launcher supports `--recover-current-schema`.
The bootstrap changes controller files only. It must use the established
root-protected exact-SHA staging procedure described in
`control-plane-upgrade-architecture.md`; do not run candidate installer source
from the writable development checkout.

From a root-protected, detached, clean candidate tree whose HEAD is exactly
`RECOVERY_SHA`, first run the installer dry run with a new absent backup path:

```bash
sudo -n <ROOT_PROTECTED_CANDIDATE>/web/deployment/bin/madar-install-control-plane \
  --backup-dir /var/lib/madar-control-plane/backups/pre-<SHA12>-<UTC>
```

Expected output ends with `control-plane installer dry-run passed`. Verify the
candidate did not change, the timer stayed disabled, and production traffic and
schema stayed unchanged. Then run the same exact source and same empty backup
path with `--apply`:

```bash
sudo -n <ROOT_PROTECTED_CANDIDATE>/web/deployment/bin/madar-install-control-plane \
  --apply --backup-dir /var/lib/madar-control-plane/backups/pre-<SHA12>-<UTC>
```

Expected output identifies the immutable `/opt/madar/control-plane/deployment`
installation and states that auto-deploy remains stopped. Abort if installation
or provenance attestation fails. Do not restore controller files ad hoc; retain
the controller backup and diagnose.

## Protected rehearsal attestation

Place the reviewed JSON at an absolute root-protected path such as:

```text
/var/lib/madar-control-plane/rehearsals/<RECOVERY_SHA>.json
```

It must be root-owned mode 0600, status `passed`, schema `96`, candidate SHA
`RECOVERY_SHA`, a current timezone-aware `created_at`, and every check required
by `validate_rehearsal_attestation()` set to `passed`. The file contains no
credentials, customer rows, hostnames identifying customers, or provider
payloads.

## Exact recovery command

Run only after a final read-only re-attestation:

```bash
sudo -n /usr/local/sbin/madar-control-plane-upgrade \
  --recover-current-schema \
  --rehearsal-attestation /var/lib/madar-control-plane/rehearsals/<RECOVERY_SHA>.json \
  <RECOVERY_SHA>
```

Expected phases are current schema recovery preflight, candidate resolution,
attestation validation, recovery contract validation, protected controller
attestation/install, controlled recovery deployment, serving attestation,
same-SHA idempotence, and cleanup. Expected final output is `SCHEMA RECOVERY:
SUCCESS`, schema `96 -> 96`, migration result `not_requested`, and auto-deploy
still disabled because its captured state was disabled.

## State transitions

1. Old schema-incompatible active slot remains routed.
2. Candidate images are built immutably for the exact SHA.
3. Inactive candidate starts without notification/calendar/deletion consumers.
4. Candidate core health, schema, Auth, Storage, Redis, and frontend pass.
5. Old queue consumers stop; candidate consumers start and pass.
6. State, schema, backup, proxy, and candidate are re-attested.
7. Existing governed switch atomically routes to the candidate.
8. Post-switch health passes at schema 96.
9. Former slot is recreated from the same candidate with consumers inactive.
10. Durable state records the active bridge, compatible fallback, and old
    incompatible release as forensic history.
11. A second exact-SHA invocation proves byte-idempotence.

## Abort conditions

Before the switch, any failure stops/removes the candidate, restores old
consumers if they were stopped, leaves old traffic unchanged, and records the
failure. After the switch, the old binary is never selected because it cannot
serve schema 96. The timer remains disabled and the checkpoint requires
forward repair.

Abort on stale or missing backup, missing Node 1 proof, schema other than 96,
candidate contract drift, migration request, dirty checkout, changed proxy,
changed durable state, image mismatch, worker overlap, health failure, missing
rehearsal check, stale SHA, or any unexpected readiness degradation.

## Recovery after interruption

Rerun the exact same command and SHA after diagnosing the interruption. If the
old slot is still routed, the state machine cleans the incomplete candidate and
restarts the guarded attempt. If the bridge is already routed, it continues
forward from the checkpoint and establishes the compatible fallback. A fully
completed rerun makes no state or proxy change.

Never edit `state.json`, mark a migration, use `git pull` in production, change
nginx manually, or downgrade the database.

## Post-recovery validation

Require exact candidate SHA on stable and active version endpoints, schema 96,
readiness 200, frontend 200, DB/Redis/Auth/Storage healthy, all required workers
healthy, actionable queues healthy, public site and representative tenant login
working, no crash loops or request storm, active/fallback slots both reporting
the schema-96 bridge, production clean, and auto-deploy disabled.

Create and verify a fresh backup, verify its Node 1 copy, and run the disposable
round-trip restore. Logical DB/files/provider-object proof does not establish
full Supabase platform recovery.

## Fallback limitation

After success, only a schema-96-compatible slot may receive traffic. The old
schema-93-era artifacts may be retained for forensics but are not a rollback
target. A failed bridge after traffic transition is repaired forward with the
same or another independently proven schema-96-compatible exact SHA.
