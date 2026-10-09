# Madar emergency routing retry — fresh approval required

No retry operation has been executed. Production routing remains HTTP 503
maintenance; the installed relay is active and the proxy is running/unhealthy.
The existing protected package, authorization, status, audits, original preimage,
service and 90 drop-in remain unchanged. This proposal applies only to the current
registered restricted local-compatible fallback. No routing architecture change,
application-image rebuild, database restore/migration, worker start or write grant
is included.

**Confirmed failure and source correction**

The actual proxy error at 20:51:33 UTC identifies old worker PID 22 connecting to
`10.254.202.5:8080` for the first frontend root GET and returning 502. That is the
old reversed upstream. Nginx master PID 7 received the candidate SIGHUP in the
same second. Root requests returned 200 at 20:51:34, before compensation's next
SIGHUP and observed 503 at 20:51:35. Original code called verify_public immediately
after sending reload and checked the frontend root before its proxy-health wait.
These logs and control flow establish that the failing request used an old
worker's configuration during asynchronous reload; the original generic failure
record contains no richer exception detail.

The source now places candidate validation, final identity verification,
publication, reload, convergence and final integrity checks inside one **180-second
hard wall-clock watchdog**. Every command and HTTP request also receives the
remaining monotonic budget. Nginx syntax is validated before reload. The on-disk
route must remain exactly approved. A successful identity response on the intended
loopback frontend router `127.0.0.1:39402/api/health/version`, absent during current
maintenance, establishes that a worker loaded that routing configuration.

Every convergence round independently checks exact Docker container/image and
configuration identities, schema 115, native local connectivity, protected
transaction identity, write fencing, stopped consumers and the preserved helper
installation. It then checks frontend/API roots, frontend `/api` and backend
readiness/version/recovery, denied POST fencing, and proxy health. Only explicit
HTTP 502/503/504 or connection availability failures are transient. Wrong identity,
transaction, fence, malformed successful response, unauthorized response or
unready/missing registered fallback aborts immediately. Three consecutive complete
successful rounds spanning at least five seconds are required; transient failure
resets the success streak. A 502/504 on the denied-POST probe is a transport failure; a successful write or invalid fence response remains fatal. No single successful GET can produce PASS.

Failure records add fixed stage names, exception class names and monotonic elapsed
time, without copying exception messages, credentials, request data or DB values.
Audit-storage failure cannot prevent compensation. New retry boot gating requires
completed success; an installing or failed retry remains blocked.

**Frozen source, plan and independent basis**

- New package SHA256: `2bc41971b5f8db7c8ddf32449f812d916a997099fa8d67646514743fc4305a14`.
- New canonical plan SHA256: `cca3c29eae4a720243497a9bc7a351f76d17d321b40a9279431e8f932347fbae`.
- Plan observed at: `2026-10-08T21:16:30.641769+00:00`.
- Previous approved package: `37c0277da599c28e2257eaa93d825dcf46cd87c0fd20aafe3bea690a1f3e07f0`.
- Previous plan: `87842c3173fe1d6c479f5186d3d0ce59aedbf48cf46515282a925a8cd8365fb6`.
- Current maintenance preimage SHA256: `81255d772e3d2b28ee07f6036b9a80fbc7685f6d67134690acc2bfeb2a83f8b8`.
- Development branch/HEAD: `recovery/provider402-signin` /
  `7ca0a0241786a974d16b692a05250ed0ac18d8a1`; no branch integration or deployment
  of unrelated uncommitted changes is proposed.

The fresh plan binds independently inspected runtime identities and original
protected inputs, plus 14 exact preserved installation/service/drop-in file
hashes. It checks the original helper's actual isolated Python argv, active
systemd state and ownership of both loopback listeners, and refuses unknown
proxy startup drop-ins. The relay remains authorized to run its unchanged source
under its original narrow authorization. That prior authorization **does not**
authorize this changed retry source, new plan or publication; fresh operator
approval of the above exact hashes is mandatory. Disputed historical PASS,
checkpoint and restore records are not used.

The independently verified backend remains `10.254.202.5:8000` (image
`sha256:2ee19aea2599c3e386c2cc9e249d0b7721b4ab3c3f01f5ab358ecdcb88353c8b`);
frontend remains `10.254.202.4:8080` (image
`sha256:d931354f8c7f0cab2a7a9a0851fe107345147ff50fefb48b62bf7fd7d8b79c5a`).
Stable routing and per-connection role resolution remain exactly the original
reviewed architecture. Both transactions remain local_rollback_active;
local Supabase is healthy, schema 115, business writes disabled and all six
canonical consumers stopped. Current public frontend/API both return 503.

**Exact proposed retry and affected resources**

1. Execute the fixed bootstrap below only after fresh approval. Hash-check source
   and canonical plan before privileged compile/exec. Recheck original installation,
   listener ownership, maintenance preimage and all live recovery conditions.
   Any mismatch or existing retry namespace/drop-in refuses installation.
2. Exclusively create a sibling root-private namespace:
   `/var/lib/madar-control-plane/emergency-routing/cca3c29eae4a720243497a9bc7a351f76d17d321b40a9279431e8f932347fbae/`.
   It contains the new reviewed source, fresh plan and explicitly issued
   authorization, new status, audits and attempt preimages. Never overwrite or
   append to the old namespace. New issuance timestamps are actual current time.
3. Exclusively add
   `/etc/systemd/system/madar-release-proxy.service.d/91-emergency-routing-retry.conf`
   and run `systemctl daemon-reload`. This additive reviewed drop-in resets only
   the old effective ExecStartPre gate and installs the new package's gate; old
   files stay byte-identical. Existing helper service/listeners remain running;
   no service restart, helper replacement, new relay, credential reconstruction
   or volatile-authority refresh is needed.
4. Under existing deploy/runtime locks, preserve exact current maintenance bytes
   in the **new** attempt namespace, validate candidate configuration using the
   production Nginx binary and isolated temporary proxy `/tmp` config, and recheck
   identities immediately before atomic/fsync publication of the unchanged stable
   routing include. Validate again and reload only `madar-release-proxy` Nginx.
5. Converge within the 180-second window and record sustained verified recovery,
   public HTTP 200 results and fence/consumer restrictions. The original helper
   keeps resolving container roles on every new connection, so stale Docker IPs
   are never introduced. After restoration, stop; no normal writable cutover.

**Customer impact, compensation and rollback**

Current maintenance continues until the new Nginx workers activate. Successful
retry restores frontend/API HTTP 200 through the existing restricted fallback;
existing tenant/MFA/database authorization and write fencing remain enforced.
No customer-data write, restore, schema change or background-consumer start occurs.
Read-only verification adds temporary inspection load; the unchanged relay keeps
its original bounded connection validation and resource limits.

A deadline or genuine failure enters the existing compensation path under a
separate **60-second watchdog**. Restore the exact current maintenance preimage,
validate/reload Nginx and observe 503 on both stable endpoints. Unsafe upstreams
are never reactivated. If compensation cannot complete or be observed, close the
new gate, disable Docker restart only for `madar-release-proxy` and stop that proxy
(two separately bounded 30-second commands). Record critical failure if proxy stop
also fails. Original helper, protected transactions, data, volumes, rollback
containers, previous audit and authorization stay retained. No cleanup is included.

If installation fails before publication, current maintenance stays untouched;
retain all new partial evidence and review before another attempt. The new gate
permits boot only with this retry's completed active status and exact route plus
preserved original installation. The old status remains maintenance and the old
gate file is preserved; effective successful boot authority comes only from the
new explicitly approved gate. Revocation, package retirement or another retry
requires a separately reviewed operation, without deleting protected evidence.

**Actual tests, checks and disclosed preparation errors**

Final targeted source suite: 195 emergency/provider/control-plane regressions,
including 37 emergency tests; exit 0, one existing root-only permission test
skipped in the unprivileged CI image. A real timer test verifies the watchdog
interrupts blocking work and restores the prior signal handler. Image, state,
missing/unready fallback, transient 502, delayed workers, persistent 502, failed
reload/compensation, namespace collision, maintenance retry, sanitized failures,
audit-storage failure and boot gating are covered. Tests run with network none,
readonly development mounts, the existing CI image pinned by digest, pulling
disabled, and no production mounts. No broad acceptance rehearsal was run.

Dependency, migration-source, transition, forward-release and secret-hygiene checks
pass; no SQL migration executed. Two known historical duplicate-content warnings.
Systemd syntax passes with the identical generated helper dependency supplied to
the local verifier; the initial unprivileged verifier could not read the protected
installed dependency. Routing include bytes are unchanged from previously validated
Nginx syntax/routing smoke; actual production candidate validation remains mandatory
inside the proposed operation. No Nginx reload or retry was performed during this task.

Preparation error: an incorrectly constructed test command pulled unused
`python:latest` and failed before executing tests. It did not change application
services, routing, customer data or protected records. The command and failure log
are retained; no image/container cleanup was performed. Corrected final tests use
only pinned existing CI image `sha256:916a7fb975afcfd3a7d10035aa7b8c49cddda68914a25b4128e49c32969335cd`
and `--pull never`. This report is an agent summary, not protected acceptance.

Exact commands, logs, plan and validation summary are retained under
`.incident-response/emergency-routing-retry-2026-10-09/`. Prior source plans and
failed test logs remain preserved; only `final-plan.json` and the source hash above
are proposed for fresh approval.

**First production-changing operation — fresh approval pending**

Replace only the placeholder with the actual fresh operator response, shell-quoted.
The prior response must not be reused. Do not execute a mutable development shell
script with privilege; issue this fixed hash-gated command directly.

```bash
cd /opt/madar-development/repository
sudo /usr/bin/python3 -I -B - '<exact operator approval received>' <<'PYBOOTSTRAP'
import hashlib, io, json, os, sys
from pathlib import Path
source = Path('/opt/madar-development/repository/web/deployment/lib/emergency_routing_repair.py')
proposal = Path('/opt/madar-development/repository/.incident-response/emergency-routing-retry-2026-10-09/final-plan.json')
code = source.read_bytes()
packet = json.loads(proposal.read_bytes())
expected_code = '2bc41971b5f8db7c8ddf32449f812d916a997099fa8d67646514743fc4305a14'
expected_plan = 'cca3c29eae4a720243497a9bc7a351f76d17d321b40a9279431e8f932347fbae'
if hashlib.sha256(code).hexdigest() != expected_code:
    raise SystemExit('reviewed_code_changed')
if hashlib.sha256(json.dumps(packet, sort_keys=True).encode()).hexdigest() != expected_plan:
    raise SystemExit('reviewed_plan_changed')
approval = sys.argv[1]
if not approval.strip() or approval == '<exact operator approval received>':
    raise SystemExit('explicit_operator_approval_required')
os.environ.clear()
os.environ.update(PATH='/usr/sbin:/usr/bin:/sbin:/bin', LANG='C.UTF-8', LC_ALL='C.UTF-8')
sys.argv = [str(source), 'retry', '--approved-plan', expected_plan,
            '--operator-approval-text', approval]
sys.stdin = io.StringIO(json.dumps(packet))
exec(compile(code, str(source), 'exec'), {'__name__': '__main__', '__file__': str(source)})
PYBOOTSTRAP
```

Once executed, report actual public endpoint, proxy, native local database,
transaction, consumer and write-fence results and stop. Normal-production provenance,
checkpoint restore applicability and writable-cutover approval remain unresolved.
