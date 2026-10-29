# Madar release-safety instructions

## Permanent development workspace (owner instruction 2026-10-25)

Use `/opt/madar-development/repository` on `Saliba-Branch` for development.
Do not create named feature branches or new `codex/*` branches. Integrate main
without rewriting published history. New author and committer name must be
`Saliba-codes`, using its GitHub-recognized noreply address configured locally.
Preserve the fifteen untracked historical documents and their inventory hashes.
The previous architecture worktree and archived phase checkouts are historical;
read-only inspection does not make them active development branches.

Use bounded run-specific scratch under `/opt/madar-development/scratch/codex-runs`.
Compact private evidence belongs in `evidence/integration`, checkpoints in
`archives/checkpoints`, and inventories in `inventory`. Never create home-directory
worktrees or evidence trees. Every disposable run needs explicit ownership,
teardown and retention; never prune globally or remove unknown/recovery resources.
Preserve the accepted `madar-full-provider-fa27b773514b` staging application until
explicitly superseded. Production remains read-only until exact-scope independent
release authorization; no timer activation or migration follows from source CI.
Schema160 registration remains closed pending actual protected acceptance.

## Release constraints

Before preparing or merging any PR targeting `main`, read [`docs/MADAR_AUTO_DEPLOY_MERGE_CONTRACT.md`](docs/MADAR_AUTO_DEPLOY_MERGE_CONTRACT.md) and treat its auto-deploy, migration, protected-path, and production-mutation rules as mandatory release constraints.

Before changing deployment, migrations, schema compatibility, Docker/Compose,
production runtime code, release-sensitive backend/frontend code, or opening a
PR targeting `main`, read [`docs/production-release-policy.md`](docs/production-release-policy.md).
Before changing automatic migration orchestration, also read
[`docs/automated-database-migration-architecture.md`](docs/automated-database-migration-architecture.md).
Before changing privileged control-plane installation or upgrade orchestration,
also read
[`docs/control-plane-upgrade-architecture.md`](docs/control-plane-upgrade-architecture.md).

The current implementation is authoritative. If deployment-gating code,
automatic migration orchestration, or compatibility metadata changes, update
the applicable policy and architecture documents in the same change. Run every
applicable release-policy check before declaring work ready, and report gates
that cannot be tested locally.

Never bypass a failed release gate or directly modify production to compensate
for a source-code rejection.
