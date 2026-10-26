# Historical release investigations, October 2026

This is a sanitized source-reconciliation record, **not a production runbook or
authorization**. It reconciles [PR #195](https://github.com/judahsleibi34/Madar/pull/195)
with [draft PR #220](https://github.com/judahsleibi34/Madar/pull/220) and reviews
15 previously untracked release documents dated October 10–12. Their descriptions
of production, backups, images and approvals are historical author-reported
observations. This consolidation does not independently rerun those operations,
validate their current applicability or transfer acceptance to another source.

## Source decisions

PR #195 has four published commits, retained on its original branch:

- `d30ca718c03185670b43cb29f39d43b99a44ea7b`: selected-profile runtime and dispatch validation; restricted routing repair.
- `86980686150dae63a7f54b9bf29413e08bd8fa45`: stopped-origin continuation and synthetic transport tests.
- `cd584b410e2c8ede231a764bf7063bf6d095a52a`: manual manifest marker binding and one exact pre-SQL continuation.
- `126481e3456abd75b14f93a3a2c5eaf92dd3a99f`: mirrored SQL fixture coverage.

Targeted integration preserves the newer controller rather than merging the old
tree over it. No published commit is rewritten. Every changed file is reconciled:

| PR #195 file | Disposition in #220 |
| --- | --- |
| `docs/production-release-policy.md` | Current policy retains stronger source/authority requirements; links this historical record and explains the manual marker scope. |
| `docs/control-plane-upgrade-architecture.md` | Current architecture retained; historical repair is documented as inactive, not a new operational path. |
| `web/deployment/bin/madar-release-deploy` | Already dispatches using the selected profile's exact range, target and exclusions; original regression test carried forward. |
| `web/deployment/lib/completed_normal_runtime.py` | Already validates the complete contract and selected profile; original range, exclusion and authority-mount tests carried forward. Newer stopped-candidate checks remain. |
| `web/deployment/lib/completed_normal_migration.py` | Restore the missing metadata-only `bind_manifest` fix: the immutable manual `STAGING` marker binds to the authorized candidate, only for the existing 136→144 profile excluding142. |
| `web/backend/tests/test_completed_normal_manual_deploy.py` | Add the exact manual dispatch/bad-range regression. |
| `web/backend/tests/test_completed_normal_runtime.py` | Add the historical manual-model and negative authority cases without replacing newer lifecycle/security tests. |
| `web/backend/tests/test_completed_normal_staging_manifest.py` | Carry forward the real mirrored-manifest fixture, plus dropped-exclusion, added142 and unregistered150 rejection tests. |
| `web/scripts/recover_completed_normal_read_only.py` | Archived only; pinned one-shot routing repair is not installed, imported by active tools or generalized. |
| `web/scripts/continue_retained_normal_upgrade.py` | Archived only; its frozen receipt/controller dependencies cannot authorize a new operation. |
| `web/scripts/retained_normal_continuation_child.py` | Archived only; no new stopped-origin worker adoption path is activated. |
| `web/scripts/retained_normal_live_write_probe.py` | Archived only; no public login, Auth-admin action or profile mutation is executed. |
| `web/backend/tests/test_retained_bridge_routing_recovery.py` | Retained with the historical source; executed privately with synthetic runtime responses. |
| `web/backend/tests/test_retained_normal_continuation.py` | Retained with the historical source; synthetic ownership, replay, source and transport tests only. |

The four historical tools and their two test modules remain recoverable from the
original Git branch and verified private source copies outside Git. Their exact
frozen context, public endpoints, package loaders, stopped-origin assumptions and
live-write capabilities make them inappropriate as current active helpers. Their
model tests do not certify a complete recovery, privileged installation or reboot.

Manifest binding changes **metadata only**. It follows existing authenticated
manifest/SQL loading and fresh protected admission. Backup, READ_ONLY authority,
lock ownership, exact migration ordering and single-use journal checks remain.
The historical legacy profile cannot adopt `STAGING`. No schema-150 profile is
registered and no old approval gains authority over a later release.

## Document review and historical lessons

All 15 originals remain untracked and unchanged in the independent development
checkout. Private copies, original SHA256/ownership/mode/timestamp records,
security review and disposition mappings are retained in the development
inventory. No complete original was approved for unchanged public inclusion.
Operational bindings, credential-file references, customer identifiers, backup
locations and unverified production-result details are intentionally omitted here.

| Original document basename | Disposition / safely retained subject |
| --- | --- |
| `completed-normal-upgrade-prerequisite-proposal-2026-10-10.md` | MERGE_INTO_EXISTING_DOC: distinct application/controller identities and missing-checkout assumptions. |
| `emergency-existing-green-routing-proposal-2026-10-10.md` | SUPERSEDED: older routing proposal, not current permission. |
| `normal-writable-production-schema115-actual-result-2026-10-10.md` | PRIVATE_EVIDENCE: reported historical production result, not current acceptance. |
| `normal-writable-production-schema115-retained-green-proposal-2026-10-10.md` | SUPERSEDED: historical exact-operation proposal. |
| `schema115-136-upgrade-baseline-2026-10-10.md` | MERGE_INTO_EXISTING_DOC: stored authority is not observed runtime health; preserve post-backup data. |
| `schema115-normal-boot-restoration-proposal-2026-10-10.md` | SUPERSEDED: exact old boot resources and approval scope are not reusable. |
| `schema136-current-data-acceptance-results-2026-10-10.md` | PRIVATE_EVIDENCE: reported restore/application results have their own source and scope. |
| `schema136-immutable-release-production-proposal-2026-10-12.md` | MERGE_INTO_EXISTING_DOC: newer main is provenance, not permission to substitute accepted application/controller bytes. |
| `schema136-production-upgrade-proposal-2026-10-12.md` | SUPERSEDED: replaced by the historical immutable-selection proposal, not reapproved here. |
| `schema144-boot-order-replacement-preflight-2026-10-12.md` | MERGE_INTO_EXISTING_DOC: failed preflight must block and preserve the consumed attempt. |
| `schema144-maintenance-interlock-retry-proposal-2026-10-12.md` | MERGE_INTO_EXISTING_DOC: exact failed-attempt reconciliation requires fresh independent authority. |
| `schema144-maintenance-production-cutover-proposal-2026-10-12.md` | SUPERSEDED: earlier plan predates boot/interlock corrections. |
| `schema144-retained-candidate-readonly-recovery-proposal-2026-10-12.md` | MERGE_INTO_EXISTING_DOC: restricted availability is distinct from NORMAL and durable recovery. |
| `schema144-retained-candidate-readonly-recovery-result-2026-10-12.md` | PRIVATE_EVIDENCE: reported routing result cannot authorize migration or worker activation. |
| `university-demonstration-final-status-2026-10-10.md` | PRIVATE_EVIDENCE: separate synthetic demo and production are distinct; access details stay private. |

The merged lessons are constraints, not claims that historical proposals ran:

- Keep application, controller, SQL and image identities distinct and authenticated.
- Observe live health and effective authority; a stored NORMAL declaration or
  healthy private candidate does not authorize traffic or worker consumption.
- Preserve current data and consumed attempts. A failed operation requires a new
  exact scope; do not replay approvals or restore older data as ordinary rollback.
- READ_ONLY availability, logical restore, full application recovery and actual
  boot acceptance are different evidence categories. Do not upgrade one into another.
- Bind compatibility to the validated profile, including the historical exclusion
  of142. A manifest placeholder is not independent execution authority.

## Current unresolved gates

The complete protected146→150 application upgrade remains **INCOMPLETE / NOT
READY**. Full Provider Staging already refused the main-base146→150 plan at
baseline `a371ba1fe2eccb781562596344e451f297309ad7` because it correctly requires
Class D review. That classification and workflow remain unchanged. Historical
schema115/136/144 documents and these source tests do not resolve either blocker,
authorize production, activate automatic deployment or change active release metadata.
