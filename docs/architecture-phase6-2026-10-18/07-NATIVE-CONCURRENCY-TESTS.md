# Native evidence available before source publication

Parent214/schema149 diagnostic:3FAIL,2PASS,0errors/skips,1.449s. All three stale
mutation assertions retained in the parent source and reproduced unchanged.

New successor test_data_deletion_fencing_database.py:37PASS,0failures/errors/skips,
10.478s on PostgreSQL17 in an owned network-none disposable database. Checks cover
request/step stale completion,failure,finalization;generation/owner/attempt errors;
simultaneous claims;database-clock lease expiry during request/step lock waits;
transaction rollback/disconnect and lost completion reply;duplicate/concurrent
completion and begin;retry/exhaustion;restart with repeated worker ID;atomic
cancellation;cross-request confusion;external intent uncertainty/canonical keys;
actual BYPASSRLS service-role grants and denied legacy/helper/direct mutation;
full ten-step user/tenant flows with synthetic external Auth;foreign tenant
preservation;owner enrollment;freeze crash recovery;quota/registry confirmation.

A prior draft had32PASS and an earlier29-execution attempt had one cleanup error:
a synthetic last admin could not be deleted because the existing safety trigger
correctly refused. The fixture was corrected to use an active owner plus a
separately disabled subject,without weakening the trigger or assertions.

The full146→150 harness runs retained147/148/149 suites before the new suite:
  sudo -n env BACKEND_TEST_IMAGE=madar-schema136-preparation-test:working \
    bash web/scripts/rehearse_migration_150.sh
Initial full draft run:122 retained executions plus23initial new ownership tests
PASS. Tightened intermediate run:122retained+32new PASS. Final37suite ran on a
fresh independently built149fixture; exact-head CI must rerun the completechain.
Repeated business cases at148/149 are executions,not invented distinct coverage.

Working-source broad backend:3956collected,3131PASS,825conditionalSKIP,57.239s;
EXTERNAL_ATTEMPTS=[],EXTERNAL_SITES=[]. This predates the final two local helper
adversarial unit tests and is not relabeled exact-final-source CI acceptance.
All native databases are synthetic; external Auth/Storage in this native unit
bridge are simulated. Full real provider/application/worker acceptance is a
separate staging gate. Private raw logs remain outside Git.

Follow-up working-source rehearsal after the lost-COMMIT-reply test and explicit
schema150 business/calendar reruns:183native executions PASS,0errors/failures/skips.
Groups:21,11,5,18,22,2,5,16,22,37,24. The37ownership/upgrade tests include sending
actual150 COMMIT without reading its acknowledgement,observing committed150 from
an independent connection,closing the caller,and rejecting repeated SQL. The
final24 rerun22reservation/inventory/order/payment/isolation cases plus2calendar
atomic-version cases at150. Prior148/149 success is not substituted for150.

Exact a8fac208 hosted backend CI separately passed3133tests/825conditionalskips,
plus211native executions across its workflow's retained and successor groups.
The new183-execution working harness is not added to or relabeled that older
exact-source receipt. Latest application-focused staging unit run:30PASS,including
Storage pagination rejection and consuming-readiness tests;no external network.

Final legacy-admission correction adds3native149cases before the38case150suite.
Working complete rehearsal187PASS (groups21,11,5,18,22,2,5,16,22,41,24),zero failures,
errors/skips. The combined41are3legacy+38deletion/upgrade assertions. The new
legacy cases had2FAIL/1PASS before correction;the same assertions now pass. No
provider was actually called by that diagnostic and no duplicate external harm
is inferred. Original150SQL and all published mirror hashes remain unchanged.

## Frozen candidate CI

Exact36bb910fa028d380a0fb130bb8beeb1b0990bd2d hosted backend check
[39128295671](https://github.com/judahsleibi34/Madar/actions/runs/39128295671)
PASS:4 observer checks;4012 backend collected,3183PASS,829conditionalSKIP,58.463s;
239native executions,zero failures/errors/skips. Native groups:
32,8,8,4,21,11,5,18,22,2,5,16,22,41,24. These include retained commercial115/145/146
rehearsals,147/148/149ownership/integrity,3legacy-admission cases+38deletion150
cases,and24business/calendar regressions at150. Repeated schema executions are
not distinct coverage. EXTERNAL_ATTEMPTS=[] and EXTERNAL_SITES=[] in broad suite.

Frontend exact-source check
[39128295628](https://github.com/judahsleibi34/Madar/actions/runs/39128295628):
1713PASS,1SKIP,233files;lint,build and dependency audit also PASS.

## Commands and boundaries

Hosted workflow commands at frozen candidate source:

```bash
python3 web/scripts/check_dependency_locks.py
python3 web/scripts/check_migrations.py
python3 web/scripts/check_migration_transitions.py
python3 web/scripts/check_forward_release.py
python3 web/scripts/check_secret_hygiene.py
docker build --target test -t madar-backend-test web/backend
python3 web/staging/integration/test_notification_observer.py
# Full docker run mounts/test environment are in .github/workflows/backend-check.yml
# The image executes: python scripts/run_tests_no_external_network.py
BACKEND_TEST_IMAGE=madar-backend-test timeout 10m bash web/scripts/rehearse_migration_115.sh
BACKEND_TEST_IMAGE=madar-backend-test timeout 10m bash web/scripts/rehearse_migration_145.sh
BACKEND_TEST_IMAGE=madar-backend-test timeout 10m bash web/scripts/rehearse_migration_146.sh
BACKEND_TEST_IMAGE=madar-backend-test timeout 10m bash web/scripts/rehearse_migration_150.sh
```

Frontend workflow,from web/frontend:

```bash
npm ci
npm run lint
npm test
npm run build
npm audit --omit=dev --audit-level=high
```

Staging full-stack/recovery commands are in13/15;all require separately authenticated
exact-source artifact directories and positive fixed-project/database identity.
These scripts are not approved production SQL executors. Browser command uses
web/staging/integration/browser-smoke.mjs with private fixture and loopback SSH
forwarding;no account,TOTP,JWT or role backup belongs in Git.

The extra python3 web/scripts/check_privileged_inventory.py check FAILS with the
same11unclassified paths at parent214;this baseline debt remains visible. No CI
assertion was removed or weakened. Broader unexecuted product/performance/recovery
acceptance is recorded explicitly in the verification matrix.
