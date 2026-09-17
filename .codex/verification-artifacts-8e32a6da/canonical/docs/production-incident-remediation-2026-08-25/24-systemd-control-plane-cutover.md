# Immutable systemd control-plane cutover

## Outcome

The legacy root auto-deploy loop is retired. The effective root service invokes
the reviewed immutable blue/green controller, and unattended deployment is GO
after one manual and three timer-driven production no-ops.

## Application-equivalent main

- `origin/main`: `2f8ecf99bfdfaca2d9fff479be9efcddada66969`;
- active application release: `67aff17f4a521a01f87bd8ad76a570acaf07df9b`;
- active slot: green;
- prepared rollback slot: blue, same schema-83-compatible release;
- runtime delta from active release to main: none;
- complete delta: three incident-report files only.

The controller deterministically treats this as application-equivalent and
does not build or promote a release merely to align a documentation merge SHA.
The production checkout was safely fast-forwarded to main.

## Installation verification

Installed root files:

- `/etc/systemd/system/madar-auto-deploy.service`;
- `/etc/systemd/system/madar-auto-deploy.timer`;
- `/etc/systemd/system/madar-release-proxy.service`;
- `/usr/local/sbin/madar-auto-deploy`;
- `/usr/local/lib/madar/web/deployment/` (reviewed controller, manifests, and
  proxy definitions).

The installed wrapper/service/timer matched their reviewed development files.
The controller directories are `root:madar` mode `0750`; executable files are
root-owned. The old service drop-in and `docker_auto.sh` no longer exist at
their former live paths.

Effective settings:

- service user/group: `madar:madar`;
- working directory: `/home/madar/saas/Madar`;
- lock: `/home/madar/.local/state/madar/releases/deploy.lock`;
- release state: `/home/madar/.local/state/madar/releases/state.json`;
- traffic switch driver: `docker-nginx`;
- upstream state:
  `/home/madar/.local/state/madar/proxy/active-upstreams.conf`;
- cadence: first run two minutes after activation, then two minutes after the
  previous service becomes inactive, plus at most 20 seconds randomized delay.

## No-op evidence

Manual no-op:

- 2026-08-26 11:18:10–11:18:12 UTC;
- result: success;
- action: application-equivalent checkout fast-forward only.

Observed timer cycles:

| Cycle | UTC | Result | Runtime effect |
| --- | --- | --- | --- |
| 1 | 11:27:19–11:27:22 | success | none |
| 2 | 11:29:29–11:29:31 | success | none |
| 3 | 11:31:49–11:31:51 | success | none |

For every cycle the active SHA and slot, all backend/frontend/worker/proxy
container IDs, release-state checksum, prepared-rollback checksum, upstream
checksum, schema 83, readiness response, and frontend HTTP 200 were unchanged.
No build, migration, worker handoff, proxy reload, traffic switch, or retry loop
occurred.

## Lock and circuit breaker

The controller uses a non-blocking `flock` on the durable `deploy.lock` file.
Focused controller tests passed 39/39 and prove overlapping-run rejection,
lock release, durable failed-SHA recording, same-SHA suppression, eligibility
of newer SHAs, explicit manual retry, active-target preservation on candidate
failure, rollback, and interrupted-run recovery. Production failed-release
state was not poisoned for this validation.

## Legacy retirement

No Madar cron entry, user timer, second enabled root timer, or unit reference to
the old live-rebuild path was found. `/usr/local/sbin/madar-auto-deploy` has no
Compose, source reset, or historical rebuild behavior and delegates only to the
immutable controller.

The unrelated/unreferenced `/home/madar/update-madar.sh` remains as a historical
manual script. It is not called by systemd or cron and has no automatic
authority. It should be archived or retired in a controlled housekeeping step,
not used for production deployment.

## Reboot safety and rollback

The timer is enabled at boot and is the sole enabled Madar auto-deploy timer.
Docker is enabled; the release proxy has `unless-stopped`; and the deployment
service orders itself after Docker and wants the proxy service. Release and
proxy state reside on persistent host paths. Static reboot safety therefore
passes. A controlled reboot drill is recommended at a future maintenance
window because this shared production host was deliberately not rebooted.

If the systemd control plane itself must be rolled back, stop and disable the
timer first, preserve current release state, verify a protected backup manifest,
restore only the intended root files, daemon-reload, inspect effective units,
and repeat the manual no-op gate before any timer enablement. Never restore the
legacy in-place deployment loop as an unattended path.
