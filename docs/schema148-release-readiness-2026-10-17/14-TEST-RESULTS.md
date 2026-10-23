# Executed validation — evolving record

Staging dedicated VM, current uncommitted continuation source:

- Focused admission/controller suite:10 PASS,0.055s.
- New native coordinated executor suite:16 PASS,11.634s. Each test clones a marked
  disposable schema146 database and uses the actual executor, exact147/148 SQL,
  native locks/transactions/grants/journal. Authorization and supervisor transport
  are explicit fixtures; they create no real authority or production receipts.
- Existing native upgrade:5 PASS,0.068s; fencing:17 PASS,6.826s;
  business:22 PASS,2.811s.60 native cases executed in total.
- First broad run3715/741 skips found1 protocol-bool validation failure and4
  errors:2 missing source-fixture paths,2 from a misplaced legacy-path block.
  Strict typing/source fixtures/legacy scope corrected; assertions retained.
  Initial Docker mountpoint failure was staging harness preparation, not a code
  defect. Focused discovery also needed its explicit repository import path.
- Corrected broad rerun:3717 collected,743 conditional skips,2974 executed PASS,
  43.403s; external attempts/sites empty. Final committed-source evidence supersedes
  these initial counts. No production operation or external notification/payment used.

Command: BACKEND_TEST_IMAGE=madar-schema136-preparation-test:working bash
web/scripts/rehearse_migration_148.sh on madar-staging. It includes coordinated
admission tests before existing147/148 suites. Private logs are retained under
/home/staging-admin/schema148-readiness-20261017/. Source policy/lock/mirror/
transition/forward-release checks pass; historical013/014 warnings retained.

## Current precommit validation

The a42e11ab source content (including PITR/browser and fresh-artifact safety
tests) was run through the isolated no-external-network backend runner:
3750 collected,746 conditional skips,3004 executed PASS in46.490s.
EXTERNAL_ATTEMPTS=[] and EXTERNAL_SITES=[]. Native conditional cases are separately
executed in their dedicated marked PostgreSQL environment, not counted as PASS
from these skips. The expanded native run passed19+5+17+22=63 cases
(12.688s/.053s/6.955s/3.471s). No assertions or historical tests removed.

Additional actual evidence: independent recovery115.19s, physical/WAL/PITR66.84s,
restored browser password/MFA/admin/refresh/mobile PASS, native authenticated
bidirectional tenant IDOR/path-user spoof/admin denial PASS. Browser uses cached
Chromium151 against a verified loopback SSH tunnel, never production.

Exact native commands and sanitized evidence files are indexed in FINAL-REPORT.
Private full logs remain on the dedicated VM; no secrets are copied into Git.

The first fresh archive a42e11ab passed byte/source provenance but staging
correctly refused image acceptance: CI .Id was config53d71..., while the
containerd import .Id was OCI manifest41f6.... No running service was replaced.
Producer correction verifies manifest+config and binds target manifest IDs;
regression cases reject tampering, unknown host ID and multi-manifest ambiguity.
Initial receipt/verification retained with ci-initial prefix, not final acceptance.
The exact a42 native rerun passed19+5+17+22 in13.611/.183/7.876/2.628s.
An initial archive-directory0700 prevented non-root test imports; public source
mount root traversal was fixed and the entire run repeated. No SQL failure hidden.

## Final release-source validation

At c3f9ce591f4706e535795b979064d3baefe421be:
- dedicated VM backend3752 collected,746 skipped,3006 executed PASS44.686s;
  external attempts/sites empty.
- artifact adversarial unit suite9 PASS, including explicit OCI/config mapping
  and latest exact-application-source CI rejection; actual initial CI archive
  helper result matches the observed staging manifest ID.
- hosted Backend Check38986641304, Frontend Check38986641467 and Schema148
  Candidate Artifacts38986641301 all completed success. Frontend check includes
  lint,233 test files/1713 passing tests/1 skip, production build.
- hosted backend executes commercial migration115/145/146 and all63 coordinated/
  fencing/business native cases in addition to the broad conditional suite.

Evidence: application-ci-c3.json, ci-c3-test-summary.json, backend-c3-summary.json,
native-a42-summary.json. The63-case exact-a42 SQL/controller run remains applicable
to c3: only provenance verifier/producer/tests and policy docs changed between
those commits, not SQL/executor/quiescence/business code. Hosted c3 also reruns63.

## Follow-on counter defect and alert validation

Live c3 worker metrics showed sent40/processed2. New polling regression FAILED
against the previous worker with AssertionError40!=0 after ownership loss. A
fixture initially mocked all threading.Thread objects and blocked the real pool;
only that exact owned disposable test container was stopped, fixture corrected,
and the failing assertion reproduced. The corrected8-case fencing contract suite
passes. Expanded native suite now64 PASS:19/12.969s +5/.072s +18/8.486s
+22/2.816s, including real stale PostgreSQL acknowledgement in the polling loop.
The authoritative final backend/CI counts below supersede earlier3752 totals.

Standalone notification inspection injection:4 PASS in2.099s on staging actual
loopback HTTP. Covers ownership/ack failure/backlog,503, consuming mismatch,
counter reset, foreign previous instance and incomplete/non-loopback inputs.
Initial local socket creation was sandbox-denied; staging rerun executed real
sockets without weakening assertions. The existing Backend Check now runs it.

Fresh c3 application acceptance PASS after explicit imported-scope resume60.155s
(resume interval only). Initial TLS utility failed because three Nginx temp
paths used read-only storage; corrected to bounded tmpfs. Backend/worker/fresh
compiled frontend images stayed exact. Native password/JWT/MFA/CSRF/refresh,
private storage/legacy avatar, PostgREST intent replay/real worker/readiness pass.
Browser then passes all9 checks with zero page errors/external requests.
This is full native integration for selected flows, not full product release
acceptance or protected controller installation/reboot testing.

## Worker-counter final source

32c77afd01a012c7d21240316d4a46e52c3cbf14 includes the counter correction and
explicit staging imported-scope reentry. Full no-external backend:3755 collected,
747 skipped,3008 executed PASS47.034s; no failures/errors/external attempts/sites.
Native current content64 PASS. Three fresh-acceptance safety cases pass, including
wrong selected source refusing before Compose. The metric namespace correction
preserves successful-send/failure event counters even if either queue source
returns a colliding sent key. The dedicated alert inspector emits fixed codes
only; it does not dispatch messages, reconcile providers or issue authority.

Hosted final32c checks all PASS: backend38987861093 (3755/747skip,57.998s;
64 native cases14.157/.101/10.141/4.151s; alert4cases2.145s), frontend
38987861101 (233 files,1713 PASS/1 skip, lint/build), fresh artifacts38987861104.
Other hosted native commercial suites:115=32,145=8,146=8+4. Their counts are
separate runs, not added to the broad suite as unique coverage. Exact job contexts
from GitHub check-runs: test-backend, build-frontend, build-candidate; expected
source github-actions. Independent branch admin is required to enforce checks.

Final fresh32 native application acceptance PASS202.336s, no imported-scope
resume required. Exact CI backend/frontend runtime IDs and original restored
password/AuthID/TOTP/private object acceptance retained. Browser32 passes9 checks,
0 page errors/0 external hosts; credentials and tunnel removed. Actual fixed
worker reports sent1/processed2, queue0, ownership-loss/ack-failure0; historical
queue totals no longer replace its delivery counters.

Expanded real HTTP tenant test passes own read/archive, bidirectional foreign
read/delete rejection with unchanged foreign rows, path-user spoof/admin/tenant
query rejection and disabled-membership read/write rejection with valid JWT. Its
first DELETE correctly failed CSRF because the fixture lacked a legitimate token.
The fixture now obtains a real application CSRF cookie/header via user_status;
expected404/403 assertions and backend CSRF policy remain unchanged. No synthetic
paid subscription or live billing activation was needed for these cleanup rights.

Final VM rerun from unmodified exact32c Git archive:64 PASS, no skips/errors:19
coordinated12.551s,5 upgrade.074s,18 fencing6.923s,22 business2.813s. Temporary
owned database/container cleaned by rehearsal trap. Final retained stack10 services,
exact32c image source/148, loopback ports,3531MiB available/43GiB disk free at
observation; health checks or running-without-healthcheck are reported distinctly.
Paired read benchmark2160 measured+180 warmup GETs has zero errors and unchanged
synthetic counts; baseline/helper resources removed. Performance is mixed, no
general improvement claim. See13 and final evidence JSON.
