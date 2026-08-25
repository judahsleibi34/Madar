# Remaining risks

## Immediate operator actions

1. **Rotate the exposed provider credential.** The credential has not been revoked or rotated. Do not repeat it in tickets, logs, or commands. Follow the previously supplied provider-specific rotation order, update every confirmed consumer atomically, restart/recreate Madar services in a controlled slot promotion, verify auth/database behavior, then revoke the old credential.
2. **Install the root control-plane units.** The timer is currently inactive but enabled at boot. Until a root operator applies the tracked installer and validates a no-op, keep it stopped and avoid rebooting; disabling the legacy unit or replacing it with the tested unit is required.

## Operational hardening

- Docker build cache is 103.6 GiB with 78.16 GiB reclaimable. Use the checked-in threshold/known-good-aware procedure; never broad-prune active or rollback images.
- Swap is nearly allocated after intensive build/test activity. Current available RAM is adequate, but continue host-pressure monitoring and schedule a controlled cache/process review.
- Production backup freshness is not yet wired into application readiness, although the pre-migration backup itself is verified.

## Authorized deferrals

- 12 real tenants still require authorized commercial mapping; no plans were assigned.
- Dedicated off-host backup media and a full replacement-host restore remain blocked on hardware arrival.
- Payment gateway and unrelated roadmap features remain out of scope.
