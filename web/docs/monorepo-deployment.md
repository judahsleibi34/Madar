# Production monorepo deployment

This page is a short operator orientation. The complete, maintained release
acceptance and migration contract is
[`docs/production-release-policy.md`](../../docs/production-release-policy.md).
Read that policy and the current implementation before changing production
deployment behavior.

## Current Node 2 layout

```text
MADAR_PRODUCTION_REPO=/srv/madar/production
MADAR_ENV_FILE=/etc/madar/production.env
MADAR_DEPLOY_STATE_ROOT=/var/lib/madar/releases
MADAR_STORAGE_ROOT=/var/lib/madar/storage
MADAR_PROXY_CONFIG_ROOT=/var/lib/madar/proxy
MADAR_CONTROL_PLANE_ROOT=/opt/madar/control-plane/deployment
```

The production checkout is a source and Git reference. Accepted application
releases run from detached immutable worktrees below the release-state root;
the active blue/green slot is never rebuilt in place. Persistent uploads and
generated files live below the storage root and are mounted into release
containers. The root-owned controller under `/opt` is the sole authoritative
auto-deploy controller. Its tracked path values are installed from
`web/deployment/production-paths.conf`.

The Compose CLI must receive the immutable release's `web` directory as its
project directory, the release Compose file plus the installed release
override, and `/etc/madar/production.env` as its environment file. Operators
must not run an in-place Compose rebuild from the production checkout or move
release state to a new directory.

## Control-plane installation

Install only through the reviewed
`web/deployment/bin/madar-install-control-plane` procedure in an approved
maintenance window. It requires the auto-deploy timer and service to be
stopped, backs up the installed controller and legacy entrypoints, publishes
an exact root-owned `/opt` tree with a source-SHA provenance marker, retires the
old `/usr/local/lib/madar/web/deployment` controller, reloads systemd, and
leaves the timer stopped for operator review. Never update the provenance
marker or isolated installed files by hand.

## Database migrations

Traffic promotion and SQL execution remain separate safety phases. A release
must first pass immutable build, compatibility, rollback, preflight, deep
validation, worker cutover, traffic switching, observation, and durable
`known_good` acceptance while the source schema is serving. Only an explicitly
opted-in expand/forward-compatible release may then enter the separately
locked, backup-first automatic migration coordinator. That coordinator pins
checksums, verifies a complete release/schema-bound backup, applies only a
contiguous manifest under a PostgreSQL advisory lock, and revalidates the
serving bridge and workers. A partially advanced schema is forward-repaired;
it is never hidden by a traffic rollback to an incompatible application.

The reviewed explicit `madar-migrate` path remains available for releases that
do not opt into automation. Neither path permits production SQL from a mutable
checkout or without the documented backup, manifest, release-identity, and
schema-transition gates.

## Commercial-entitlement setting

`COMMERCIAL_ENTITLEMENTS_ENFORCED=false` remains the temporary compatibility
setting for environments that have not completed payment-gateway and
commercial-tenant assignment rollout. It changes commercial capability
enforcement, not authentication, tenant isolation, permissions, MFA/AAL2, or
canonical billing data. Restore `true` through the protected production
environment and a normal reviewed release when that rollout is complete.

## Local development

From `web/`, use an explicit non-production environment file with
`docker-compose.yml` and `docker-compose.dev.yml`. Development defaults and
historical incident documents do not redefine the production path contract.
