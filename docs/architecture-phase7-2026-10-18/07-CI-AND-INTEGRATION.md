# Exact source, CI and integration

Application/controller source selected for native acceptance:
`b9d826ee70e87a7f3eda89c14a78004b79fd6dab`.
Documentation published afterwards does not relabel this source or its images.

| Check | Exact-source result | Evidence |
|---|---|---|
| `test-backend` | PASS:3,338 passed,833 conditional skips;4,171 discovered,61.552s | [Backend run39137752654](https://github.com/judahsleibi34/Madar/actions/runs/39137752654) |
| Native PostgreSQL harness | PASS:243 executions,0 failures/skips,16 groups | Same backend run; independently created disposable PostgreSQL |
| `build-frontend` | PASS:1,713 passed,1 skipped;233 files;lint/build/shipped-dependency audit passed | [Frontend run39137752588](https://github.com/judahsleibi34/Madar/actions/runs/39137752588) |
| `build-candidate` | PASS:fresh locked backend/frontend archives | [Artifact run39137752593](https://github.com/judahsleibi34/Madar/actions/runs/39137752593) |

Native execution groups were32,8,8,4,21,11,5,18,22,2,5,16,22,43,24,2.
They include repeated business-regression executions at different schema boundaries;
243 is an execution count, not243 distinct tests. The43-case group includes38
deletion ownership/workflow cases and five legacy-admission cases. Four separate
loopback notification-observer tests passed in2.144s. Conditional backend skips
are not executed passes, and are not silently credited to native coverage.

The workflows check out the pull request's exact head, require a clean checkout,
use `contents:read`, and disable checkout credential persistence. The backend
preflight runs dependency-lock, mirrored-migration, transition, forward-release,
secret-hygiene and privileged-inventory checks. The unchanged inventory checker
now covers78 application paths. The artifact name retains the historical
`schema148-candidate` prefix; authenticated source/input/image identity determines
its meaning, not its name. Artifacts expire after seven days and must be renewed
when necessary. Successful CI is not production authorization.

## Failures retained and corrected

The first211/179 runs failed a new staging-wrapper test because it assumed the
local full repository layout. Actual CI mounts source components hermetically.
Commit4bd32241 fixes only the fixture by building a temporary complete tree from
real mounted migration bytes; assertions and historical SQL remain unchanged.
All52 related tests passed locally and in the hermetic layout afterwards.

At4bd32241, backend unit tests passed3,338 with831 skips, but native admission
rejected the terminal legacy-request fixture. The old helper did not log exact
counter values, so that specific failure's cause remains **unproven**. Investigation
repeated the original three native cases30 times:90 passed. A separate actual
PostgreSQL regression then confirmed transaction-local statistics caching could
hide a newly connected writer or retain an already exited writer. Commitb9d826ee
clears the observer's statistics snapshot before each strict observation. Five
native cases pass; the final CI243 execution result includes those cases. This
does not rewrite the historical4bd failure as a proven snapshot failure. See
`06-QUIESCENCE-SNAPSHOT-REGRESSION.md` for before/after evidence.

## Corrected controller/test head onOctober20

Exact source`3fde3ef15ffb463ff9fad83d83514aa3a2cd048f` adds the source-only MVCC
isolation guard and makes the object-permission test fixture independent of
shell umask. The latter correction followed a retained local failure:under077,
mkdir already produced0700, so chmod0700 did not mutate permissions. Giving the
private fixture an explicit0750 preimage preserves the original refusal assertion.
All110 scoped controller/filesystem/component tests then passed under umask077.

| Check | Exact-source result | Evidence |
|---|---|---|
| Backend | 3,338 passed,835 conditional skips;4,173 discovered,58.083s | [Run39383868356](https://github.com/judahsleibi34/Madar/actions/runs/39383868356) |
| Native PostgreSQL | 245 executions,0 failures/skips;the deletion/admission group grows43→45 | Same backend run |
| Frontend | 1,713 passed,1 skipped;233 files;lint/build/audit passed | [Run39383868513](https://github.com/judahsleibi34/Madar/actions/runs/39383868513) |
| Fresh candidate artifacts | PASS,exact3fde3ef1 source | [Run39383868450](https://github.com/judahsleibi34/Madar/actions/runs/39383868450) |

The two new native cases reject actual REPEATABLE READ/SERIALIZABLE transactions
against the full disposable149 schema. The separate minimal-schema native
before/after reproduction is documented in`10-MVCC-OBSERVATION-REGRESSION.md`.
No historical SQL changed. Full application/browser acceptance still identifies
b9d826ee; it is not relabeled as3fde3ef1. Corrected-head controller/image evidence
and earlier runtime evidence remain separate. Subsequent reporting commits need
their own exact-head checks and are not automatically accepted images.

### Corrected-head artifact inspection

Fresh archive12246633018 from39383868450/attempt1 was downloaded separately,
matched to authenticated GitHub digest and size, then inspected using the actual
clean3fde3ef1 source on staging. INSPECT passed without image import or service
mutation. It explicitly reported the prior project preserved; it did not adopt
that project's old images as the new source.

Archive462,809,398bytes,SHA256
`2cc40109dca4b92ab14e3dca4945594e3d5aeffff57a146ecbb14d860eb41924`.
Verified backend configurationID:
`sha256:6086b4cad5f200253f1eef6143f7db4dcb42d762eaefd799e4fdb21f439cbbc4`.
Verified frontend configurationID:
`sha256:1659afe3c037f1b844bb2b1c7fae10d4b2d2910760d50510c2495e913314a8bd`.
These are fresh authenticated image/archive identities, not registry publication,
native3fde3ef1 application acceptance or production artifact authorization.

## Canonical integration and deployment boundary

Use corrected PR212 as the consolidated baseline, followed by213,214,215 and
draft216. Do not mechanically merge overlapping original PR209–211. All published
histories are preserved; no PR was merged or force-pushed. PR216 targets PR215's
branch. Every new author and committer is checked locally and through GitHub by
exact SHA against `Saliba-codes`.

Main remains`876b65e73ea8ceaf398145d8677019184798a95c`;PR215 remains open/draft at
`86b022f208579341b2a9171255df4df14a9e4348`. Bounded observation found the production
auto-deploy timer disabled, but this is not exhaustive webhook/actor proof.
Recheck merge-triggered automation independently before any future integration.
No main merge, production controller installation or production SQL effect was
performed. Operational schema150 admission remains deliberately unregistered.

## Administrator-controlled protection still required

Read-only GitHub inspection again found main unprotected,zero rulesets and
`admin:false` for the available credential. No administration setting was changed.
The repository administrator should create an active main ruleset requiring pull
requests, at least one independent approval, stale-approval dismissal, backend
`test-backend` and frontend `build-frontend` checks, and resolution of review
conversations. Block force pushes and deletion. Restrict bypass to an explicitly
reviewed emergency group; apply rules to administrators where supported. Protect
production deployment environments and keep workflow tokens least privileged.

`build-candidate` currently runs on pull requests targeting main and the explicitly
listed release dependency branches, plus manual dispatch; it has no push-main
trigger. Require it for the corresponding release PR policy only after confirming
that every applicable PR actually schedules it. Do not configure a required check
for a branch/event combination that never runs it. Required checks must bind to
the GitHub Actions application and the intended latest head; do not accept an old
run or a manually named external status as equivalent evidence.

Administrator acceptance:verify a PR without independent approval cannot merge;
a failing/missing required check blocks it; force push/deletion are refused;
ordinary PRs schedule all their required contexts; a new commit dismisses stale
approval; emergency bypass and production environment approvals are audited.
These are instructions, not claims that protection or human approval exists.
