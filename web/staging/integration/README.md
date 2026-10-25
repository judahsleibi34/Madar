# Dedicated native integration staging

## Private canonical160 transport on synthetic schema146

`private_provider_transport.py` runs only in an otherwise empty disposable
guest, not in the accepted staging application. It requires an expiring,
root-owned mode0600 `/etc/madar-disposable-test.json` matching its measured DMI
UUID, with `disposable: true`, `production_authority: false`, and `expires_at`
(UTC ISO8601), plus an active `codex-test-isolation.service`. Provision and
independently bound the guest lifetime before running it. The marker grants no
release or write authority. The canonical repository must be at the exact SHA;
download its authenticated CI artifact package to
`/opt/madar-development/evidence/integration/artifacts-<first12-of-SHA>`.

```bash
python3 web/staging/integration/private_provider_transport.py \
  --source-sha <exact-40-character-commit> \
  --guest-uuid <owned-disposable-guest-DMI-UUID> \
  --artifacts /opt/madar-development/evidence/integration/artifacts-<first12-of-SHA>
```

The fixture initializes only an empty, marked schema146 database from captured
Git SQL. It never executes migrations147–160. Real Auth/REST/Storage, Redis,
parser, backend and the accepted frontend image's private gateway have bounded
resources and no published host ports. PostgreSQL is reachable from the backend
only through that gateway. Synthetic login, TOTP/AAL2, token rotation, private
object bytes/anonymous denial, REST, calendar grants and wrong-cluster refusal
are tested inside the accepted backend image. The actual gateway runtime must
also pass the controller's strict configuration verifier.

The fixture also creates two designated tenant/account/private-object fixtures,
then exercises the source-owned installed observer's actual account probes and
PostgreSQL material digest before and after restarting the native providers.
The same original passwords, verified factors, relationships and private bytes
must survive; the backend must regain private gateway/calendar connectivity.
Native addresses are measured again after restart. Its compact receipt binds
the harness/observer bytes separately from the accepted application image SHA.

Every exit unwinds owned containers, networks and disposable data volumes,
including ordinary termination signals. Failure logs are private; compact
receipts distinguish this connectivity fixture from a protected upgrade.
Imported/pinned images are explicitly retained only within the expiring guest
for reuse; the provisioning owner must remove its disk after testing. SIGKILL
or guest loss relies on that independent host watchdog and teardown. No result
from this fixture establishes original-state migration preservation, independent
recovery, write handoff, public activation or schema160 operational admission.

This separate harness runs **only on `madar-staging`** and never reads production
environment files. It uses native GoTrue, PostgREST and Storage with PostgreSQL17,
Redis and the candidate API/notification worker. It is distinct from the retained
schema81/83 synthetic gateway harness in `web/staging`.

Copy the tracked committed source to the VM. Import the exact images named in
`compose.yaml`, plus the Dockerfile base application image, if the VM remains
offline. Exporting immutable images from another host is read-only; do not copy
container writable layers, production volumes or environment files.

Run as `staging-admin` from that source tree:

```bash
python3 web/staging/integration/manage.py prepare --source-sha <exact-40-character-commit>
python3 web/staging/integration/manage.py up
python3 web/staging/integration/manage.py schema
python3 web/staging/integration/manage.py status
python3 web/staging/integration/smoke.py
python3 web/staging/integration/tenant_smoke.py
python3 web/staging/integration/worker_recovery.py
python3 web/staging/integration/redis_failure.py
python3 web/staging/integration/restore.py
```

Capture the SHA using `git rev-parse HEAD` at the source before transferring it.
The private runtime is `~/madar-hardening-20261016`, with generated credentials,
database marker and ownership record. Never put it in Git. `prepare` refuses an
existing runtime. Install host OpenSSL for the generated seven-day self-signed
TLS identity. Build the frontend first with `npm ci` then
`MADAR_REQUIRE_PRODUCTION_API_URL=true VITE_API_URL=/api npm run build` and copy
`web/frontend/dist` to the corresponding source path on the VM.

Native provider ports publish only at127.0.0.1:18081; the frontend uses
127.0.0.1:18080 (HTTP) and127.0.0.1:18443 (TLS). PostgreSQL and Redis have no
published ports. Only the proxies also join an owned ingress bridge with IP
masquerading disabled: Docker suppresses published ports on internal-only
containers. Application/data services remain exclusively internal. All services
have bounded resources and logs. Auto-confirmed synthetic email identities
are staging fixtures; external email, push, OAuth, payments and AI are disabled.
The source-overlay Dockerfile verifies dependency constraints and `pip check`;
it does not replace the regular fresh locked CI build.

After transferring a newer committed source archive, preserve credentials/data
and select that exact source with `manage.py up --source-sha <new-commit>`.
Partial source/configuration identity mismatches reject before Docker mutation.
Base application/dependency image IDs are checked before building. `up` restarts
the API/worker/frontend on an already initialized148 database without replaying
SQL. It never advances a populated schema automatically.

`smoke.py` creates native synthetic Auth/TOTP/Storage/notification fixtures and
checks actual API MFA admission, denied AAL1 admin access, rejected CSRF,
single-use pending sessions, private object denial and worker processing.
`tenant_smoke.py` creates two synthetic tenants and verifies native authenticated
builder ownership, cross-tenant404, spoofed user403 and ordinary-user admin403.
`redis_failure.py` verifies memory/noeviction/network bounds, briefly stops only
the owned Redis, checks login503 and degraded readiness, then restores it in
`finally`. Run these drills serially, outside performance measurement.
`worker_recovery.py` pauses only this worker, tests lease/retry/dead-letter SQL
within a rolled-back transaction, then resumes it.

`restore.py` briefly stops only this project's synthetic writers. It saves
private database/object archives, restores a NEW database and object volume,
compares all public/Auth/Storage tables, sequence states and file hashes, and
restarts the original services in `finally`. Restored copies and evidence stay
under this project's names for review. This is same-cluster component recovery;
it does not prove PITR, offsite recovery or complete restored-app acceptance.

For a measured comparison, transfer an exact baseline Git archive into an owned
directory named `baseline`, then run:

```bash
python3 web/staging/integration/benchmark.py --baseline-source ~/architecture-hardening-20261016/baseline
```

This uses60 requests/four clients per selected endpoint, private synthetic
cookies, and equally bounded temporary baseline API/proxy services. It removes
only those temporary services afterward. It never follows HTTP redirects or
uses environment HTTP proxies. Do not run other test load concurrently.
The default PostgreSQL2CPU/768MiB and Auth1CPU/192MiB limits reflect observed
quota pressure in this four-vCPU VM. The benchmark records CPU throttling and
query IDs/costs (never query text); pg_stat_statements is staging-only. Sixty
requests cannot establish a stable production p99 or a capacity limit.

For browser verification, forward ONLY loopback18443 to this VM's18443 with
`ssh -F ~/.ssh/config -o ExitOnForwardFailure=yes -L 127.0.0.1:18443:127.0.0.1:18443 -N madar-staging`.
Copy only the synthetic `smoke-fixture.json` to a mode0600 local temporary file.
With frontend Playwright dependencies/browser installed:

```bash
MADAR_STAGING_BROWSER_HOST=madar-staging node web/staging/integration/browser-smoke.mjs /private/synthetic-fixture.json
```

The browser accepts this staging self-signed certificate explicitly, checks the
real Secure/HttpOnly/SameSite login/MFA cookies and admin API, then tests a mobile
login viewport. Its desktop context blocks external network hosts. This limited
flow does not replace the repository's full authenticated Playwright suite.

`schema` accepts only a fresh marked owned database and rehearses immutable
history to148 via the selected learning143 branch, excluding142. It refuses a
second initialization. Existing shared staging databases are never selected.
Do not use this command for production migrations or claim it grants production
migration/release authority. Private Docker errors can contain generated staging
credentials: inspect them on the VM and sanitize evidence before sharing.

Stop only the owned project, preserving named volumes and credentials:

```bash
python3 web/staging/integration/manage.py down
```

The harness checks labels before teardown and rejects unowned resources. There
is deliberately no broad cleanup or automatic volume deletion command. Full
production parity additionally requires external delivery, OAuth, all workers,
durable application filesystem mounts, TLS/edge routing and governed release
acceptance; those are not implied by successful startup.


## Explicit synthetic146→148 follow-up

This follow-up worker requires protocol2/schema147; the branch harness targets148.
The historical `madar-hardening-synthetic-146` comment remains an ownership marker,
not a claim about the current version. `up` refuses an older populated schema;
it does not silently migrate or start the new consumer against146.

After verifying the exact committed source/archive and the owned madar-staging
project, run `python3 web/staging/integration/upgrade_notifications.py`. This
validates both source-pinned candidates, pauses only the owned synthetic writers,
refuses any processing delivery, retains a private logical backup and records
committed147/148 checkpoints. It verifies original application/Auth/MFA/Storage rows and sequences across SQL, excluding only the new generation field when starting at146 and core schema state. It leaves those writers stopped on success. A failure
may restart the original writers ONLY if the database remains146; after147 it must
remain stopped for forward repair. Re-running resumes147 or recognizes148 without
replaying committed SQL. No automatic requeue or production path exists.

Then `manage.py up --source-sha <exact-new-sha>` builds the source-overlay image,
verifies target148 before publishing148 runtime compatibility, and starts the new
API/worker. Run smoke.py and worker_recovery.py against the actual native provider.
Restore evidence reads the observed schema instead of a hardcoded146. A fresh
`prepare`/`schema` initializes to148 directly; production still requires its separate
reviewed controller admission, maintenance/backup gates and approval.
