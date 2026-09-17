# Executive summary

Madar production is healthy after a successful immutable blue/green promotion.

- Previous production SHA: `0eaa9edd297d2fd6618d50ae5dfc4b08c94ba1df`.
- Failed merged SHA: `eb22f736d1a3342b24413e6b4fa2884d4c62eb1c`.
- First promoted SHA: `ab6844683d89f652e10edc0bc7fefd22791db75f`.
- Current active application SHA: `67aff17f4a521a01f87bd8ad76a570acaf07df9b`.
- Active slot: `green`; prepared compatible rollback slot: `blue` at the same
  schema-83-compatible application SHA.
- Database: PostgreSQL 17, schema 83 after verified migrations 82 and 83.
- External frontend and API version checks pass.
- Readiness reports database, Redis, auth, storage, schema, MFA policy, workers, and queues healthy. Email, push, AI local execution, and remote ingestion are truthfully disabled.

The incident had four confirmed causes: the legacy deployer replaced the live stack in place; the hardened release required a dedicated `CSRF_SECRET`; the legacy path supplied mutable/default release identity; and production enabled remote URL ingestion without its required isolation boundary. The two-minute timer retried the same bad SHA because the legacy system had no durable bad-release circuit breaker.

The new controller builds immutable SHA-tagged artifacts, validates an inactive slot, attests schema compatibility and release identity, cuts workers over deliberately, switches traffic through a stable local proxy, retains known-good artifacts, serializes deployments, records durable state, and suppresses failed SHAs.

## Post-promotion login regression and correction

Live browser testing found that the first promoted frontend sent login to its
own origin at `https://madarportal.com/api/auth/login`, which returned frontend
HTML with HTTP 405. The immutable builder had not passed `VITE_API_URL` into the
frontend Docker build, so Vite compiled the client fallback `/api`.

Release `4faf63a6...` fixes the build contract, rejects a missing or incorrect
production API origin, records it in immutable image metadata, and makes the
candidate controller scan the running frontend bundle before promotion. The
live bundle now contains `https://api.madarportal.com`; login resolves to
`https://api.madarportal.com/auth/login`. Credential-free preflight returns 200
with exact-origin CORS and a controlled empty login POST returns JSON 422. The
old `/api/auth/login` string is absent from the live bundle.

## Credential and control-plane completion

The replacement Supabase server credential is active in production and the
prepared rollback slot; the exposed old individual key is no longer used by
Madar. Provider-side revocation of that superseded key remains an explicit
operator action.

On 2026-08-26 the root-owned legacy auto-deploy systemd path was replaced by
the reviewed immutable controller. One manual no-op and three real timer no-ops
completed without changing application/worker/proxy container IDs, release
state, rollback preparation, schema, or traffic. The timer is enabled and
active. Unattended immutable deployment is technically **GO**; the remaining
commercial mapping, physical-media DR, and future payment work remain separate
authorized prerequisites/deferrals.
