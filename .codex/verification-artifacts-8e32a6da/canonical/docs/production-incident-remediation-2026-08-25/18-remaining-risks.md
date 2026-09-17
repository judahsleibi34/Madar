# Remaining risks

## Immediate operator actions

1. **Revoke the superseded exposed provider key.** Madar production and its
   rollback slot have already been rebuilt and validated with the replacement
   key. The old individual provider key is no longer used by Madar, but its
   provider-side revocation remains an operator action.
2. **Resolve optional Cloudflare script injection.** The edge adds an inline
   Cloudflare block and Browser Insights source that strict Madar CSP blocks.
   Prefer disabling the optional Cloudflare feature. Any CSP expansion requires
   explicit operator approval and should be minimal.

## Operational hardening

- The immutable root control plane is installed and its timer is enabled after
  a manual no-op and three timer no-ops. A controlled shared-host reboot drill
  is still recommended when an approved maintenance window is available.
- `/home/madar/update-madar.sh` is an unreferenced historical manual script
  containing the former in-place Compose workflow. It has no systemd/cron
  authority; retire or archive it during controlled operator housekeeping so
  it cannot be used accidentally.

- Docker build cache is 103.6 GiB with 78.16 GiB reclaimable. Use the checked-in threshold/known-good-aware procedure; never broad-prune active or rollback images.
- Swap is nearly allocated after intensive build/test activity. Current available RAM is adequate, but continue host-pressure monitoring and schedule a controlled cache/process review.
- Production backup freshness is not yet wired into application readiness, although the pre-migration backup itself is verified.

## Authorized deferrals

- 12 real tenants still require authorized commercial mapping; no plans were assigned.
- Dedicated off-host backup media and a full replacement-host restore remain blocked on hardware arrival.
- Payment gateway and unrelated roadmap features remain out of scope.
