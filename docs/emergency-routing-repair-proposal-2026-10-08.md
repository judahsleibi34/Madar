# Madar emergency routing repair — awaiting explicit operator approval

Production has not been changed. Public frontend and backend last observed HTTP
502; proxy unhealthy. Fresh read-only plan created `2026-10-08T20:37:00.846824+00:00`.

**Exact source and authorization scope**

- Development checkout: `recovery/provider402-signin`, HEAD
  `7ca0a0241786a974d16b692a05250ed0ac18d8a1`.
- Fetched main: `be2925cf4dca5a185a2226860c453fce10248125`.
  Fetched recovery: `7ca0a0241786a974d16b692a05250ed0ac18d8a1`.
  Main-only / recovery-only: **0 / 1**.
- Sole unmerged recovery commit: `7ca0a024`, write-authority readability
  under the private launcher umask (4 runtime lines and 29 regression-test lines).
  No PR or merge conflict was found. Main already includes the bytecode,
  emergency-acceptance, SMTP, local-provider and fallback fixes.
- Recommendation: review and integrate that permission commit through a PR;
  separately review this emergency package and the existing uncommitted
  repeat-rollback changes. Do not promote the recovery branch or merge emergency
  authority code wholesale. No source history, branch, commit or remote was rewritten.
- This operation installs only the standalone emergency package; it imports none
  of the existing controller and deploys none of the other uncommitted changes.
- Package SHA256: `37c0277da599c28e2257eaa93d825dcf46cd87c0fd20aafe3bea690a1f3e07f0`.
- Fresh plan digest: `87842c3173fe1d6c479f5186d3d0ce59aedbf48cf46515282a925a8cd8365fb6`.
- Scope: `restricted-local-fallback-routing-only-v1`. Approval applies only to these exact
  source bytes, current bound original state and runtime identities. It persists
  across reboots while those bindings remain valid; changed state/identities or
  a new root-owned `revoked` marker deny new relay connections. No writable
  production or normal cutover authority is granted.

**Independent current observations**

| Item | Verified current value |
| --- | --- |
| Public frontend | HTTP 502 |
| Public API | HTTP 502 |
| Proxy | Running, unhealthy; host network |
| Actual registered backend | 10.254.202.5:8000, ready |
| Actual registered frontend | 10.254.202.4:8080, HTTP 200 |
| Current configured backend | 10.254.202.4:8000 — frontend container |
| Current configured frontend | 10.254.202.5:8080 — backend container |
| Database | Healthy native local Supabase; READ ONLY SQL schema query = 115 |
| Both protected transactions | local_rollback_active; original bytes/hash-bound |
| Write authority | READ_ONLY; backend recovery restriction and denied POST verified |
| Consumers | Six blue/green business consumers stopped, restart=no; all retained matching workers also stopped |

Registered backend container ID: `70aac7f4cc2a7308cef151c4fe4a08bbae1d74a09d7c539d008ecbd15024debd`. Actual backend image:
`sha256:2ee19aea2599c3e386c2cc9e249d0b7721b4ab3c3f01f5ab358ecdcb88353c8b`.
Registered frontend container ID: `b837ca68c2a1a4386b30e0a4dd3d1938fef117c0400140a6266ea878803813e7`. Actual frontend image:
`sha256:d931354f8c7f0cab2a7a9a0851fe107345147ff50fefb48b62bf7fd7d8b79c5a`.
Image revision labels, recovery contracts and readiness identity report
`be2925cf4dca5a185a2226860c453fce10248125`. Digest/identity agreement is independently verified;
this is not independent proof of historical image build provenance.

The plan independently inspects Docker identities, image IDs, configuration hashes,
role aliases/networks, backend/frontend availability, native Supabase configuration,
native database URL hosts/ports, read-only schema 115, transaction identity/state,
write authority and consumer inhibition. Configuration values containing secrets
are hashed, never copied into the report or new authorization. Missing old `/run`
credentials are neither read nor reconstructed.

Root cause: Docker reassigned role addresses after reboot, while persisted upstream
IP literals and the installed controller lack boot reconciliation. The frontend
also caches backend DNS at startup; the proposed include bypasses that cache on
API, uploads and existing legacy backend routes, retaining path rewrites, host
headers and the independently inspected frontend security policy.

**Evidence classification**

- VERIFIED: current observations and identities above; actual current-source test
  executions below. Existing checkpoint listed-byte checks are valid only for
  current file integrity.
- UNVERIFIED: historical operator-approval claim, independent current-source
  acceptance provenance of protected aggregate PASS records, and independent
  restore verification of extended checkpoint manifests.
- INCONSISTENT: an old HTTP-only script labeled browser connectivity PASS, and
  transaction receipts that describe rollback activation without today's correct
  public routing. These observations do not establish wrongdoing.
- INVALID applicability: treating an earlier restore report as proof of a later
  extended checkpoint, or earlier-source acceptance as authorization for these
  new source bytes.

The detailed preserved investigation is `docs/incident-response-2026-10-08.md`.
This fresh operation consumes **no historical PASS record**, checkpoint or old
activation receipt as its authorization. Its only authorization will be the
operator's explicit approval of this exact fresh source/plan scope, recorded with
actual issuance time in a new root-private namespace. Approval has not yet been
received; no authorization record has been created.

**Exact proposed production operation and affected resources**

1. Execute the hash-gated bootstrap below after approval. It verifies source/plan
   digests before executing reviewed bytes as root, then repeats all live checks.
   Any changed bound input, image, container configuration or transaction refuses
   the operation. No reused `/run` credential, independent-test summary or expired
   installation witness participates.
2. Create `/var/lib/madar-control-plane/emergency-routing/87842c3173fe1d6c479f5186d3d0ce59aedbf48cf46515282a925a8cd8365fb6/`
   (root-private): immutable approved `repair.py`, plan, fresh authorization,
   status, exclusive audit records and exact routing preimages.
3. Create and enable `madar-emergency-routing.service`, and add only
   `/etc/systemd/system/madar-release-proxy.service.d/90-emergency-routing.conf`.
   Run `systemctl daemon-reload` and `systemctl enable --now
   madar-emergency-routing.service`. The existing installed controller is unchanged.
4. The relay listens **only** on 127.0.0.1:29401 (backend) and :39401 (frontend).
   Each new connection checks the fresh authorization and all bound live recovery
   conditions, then resolves the verified container's **current** address. No
   Docker IP is cached or published. A proxy startup gate rejects changed approval
   state or stale routing after reboot. Changed container IDs/images fail closed;
   a recreated container requires another explicit authorization.
5. Under existing deploy/runtime locks, preserve exact original
   `/var/lib/madar/proxy/active-upstreams.conf` bytes in the new attempt directory.
   Validate the complete candidate with the pinned production Nginx binary using
   a temporary `/tmp/madar-emergency-preflight-*.conf` inside **only the proxy**;
   remove that temporary proxy file afterward. Recheck identities immediately
   before atomic fsync publication of the approved include. The include uses
   stable relay ports plus Nginx's loopback :39402 frontend router. Validate
   `nginx -t` again before `nginx -s reload` in `madar-release-proxy`.
6. Verify public portal/API root 200, backend and frontend `/api` readiness,
   source identity, recovery restrictions, denied write probe, proxy health and
   unchanged original protected inputs. Record actual outcome in the new audit.
   Stop incident work after availability restoration; do not start normal cutover.

The candidate include and complete validated Nginx configuration are preserved in
`.incident-response/emergency-routing-2026-10-08/nginx-route-v3.conf`.
The installed files are new and exclusive; collisions refuse installation.
Old transactions, credentials, receipts, manifests, customer volumes and database
contents are never overwritten by this operation. No application service is
rebuilt or restarted. The only application-facing reload is the release proxy.

**Expected customer impact and rollback**

Successful publication restores frontend and API traffic to the existing
restricted local fallback. Auth/read paths remain governed by the existing
application; business writes remain 503-fenced and consumers remain stopped.
Fresh validation on every relay connection adds temporary latency and Docker/
read-only SQL inspection load. Connections stream without request/payload logging;
concurrency and service resources are bounded. Temporary boot/runtime failures
return 503 rather than forwarding to unchecked endpoints.

On publication, reload or public-verification failure, preserve all new artifacts
and exact prior route bytes. Revalidate current identities: restore the exact
previous include only when it is a verified safe route. Today's reversed include
is retained as evidence and is **not safe to reactivate**. Otherwise atomically
publish the reviewed loopback Nginx 503 maintenance include, validate/reload and
observe 503 on both stable endpoints. If compensation or maintenance observation
fails, close the startup gate, disable restart **only for madar-release-proxy** and
stop that proxy; record critical failure if stopping also fails. These narrowly
scoped compensation actions are part of the proposed approval. No DB restore,
transaction reset, volume/container deletion or consumer change is used.
A failure before route publication leaves the original routing unchanged and
records failed installation; retained new artifacts require review before retry.

Revocation or removal of the helper alone is not a safe availability rollback:
it deliberately causes 503. Package/unit retirement or another routing plan
requires a separate reviewed operation. This proposal does not authorize manual
restoration of the known broken include or removal of evidence.

**Actual validation and its limits**

- Final-source backend CI: **2165 tests**, **237 skipped**, exit 0, no external
  network attempts; current checkout mounted read-only in a retained CI image,
  disposable container with `--network none`. This includes all 24 focused new
  emergency tests covering the required trust, reassignment and failure cases.
- Real isolated Nginx syntax validation: candidate route and maintenance PASS.
  An initial test-container cache mount failure is retained; corrected disposable
  cache configuration passes. Nothing was loaded in production.
- Real isolated Nginx routing smoke: API prefix stripping, callback route, uploads,
  legacy site/store/forms rewrites and frontend root PASS against loopback mocks.
- Systemd unit/drop-in syntax PASS, without installation/reload.
- Dependency, migration-source, transition, forward-release and secret checks PASS;
  no SQL migration executed. Two known historical duplicate-content warnings.
- `git diff --check` PASS.

Logs, exact CI command, source hashes, exit status and fresh plan are retained in
`.incident-response/emergency-routing-2026-10-08/`. These are development validation
records, not protected production acceptance. No real reboot, container restart,
proxy reload or write attempt at a business endpoint was performed in production.
The POST fence probe targets a nonexistent path and must be denied before routing
or business code; all SQL is explicitly BEGIN READ ONLY / ROLLBACK.

**First production-changing command — do not execute before approval**

Replace the approval placeholder only with the actual explicit operator response,
using shell-safe quoting. The command text is fixed; no development shell script
is sourced or run with privilege. The first production write occurs only inside
the verified install after its fresh live checks pass.

```bash
cd /opt/madar-development/repository
sudo /usr/bin/python3 -I -B - '<exact operator approval received>' <<'PYBOOTSTRAP'
import hashlib, io, json, os, sys
from pathlib import Path
source = Path('/opt/madar-development/repository/web/deployment/lib/emergency_routing_repair.py')
proposal = Path('/opt/madar-development/repository/.incident-response/emergency-routing-2026-10-08/final-plan.json')
code = source.read_bytes()
packet = json.loads(proposal.read_bytes())
expected_code = '37c0277da599c28e2257eaa93d825dcf46cd87c0fd20aafe3bea690a1f3e07f0'
expected_plan = '87842c3173fe1d6c479f5186d3d0ce59aedbf48cf46515282a925a8cd8365fb6'
if hashlib.sha256(code).hexdigest() != expected_code:
    raise SystemExit('reviewed_code_changed')
if hashlib.sha256(json.dumps(packet, sort_keys=True).encode()).hexdigest() != expected_plan:
    raise SystemExit('reviewed_plan_changed')
approval = sys.argv[1]
if not approval.strip() or approval == '<exact operator approval received>':
    raise SystemExit('explicit_operator_approval_required')
os.environ.clear()
os.environ.update(PATH='/usr/sbin:/usr/bin:/sbin:/bin', LANG='C.UTF-8', LC_ALL='C.UTF-8')
sys.argv = [str(source), 'install', '--approved-plan', expected_plan,
            '--operator-approval-text', approval]
sys.stdin = io.StringIO(json.dumps(packet))
exec(compile(code, str(source), 'exec'), {'__name__': '__main__', '__file__': str(source)})
PYBOOTSTRAP
```

Remaining normal-production blockers: independent historical authorization and
extended-checkpoint restore provenance review; governed active-transaction repair
and permission fix integration; normal writable-production acceptance and explicit
approval. None is waived by this routing-only authorization.
