# Madar release-safety instructions

## Permanent development workspace

In environments where `/opt/madar-development/worktrees/architecture` exists,
reuse that canonical architecture worktree. In the owner development environment
where `/opt/madar-development` is unavailable, use the existing owner checkout at
`/home/judah/Madar Projects/Madar` on `Judah_branch`. Preserve all uncommitted and
untracked owner work there. Do not create Madar clones, branches or worktrees merely
for another phase, and do not create evidence or scratch directories under
`/home/madar`.

The existing `/opt/madar-development/repository` checkout, when present, is
separate and may contain uncommitted work and active runtime dependencies.
Preserve it. Do not create an isolated worktree unless the project owner gives
separate explicit authorization. Preserve published branches/history.

Keep current private evidence in `/opt/madar-development/evidence/integration`,
historical evidence in `evidence/historical`, checkpoints in
`archives/checkpoints`, historical worktrees in `archives/worktrees`, and
temporary development files in `scratch`, all relative to that development root.
Use restricted permissions for private evidence and keep it out of Git.
Record relocation and integrity manifests under the root's `inventory` directory.

Before moving or retiring anything, inspect Git state, ignored/untracked files,
active process/service/container references and resource ownership. Prefer
Git-aware relocation and reversible archival. Never discard dirty work, remove
unknown data, delete branches or use broad Git/Docker cleanup. Preserve production,
backup, recovery and unrelated-project paths and dependencies. Historical paths
in old reports describe their original test environments; consult the private
relocation manifests rather than rewriting historical evidence.

In the owner development environment, start subsequent sessions with:

```bash
cd "/home/judah/Madar Projects/Madar"
codex
```

Workspace consolidation and passing CI grant no production authority. Keep the
canonical architecture PR draft until independent review permits otherwise;
do not merge, enable auto-deploy or perform production mutations without separate
authorization. The protected schema-150 operation remains blocked/incomplete.

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
