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
