# PR220 implemented scope split

The owner-approved criteria are fixed in `ACCEPTANCE-SCOPE.json`. Application
architecture, integrity, security regression, fresh current-source staging and
production isolation are the only acceptance workstreams in this PR.

## Retained together

Canonical157 delivery fencing,158 reservation capacity,159 outbox fencing and160
deletion ownership remain byte-identical with their SQL mirrors, reconciliation
inventory, protocol2 clients and native concurrency/rollback tests. Main001–156
and historical architecture SQL archives remain unchanged. Calendar domain SQL,
cache/security fixes, backend authority validation and credential isolation stay.

## Minimum staging

`full_provider_staging.py FRESH_APPLICATION` initializes a newly identified,
owned empty database through canonical160. It keeps the real main-to-source plan
and its Class D classification in evidence; it never substitutes HEAD as a fake
base. Exact-source CI/artifact verification and resource/actor/configuration
checks remain. The twelve-service fixture includes native Auth/Rest/Storage,
application/frontend/Redis, notification/deletion and calendar-sync workers.
Only the backend receives the pinned authenticator calendar SQL transport.
`REHEARSE` still rejects Class D before effects; fresh acceptance explicitly
reports that existing-database upgrade acceptance is absent.

## Deferred without unsafe blanket reversions

No new maintenance coordinator, issuer, profile registration or activation is
implemented. Existing unregistered `_execute_maintenance` code and provider,
backup/handoff/boot helpers are retained inert because native/source validators,
root-lock checks, artifact capture and historical profiles share those files.
`schema160_release.admitted_manifest()` still refuses; ordinary manifest loading
refuses the new and superseded histories; automatic dispatch remains false.
Completing the installed guards/inventory producer, real protected preserved-data
upgrade, independent receiver/restore, target handoff, proxy/reboot recovery and
automation belongs in a subsequent release PR. Passing modeled controller cases
remains supporting historical evidence and is not PR220 staging acceptance.

Published commit anchors: application/calendar `3d35e418`, `88075814`,
`2b9663fe`; canonical reconciliation `21e6f831`, `0bd06575`, `196f60c4`;
shared/controller preparation `976c3cbd`, `8da6bbb8`, `1f72e150`, `b0c58bcd`,
`326688c3`, `47857fbc`. These are mixed commits, not whole-commit revert units.
No published history, remote branch or original author is rewritten.

## Merge isolation boundary

The active production release descriptor remains144→146. Repo workflows have
read-only credentials and no production deployment step. Installed controller
provenance/guard and timer observations are recorded privately. External
main-push/merge webhooks, Apps, Vercel and other pollers require actual repository
administrator visibility; missing visibility is a merge blocker, not proof that
no trigger exists. No production mutation, merge or automation activation occurs.
