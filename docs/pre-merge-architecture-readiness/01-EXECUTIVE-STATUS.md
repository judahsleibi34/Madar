# PR220 reduced-scope acceptance

The owner approved application architecture, integrity, security regression,
current-source staging and production isolation as the fixed acceptance scope.
See `ACCEPTANCE-SCOPE.json` for the measurable gates. Fresh synthetic staging
is separate from the unaccepted protected146→160 production operation.
Production controller completion and automation are deferred; existing source
and historical reports below are not claims of operational acceptance.

# Pre-merge engineering status — 2026-10-21

**ENGINEERING NOT READY FOR HUMAN CODE REVIEW.**

**Did the actual protected controller upgrade a preserved running schema-146
application to schema150? NO.** The operation remains unregistered and blocked.
This package records incomplete acceptance; it does not request merge or release.

Implementation commit `83dce3da2204980d5d89fc071cf1fc9fbe0b5cd0` corrects
migration-connection failure handling and an object-measurement refusal caused
by unrelated ancestor-directory activity. It does not complete the coordinator.
Published SQL, classification, workflow gates and protected authority remain intact.

Commit `48df165cd8767a92e02ca6b098da5f28c1915f1e` additionally fixes CI evidence
that regenerated a safer tail from an advanced fixture, and binds the generic
rehearsal's exact origin under the existing executor lock. Its74-case suite
passed (45source/model,29native PostgreSQL); this is not protected acceptance.

The decisive missing connections are listed in
[protected acceptance](04-PROTECTED-RELEASE-ACCEPTANCE.md). Native SQL and
component restoration passed within their stated scope. They do not substitute
for a running preserved-application release, independent protected handoff,
worker/proxy activation, or privileged crash/reboot acceptance.

PR220 must remain draft against main. Human review, repository protection,
external trigger verification and production authorization are separate gates.
See [the matrix](FINAL-VERIFICATION-MATRIX.json) and [merge safety](09-MERGE-SAFETY.md).
