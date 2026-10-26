# Phase VII engineering report

Assessment updated2026-10-20. **NOT READY for production.**
Draft[PR216](https://github.com/judahsleibi34/Madar/pull/216) is reviewable
implementation progress. The complete protected146→150 operation remains
unimplemented/unproven at several mandatory boundaries. Operational admission
stays unregistered. No production authorization was issued or inferred.

## Repository and exact identities

| Identity | Verified value |
|---|---|
| Main | `876b65e73ea8ceaf398145d8677019184798a95c` |
| Parent[PR215](https://github.com/judahsleibi34/Madar/pull/215) | OPEN/draft,`86b022f208579341b2a9171255df4df14a9e4348` |
| Branch | `codex/phase7-protected-controller-20261018` |
| Corrected code/test head | `3fde3ef15ffb463ff9fad83d83514aa3a2cd048f` |
| Native application/browser source | `b9d826ee70e87a7f3eda89c14a78004b79fd6dab` |
| Latest actual guest installation source | `bd0c614cfb92417740ce8d8bffacb98f6636e48a` |
| Source installed at actual guest reboot | `1b1dc54d8f19a2b1c83c618da89a42d8758b6993` |
| New author and committer | Saliba Rishmawi,`75858844+Saliba-codes@users.noreply.github.com`;GitHub both`Saliba-codes` |

Subsequent reporting commits retain their own Git identity and exact-head CI;
they do not relabel the source/image/installation receipts above. The final
reporting SHA and clean-worktree check are available in the PR's latest commit
and session completion message. Existing worktrees/histories were preserved.
Corrected ancestry is212→213→214→215→216;overlapping209–211 are not mechanically
merged. All inspected PR209–215 remain open/draft/unmerged. No main change or
force push occurred.

Focused commits before this reporting commit:

| Commit | Change |
|---|---|
| 50a06ff9 | Review eleven privileged omissions; enforce unchanged checker in CI |
| 1b1dc54d | Verified bounded isolated KVM guest tooling |
| 1fcf89b0 | Preserve referenced private-upload bytes after uncertain metadata commit |
| 7ec7a2bb | Repair only the positively unstarted QEMU launch; retain seccomp |
| a9094777 | Exact actor inventory and bounded object preservation |
| c2d63b6d | Concrete guarded provider fencing/private recovery adapter |
| bd0c614c | Reject unreachable provider lifecycle declarations before fencing |
| 91c3637f | Separate fresh exact-source native150 acceptance wrapper |
| 21177331 | Actual protected installation and persistent guest reboot evidence |
| 17943d6a | Typed non-authoritative private-journal status projection |
| 4bd32241 | Hermetic CI fixture uses actual immutable migration inputs |
| b9d826ee | Refresh activity statistics before every cursor-based observation |
| 58dd5c47 | Reject stale MVCC transaction snapshots for queue admission |
| 3fde3ef1 | Deterministic object-permission fixture under restrictive umask |

## Implemented controller and provider work

`schema150_provider_adapter.py` binds fixed internal Docker/systemd/SQL/private
HTTP effects to the existing persistent maintenance lifecycle. It is subordinate
source:there is no alternative issuer, arbitrary shell/SQL interface, production
entrypoint or registration bypass. Existing fresh authorization, exact source,
actual held deployment/upgrade flocks, root-private inventory/journal and live
cluster/container identity are required at each effect.

Positive provider identity/scope checks precede fencing. Original role attributes,
memberships and private roles-only DDL are preserved. The boot barrier precedes
effects; measured supervisors require exact effective negative conditions and
inactive/dead/no-job/no-PID state. Fixed measured actors lose restart capability
and stop; roles are fenced transactionally. Existing sessions are separately
observed with bounded drain refusal;NOLOGIN is never treated as disconnection.
Unknown consumers, sessions, publication/resolver overrides and unrelated
container exclusions without live proof fail closed.

Descriptor-based object measurement separates live root identity from actual
fenced two-pass content capture. Original measured roots and the private fenced
checkpoint must survive later boundaries. Database bytes are never scanned by
this helper. Original roles may be restored privately at150 while ingress/worker/
boot fences remain. The adapter checks existing target authority before business
worker/ingress activation and clears the boot barrier last; it cannot issue that
authority. The read-only status command reports verified journal history and
barrier conflict, explicitly not current database/service acceptance.

**Unfinished engineering:**sealed future-candidate publication; exhaustive dormant
host/manual writers and alternate supervisors; authenticated live exclusions;
maintenance-aware ordinary backup/replica/restore preserving original roles;
candidate preparation; captured migration/private acceptance/write-handoff and
boot/proxy recovery integration. These prevent operational registration, beyond
the independently controlled human/production gates. See
[adapter review](03-PROVIDER-ADAPTER-AND-CONTROLLER.md) and
[operator runbook](05-OPERATOR-RUNBOOK-AND-ROADMAP.md).

## Confirmed findings and repairs

1. Actual PostgreSQL metadata committed before an upload acknowledgement was
   lost. Old exception cleanup deleted referenced private bytes. Two native
   baseline tests failed; repaired native tests and service regressions pass.
   Unknown outcomes retain bytes/quota and operation identity, rather than infer
   rollback. Production occurrence was not established. Existing lost bytes, if
   any, require scoped owner-approved recovery; this source cannot recreate them.
2. A transaction-local activity snapshot could hide a new client or retain an
   exited one. The helper now refreshes its own statistics snapshot before each
   unchanged strict observation. Five native cases passed after correction.
3. Separate native evidence showed REPEATABLE READ/SERIALIZABLE could hide newly
   committed queue work even after the writer exited and activity refreshed.
   Those levels now refuse before observation; READ COMMITTED/READ UNCOMMITTED
   retain fresh statement checks. Four native before/after cases and two new
   full-schema hosted regressions establish the correction. No current persistent
   operational cursor caller or production occurrence was found.

Independent draft review also corrected libpq override, secondary alias,
supervisor-state, effective host-publication, condition ordering and lifecycle
declaration failures before admission. The unchanged privileged checker now
passes78 paths after per-path review of all eleven omissions. Inventory
completeness is not proof of platform-wide authorization. Broad deletion/provider
credentials and a complete authorized uncertain-effect reconciliation framework
remain open. No credential rotation, unrestricted repair endpoint or new schema
was introduced. See[security/failure evidence](08-SECURITY-AND-FAILURE-EVIDENCE.md).

## Privileged installation and recovery

A dedicated signed-image KVM guest ran real root-owned installation, effective
systemd verification, actual atomic replacement and authorization/source/root/
lock refusal probes. A real guest reboot preserved the test barrier and disabled
timers. The laterbd0 replacement verified182 exact installed files and imported
schema150 helpers. The guest is powered off with its disk/evidence retained.
Node2 and the staging host were not rebooted. The harmless native barrier test
is not actual application/provider fencing or complete coordinated release
recovery. Exact failures and scope are in[guest evidence](02-ISOLATED-PRIVILEGED-VM.md).

The schema150 manifest remains exact147→148→149→150,policy`none`,unselected and
operationally rejected. Published001–150 SQL and selected`release.json` have no
diff from the parent.150 mirrored SHA256 remains
`63d4d0c7af93bd3c3e93158a2e281b41eed23b83bfafd4b3f1ba22313533b722`.
No151 was needed. Intermediate schemas must remain READ_ONLY. After incompatible
commits, do not restore old grants/workers or replay consumed approval. Actual
full privileged between-COMMIT interruption/re-entry, provider recovery, write
handoff and proxy recovery are not accepted by model evidence.

## Fresh artifacts, native staging and restored application

Freshb9 artifacts were authenticated/imported into a separate fixed PhaseVII
project. A new cluster restored independent synthetic148 roles/database/eight
object files, verified fingerprints, executed captured149/150 and accepted real
Auth/MFA/Storage/notifications/readiness at150/2/2/2. Original password/authID/TOTP/
private object bytes survived; anonymous private access was denied. Real consuming
workers completed all ten deletion steps for both a synthetic user and tenant,
each with two confirmed external intents and one request attempt. Foreign tenant
data was preserved; worker restart consumption passed.

Native scope elapsed311.042s;outer wrapper315.157s. Nine browser groups passed
onOctober20 with Chrome151.0.7922.34,zero page errors or external-host blocks.
These times are not RTO/performance certification. External integration revocation,
host-file deletion and lost external replies were not exercised in this runtime
probe. Exactb9 images/archive/source and native outcomes are in
[full-stack evidence](fresh-schema150-acceptance.md).

Staging had4vCPU/5,402MiBRAM and HDD-backed storage. On resumption it was swapping.
After acceptance, only the eleven attested PhaseVII services were stopped; their
data, receipts and configurations remain. The22 retained source/recovery container
identities/images/running states were preserved. Available memory rose from1,468
to2,316MiB. The tunnel closed and the small isolated MVCC fixture was removed.
The new stack is deliberately stopped; the retained PhaseVI source remains active.

Fresh corrected3fde3ef1 images were independently built and authenticated, and
actual staging INSPECT passed without image import or service mutation. They are
not reported as natively acceptedb9 images. Exact IDs, artifact digests and CI links
are in[CI/artifact evidence](07-CI-AND-INTEGRATION.md).

No new full150 maintenance-journal restore, complete object-aware PITR, damaged-WAL
matrix or off-host recovery was completed. The guest shares the physical staging
host. RPO≤15minutes/RTO≤4hours remain uncertified. See
[recovery/coverage limits](09-RECOVERY-AND-REMAINING-COVERAGE.md).

## Tests and retained failures

| Environment/command | Actual result |
|---|---|
| Exact3fde3ef1 hosted backend:`python scripts/run_tests_no_external_network.py` in locked test image | 3,338 passed,835 conditional skips;4,173 discovered,58.083s |
| Hosted bounded native harness:`timeout 10m bash web/scripts/rehearse_migration_{115,145,146,150}.sh`,each separately | 245 native executions,0 failures/skips;includes repeated schema-boundary business cases |
| Frontend:`npm ci`,`npm run lint`,`npm test`,`npm run build`,`npm audit --omit=dev --audit-level=high` | 1,713 passed,1 skipped;233 files;lint/build/audit passed |
| Eight scoped controller/component modules under umask077 | 110 passed,0 failures/skips,0.715s after deterministic fixture repair |
| New native application:`phase7_schema150_acceptance.py REHEARSE --source-sha b9d826ee70e87a7f3eda89c14a78004b79fd6dab --artifacts <private-authenticated-directory>` | PASS;true providers/workers and restored application;scope above |
| Browser:`browser-smoke.mjs <private-fixture>` through verified23443 loopback tunnel,exact source assertion | Nine groups PASS;not complete productE2E |
| Corrected artifact:`phase7_schema150_acceptance.py INSPECT --source-sha 3fde3ef15ffb463ff9fad83d83514aa3a2cd048f --artifacts <private-authenticated-directory>` | PASS;no runtime mutation |
| Required release-policy checks | Locks,migration mirrors/transitions,forward contract,tracked-secret hygiene,privileged inventory PASS |

[Backend/native39383868356](https://github.com/judahsleibi34/Madar/actions/runs/39383868356),
[frontend39383868513](https://github.com/judahsleibi34/Madar/actions/runs/39383868513),
[fresh images39383868450](https://github.com/judahsleibi34/Madar/actions/runs/39383868450)
all passed exact3fde3ef1. Earlierb9 native runtime source checks are linked in
the CI document. Conditional skips are not passes. Counts are not summed across
overlapping focused/native/full-suite runs.

Retained failures include the native upload baseline, statistics/MVCC baseline,
first unstarted QEMU launch, raw-root bytecode probe, full-CLI earlier ownership
refusal, hermetic fixture mismatch, restrictive-umask fixture mismatch, and an
earlier hosted positive-admission rejection whose exact cause remains unproven.
Each is distinguished from a repaired implementation failure or fixture/environment
failure in the linked reports. No failing assertion was weakened or suppressed.
Two historical013/014 duplicate-content warnings remain. No new general speedup,
capacity,p99,SLO or RPO/RTO claim is made.

## Production readiness and required next work

The[39-gate matrix](VERIFICATION-MATRIX.md),also[JSON](VERIFICATION-MATRIX.json),
records8PASS,21PARTIAL,6BLOCKED,1FAIL and3NOT TESTED. Gate scopes explicitly
separate current controller source,b9 runtime and older installed/reboot sources.
No staging PASS satisfies an independent production gate.

October20 bounded read-only inspection again found production schema146 and its
installed controller marker matching the private baseline. Its auto-deploy timer
was disabled/inactive. Main remains unprotected withzero rulesets and noadmin
permission for the available credential. Timer state is not exhaustive merge-hook
proof. No production SQL/schema/service/controller/role/network/backup/secret/
billing mutation or main merge occurred.

| Priority | Remaining requirement and acceptance |
|---|---|
| P0 follow-up if affected records exist | Owner-approved scoped investigation/recovery of prior upload missing bytes;production occurrence unestablished |
| P1 engineering | Complete source-bound ordinary maintenance backup/replica/restore and candidate publication;actual original-role restoration and READ_ONLY candidate proof |
| P1 engineering | Complete exhaustive writer/supervisor/exclusion inventory and coordinator/private acceptance/write-handoff/boot/proxy adapters;actual privileged146→150 interruption/re-entry matrix |
| P1 engineering | Scoped deletion identity/broker and audited uncertain-provider-effect resolution;native wrong-scope/lost-response/reclaim/retry tests |
| P1 controlled human/admin actions | Main ruleset,independent review,current-production backup/restore/replica evidence,maintenance/reconciliation approval,and fresh protected authorization;none self-issued |
| P2 | Whole application/object-aware/off-host PITR,broader product/tenant/browser/cache coverage,native alert delivery and representative paired performance |
| P3 | Defer infrastructure/scaling/enterprise expansion until release-critical correctness is proven |

Recommendation:continue independent review of draft216 and its corrected stack;
do not merge or promote. Complete the engineering gates before requesting final
operational authorization. The safe result is preserved production boundaries,
reproducible fixes and explicit unfinished work, not an apparently executable
profile obtained by removing the protective rejection.
