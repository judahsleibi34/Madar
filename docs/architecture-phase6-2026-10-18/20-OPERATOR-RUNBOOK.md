# Future operator runbook — do not execute production cutover

## A. Read-only preflight

Verify host/environment identity,actual schema/current release/controller/source,
main and dependency ancestry,exact accepted CI/artifacts,migration mirror hashes,
current backup/restore/replica evidence and all consumer/writer/supervisor ownership.
Inspect delivery,outbox,deletion request/step processing states,leases,idle/active
sessions,locks and prepared transactions with bounded metadata-only queries.
Preserve private evidence. Unknown identities or ambiguous provider effects block.
Do not treat146Git metadata as proof of actual deployment,or expired processing
leases as proof that no external provider acted. Do not reset/delete queue rows.

## B. Maintenance preparation — independent authorization required

Before any approved maintenance,the concrete protected provider adapter,backup/
boot/write-handoff integration and privileged interruption acceptance must be
implemented and independently reviewed. The150 profile remains unregistered and
cannot currently execute a production operation. Establish independent review,
main protection,artifact acceptance,maintenance window,business impact,operator
approval and reconciled processing work. Every pre150 boundary also rejects ANY
nonterminal legacy deletion request,even pending/waiting_retry with no live lease;
unknown old external outcomes and lost original freeze state cannot be inferred
from idle status. A separately approved reconciliation must close that backlog;
never reset/cancel it merely to unblock admission. Preserve original roles/services/ingress/
object-writer preimages durably before effects. Never infer role defaults.

## C. Intended coordinated execution — existing controller only

Once engineering gates are actually closed:positive native credential/scope probes
first;arm persistent boot restriction;fence ingress,supervisors,object writers and
roles;drain identified established sessions;verify queues/locks/prepared work;
verify backup/restore/replica;execute captured authenticated147,148,149,150bytes
under the approved operation;verify every committed boundary and preservation.
Intermediate147/148/149 remain READ_ONLY. After150,start providers privately with
recorded original role state while ingress/workers/boot stay fenced and target
write grant is absent;run native probes;existing protected handoff establishes
fresh accepted150authority;only then start accepted workers,restore ingress and
clear boot restriction. This sequence is a design,not a runnable production recipe.

## D. Failure response

Before each SQL commit,rollback preserves previous committed schema;after a lost
COMMIT response,observe actual database state independently. Never infer rollback.
After any committed fencing migration,do not restore legacy consumers/broad old
grants or activate an incompatible app. Preserve maintenance,journals,preimages,
backup/images and actual schema evidence. Forward continuation needs independently
valid fresh authority;consumed approval is not replayed. Unknown external intent
requires evidence/reconciliation,not blind destructive resend. Automatic database
restore is not ordinary rollback and may overwrite newer customer data.

## E. Post-release acceptance

Verify actual150/2/2/2,source/image/runtime hashes,health AND worker consumption,
Auth login/refresh/MFA/AAL2,CSRF,private/public Storage/object integrity,tenant
isolation,notification enqueue/resolve/deliver,retry/ownership loss,deletion full
workflow/resumption,reservations/order/payment invariants,queue age/dead-letter,
errors/latency,current backup and independent restoration. Healthy containers alone
are insufficient. Do not use live payments or customer deletion as smoke fixtures.

## F. Final independent decision

TECHNICALLY VALIDATED and AUTHORIZED FOR PRODUCTION remain separate states.
No tool in this source/report self-issues the latter. This session leaves the
production runbook unexecuted. Ordinary source/staging work does not need repeated
permission;production maintenance,controller install,write authority and promotion
each remain independently controlled under existing release policy.
