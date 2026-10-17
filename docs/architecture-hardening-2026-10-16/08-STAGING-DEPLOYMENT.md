# Reproducing and operating the native staging candidate

The executable procedure is `web/staging/integration/README.md` and guarded
`manage.py`. It is separate from `web/staging`'s historical synthetic facade.

1. Verify `ssh -F /home/madar/.ssh/config -o BatchMode=yes madar-staging
   'hostname; id; sudo -n true'`. Explicit-F avoids this host's system SSH config
   ownership error. No SSH ownership/security relaxation was made.
2. Transfer a **new directory** from `git archive <exact-sha>`; do not overlay
   deleted/renamed source files onto an earlier test tree. Build frontend with
   exact `npm ci`, production API guard and `/api`; copy dist to that source tree.
3. Import pinned native images and the attested application/frontend bases if
   offline. Do not import production volumes, environments or writable layers.
4. On first use, `manage.py prepare --source-sha <40hex>` generates a private
   owned runtime. It refuses existing paths and any hostname except madar-staging.
5. `manage.py up` starts DB/Redis, checks the synthetic database comment BEFORE
   native provider migrations, then native Auth/REST/Storage. `manage.py schema`
   initializes only a fresh marked database via immutable SQL to146, excluding
   branch142 in favor of the selected143 history. It rejects repeat initialization.
6. For existing146 data, `manage.py up --source-sha <newsha>` preserves credentials
   and records source changes; partial binding mismatches reject before Docker.
7. Run `smoke.py`, `tenant_smoke.py`, `worker_recovery.py`, `redis_failure.py`,
   `restore.py` serially. These create synthetic data and briefly pause only
   their explicitly owned project components. Never run them on production.
8. Use `manage.py status` plus application readiness and smoke assertions. A
   container marked up is insufficient acceptance evidence.
9. `manage.py down` stops/removes only owned project containers/networks while
   preserving volumes/private evidence. There is deliberately no volume purge.

Final deployed source is0c591b8fc790246936df6d370ebe455f46a17cd2
at `~/architecture-hardening-20261016/revisions/<sha>`. Its application code is
identical to the fully tested/benchmarked27860bf2; subsequent changes wire CI and
correct inherited image provenance labels. Readiness and eight orchestration
safeguards passed after the final rebuild. Later report-only commits do not alter
application code. The fresh archive avoids a stale renamed test left in a
development overlay. Runtime and image revision/release labels bind the selected
source; the old dependency base is recorded separately. See sanitized
`evidence/staging-final-status.json`.

All native smoke results are summarized in09-TEST-RESULTS.md and sanitized
`evidence/`. Private full logs and synthetic credentials remain on the VM.
Initial attempts caught a wrong source SHA before application startup, YAML
flow-list tmpfs parsing, native ownership/grant setup, Docker internal-port
behavior and restore helper permissions/stdin issues. They were fixed and rerun;
they were not relabeled successes.

## Browser and routing scope

Loopback TLS18443 was forwarded over SSH; Chromium accepted the staging-only
self-signed certificate explicitly. Native password/TOTP/admin login, private
cookie attributes and a mobile login viewport passed. Frontend-to-backend `/api`
routing is real. The frontend public-domain build default still differs from the
backend hardening.test tenant domain, so full published/custom-domain tenant
browser parity remains unverified. Existing full Playwright tests lack required
published-form fixture/environment inputs and were not reported as passing.

## Backup/recovery scope

`restore.py` stops owned synthetic writers, checks all source table/sequence
fingerprints, makes private archives with SHA256, restores a new DB and a new
owned object volume, compares data and MFA factors, then restarts originals in
`finally`. Copies/logs remain for inspection. Failed attempts are retained as
private diagnostics. No source/customer data was restored over an existing DB.
This uses the same cluster/roles and does not meet a full-system DR gate.

## Parity limitations

Native provider compatibility is substantially stronger than the old facade.
It is still not production parity: SMTP/push/OAuth/live payments/AI/Realtime,
additional workers, durable managed application filesystem, full public tenant
routing, edge TLS and production release admission remain separate gates.
No live billing transaction or production auth-provider cutover was attempted.
