# Next actions

## Required before launch

1. Obtain authorized commercial decisions for all 12 production tenants, review the mapping dry-run, and apply only the approved canonical states.
2. Install the dedicated encrypted backup drives using the prepared mount-identity checks, verify off-host copies, and complete a full isolated replacement-host restore.
3. Recover Node 1 operational headroom: preservation-aware Docker cache cleanup, reduce swap pressure, and repeat the capacity snapshot.
4. Approve retention policy for audit, billing, analytics/webhook, form/quiz/reservation, and deletion-evidence classes; configure and verify it.
5. Connect the selected production alert transport and prove end-to-end delivery without exposing secrets.
6. Execute the production promotion checklist in a controlled maintenance window; do not install the staging topology verbatim.

## Before enabling optional integrations

- Implement and mock-test Microsoft provider-side grant revocation before enabling Microsoft calendar.
- Review provider credentials, OAuth scopes/callbacks, outage policy, and deletion behavior for each integration.
- Give any future payment gateway a separate threat model, webhook idempotency/replay, settlement reconciliation, and operational readiness review.

## Near-term evidence improvement

- Run an overnight staging soak and record resource/queue/database growth.
- Rebaseline thresholds after cache/swap maintenance and after first controlled customer cohort.
- Continue periodic dependency, secret, migration-parity, restore, and adversarial tenant-isolation drills.
