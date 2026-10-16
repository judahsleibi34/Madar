# Dedicated native integration staging

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
python3 web/staging/integration/worker_recovery.py
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
the API/worker/frontend on an already initialized146 database without replaying
SQL. It never advances a populated schema automatically.

`smoke.py` creates native synthetic Auth/TOTP/Storage/notification fixtures and
checks actual API MFA admission, denied AAL1 admin access, rejected CSRF,
single-use pending sessions, private object denial and worker processing.
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
history to146 via the selected learning143 branch, excluding142. It refuses a
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
