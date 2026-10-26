# Phase VI implementation report

## 1. Executive summary

The confirmed stale deletion request failure,request finalization and step
completion defects are repaired through new migration150 and database-enforced
protocol2. They were reproduced on exact PR214/schema149 with3FAIL/2PASS. The
new38-case native ownership/upgrade suite passes without weakening the original
invariants. Real synthetic user AND tenant deletion completed through actual
GoTrue/Storage/PostgREST and a consuming worker;foreign tenant/object state survived.

Additional fixes include complete bounded Storage absence pagination,source
admission blocking every unreconciled nonterminal legacy deletion request,strict
restoration configuration derived from pinned source templates,and shared locks
for competing candidate refresh/source recovery. The legacy-admission diagnostic
changed from2FAIL/1PASS to3PASS without editing published150SQL or inventing a151.

**READY FOR CODE REVIEW. NOT READY for production.** The new coordinated profile
is intentionally unregistered. Concrete protected provider/coordinator/backup/
boot/write-handoff integration remains unfinished engineering. Current production
backup/replica evidence,privileged lifecycle acceptance,main protection,independent
human review and separately issued production authority remain unmet.

## 2. Repository and identity

Baseline PR214:80c05aec7cd7efa9d76f61f4eb0e44ec1183d617,OPEN/unmerged.
Main:876b65e73ea8ceaf398145d8677019184798a95c.
Branch:codex/schema150-deletion-integrity-20261018.
Draft [PR215](https://github.com/judahsleibi34/Madar/pull/215) targets214.
Frozen validated code candidate:36bb910fa028d380a0fb130bb8beeb1b0990bd2d.
This report and related documentation are committed afterward;their review-head
commit is distinct from the exact accepted runtime. No old image was relabeled.

New implementation commits in order:

| Commit | Change |
| --- | --- |
|52ac0dfc|Native baseline and protocol design|
|7268ab3b|Database request/step/effect fencing|
|b2600dc3|Private provider recovery before protected write authority|
|a8fac208|Fresh native schema150/consuming deletion acceptance|
|420eef79|Consuming readiness and complete Storage verification|
|299dcfe5|Lost migration reply and150business regressions|
|8e17a128|Authenticated independent full-app restoration|
|3bff7dd9|Unreconciled legacy deletion backlog admission rejection|
|36bb910f|Shared source/target recovery locks and fresh candidate acceptance|

Local author/committer areSaliba Rishmawi,requested Saliba-codes noreply address.
GitHub both author AND committer mappings were verified asSaliba-codes for every
published commit. Existing attribution/history/worktrees were preserved. Canonical
corrected dependency chain212→213→214→215;212already contains209–211. No main merge,
force push,branch deletion or automatic deployment occurred.

## 3. Deletion integrity

Legacy lifecycle writes lacked original generation/live-lease comparisons. Stale
workers could clear a successor lease,finalize its request or overwrite step output.
The repair locks request before step/effect,compares original request/worker/claim
generation/request attempt/step attempt/state,and checks PostgreSQL time AFTER
lock waits. Expired or superseded operations cannot acknowledge completion,failure,
retry,verification,cancellation or finalization. Helpers are owner-only;runtime
direct lifecycle mutation and legacy mutation RPCs are revoked.

Finalization checks the authoritative exact ten-step graph,not worker assertions.
Cancellation eligibility and original freeze restoration are atomic. Creation
captures original identity/status before freezing,serializes owner decisions,and
rejects cross-request scope confusion. Local idempotent operations recover under
new generations;durable canonical external intent precedes provider requests.
Unknown outcome becomes manual intervention rather than automatic destructive
replay. No claim of exactly-once external deletion is made. A request already sent
by a stale worker cannot be undone by database fencing.

Before publication,three additional draftSQL defects were reproduced and fixed:
idempotent freeze crash recovery,active replacement-owner eligibility,and quota/
registry confirmation. Published SQL was never rewritten. Broad service-role
credentials still reach other platform business/provider APIs;this repair fences
the reviewed lifecycle interfaces,not every malicious/legacy global-credential
holder. Scoped deletion credentials/broker and complete consumer exclusion remainP1.

## 4. Migration and release boundaries

New mirrored150_fence_data_deletion_ownership.sql SHA256:
`63d4d0c7af93bd3c3e93158a2e281b41eed23b83bfafd4b3f1ba22313533b722`.
001–149 and active146release descriptor are unchanged.150requires149,core-state
locking,clear processing/lease state,and atomic schema update. Runtime direct
INSERT/UPDATE/DELETE/TRUNCATE on lifecycle tables is denied;reviewed protocolRPCs
retain required service-role execution while anon/authenticated/helpers are denied.

Explicit unselected146→147→148→149→150candidate captures authenticated SQL bytes,
checks mirrors/order/manifests and retains policy:none for coordinated execution.
Every pre150 source-admission boundary also rejects nonterminal legacy deletion
backlog;idle waiting_retry is not evidence of safe external outcome or original
freeze state. Separately approved reconciliation is required. No automatic reset.

Precommit errors restore the previous committed schema;lost COMMIT responses require
independent schema observation. Native tests send150COMMIT without reading its reply,
observe committed150 independently,and reject repeated SQL. After commit,do not
restart legacy consumers or restore broad old grants. Forward repair needs reviewed
compatible components and valid independent authority. Database restore can erase
newer data and is not ordinary application rollback.

## 5. Workers and external effects

At150,delivery2/outbox2/deletion2 are independently checked. Deletion worker checks
NORMAL and exact protocol at startup and every consuming poll;149is blocked,READ_ONLY
is healthy but nonconsuming,no legacy fallback exists. Backend readiness requires
statusok AND consumingtrue. Restart with repeated worker IDs does not preserve
claim ownership;native generation/lease/retry/lock tests exercise successors.

Provider calls occur outside row locks,after durable intent and live claim renewal.
Structured404/410/exact absence codes are distinguished from arbitrary errors.
Incomplete/ambiguous external outcomes require reconciliation. Storage absence
verification uses stable bounded pagination;later-page presence or exhausted/malformed
results reject finalization. Host-file paths use pinned directory descriptors.
Real integration revocation/host-file deletion and lost external provider replies
are not covered by the full-stack happy-path fixture;see06for exact limits.

## 6. Protected controller and provider lifecycle

The source model durably binds exact operation/source/controller/database/inventory,
original role/service preimages,boot/ingress/supervisor/object/role/session fences,
quiescence and per-migration boundaries. After150,providers recover PRIVATELY with
original role state while ingress/workers/boot stay fenced and target grant is
absent. Only the existing independent protected handoff may establish fresh150
NORMAL authority;accepted workers/ingress resume afterward. Interrupted intent is
observation-only reentry,not blind replay. No parallel issuer or arbitrarySQLexecutor.

Model tests use real private journals/flock but injected effects. The concrete
production adapter,maintenance-aware backup/candidate/runtime/migration/handoff/
boot wiring and actual isolated privileged installation/reboot are NOT complete.
The profile remains unregistered and cannot be enabled by callerPASS packets.
See10,12,20,21for exact missing functions and prerequisites.

## 7. Executed validation

Frozen36bb910f backend [CI39128295671](https://github.com/judahsleibi34/Madar/actions/runs/39128295671):
4012collected,3183PASS,829conditionalSKIP,58.463s;4observer checksPASS;239native
PostgreSQL executionsPASS across retained and150groups,zero native failures/errors/
skips. Repeated schema runs are executions,not distinct coverage. The final41group
contains3legacy149admission+38deletion150cases;24business/calendar cases run at150.
Reservations,stock/order,simulated payment replay,tenant isolation and calendar
atomic versions retain assertions. Broad suite external attempts/sites are empty.

Frozen frontend [CI39128295628](https://github.com/judahsleibi34/Madar/actions/runs/39128295628):
1713PASS,1SKIP,233files;lint/build/auditPASS.
Fresh artifact [CI39128295629](https://github.com/judahsleibi34/Madar/actions/runs/39128295629):
PASS,artifact12136249264. Exact artifact/image digests are in14. Source dependency
locks,mirrors/transitions,forward release and tracked secret-file checksPASS.
Additional privileged inventory checkFAILS with the same11unclassified paths as
exact parent214;baseline debt is visible and assertions were not weakened.

Commands and baseline/working/hosted evidence distinctions are in07. Selected
browser checks do not establish complete forms/builder/ecommerce/admin product
coverage. No general performance improvement or production capacity/SLO is claimed.

## 8. Staging and restoration evidence

First native fresh acceptance:a8fac208,305.324s,independent synthetic148origin
restored then upgraded149/150,protocol150/2/2/2. Actual full150application backup
and restore:8e17a128,394.893s,new independent role-free PostgreSQL cluster,original
roles/passwords/memberships/grants/owners/RLS/definers,all row/sequence/object roots
verified BEFORE provider activation. Original identity/password/TOTP/private object
and fresh native provider probes,actual user+tenant deletion and consuming worker
restart passed;source fences/roots were re-observed afterward.

Final code candidate36bb910f fresh authenticated images accepted on that restored
150database in311.759s. SAME system identity and original roles/ACL/rows/sequences/
object bytes survived preactivation infrastructure recreation. It is explicitly
an image refresh,not a second restore or migration. Native Auth/MFA/Storage/
notifications and actual user+tenant ten-step deletion passed,first attempt,two
confirmed effects each,completed_with_retained_records,foreign state preserved.
Fresh OCI backend/worker identity:
`sha256:2dfe12742434d5aa8c8159273a8ab53a306d71b34a459eadbe6562e78d5e3ff0`;
frontend:
`sha256:4619f66617518c5273fe04a726fbc853cefdb21e522416574ea8556946afa34c`.
No /app source overlay or old-image relabeling. Browser Chromium151nine selected
auth/MFA/admin/refresh/cookie/mobile groupsPASS,zero page errors/external requests.
Temporary loopback tunnel closed.

The11service isolated stack uses fixed owner labels,synthetic DBmarkers,private
networks,loopback bindings,restart=no and bounded memory/CPU/PIDs. It includes
PostgreSQL17,GoTrue,PostgREST,Storage,Redis,backend,frontend/gateway and notification/
deletion workers. Freshness means accepted exact source/images,not production
controller authorization. Original source and final target states after explicit
recovery are recorded below. Useful private reports/journals/volumes are retained;
raw credentials and production operational evidence are not published.

## 9. Failure and recovery evidence

The owned source GoTrue restart immediately failed under recordedNOLOGIN fencing;
restarting ONLY its PostgreSQL container retained150/2/2/2,NOLOGIN and original
row/sequence/object roots.64.209s. First probe wrongly expected a still-running
provider;its assumption was corrected to check actual structured startup denial.
No writable bypass was observed;the running-provider rejection branch was not
claimed exercised. This is Docker/provider evidence,not systemd/reboot acceptance.

Two real negative logical restores in a new network-none boundedPGinstancePASS
in5.745s:missing original roles and half-truncated custom archive. Each failed
with single-transaction rollback,leaving zero app/Auth/Storage tables. Temporary
PGremoved by exact ownership checks;accepted source/target untouched.

Full application WAL/PITR/object consistency,missing/corruptWAL/basebackup,off-host
restoration,current-production-data backup/replica and certifiedRPO/RTO remain
NOTTESTED/BLOCKED. Same-VM drill durations are not recovery-objective compliance.

## 10. Security and production assessment

Core lifecycle P0defects are corrected in the reviewed database/API boundary.
Broad global service-role resource/provider access and complete legacy/manual
actor exclusion remainP1;no platform-wide isolation certification. Readiness
and source inspection never issue write authority. Mainprotected=false/rulesets=[]
were rechecked;credential has no admin right.11pre-existing privileged inventory
omissions remainFAIL. Narrow tracked secret-file hygiene is not historical secret
rotation or a complete repository exposure audit.

Read-only production metadata still reports146;auto-deploy timer disabled. This
does not prove every automation hook is inert or authorize integration. No customer
data export,production write/migration,restart,controller installation,grant,network
change,billing action,backup deletion or main merge was executed.

## 11. Remaining work and recommendation

P0:preserve protocol fencing,uncertain-effect manual handling and publishedSQL
immutability. No new unresolved reproduced lifecycle P0is claimed.
P1engineering:concrete protected provider adapter and fixed writer inventory;
maintenance-aware candidate/backup/migration/private-acceptance/write-handoff/boot
coordinator integration;real isolated privileged interrupted installation/reboot/
reentry;scoped deletion credentials/broker and independently reviewed uncertain-
effect reconciliation tooling. Register150only AFTER those paths are proven.
P1independent gates:administrator main/environment protection,human code/SQLreview,
current-data backup/restore/replica evidence,accepted artifact/maintenance scope and
fresh existing protected authorization. Independent authorization cannot replace
unfinished engineering.
P2:object-aware full-appPITR,off-host recovery/failure cases,broader productE2E/
tenant writes,recurrence atomicity,cross-process cache,complete alert delivery and
representative paired benchmarks;fix baseline inventory debt by function review.
P3:optional platform/scaling work after integrity/recovery gates.

PR215is suitable for independent CODEreview as a draft;production promotion remains
NOTREADY. Do not mechanically merge overlapping209–211 alongside212. Exact-source
artifact/CI and staging acceptance must be renewed after future code changes.
No tool/report/journal here supplies independent operator authorization.

## 12. Final retained staging state

Explicit36bbharness RESUME-SOURCE PASS:recorded originala8fac208 roles/service
identities restored,preservation checkpoint verified,positive provider and
consuming worker checks passed. Original schema150sourcea8fac208 is active.
The independently restored final36bbcandidate was stopped ONLY AFTER its live
native/browser/worker acceptance to bound memory;its volumes/images/configuration/
journals/reports are retained. No original source image was relabeled as36bb.
Source and target artifact identities remain distinct and authenticated.

Repeated completed RESUME-SOURCE was then actually invoked and rejected with
restore150_source_resume_already_consumed. Source AND target container identities,
images,running state,start timestamps and restart counts were unchanged across
the rejected call. No source/target restart or replay was hidden. Final observed
staging headroom:2929MiB available memory,19.47GiB free disk. Unrelated projects
were preserved;no broad Docker cleanup was performed.

## 13. Performance and observability limits

No new representative paired API/business benchmark was executed. Acceptance
305.324s,independent restoration394.893s,fresh refresh311.759s,provider/DBrestart
64.209s and negative restore5.745s are drill durations,not latency speedups,
production throughput or certifiedRPO/RTO. HDD-backed4vCPU/5402MiB staging remains
resource constrained;per-service CPU/memory/PID bounds are validated. No quota
change was made to manufacture a candidate performance improvement.

Deletion ownership/protocol/step/worker signals and existing observer4checks pass.
A complete new durable alert emission→delivery→retry→dedup→clear path was not
validated in this phase. Product forms/builder/commerceE2E,recurrence completeness,
cross-process catalog invalidation and off-host/object-awarePITR remain explicit
P2work. Selected passing tests are not platform-wide certification.

## 14. Final acceptance decision

READY FOR CODE REVIEW;NOT READY for production. Neither TECHNICALLY READY FOR
OPERATOR REVIEW nor AUTHORIZED FOR PRODUCTION is established. The machine-readable
and human verification matrices separate scopedPASS from PARTIAL/FAIL/BLOCKED/
NOTTESTED. Unregistered profile,unfinished concrete controller/provider lifecycle,
privileged installation/boot/handoff acceptance,broad-credential consumer isolation,
main protection,current-data/replica evidence and independent review/approval remain
material gates. Review the draft successor and continue those P1engineering tasks
before requesting a future independently authorized production maintenance operation.
