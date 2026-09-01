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

For a reviewed environment-only change to the currently active immutable
release, stop the auto-deploy timer and use the installed controller's explicit
mode:

```bash
/opt/madar/control-plane/deployment/bin/madar-release-deploy \
  <exact-known-good-sha> --refresh-active-runtime --slot <active-slot>
```

The installed command loads the root-owned production path contract itself.
It refuses a SHA, slot, schema, image, core-health, Compose, secret-hygiene, or
storage mismatch before recreating anything. It uses existing images only,
restores parser/queue workers if absent, performs no migration or traffic
switch, and requires full slot and stable-route validation before recording
success. Do not invoke raw production Compose as a config-refresh substitute.

The Compose CLI must receive the immutable release's `web` directory as its
project directory, the release Compose file plus the installed release
override, and `/etc/madar/production.env` as its environment file. Operators
must not run an in-place Compose rebuild from the production checkout or move
release state to a new directory.

## Normal and protected releases

A normal release is merged to `main` and handled by automatic deployment. A
release that changes protected control-plane paths is deliberately different:

```text
merge to main
→ provenance guard blocks non-root deployment
→ operator obtains the exact 40-character origin/main SHA
→ operator authorizes one transaction
```

```bash
sudo madar-control-plane-upgrade <exact-40-character-sha>
```

The command validates healthy production, the pinned Git remote and exact
fast-forward SHA; quiesces automation; creates protected immutable staging;
runs installer dry-run and apply with a root-owned backup; performs one
canonical deployment; attests stable/active identity, readiness and migration
terminal state; performs a deterministic same-SHA cycle; and restores the
timer's original enabled/active state. Inspect the same transaction without
mutation with:

```bash
sudo madar-control-plane-upgrade --dry-run <exact-40-character-sha>
```

Audit JSON/logs are stored under
`/var/lib/madar-control-plane/upgrades/history`. Controller backups are stored
under `/var/lib/madar-control-plane/backups`. This root-controlled sibling is
separate from application-owned `/var/lib/madar`. An initially disabled timer stays
disabled. A pre-install failure restores the original timer state only after
the old controller and serving release re-attest. A post-install or
post-promotion failure leaves the timer disabled; post-promotion/schema repair
is forward-only and never triggers an automatic traffic or database rollback.

The full trust model and phase semantics are in
[`docs/control-plane-upgrade-architecture.md`](../../docs/control-plane-upgrade-architecture.md).

Do not manually pull `/srv/madar/production`, run migration SQL, switch
blue/green traffic, hand-copy control-plane files, edit provenance/release
state, or re-enable the timer after a failed post-promotion transaction without
diagnosis.

### One-time bootstrap

The first release containing the upgrader cannot be installed by a command that
does not yet exist in the trusted controller. It therefore requires one final
use of the existing approved exact-SHA manual installation procedure: quiesce
the timer/service, build a root-protected exact-SHA worktree, run
`web/deployment/bin/madar-install-control-plane` dry-run, create the protected
backup, apply as root, attest provenance/path contract/health, run the
controlled deployment and same-SHA check, then restore automation. That install
places `/usr/local/sbin/madar-control-plane-upgrade`. Future protected releases
must use the one-command workflow.

Use a unique bootstrap backup below
`/var/lib/madar-control-plane/backups`, not below application-owned
`/var/lib/madar`. Dry-run performs the complete shared static preflight and
must pass before apply; apply repeats it before creating the mode-0700 upgrade
state hierarchy or backup.

Never update the provenance marker or isolated installed files by hand.

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
