# Future operator runbook — not executed production instructions

Status: NOT READY. Technical staging evidence and independently authorized
production execution are separate. This document issues no authorization.
Read the existing production-release-policy.md and protected-controller contracts.
Do not run ordinary deploy/migrate scripts to bypass coordinated147 admission.

## A. Read-only preflight

From a clean reviewed checkout with the intended controller source:

```sh
hostname
id
sudo -n true
git status --short
git log -1 --format='%H %an <%ae>'
python3 web/scripts/schema148_preflight.py VALIDATE_SOURCE
python3 web/scripts/schema148_preflight.py INSPECT \
  --expected-host '<approved-production-host>' \
  --expected-system-identifier '<approved-cluster-identifier>' \
  --database-container '<approved-container>' --database '<approved-database>' \
  --docker-sudo --environment production
```

Replace the placeholders from the independently approved private inventory.
The expected cluster identity is the privately observed baseline, not permission to accept
a changed cluster. A mismatch must be investigated, not bypassed by substituting
whatever identifier the command prints. Inspection includes only bounded READ
ONLY SQL, queue counts and hashed processing references. No provider outcome is
inferred. An empty queue inspection is transient; it does not prove fencing.

Verify actual serving app/controller/slot/schema from protected read-only records,
not Git HEAD. Inventory every retained/active notification process/container,
manual launch, alternate slot, Compose profile, boot actor, timer and supervisor.
The private inventory includes retained historical slots and unrelated workloads.
Treat stopped old slots as restart risks. Unknown ownership blocks admission.
Keep host/cluster/container/unit identities and raw reports in the approved private
operator workspace; they are intentionally excluded from this public PR.

Verify current backup/replica/restore evidence, free disk/RAM, network, locks,
roles/grants, exact migration history/structure and current-data roots. The source
preflight intentionally leaves these gates incomplete rather than inventing PASS.
Use `RECONCILE_REPORT` with the same explicit identity arguments for inspection
only. Preserve private evidence outside Git; do not export customer content.

Validate exact source and artifact CI. The non-mutating archive preparation is:

```sh
python3 web/scripts/fetch_schema148_artifacts.py \
  --run-id <accepted-artifact-run-id> --source-sha <accepted-application-SHA> \
  --output /home/madar/<new-private-artifact-directory>
```

This downloads/verifies archives only. It neither imports images nor grants
production acceptance. The protected admission requeries artifact and latest
exact-source backend/frontend CI. Bind native containerd manifest IDs, not the
build host's configuration IDs. Unknown image-store behavior refuses. Artifacts
expire after seven days; fresh accepted builds are required after expiry.

After integration209→210→211, run fresh locked artifact CI for the exact reviewed
integrated application source (workflow_dispatch if its PR branch filter no longer
applies). Current unmerged branch artifacts do not prove canonical-main admission.
The controller may have a separately reviewed exact source; its own CI is required.

## B. Maintenance preparation — independently authorized

No actions in this section were executed against production.

1. Independently approve maintenance window, expected notification delay/read-only
   interruption, business impact, accepted source/images/controller and exact
   immutable operation plan. Confirm customer-data privacy/rehearsal authority.
2. Review/install the source-bound controller through the existing protected
   installation mechanism. Do not overwrite installed controller files manually.
3. Complete privacy-safe current-data146 rehearsal and independent restore,
   all Auth/Storage roots and approved provider-writer/ingress quiescence (including
   volatile session/audit state), replica/backup evidence, compatibility and rollback
   limits. Synthetic reports here do not satisfy that acceptance.
4. Review the digest-bound notification cutover policy: every target legacy ID/image,
   candidate identity and supervisors. Exclude unrelated SDK consumers only through
   measured spec/image/target REST and cryptographic/live native proof. Never stop
   unrelated services. Disable/fence restart owners through the existing actor.
5. Drain owned old consumers; wait for in-flight external calls where practical.
   Review all processing rows, including expired/null leases. Preserve provider
   receipts and original DB evidence. Known accepted/known rejected/unknown require
   separately approved exact reconciliation. Unknown means BLOCKED. No blind reset,
   sent marking, deletion or grant restoration to unblock147.
6. Recollect fresh operational evidence; source PASS is not operational authority.
   Only the independent root issuer may create the operation's genuine approval
   and systemd credential through existing policy. Do not generate example tokens.

## C. Coordinated execution — existing protected coordinator only

The approved frozen entrypoint is
`web/scripts/continue_completed_normal_upgrade.py` in its measured root-owned source
package. Its modes are `preflight`, `execute`, `forward-preflight`, `forward-resume`,
`boot`, `proxy-gate`; source-package, approved-source and approved-plan are mandatory
exact digests/paths. Root isolated Python, immutable packet, existing locks,
protected receipts and fresh credentials remain mandatory. Bare invocation does
not authorize anything. No executable production command or approval was prepared
in this session because the required reviewed plan/authorization does not exist.

The existing actor must perform, in order:

1. Remeasure serving146/controller/history/source/artifacts/rehearsal/resource and
   backup preimages under the existing deployment/upgrade locks.
2. Prepare compatible candidate READ_ONLY and verify its exact core/health; fence
   owned origin worker, boot and write authority, establish maintenance and observe
   the existing multi-round READ_ONLY drain.
3. Seal live consumer/database quiescence; no processing, active foreign transaction,
   prepared transaction or queue lock. Perform protected backup/restore/replica gates.
4. Before each SQL entry, remeasure fresh authority/core/consumers/native schema.
   Apply exact147 then148 through the existing locked executor. Each migration
   has its own transaction/commit boundary; retain append-only journal/checksums.
5. Verify original-column public/all Auth/Storage roots, history/schema/RPC/grants,
   target readiness and accepted application behavior. Only then issue target
   NORMAL148, promote proxy/slot, activate owned protocol2 worker and complete
   post-deployment backup/acceptance through existing actor.

Never select old uncoordinated scripts, invoke production psql migrations directly,
edit historical receipts, replay consumed credentials or enable auto-deploy.

## D. Failure response

| Failure point | Required response |
|---|---|
| Before147 commit | Inspect DB/history and owned state. SQL rollback is proven only when DB confirms146. Consumed approval remains consumed. Existing actor decides safe origin restoration. |
| Lost connection/executor crash | Preserve journals and source/backup evidence. Actual DB schema controls committed progress; stale journal is not rollback evidence. |
|147 committed,148 absent/failed | Keep old workers and legacy grants fenced; maintenance/READ_ONLY. No rollback to unfenced source. Fresh reviewed forward-resumption scope/credential, not parent replay. |
|148 committed, no completion receipt | Keep READ_ONLY. Remeasure target state/preservation and repair forward through existing actor; never forge completion. |
| New worker/app/proxy startup fails | Withhold/revoke NORMAL as existing coordinator specifies. Preserve incompatible origin fencing after147. No ad hoc proxy promotion or legacy worker restart. |
| Provider accepted but acknowledgement failed | Preserve delivery generation/state and provider evidence. Do not resend or acknowledge unfenced; separately review at-least-once duplicate risk. |
| Source/checksum/image/authority/ownership mismatch | Stop that operation, preserve evidence, obtain corrected reviewed source/scope and fresh approval. Never retry blanket privileged effects. |
| Reboot/interrupted promotion | Compatible boot gate must validate exact schema/completion/grants/ownership. Missing evidence at147 stays fenced. Real full restart acceptance remains untested here. |

A SQL-only forward scope does not finish deployment or issue NORMAL. It cannot
restore a customer database or reuse old privileges. Database rollback after147
is not an application rollback plan. Explicit148-compatible application rollback
requires separately accepted images and existing authority.

## E. Post-deployment acceptance

After independent authorization and protected execution, verify exact schema148,
147/148 history/checksums, protocol2 function, revoked legacy finish/direct writes,
reservation locking and original data roots. Verify backend/frontend/controller
source and image identities, slot/proxy ownership, readiness and genuine worker
consuming authority. Exercise approved Auth/MFA, tenant boundaries, private/public
Storage and representative reservation/notification behavior with safe fixtures.
Observe ownership-loss/acknowledgement-failure counters, queue depth/age, retries,
dead letters, API errors/latency and resource pressure. Capture fresh backup and
required replica/restore evidence. No live billing transaction is part of this runbook.

## F. Final operator approval

This PR can provide TECHNICALLY VALIDATED evidence for specific synthetic scopes.
It is currently NOT READY as a complete production release. Only the existing
independently controlled approval and successful protected admission may authorize
production. A readiness JSON, CI success, draft PR, staging image import or this
runbook must never be interpreted as AUTHORIZED FOR PRODUCTION.
