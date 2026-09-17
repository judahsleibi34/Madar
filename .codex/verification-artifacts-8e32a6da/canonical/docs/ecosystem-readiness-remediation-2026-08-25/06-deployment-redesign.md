# Immutable release and rollback redesign

## Architecture prepared in development

`web/deployment/lib/release_deployer.py` implements an explicit locked state machine:

`validate SHA -> suppress known-bad SHA -> build immutable candidate -> capture digests -> observe schema -> preflight -> start inactive slot -> deep validate -> atomic traffic switch -> observe -> mark known-good`.

Blue and green are isolated Compose projects with distinct local ports. Image tags include the full Git SHA; the durable release record includes SHA, image references/digests, schema state, slot, timestamps, phase, result, previous known-good and traffic target. A pre-switch failure destroys only the candidate. A post-switch failure switches routing back to the retained known-good slot and does not rebuild historical source. `flock`, failed-SHA state and an explicit `--retry-failed` control prevent overlapping/two-minute bad-build storms.

`madar-release-deploy` builds from a detached SHA worktree, records the local image ID behind each full-SHA tag, verifies that tag-to-ID binding again immediately before candidate start, and checks `/health/version`, backend readiness and frontend response before invoking an operator-configured atomic route switch. A local Docker config ID is not misrepresented as a registry manifest digest; a future registry promotion must additionally record/verify its manifest digest. The old auto-deploy entry points now delegate to this state machine. Nothing was installed on Node 1 production.

## Schema compatibility

`web/deployment/releases/release.json` declares compatibility 81–82, target 82, rollback 81–82 and migration class `expand-only`. Migration 082 is additive. Safe promotion is:

1. Take and verify a pre-migration backup.
2. Build immutable compatibility code that runs with schema 81 and 82.
3. Start/validate the inactive candidate against schema 81.
4. Acquire a database migration lock and apply checksum-verified migration 082 once.
5. Revalidate schema 82, candidate and retained code compatibility.
6. Switch traffic, observe, then mark known-good.

The current helper validates compatibility but intentionally does **not** automatically migrate a production database. A staged, backup-first migration executor and failure drill remain required. Destructive migration reversal is prohibited; if a future schema breaks old code, forward repair or coordinated cutover replaces automatic rollback.

## Fault coverage and remaining gate

Unit tests cover build failure, backend/frontend/worker/dependency/preflight failure, incompatible schema, candidate failure, switch/observation failure, rollback switch, overlapping invocation and repeated bad SHA. Required before installation: staging tests with real Compose/proxy, database lock/migration failure, interruption/reboot at every durable phase, storage failure, false-positive readiness, and retained known-good traffic proof. Therefore `MADAR-DEPLOY-001/002` remain partially fixed and G16 remains blocked.
