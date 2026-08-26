# Supabase compatibility production promotion

Date: 2026-08-26 UTC

## Scope and credential safety

Commit `67aff17f4a521a01f87bd8ad76a570acaf07df9b` was promoted to production
without changing `SUPABASE_SERVICE_KEY`. The newly created replacement Secret
API key was not read, prompted for, tested, logged, or provisioned. The
production environment file remained mode `0600` with unchanged ownership and
modification time. No provider credential was revoked.

The existing pre-rotation server credential remained active throughout the
promotion. Local evidence established earlier in the campaign that this
credential is an older opaque Supabase Secret API key, rather than a JWT-shaped
legacy service-role key. This terminology correction does not change the
rotation plan: it is the exposed credential that must remain valid until the
operator provisions and verifies the replacement in a later phase.

## Candidate and validation

- Development branch: `builder-backend`
- Candidate: `67aff17f4a521a01f87bd8ad76a570acaf07df9b`
- Previous active release: `4faf63a67cbcfe884d3cbeeaa2f39ae9f0a37467`
- Database schema: `83` (unchanged)
- Focused compatibility/auth suite: 84 passed, 0 failed, network disabled
- Previously completed full backend suite on the exact candidate: 1,082 passed,
  0 failed, 0 external network attempts
- Frontend unit suite on the exact tree: 744 passed, 1 intentional skip
- Frontend lint: pass
- Production frontend build/API-origin audits: pass
- Migration mirror check: 83/83, 0 errors, 2 documented historical warnings

The inactive blue slot passed liveness, readiness, exact release identity,
schema compatibility, storage readiness, frontend HTTP, canonical production
API-origin validation, login-route CORS/controlled-error validation, and
read-only provider probes for PostgREST, RPC, Auth Admin, and Storage. Queue
consumers remained inactive during this candidate validation.

## Controlled promotion

The first switch attempt safely failed before traffic mutation because the
operator invocation omitted two switch-helper-specific variables:
`MADAR_TRAFFIC_SWITCH_DRIVER` and `MADAR_ACTIVE_UPSTREAMS_FILE`. The helper
therefore attempted its root-owned default path. The controller restored the
green workers, removed the failed blue candidate, recorded the failure, and
left green traffic healthy.

The existing proxy topology was inspected and the correct user-scoped contract
was verified with a no-op switch to green. The configured driver is
`docker-nginx`, the active upstream file is the existing protected Madar
user-state proxy path, and the proxy container is `madar-release-proxy`.

An explicit manual retry was then performed for the same reviewed SHA. Immutable
images were reused by digest, blue passed all gates, workers were handed off,
the proxy configuration was syntax-checked and atomically reloaded, and the
controller completed its observation window. The failed-release suppression
entry was cleared only after success.

## Final state

- Active slot: blue
- Active release: `67aff17f4a521a01f87bd8ad76a570acaf07df9b`
- Retained rollback slot: green
- Retained rollback release: `4faf63a67cbcfe884d3cbeeaa2f39ae9f0a37467`
- Schema: 83
- Active backend and all active workers: healthy
- Post-switch provider probes: PostgREST, RPC, Auth Admin, and Storage pass
- Public frontend: HTTP 200
- Public login invalid-payload probe: controlled JSON HTTP 422 from the API
  origin with exact allowed-origin CORS
- Unapproved-origin preflight: denied
- Severe active-container log patterns during the promotion window: 0
- `madar-auto-deploy.timer`: inactive
- Root systemd units: unchanged
- Remote push: none

No real account password was available or used. Consequently, the dashboard
shell and auth-provider/admin connectivity were validated, but no fresh real-user
authenticated dashboard session was created during this credential-safe phase.

## Decision

The opaque-key compatibility code is active in production and the existing
credential continues to work across the backend, workers, readiness/schema
probes, Auth Admin, Storage, PostgREST, and RPC. Production is ready for the
operator-controlled replacement-key provisioning phase. Provisioning, parallel
verification, and old-key revocation remain separate future actions.
