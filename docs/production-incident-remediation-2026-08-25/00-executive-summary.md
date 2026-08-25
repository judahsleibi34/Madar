# Executive summary

Madar production is healthy after a successful immutable blue/green promotion.

- Previous production SHA: `0eaa9edd297d2fd6618d50ae5dfc4b08c94ba1df`.
- Failed merged SHA: `eb22f736d1a3342b24413e6b4fa2884d4c62eb1c`.
- Active application SHA: `ab6844683d89f652e10edc0bc7fefd22791db75f`.
- Active slot: `blue`; retained compatible slot: `green`.
- Database: PostgreSQL 17, schema 83 after verified migrations 82 and 83.
- External frontend and API version checks pass.
- Readiness reports database, Redis, auth, storage, schema, MFA policy, workers, and queues healthy. Email, push, AI local execution, and remote ingestion are truthfully disabled.

The incident had four confirmed causes: the legacy deployer replaced the live stack in place; the hardened release required a dedicated `CSRF_SECRET`; the legacy path supplied mutable/default release identity; and production enabled remote URL ingestion without its required isolation boundary. The two-minute timer retried the same bad SHA because the legacy system had no durable bad-release circuit breaker.

The new controller builds immutable SHA-tagged artifacts, validates an inactive slot, attests schema compatibility and release identity, cuts workers over deliberately, switches traffic through a stable local proxy, retains known-good artifacts, serializes deployments, records durable state, and suppresses failed SHAs.

Two issues prevent a fully green operational handoff today:

1. The provider credential exposed during investigation has not yet been rotated. Its value is not repeated in this report.
2. Root authentication is required to install the tracked systemd units. The root unit remains legacy, so `madar-auto-deploy.timer` remains intentionally inactive. The legacy executable chain is bridged to the safe controller, but the old privileged storage-preparation drop-in and timer semantics must not be enabled.

Accordingly, the current release is healthy and the promotion was successful, but unattended deployment remains disabled and full production security readiness is **NO-GO until credential rotation**.
