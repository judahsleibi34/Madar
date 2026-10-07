# Provider402 sign-in recovery

This profile is separate from ordinary deployment, automatic migration,
forward repair and schema recovery. Merely merging this source never activates
it. The installed controller guard continues to require privileged review.

`MADAR_RECOVERY_PROFILE=provider402-signin` selects an application-enforced
positive allowlist. All unreviewed routes, including GET/RPC routes, return 503
`provider_recovery_read_only`. Only existing-user Auth/session/MFA operations,
health/status, existing account/tenant/project reads and mediated assets are
admitted. Account lifecycle provisioning, implicit website-settings creation,
admin impersonation, signup, email reset, MFA enrollment/removal and uploads
remain unavailable. Existing tenant and AAL2 checks still run. SDK egress
additionally denies provider writes except reviewed session/security operations
inside the admitted Auth request context. No business table or RPC write is
approved. Workers refuse startup even when their normal enabled flag is true.

The recovery transaction in `web/deployment/lib/provider_recovery.py` requires
an independently collected, exact-SHA contract. Both hosted Auth and REST must
actually return 402; source schema must be 115. Unknown or unrelated readiness
failures stop recovery. Stale hosted-era backup freshness is permissible only
with a newly verified local checkpoint, without changing the old marker. Local
Auth/REST/Storage, image provenance, private network, loopback ports, linkage,
AAL2, isolation, write fence and a live local-compatible rollback runtime must
all validate before any mutation. Release schema and rollback ranges are
exactly 115, migration policy/class `none`, with no manifest key present.

The state machine owns deploy/runtime locks, writes a durable separate interlock
before candidate work, requires workers inhibited in both slots before traffic,
and writes explicit `RECOVERY` worker authority. Normal deployment and migration
credentials cannot take over this operation. Errors preserve the interlock and
select only the attested local rollback runtime. A process crash requires
operator diagnosis; there is no unattended retry or automatic recovery exit.

Rollback changes runtime/routing only and reuses the current local database and
Auth sessions. Never restore an old database checkpoint over sessions accepted
since recovery activation, and never use hosted HTTP as the fallback. Synthetic
test-account cleanup remains deferred.

## Activation boundary

The application fences and transaction library alone do not authorize a
production adapter or controller bootstrap installation. Production activation
must remain blocked until a protected adapter collects fresh evidence, binds
its one-time credential to this profile and rehearsal, prepares a live local
fallback without replacing serving production, and exercises the existing
protected traffic driver. Human exact-image login/MFA tests are also required.
A fake operations adapter or past human tests are not evidence for production
activation. No command should be improvised to bypass the installed guard.
