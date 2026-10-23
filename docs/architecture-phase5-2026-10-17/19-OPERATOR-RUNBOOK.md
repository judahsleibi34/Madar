# Operator boundaries

## A. Read-only preflight

Verify machine, actual deployed schema/controller/serving source, current CI and
exact image digests; inspect known worker/provider/supervisor identities, both
queue processing states, deletion leases, active/idle/prepared sessions, locks,
backup/restore/replica and object scope. Use bounded metadata, not customer exports.
`python3 web/scripts/schema149_preflight.py INSPECT` checks source/evidence only.
No sourceSHA or healthy container substitutes for deployed-state proof.

## B. Maintenance preparation — future independent authorization required

Do not execute this production cutover now. Complete restricted provider adapter,
original-role backup integration, deletion ownership successor, privileged boot/
restart/current-data/replica rehearsal and independent source/artifact review first.
Reconcile every processing delivery AND outbox, including expired claims; preserve
unknown provider outcomes, never reset/delete rows to force admission.

## C. Future governed execution

Existing protected coordinator only; fresh exact-bound single-use approval/locks.
Positive probes precede persistent ingress/supervisor/object/role/session fences;
verified original-role backup and quiescent data/object snapshot precede147→148→149.
No intermediate NORMAL. Preserve sealed commits, roots, images and receipts. Only
independently accepted target/worker/provider/recovery gates can permit authority.
Current source deliberately rejects that production path before effects.

## D. Failure response

Beforecommit, SQL rollback may retain origin; after147/148/149commit, verify actual
schema/ACLs and repair forward with fresh authority. Keep incompatible workers
stopped. Lost responses never prove rollback. Do not replay approval, restore old
grants or automatically restore a customer backup. Preserve uncertain effects.

## E. Acceptance and final approval

ActualAuth/MFA/Storage/tenant/business/worker/queue/readiness and recovery checks
are required on exact accepted images. CODE REVIEW, technical operator readiness
and production authorization are distinct. No production authorization is issued.
