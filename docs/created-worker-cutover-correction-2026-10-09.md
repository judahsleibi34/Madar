# CREATED-worker cutover correction and retained-candidate continuation

The consumed attempt `75bbd2a64e5a62387e3844561c690a5b98d37edd3fa6934002b00b48b83bee90`
created a restricted green candidate before failing at
`DetachedRecoveryCandidate.verify_recorded_runtime()` with
`detached_network_attachment_changed`. An independent read-only execution of
its frozen verifier reproduced that error. The corrected measured verifier
validated the same retained resources, local DB/Auth/Storage/schema checks,
frontend, source identity and denied business operations without modifying them.
The three business standbys were genuinely CREATED with empty runtime NetworkID
values. Existing Docker bridge identities and network declarations were intact.

The lifecycle-specific correction retains exact container/image/specification,
network-name/object and role-alias checks before startup. Only CREATED, never-
started business workers may omit runtime endpoint IDs. After governed startup,
all actual NetworkIDs must be populated and match. A new exclusive plan/CID-bound
start intent prevents an unauthorized start after ownership publication. Docker
also changes HostConfig.OomKillDisable from false to null on first startup;
the verifier permits only that observed equivalent transition for started
business workers, comparing against the original hash without editing receipts.
True, changed identities/images/configuration/mounts and other alterations fail.

Real disposable Docker tests use a shell-only container from the accepted image,
three isolated internal networks, no customer/provider connectivity, no host
ports or credentials. They exercise actual CREATED/RUNNING/stopped lifecycle,
network reassignment, aliases, unexpected attachments, altered specification and
premature-start rejection. Only these exact test fixtures are removed afterward.
Synthetic regressions supplement those observations and are not acceptance proof.

## Retained candidate

The original six containers, bridge, authority and protected records remain.
The candidate is bound to application revision
`2009d8d2e2b8fa492231725118206ba83f844f75`; its acceptance is not transferable to a
new revision. Its detached backend/frontend currently own green 8201/3200.
The new continuation binds the original plan/authorization/journal/contract/
identities/READ_ONLY-authority hashes as data, requiring precisely the three
pre-publication authorized/pending/failed events and unchanged recovery inputs.
It independently verifies the old exact resources and never-started consumers.

Under NEW explicit authorization and both deployment locks, a new exclusive
retirement receipt permits stopping only the unpublished frontend, backend and
parser by exact ID, in that order. This frees their detached ports while the
registered emergency fallback continues serving. Nothing is deleted, no old
receipt is changed, and the three old business workers remain CREATED. Actual
free sockets are then mandatory before creating a NEW exact-source candidate
using the shared preflight/staging resolver, green 8201/3200 and a new free bridge
(current read-only observation: 10.253.2.0/24). Unknown or changed ownership fails.
Stopped prior port declarations are usable only when individually hash-bound.
An interrupted or failed attempt is consumed; it is never automatically replayed.

## Remaining-stage lifecycle review

* Controller installation follows sustained public READ_ONLY candidate handoff;
  no old /run credential is reconstructed. The emergency installation remains
  until the new governed handoff, with current-data fallback compensation ready.
* Public routing validates Nginx before reload and requires bounded sustained
  convergence; worker readiness is not required before intentional startup.
* Single-owner handoff checks exact stopped retained resources before rename,
  preserves their names/resources and records ownership before worker start.
  Start intents are exclusive, and post-start identity/network/read-only/health
  verification completes before the normal grant.
* Final write-authority publication follows source fence/reconciliation,
  controller/routing/native DB and standby checks. Schema stays 115, migration
  policy none, no customer DB restore. The NORMAL grant remains the last gate.
* Backup configuration moves to the native local provider only through normal
  finalization. Original timer states remain idle until fresh normal backup,
  independent restore and append-only Node 1 replication complete.
* Boot validation binds stopped-after-start IDs before startup, then requires
  full running attachments/readiness before restoring normal authority. Failed
  compensation may stop exact bound workers using the same narrow metadata
  comparison; it cannot issue write or start authority.

A final approval proposal requires passing CI, new immutable package/source/image
bindings, independently executed exact-image acceptance and exact-plan read-only
preflight. This engineering record grants no production authority and is not a
substitute for that proposal. Original checkpoint/restore, MFA and historical
acceptance evidence remain preserved under their original bindings.
