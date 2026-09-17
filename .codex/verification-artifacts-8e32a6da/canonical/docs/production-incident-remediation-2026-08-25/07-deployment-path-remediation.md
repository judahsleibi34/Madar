# Deployment path remediation

The production release controller now provides:

- exact Git SHA source verification and detached release worktrees;
- immutable backend/frontend SHA tags plus image IDs and OCI revision/creation labels;
- deterministic, non-overlapping blue/green networks and loopback ports;
- inactive candidate startup without shared queue consumers;
- schema/version/readiness/frontend validation before switch;
- exact production frontend API-origin build arguments, immutable origin label,
  and a running-bundle origin check before switch;
- deliberate notification, calendar, and schema-gated deletion-worker cutover;
- stable local Docker-nginx traffic proxy on ports 8001/3000;
- atomic proxy configuration replacement, nginx config test/reload, and stable identity verification;
- retained previous slot and immutable artifacts;
- nonblocking deployment lock, durable checkpoints, interruption recovery, and failed-SHA circuit breaker;
- no `git reset`, mutable `latest` authority, or rollback rebuild.

Inactive services are force-recreated so a slot retained from an older Compose
topology cannot be restarted against a deleted legacy network. This guard was
added after the first corrective candidate safely failed before switch on such
a stale Redis network attachment.

The final active application images carry SHA `4faf63a6...` and exact recorded image IDs. Backend-derived workers intentionally share the immutable backend image and use distinct commands.
