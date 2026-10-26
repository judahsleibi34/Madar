# Madar schema148 continuation — implementation report

## 1. Executive summary

A separate stacked PR211 extends the existing protected completed-NORMAL release
architecture with exact146→147→148 admission. It retains the notification fencing
and reservation fixes from210, rejects unsafe consumers/quiescence/artifacts,
compares all Auth/Storage roots, and preserves the existing authorization,
installation, backup, migration, READ_ONLY, promotion and forward-repair boundaries.

The work includes actual native SQL/lock/process-crash tests, independent native
application restoration, component WAL/PITR, fresh locked CI images and selected
browser/tenant mutation acceptance. Actual staging exposed two image/edge harness
problems, corrected and retested, plus a genuine worker metric collision: historical
outbox totals falsely replaced acknowledged-send counters. That defect is fixed
and covered by a failing-before/passing-after poll-loop regression and native stale
acknowledgement test. No additional financial routine defect was confirmed.

Production remains unchanged at146. **NOT READY** for production release: required
current-data acceptance, protected controller/backup-receiver acceptance, complete
reviewed supervisor ownership, current backup/replica and independent operator
approval are absent. Source and scoped synthetic evidence are ready for review.

## 2. Repository state

- Baseline210:3fba1c18b310bf0e16c0e6a1540ee8de72b633f4, containing209/f65aa472.
- Main observed876b65e73ea8ceaf398145d8677019184798a95c;209/210 remain OPEN/unmerged.
- Branch:codex/schema148-release-readiness-20261017. Worktree:
  /home/madar/Madar-schema148-release-readiness-20261017.
- Draft follow-up:[PR211](https://github.com/judahsleibi34/Madar/pull/211), base210.
  Integration order209→210→211; no merge, rebase, force-push or main mutation.
- Exact native-staging application image / validated release-code source:
  **32c77afd01a012c7d21240316d4a46e52c3cbf14**. Later delivery documentation/benchmark
  tooling commit is identified by PR HEAD and the completion response; it does not
  change this runtime source or the immutable SQL/image acceptance identities.
- Commits:4f2c31ae admission;d53e8961 independent recovery/readiness;
  8c41aff1 fresh provenance/consumer scope;a42e11ab WAL/browser;
  c3f9ce59 OCI identity/application CI;e32d33e7 counter/alerts;
  32c77afd staging explicit import reentry; final evidence/tooling commit follows.
- All new commit authors and committers use Saliba Rishmawi,
  75858844+Saliba-codes@users.noreply.github.com, mapped to **Saliba-codes**.
  Existing published history/worktrees preserved.

Changed groups:deployment admission/execution/evidence/boot/backup modules;
backend write-authority range and worker counters; exact new bridge/manifest;
adversarial native/unit tests; fresh CI producer/verifier/workflow; read-only
operator tools; isolated recovery/PITR/fresh-image/browser/tenant/performance
harnesses; policy documentation and this evidence directory. No dependency added.

## 3. Release engineering

New unselected profile5:completed-normal-schema146-148-coordinated-release.
Source146,target148; exact147 then148 only; rollback148-only; ordinary migration
policy remains none. Existing profiles1–4 and active release.json remain fixed.

Combined manifest SHA256:ddc9d0efc386f43cf35c6b73edc394feab5a7f29576596cc2df53340b5111051.
Bridge:60a6b0ad05d0d823e88db963522835459287698ac94bef7cbdea1615240d55a7.
147:bc76737e03ddf3dc369e444f34435dbded600ab1cae3209555b5bde6647d60f3.
148:a6788acfbe91129fcc55cbcd9c42440bbb91a785518afb99830c6137ed3c3096.
**No historical SQL/mirror/old manifest changed; no149 added.**

The ordinary loader still rejects coordinated147. Fresh protected authorization,
source/checksum/order verification and mandatory live guards admit it only through
the existing coordinator/executor. No new production SQL connection factory,
privileged issuer or parallel deployment path. The frozen source/installer include
new modules; installed production code is untouched. NORMAL is rejected at146/147
for the new range. All original SQL/preservation/acceptance gates precede148 grant.

Fresh artifact workflow binds exact head/source, pinned base/dependency inputs,
GitHub run/attempt/repository/path, artifact digest, archive hashes, runtime IDs
and labels. Latest exact-application backend/frontend CI is independently requeried.
The producer distinguishes build-host configuration IDs from single OCI manifest
IDs; staging initially refused their mismatch. Imported identities never get silently
substituted after acceptance. Overlay images do not meet this gate. These are
locked fresh accepted artifacts, not bit-for-bit rebuild reproducibility or operator
approval. Other image-store/archive layouts fail closed. Artifacts expire in7days.

Final artifact run38987861104, artifact12084150675, archive digest
51611d774689922dcff2f6dbc39620e85c9bf6a4ef570859e714dba3fe39e1c7.
Backend:sha256:e9a5e0924547e28b39ed7348a6998d5397b5688bebb030f46847e50a26091399.
Frontend:sha256:b50bd74273456b1da2d9e9d938951bc2c1d509ddaa174f7deb8a27b584ba8741.
See evidence/ci-final-receipt.json and ci-final-verification.json.

## 4. Worker cutover

Read-only production inventory covers active/historical consumers, boot actors,
supervisors and unrelated workloads. Detailed topology, identifiers, counts and
queue observations remain in a private local operator handoff, excluded from Git.
No production worker/supervisor was stopped. Complete ownership remains unapproved.

The new guard checks all Docker candidates and host process/cgroup visibility,
including manual/docker-exec paths, with a positive candidate PID control.
Reviewed unrelated exclusions require immutable image/spec/target REST binding,
different HS256 authority and actual native200 versus401/PGRST301 proof. Shared/
expired credentials, direct DB/signing credentials, unknown schemes/PGRST303 and
unmanaged consumers refuse. A synthetic native signing-scope probe actually passed.

Existing actor drains/fences owned old worker/boot/write authority; before backup
and each SQL transition require exact native cluster/schema, zero processing rows
(including expired claims), other transactions, prepared transactions and queue
locks. A processing outcome is uncertain without independent provider evidence.
Inspection never resets, marks sent or deletes such a row. Root authorization and
reconciliation remain separate. See04/05 and the operator runbook.

Protocol1 SQL works before147, protocol2 active startup rejects missing fencing,
READ_ONLY source tests forbid any consuming/scheduling RPC,147 revokes legacy
claim/finish/direct writes, protocol2 processes real native148 work. Full legacy
Python image/supervisor/reboot acceptance is not claimed. External acceptance
before lost acknowledgement remains at-least-once: provider idempotency or reviewed
reconciliation is required; generation fencing alone cannot guarantee no duplicate.

## 5. Schema146→148 validation

**64 native cases pass**:19 coordinated executor/guard,5 baseline146/upgrade,
18 generation fencing/worker and22 reservation/inventory/payment cases. Actual
PostgreSQL transactions, independent connections, row/DDL locks, disconnects,
executor process exits/journals, checksums, grants and DB clock are exercised.
Provider/supervisor/authorization transport fixtures are explicitly limited.

Coverage includes live/expired claims, competing legacy claim, resurrection,
checksum/source/order failure, wrong cluster, before147 rollback, after147 COMMIT
crash with stale journal, failed148 retaining147 fencing, fresh forward scope,
re-entry refusal, lock timeouts and original-column all Auth/Storage root comparison.
All stale sent/retry/dead/revoked outcomes reject after lease/ownership loss.

The new polling test runs real native reclaim/finish through worker main and proves
queue totals cannot fabricate sent/failed/dead counters. Native business cases
cover capacity/reactivation, no oversell, duplicate order/payment/COD/refund replay,
rollback, decimal snapshots, foreign resources and late payment authority. No live
gateway or billing action. Full interruption matrix and limits are in06/07.

## 6. Disaster recovery

Independent restore passed115.19s on a genuinely fresh PG cluster with no preexisting
Auth/Storage roles. Source/restored system IDs differ.177 table roots,21 sequences,
8 object bytes, all role attributes/passwords/memberships, owners/grants/RLS/definer
configuration preserved. Original password/AuthID/TOTP/private object works;
anonymous access rejects; fresh native app/Auth/MFA/Storage/worker flows and22
business tests pass. Original identity also passes again under the final fresh image.

Actual physical base backup+pg_verifybackup+named-target WAL recovery passed66.84s:
source became[2,3], recovered paused target retained[1,2]. Incomplete base backup,
missing archive and corrupt archive do not become accepted/writable recovery.
Small exact owned volumes/private archives retained; drill containers removed.

Limits:same VM; no off-host/bare-host full restore, no full application PITR,
production archive/replica acceptance, fencing/failover/quorum or measured production
RPO/RTO.115.19s/66.84s are synthetic drill intervals, not4h RTO/15min RPO evidence.
Attempts1/2 failed on staging Compose/Origin targeting and were preserved/stopped;
only attempt3 is reported successful. See10 and evidence JSON.

## 7. Security

Prior confirmed P0 notification ownership and reservation reactivation defects
remain fixed. New source admission fails closed and retains protected boundaries.
New counter defect is fixed without modifying DB status or ownership rules.
Native real-JWT tenant checks now include bidirectional reads/deletes, unchanged
foreign rows, path-user spoofing, admin denial and immediate disabled-membership
read/write denial. Legitimate CSRF cookie/header is required and used.

Service-role BYPASSRLS still requires correct application checks; selected tests do
not certify every tenant domain. Main protected=false, rulesets=[], token admin=false.
Current-data/controller acceptance and complete supervisor review remain high risks.
No production credential copied, customer repair, live provider request, billing
activation, secret rotation or production controller mutation. See11/15.

## 8. Business integrity

22 native business cases pass after the exact upgrade and in the restored database.
No new confirmed financial/inventory defect warranted changing working routines.
Payments use synthetic provider boundaries; real settlement/refund/chargeback and
all subscription transitions remain unproven. Full forms concurrent-edit/publish/
checkout browser workflows remain on the roadmap. The tenant archive test exercises
legitimate cleanup rights without disabling entitlements or activating subscriptions.

## 9. Performance

See13-PERFORMANCE-RESULTS.md and evidence/paired-benchmark.json for actual randomized
paired measurements and resource/dataset conditions. No speculative admin query
optimization was reintroduced. No general speedup, p99 or production capacity claim.

## 10. Tests and CI

Commands:

```sh
python3 web/scripts/check_dependency_locks.py
python3 web/scripts/check_migrations.py
python3 web/scripts/check_migration_transitions.py
python3 web/scripts/check_forward_release.py
python3 web/scripts/check_secret_hygiene.py
git diff --check
# Dedicated VM, locked cached test image and marked disposable PostgreSQL only:
sudo -n env BACKEND_TEST_IMAGE=madar-schema136-preparation-test:working \
  bash web/scripts/rehearse_migration_148.sh
# Existing isolated fixture/mount/no-external-network runner:
bash ~/schema148-readiness-20261017/run-backend.sh
python3 web/staging/integration/test_notification_observer.py
```

Full backend:3755 collected,747 conditional skips,**3008 executed PASS**; VM47.034s,
hosted57.998s. No external attempts/sites. Conditional native cases run separately.
Hosted64 native cases pass; commercial115/145/146 suites additionally32/8/(8+4).
Frontend:lint/build,233 files,**1713 PASS/1 skip**. Observer4 actual loopback failure
injection cases pass; final image native and Chromium9 selected checks pass.

Release-code CI:[Backend38987861093](https://github.com/judahsleibi34/Madar/actions/runs/38987861093),
[Frontend38987861101](https://github.com/judahsleibi34/Madar/actions/runs/38987861101),
[Artifacts38987861104](https://github.com/judahsleibi34/Madar/actions/runs/38987861104).
Exact check names:test-backend,build-frontend,build-candidate; source github-actions.
Final delivery-head checks are available on PR211. CI does not authorize production.

Failures were investigated, not suppressed: initial strict-type/source-fixture/
legacy-scope baseline errors corrected; first artifact identity mismatch refused;
TLS edge temp paths corrected with explicit verified resume; new counter test failed
40!=0 before fix; native tenant mutation first rejected missing CSRF and the fixture
was corrected. Assertion/security policy remained intact. Historical013/014 duplicate
migration warnings remain.14-TEST-RESULTS.md retains commands/counts and scope history.

## 11. Staging

Dedicated madar-staging:4vCPU,5402MiB, rotational virtual storage; resource bounded
CPU/memory/PID/logs and private networks/loopback ports. Original native nine-service
4f stack retained. Independent recovered ten-service stack now serves exact32c77afd,
actual148, fresh backend/worker/frontend; final acceptance202.336s without resume.
Native Auth/MFA/Storage/real delivery/readiness and original restored identity pass.
Final browser passes9 checks,0 page errors/0 external hosts; private temporary fixture
and SSH tunnel removed. Final worker sent1/processed2, failure/ownership/ack counters0;
queue gauges no longer overwrite delivery events. See final state/evidence files.

Original ports18080/18443/18081; restored19080/19443/19081, loopback only. Secrets,
roles dumps, DB/object archives stay private on VM. Attempts1/2 stopped and preserved;
unrelated staging data services untouched. No broad prune, reboot or unowned deletion.

## 12. Production readiness

**NOT READY** as a complete production release.43 explicit gates in15 plus the
read-only machine report distinguish PASS/FAIL/PARTIAL/BLOCKED/NOT TESTED. Missing
or stale operational evidence never becomes PASS; operator PASS packets cannot
issue authority. Production remains146; exact serving application/controller observations are private.

Unmet:integration/independent review/branch protection; privacy-safe current-data
146 rehearsal, all roots/anomaly review and Auth/Storage provider-writer quiescence;
protected controller/receiver acceptance;
complete consumer/supervisor/boot ownership; current backup/independent restore/
replica; accepted immutable integrated-source artifacts; maintenance/impact,
reconciliation/rollback-limit and fresh protected approval. Synthetic success is
not a replacement. No production runbook execution occurred.

## 13. Remaining roadmap

P0:no newly reproduced uncorrected P0 in executed scope; any tenant/authority/
financial failure blocks release. P1:above admission/recovery gates, real isolated
privileged boot/re-entry rehearsal and approved current-data integrity acceptance.
P2:remaining tenant mutation domains, complete forms/builder/checkout browser flows,
cross-process cache invalidation, outbox resolver ownership, durable operational
alert delivery and larger representative performance workload. P3:only justified
enterprise/Athena/provider/scaling foundations after P1.17 contains acceptance criteria.

## 14. Genuinely required independent actions

1. Repository administrator:configure main PR+independent-review rules, required
   github-actions test-backend/build-frontend checks, no force push/deletion and
   restricted bypass. API confirmed no rulesets and no available admin permission.
   Candidate artifact acceptance additionally requires its exact build-candidate
   workflow; its PR path filter is not a universal main-required context.
2. Independent reviewers/operators:review/integrate209→210→211, select exact
   integrated source and fresh accepted artifacts/controller. After integration,
   dispatch fresh artifact CI if branch filtering requires it; do not reuse a stale
   branch approval or expired7day artifact as authority.
3. Privacy/operations owners:authorize current-data rehearsal/backup/replica and
   controller/Node1 backup-receiver acceptance, approve complete actor/reconciliation
   policy and maintenance/impact/forward-only limits, then issue the existing fresh
   protected operation approval. No approval/token was prepared or forged here.

All executable staging/source tasks described as completed were done by this
session; these are separate controlled prerequisites, not requests to redo them.

## 15. Final recommendation

Review PR211 as the third stacked change. The modular monolith/provider interfaces,
immutable migrations and protected release model are preserved. Source security and
integrity coverage, independent recovery and fresh-artifact evidence improve
materially. Performance remains workload-specific; observability now reports honest
acknowledged-send counts but production alerting is not installed. Staging provides
selected native application parity, not full protected production release acceptance.
Production deployment remains blocked. Use16-OPERATOR-RUNBOOK.md only after genuinely
independent authorization; no release promotion or merge is authorized by this report.

## Publication boundary

Automatic approval review rejected publishing raw production topology/operational
metadata. The public report/evidence was sanitized; full read-only observations
remain in a private local handoff, excluded from Git. No approval was bypassed,
no protected evidence forged and no production mutation performed. Public source,
synthetic staging evidence and readiness limitations remain reviewable.

The newly collected raw production inventory/preflight was never pushed. Current
public baseline documentation also removes operational identifiers by a forward
redaction; earlier published history is preserved, not rewritten or purged.
