# Canonical Madar development workspace

The architecture implementation is reviewed through [draft PR #220](https://github.com/judahsleibi34/Madar/pull/220)
against `main`. Consolidation preserves published commits and attribution; it is
not a merge, production deployment or approval of the incomplete protected release.

## Locations

| Purpose | Path under `/opt/madar-development` |
| --- | --- |
| Existing independent checkout; preserve its branch and local files | `repository/` |
| Canonical architecture worktree | `worktrees/architecture/` |
| Necessary additional isolated worktrees | `worktrees/<purpose>/` |
| Current private integration evidence | `evidence/integration/` |
| Historical private development evidence | `evidence/historical/` |
| Historical checkouts, including the shared Git repository | `archives/worktrees/` |
| Development recovery checkpoints | `archives/checkpoints/` |
| Disposable development scratch | `scratch/` |
| Private inventories, relocation manifests and integrity results | `inventory/` |

The shared Git object database for the architecture and historical worktrees is
retained at `archives/worktrees/Madar-corrective/.git`. Git-aware worktree moves
and `git worktree repair` preserve its links. Do not delete that archive: the
canonical worktree depends on it. The existing `repository/` is a different
repository and was not replaced or reset.

Start future sessions with `cd /opt/madar-development/worktrees/architecture`
followed by `codex`. Inspect `git status --short --branch` and
`git worktree list --porcelain` before work. Reuse the existing worktree/PR;
another engineering phase alone does not justify another checkout or PR.

Use `git worktree add /opt/madar-development/worktrees/<purpose> <branch>` only
when isolation is needed, after checking branch/worktree availability. Never
create Madar worktrees, evidence or scratch directories in `/home/madar`.

## Preservation and cleanup

Inventory tracked, untracked and ignored files and check actual process,
supervisor and container references before relocation. Keep dirty work and
historical evidence recoverable. Prefer reversible archival and supported Git
operations. Do not use forced worktree removal, destructive Git cleanup, broad
Docker cleanup, branch deletion or history rewrites as organizational shortcuts.

Private inventories map original paths to verified destinations. Historical
reports retain their original environment paths and evidence scope. Do not
rewrite those reports to imply tests ran in the relocated environment. Private
evidence stays outside Git, with restricted permissions.

Preserve home configuration/credentials, unrelated projects, production and
backup/recovery artifacts, and paths still referenced by services or containers.
In particular, `Madar-control-plane-cutover` is linked to the production Git
repository, while `master-implementation-20260908` has retained Docker bind
references. They are excluded from development cleanup. Unknown items stay in
place until ownership and dependencies are established.

## Release boundaries

Main remains unchanged by consolidation. PR #195 has separate history and must
not be closed automatically. Superseded architecture PRs may close only after
ancestry/coverage verification and fresh successful CI for #220 against main;
their branches and historical reviews remain preserved.

The protected schema-146→150 release remains **INCOMPLETE / NOT READY**, and its
operational profile remains blocked. No full protected application upgrade,
independent write handoff or production rollout is established by consolidation.
See [the existing final engineering report](final-protected-release-2026-10-20/FINAL-REPORT.md).
Independent review, administrator-controlled branch protection, current-production
recovery evidence and fresh protected production authorization remain separate.
