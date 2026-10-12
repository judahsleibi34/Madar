# Schema-144 manual production release: verified checkpoint

Recorded 2026-10-12. **Production approval ready: NO.** This document records
completed work and unresolved execution gates. It is not a production plan,
authorization receipt, or claim that the complete manual deployment passed.

## Live baseline

Read-only inspection and the installed `attest_compatible_runtime()` pass:

| Item | Actual state |
| --- | --- |
| Canonical main | `eacfb005230063f792b7f60021b835abb473a142` |
| Development branch | `fix/manual-main-schema144-release`, draft PR [189](https://github.com/judahsleibi34/Madar/pull/189) |
| Production application | `81cebfeb024341cd8d784402ba1f92ed2e63fb3d` |
| Installed controller / production checkout | `dbc26321edda331beb3c59e21fc05a6a250beacf` |
| Database | Current native PostgreSQL, schema **136** |
| Production | GREEN, **NORMAL**, version-2 business-write grant |
| Public frontend / API | HTTP **200** / HTTP **200**, `ready: true` |
| Business consumers | Notification, calendar-sync and data-deletion: healthy |
| Worker owner | GREEN application, generation `dadd80ecc5471ee7d544e45109ca4d0a9eb0967047cf0a1faaecf0898e9714e2` |
| Native backup timers | `madar-backup`, `madar-node1-backup`, `madar-backup-verify`: enabled and active |
| Auto-deploy | Timer disabled/inactive; service static/inactive |
| Production changed by this preparation | **NO** |

The stored current grant binds the application above, schema136 and range115..136.
It cannot authorize a new144 application. Historical completion, recovery,
authorization and execution records remain unchanged. No authenticated customer
mutation was performed as part of these read-only checks.

## Selected migration contract and valid evidence

Target remains **144**, with the exact lineage:
**136 → 137 → 138 → 139 → 140 → 141 → 143 → 144**.
Migration142 is excluded. Its specialized exchange functionality is not claimed.
The new source descriptors are unselected; active `release.json` still targets136.

| Artifact | Measured SHA-256 |
| --- | --- |
| `learning-136-144-path.json` | `ea2654bedb35f38cf7bfb59d5d7f18c82099344de8133f0d0e74efcdb92d9571` |
| `migrations-137-144-learning.json` | `d1016392aa863d7f8b2197bd1e2b479799ceb0ce5502e61840f41f002878f3c0` |
| `schema-136-144-learning-bridge.json` | `3bfea4deb6d987e9b5a0b631a962bdb2bb6b40a812187089f7ea19ce11437ad1` |
| Private SQL result | `948e5107eae1121f853eb010d56564e5ee6e2358202e21212331439f75a21c6a` |

The real current-data SQL rehearsal remains applicable: actual migrations,
162 original tables, Auth/storage, ownership, the exact139 ACL tightening,
zero invalid indexes, injected SQL failure and forward resumption passed.
The executor, SQL and these descriptors have not changed in this follow-up.
The SQL campaign was not repeated. Its protected original result is retained at
`.incident-response/manual-main-release-20261012/private-migrations-v5-stdout.json`.

At correction commit `af2cdd34e14ea2769e1b3a07236073dec98cbeba`, exact-SHA CI passed:
backend **2694 passed / 662 skipped**, frontend **1562 passed / 1 skipped**.
Runs: [Backend](https://github.com/judahsleibi34/Madar/actions/runs/38252688116),
[Frontend](https://github.com/judahsleibi34/Madar/actions/runs/38252688111).
These are CI results, not acceptance of new application images.

## Demonstrated correction completed in this follow-up

The write-authority Compose overlay hard-coded115..136. It would overwrite the
candidate's136..144 environment even after its source contract was accepted.
It now requires explicit minimum/maximum from the deployment environment and
carries the declared exclusion. Missing bounds fail configuration rendering.
Existing authority mounts remain read-only, with `create_host_path: false`.

Changed files:

- `web/deployment/docker-compose.write-authority.yml`
- `web/deployment/bin/madar-release-deploy`
- `web/backend/tests/test_completed_normal_compose.py`
- `docs/production-release-policy.md`
- `docs/control-plane-upgrade-architecture.md`
- This checkpoint document.

**12 focused tests pass** on the deployment host. The144 test validates the
pinned descriptor, manifest and bridge hashes, loads that actual compatibility
contract through the actual deployment environment builder, and renders the
base/release/authority Compose stack. Stale115..136 values in both shell and env
file cannot replace136..144 with142 excluded. All four business roles retain the
read-only authority mount and container security settings. Missing minimum or
maximum rejects rendering. Historical admission with a144 selected range rejects
before Docker. Missing/modified grants and image/slot mismatches remain rejected.
Allocation, image and contract identifiers used only for rendering are synthetic;
this does not claim144 admission, credential issuance or image acceptance.
Dependency locks, migration mirrors, schema transitions, forward-release,
exact learning route and secret hygiene checks pass. Two unchanged historical
013/014 duplicate-content warnings remain; migration validation reports zero errors.
Exact-head mandatory CI must also pass on PR189 before review/integration.

## Retained BLUE: measured, not retired

GREEN continues serving8201/3200. Both standard BLUE application ports are busy:

| Resource | Exact ID | Image / listener |
| --- | --- | --- |
| `madar-blue-backend` | `eaa23937da821f8896c26d7c0bb6a3685dc7fbe73cf0a43bbcfef219c14abe63` | `sha256:f87823ed4f2068a89b91fd1713f3b754645aac57ddad126a0fa5bb597ffb4900`, 127.0.0.1:8101 |
| `madar-blue-frontend` | `5bf07374f89d8a78827a62605cdc4f5bddfed0847d615aa74e1afad545470c90` | `sha256:dd3fcbb036fabd2955772ced12d9536a3bc845037ac8a9d5bd23ca841681a546`, 127.0.0.1:3100 |

The BLUE backend mounts current managed assets writable and its historical
authority read-only. Its networks are `madar-normal-82c2321cc671-runtime`,
`madar-provider402-rehearsal-94750f00e0d3-candidate-blue-runtime`, and
`madar-supabase-client`. The frontend uses the first network. These resources
were not stopped, removed, renamed or detached. A fresh authorized transaction
must bind their full specifications and dependencies, recheck them under locks,
and retire only the approved services without deleting customer volumes/assets.
No governed144 retirement implementation or passing retirement rehearsal is claimed.

## Backup, replica and storage

Current verified ordinary backup: `madar-20261012T073631Z`, manifest
`b90407e75ca64bad894cfc94d784f40c4a0d8e4db8954ba7caded5f0fa2d9e0c`.
Its465 local checksum entries passed during the existing rehearsal preparation;
its dump was actually restored for that SQL rehearsal. The complete artifact
occupies311,455,744 bytes. The current latest marker still identifies this backup.

Node1 replica:
`/srv/data2/madar-backups/normal-local-production/f39f7cf82913d30d4f8686ae5cd2ca59626d97faadb8557349b9c83cdcbf5b63/madar-20261012T073631Z`.
The approved existing SSH alias was used read-only. The replica's manifest
matches and `sha256sum -c SHA256SUMS --quiet` exited0 again. Node1 available
capacity measured910,005,493,760 bytes. No original backup or pointer was changed.

Node2 available space measured37,491,343,360 bytes (**34.92 GiB**), leaving
about4.92 GiB allocation above the mandatory30 GiB reserve. Two backups at the
observed size occupy about0.58 GiB. New-image preparation, independent Docker
storage and full application-service peak have not been measured as fitting.
Aggregate Docker reclaimable estimates are not disposable-resource proof.
No shared image, historical fixture, volume or backup was deleted; no HDD was touched.

## Full rehearsal: BLOCKED

The rejected privileged Docker/systemd fixture remains prohibited and preserved.
It exposes production host block devices and cannot provide this acceptance.

Unprivileged `unshare --user --map-root-user` rejects UID-map setup.
RootlessKit3.2.0 with network disabled fails because `newuidmap` is absent;
`newgidmap` is absent too. No helpers were installed or host security changed.
A root-assisted **subordinate-ID** namespace smoke check succeeds and denies
reading the host Docker socket/production credential directory and writing the
production checkout/protected authority. This is only a probe, **not** complete
isolation acceptance. It has no verified private root filesystem, delegated
cgroups, private Docker daemon, genuine systemd credential lifecycle or restart
rehearsal. No VM or replacement deployment framework was created.

Further RootlessKit, namespace, VM and rehearsal-environment work is stopped
under the operator's P0 update. No complete release rehearsal can be claimed
from Compose rendering or SQL tests.

## Smallest alternative validation strategy and risks

Keep the working136 deployment unchanged. Reuse the existing installed136
completion attestor, known-good backup/replica proof and unchanged seven-SQL
rehearsal. Validate the remaining manual transition in bounded stages: exact
controller inventory/preimages and authorization negatives; actual Compose
render and port/name/network feasibility; worker/authority/boot state-machine
failure injection using existing fixtures; then exact-image application checks
against private data only where an already safe fixture exists. No new privileged
environment or controller framework is required for those source/read-only checks.

This alternative yields component evidence, **not** complete operational
acceptance. It does not prove real new-controller installation, systemd credential
delivery, occupied-BLUE retirement, Docker/systemd restart or the combined
forward-recovery sequence. Those risks remain unverified. A runtime safety guard
must still reject absent or mismatched fresh authority. Existing136 acceptance
cannot attest new144 images or changed privileged executables. Do not suppress
those guards or turn this alternative into a PASS receipt.

The next correction is confined to the existing manual installer/admission and
boot path, with a new candidate-specific136→144 contract and explicit resource
preimages. It must not broaden the historical115→136 contract. Retained BLUE
requires exact-ID retirement under deployment locks, with managed mounts and
volumes preserved and GREEN still serving until the compatible candidate is
verified. Neither remaining operation is implemented or accepted in this change.

## Remaining release engineering and approval boundary

| Gate | Status and precise remaining work |
| --- | --- |
| Controller/source-role handoff | **NOT COMPLETE.** Installed attestation accepts the legitimate136 origin, but real candidate admission remains bound to `completed-normal-schema115-136-upgrade`. Reuse the verifier and existing installer with a fresh manually scoped136→144 contract and exact inventory attestation; do not widen historical receipts. |
| BLUE preparation | **NOT COMPLETE.** IDs/listeners/mounts are measured. Implement and privately rehearse exact-resource retirement/replacement under locks with GREEN preservation. |
| Exact144 application acceptance | **NOT EXECUTED.** Neither a backend nor frontend image has been frozen/accepted for the selected new source. The currently running81cebfeb image pair is not acceptance of latest main. Review/integrate PR189, freeze the resulting source and accept that image pair at136/144. |
| Worker/write/boot handoff | **NOT COMPLETE.** Existing coordinator and compatible boot validators explicitly bind115..136. Adapt only the manually authorized path, retain revoked historical grants, and prove singleton ownership and schema-aware forward recovery. |
| Complete manual lifecycle | **BLOCKED / NOT EXECUTED.** Requires the isolated target above and the completed scoped operation, including genuine credential delivery, proxy/boot/restart behavior, ordinary backup/restore and replica semantics. |
| Storage peak | **UNVERIFIED.** No large allocation may begin until measured to retain30 GiB. |
| Final exact-plan preflight | **NOT PASSED.** No immutable complete144 operation exists yet. |

The installed upgrade dry run previously stopped at `candidate_resolution` with
`approved_sha_not_current_origin_main`: actual remote main is eacfb005, while
production's cached origin/main is fa133941. No live Git fetch was performed
to suppress that guard. A future approved complete operation must include its
exact governed reference refresh; that alone does not resolve the later gates.

Before SQL advancement, preserve serving GREEN and fence/retire only exact
authorized resources. After advancement beyond136, GREEN's136-only application
is not a safe fallback: retain the newly accepted compatible candidate and use
current-data-preserving forward recovery or maintenance. Never automatically
restore an older database. Current customer writes remain authoritative.

Expected write-fencing/downtime: **not measured**, because the complete handoff
has not executed. Final controller, application images, source package, plan,
entrypoint and wrapper hashes: **not generated**. No placeholder operation or
production approval request is supplied while these mandatory gates remain open.

**Production remains NORMAL at136. Schema144 release preparation is incomplete.**
